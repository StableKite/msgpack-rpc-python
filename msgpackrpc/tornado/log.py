#!/usr/bin/env python
#
# Copyright 2012 Facebook
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.
"""Logging support for Tornado.

Tornado uses three logger streams:

* ``msgpackrpc.tornado.access``: Per-request logging for Tornado's HTTP servers (and
  potentially other servers in the future)
* ``msgpackrpc.tornado.application``: Logging of errors from application code (i.e.
  uncaught exceptions from callbacks)
* ``msgpackrpc.tornado.general``: General-purpose logging, including any errors
  or warnings from Tornado itself.

These streams may be configured independently using the standard library's
`logging` module.  For example, you may wish to send ``msgpackrpc.tornado.access`` logs
to a separate file for analysis.
"""
from __future__ import absolute_import, division, print_function

import logging
import logging.handlers
import sys

from msgpackrpc.tornado.escape import _unicode
from msgpackrpc.tornado.util import unicode_type, basestring_type

try:
    import colorama
except ImportError:
    colorama = None

try:
    import curses  # type: ignore
except ImportError:
    curses = None

# Logger objects for internal tornado use
access_log = logging.getLogger("msgpackrpc.tornado.access")
app_log = logging.getLogger("msgpackrpc.tornado.application")
gen_log = logging.getLogger("msgpackrpc.tornado.general")


def _stderr_supports_color():
    try:
        if hasattr(sys.stderr, 'isatty') and sys.stderr.isatty():
            if curses:
                curses.setupterm()
                if curses.tigetnum("colors") > 0:
                    return True
            elif colorama:
                if sys.stderr is getattr(colorama.initialise, 'wrapped_stderr',
                                         object()):
                    return True
    except Exception:
        # Very broad exception handling because it's always better to
        # fall back to non-colored logs than to break at startup.
        pass
    return False


def _safe_unicode(s):
    try:
        return _unicode(s)
    except UnicodeDecodeError:
        return repr(s)


class LogFormatter(logging.Formatter):
    """Log formatter used in Tornado.

    Key features of this formatter are:

    * Color support when logging to a terminal that supports it.
    * Timestamps on every log line.
    * Robust against str/bytes encoding problems.

    This formatter is enabled automatically by
    `msgpackrpc.tornado.options.parse_command_line` or `msgpackrpc.tornado.options.parse_config_file`
    (unless ``--logging=none`` is used).

    Color support on Windows versions that do not support ANSI color codes is
    enabled by use of the colorama__ library. Applications that wish to use
    this must first initialize colorama with a call to ``colorama.init``.
    See the colorama documentation for details.

    __ https://pypi.python.org/pypi/colorama

    .. versionchanged:: 4.5
       Added support for ``colorama``. Changed the constructor
       signature to be compatible with `logging.config.dictConfig`.
    """
    DEFAULT_FORMAT = '%(color)s[%(levelname)1.1s %(asctime)s %(module)s:%(lineno)d]%(end_color)s %(message)s'
    DEFAULT_DATE_FORMAT = '%y%m%d %H:%M:%S'
    DEFAULT_COLORS = {
        logging.DEBUG: 4,  # Blue
        logging.INFO: 2,  # Green
        logging.WARNING: 3,  # Yellow
        logging.ERROR: 1,  # Red
    }

    def __init__(self, fmt=DEFAULT_FORMAT, datefmt=DEFAULT_DATE_FORMAT,
                 style='%', color=True, colors=DEFAULT_COLORS):
        r"""
        :arg bool color: Enables color support.
        :arg string fmt: Log message format.
          It will be applied to the attributes dict of log records. The
          text between ``%(color)s`` and ``%(end_color)s`` will be colored
          depending on the level if color support is on.
        :arg dict colors: color mappings from logging level to terminal color
          code
        :arg string datefmt: Datetime format.
          Used for formatting ``(asctime)`` placeholder in ``prefix_fmt``.

        .. versionchanged:: 3.2

           Added ``fmt`` and ``datefmt`` arguments.
        """
        logging.Formatter.__init__(self, datefmt=datefmt)
        self._fmt = fmt

        self._colors = {}
        if color and _stderr_supports_color():
            if curses is not None:
                # The curses module has some str/bytes confusion in
                # python3.  Until version 3.2.3, most methods return
                # bytes, but only accept strings.  In addition, we want to
                # output these strings with the logging module, which
                # works with unicode strings.  The explicit calls to
                # unicode() below are harmless in python2 but will do the
                # right conversion in python 3.
                fg_color = (curses.tigetstr("setaf") or
                            curses.tigetstr("setf") or "")
                if (3, 0) < sys.version_info < (3, 2, 3):
                    fg_color = unicode_type(fg_color, "ascii")

                for levelno, code in colors.items():
                    self._colors[levelno] = unicode_type(curses.tparm(fg_color, code), "ascii")
                self._normal = unicode_type(curses.tigetstr("sgr0"), "ascii")
            else:
                # If curses is not present (currently we'll only get here for
                # colorama on windows), assume hard-coded ANSI color codes.
                for levelno, code in colors.items():
                    self._colors[levelno] = '\033[2;3%dm' % code
                self._normal = '\033[0m'
        else:
            self._normal = ''

    def format(self, record):
        try:
            message = record.getMessage()
            assert isinstance(message, basestring_type)  # guaranteed by logging
            # Encoding notes:  The logging module prefers to work with character
            # strings, but only enforces that log messages are instances of
            # basestring.  In python 2, non-ascii bytestrings will make
            # their way through the logging framework until they blow up with
            # an unhelpful decoding error (with this formatter it happens
            # when we attach the prefix, but there are other opportunities for
            # exceptions further along in the framework).
            #
            # If a byte string makes it this far, convert it to unicode to
            # ensure it will make it out to the logs.  Use repr() as a fallback
            # to ensure that all byte strings can be converted successfully,
            # but don't do it by default so we don't add extra quotes to ascii
            # bytestrings.  This is a bit of a hacky place to do this, but
            # it's worth it since the encoding errors that would otherwise
            # result are so useless (and tornado is fond of using utf8-encoded
            # byte strings whereever possible).
            record.message = _safe_unicode(message)
        except Exception as e:
            record.message = "Bad message (%r): %r" % (e, record.__dict__)

        record.asctime = self.formatTime(record, self.datefmt)

        if record.levelno in self._colors:
            record.color = self._colors[record.levelno]
            record.end_color = self._normal
        else:
            record.color = record.end_color = ''

        formatted = self._fmt % record.__dict__

        if record.exc_info:
            if not record.exc_text:
                record.exc_text = self.formatException(record.exc_info)
        if record.exc_text:
            # exc_text contains multiple lines.  We need to _safe_unicode
            # each line separately so that non-utf8 bytes don't cause
            # all the newlines to turn into '\n'.
            lines = [formatted.rstrip()]
            lines.extend(_safe_unicode(ln) for ln in record.exc_text.split('\n'))
            formatted = '\n'.join(lines)
        return formatted.replace("\n", "\n    ")


