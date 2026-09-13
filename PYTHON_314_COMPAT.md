# Python 3.14 compatibility fixes

This fork has been updated for modern Python / CPython 3.14t compatibility:

- fixed the historical `asyncio.async` syntax in the bundled Tornado tests;
- fixed invalid escape sequence warnings in bundled Tornado sources/tests;
- updated `collections.MutableMapping` to `collections.abc.MutableMapping`;
- updated MessagePack transport code for modern `msgpack>=1.0.0`;
- replaced the obsolete `msgpack-python` dependency with `msgpack`;
- switched build imports from `distutils` to `setuptools`;
- declared Python `>=3.9`;
- declared the small websocket masking C extension as compatible with free-threaded CPython where supported.
## CI / free-threaded wheel notes

- `ci_wheel_smoke.py` is copied into cibuildwheel's isolated test directory via `CIBW_TEST_SOURCES`, so imports resolve to the installed wheel rather than the source checkout.
- `speedups.c` uses the `Py_mod_gil` module slot on CPython 3.13+ to declare that the stateless masking extension is safe without the GIL.