def enable_pretty_logging(options=None, logger=None):
    """Turns on formatted logging output as configured.

    This is called automatically by `msgpackrpc.tornado.options.parse_command_line`
    and `msgpackrpc.tornado.options.parse_config_file`.
    """
    if options is None:
        import msgpackrpc.tornado.options
        options = msgpackrpc.tornado.options.options
    if options.logging is None or options.logging.lower() == 'none':
        return
    if logger is None:
        logger = logging.getLogger()
    logger.setLevel(getattr(logging, options.logging.upper()))
    if options.log_file_prefix:
        rotate_mode = options.log_rotate_mode
        if rotate_mode == 'size':
            channel = logging.handlers.RotatingFileHandler(
                filename=options.log_file_prefix,
                maxBytes=options.log_file_max_size,
                backupCount=options.log_file_num_backups)
        elif rotate_mode == 'time':
            channel = logging.handlers.TimedRotatingFileHandler(
                filename=options.log_file_prefix,
                when=options.log_rotate_when,
                interval=options.log_rotate_interval,
                backupCount=options.log_file_num_backups)
        else:
            error_message = 'The value of log_rotate_mode option should be ' +\
                            '"size" or "time", not "%s".' % rotate_mode
            raise ValueError(error_message)
        channel.setFormatter(LogFormatter(color=False))
        logger.addHandler(channel)

    if (options.log_to_stderr or
            (options.log_to_stderr is None and not logger.handlers)):
        # Set up color if we are in a tty and curses is installed
        channel = logging.StreamHandler()
        channel.setFormatter(LogFormatter())
        logger.addHandler(channel)


def define_logging_options(options=None):
    """Add logging-related flags to ``options``.

    These options are present automatically on the default options instance;
    this method is only necessary if you have created your own `.OptionParser`.

    .. versionadded:: 4.2
        This function existed in prior versions but was broken and undocumented until 4.2.
    """
    if options is None:
        # late import to prevent cycle
        import msgpackrpc.tornado.options
        options = msgpackrpc.tornado.options.options
    options.define("logging", default="info",
                   help=("Set the Python log level. If 'none', tornado won't touch the "
                         "logging configuration."),
                   metavar="debug|info|warning|error|none")
    options.define("log_to_stderr", type=bool, default=None,
                   help=("Send log output to stderr (colorized if possible). "
                         "By default use stderr if --log_file_prefix is not set and "
                         "no other logging is configured."))
    options.define("log_file_prefix", type=str, default=None, metavar="PATH",
                   help=("Path prefix for log files. "
                         "Note that if you are running multiple tornado processes, "
                         "log_file_prefix must be different for each of them (e.g. "
                         "include the port number)"))
    options.define("log_file_max_size", type=int, default=100 * 1000 * 1000,
                   help="max size of log files before rollover")
    options.define("log_file_num_backups", type=int, default=10,
                   help="number of log files to keep")

    options.define("log_rotate_when", type=str, default='midnight',
                   help=("specify the type of TimedRotatingFileHandler interval "
                         "other options:('S', 'M', 'H', 'D', 'W0'-'W6')"))
    options.define("log_rotate_interval", type=int, default=1,
                   help="The interval value of timed rotating")

    options.define("log_rotate_mode", type=str, default='size',
                   help="The mode of rotating files(time or size)")

    options.add_parse_callback(lambda: enable_pretty_logging(options))
