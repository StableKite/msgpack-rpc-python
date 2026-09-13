from importlib import metadata
from pathlib import Path
import sys
import sysconfig

if sysconfig.get_config_var("Py_GIL_DISABLED") != 1:
    raise SystemExit("Expected CPython free-threaded build")

import msgpack
import msgpackrpc
from msgpackrpc.tornado import speedups
from msgpackrpc.transport.tcp import BaseSocket

if hasattr(sys, "_is_gil_enabled") and sys._is_gil_enabled():
    raise SystemExit("GIL was enabled after importing runtime extensions")

installed_version = metadata.version("msgpack-rpc-python")
if installed_version != "0.5.0":
    raise SystemExit(
        "Unexpected installed msgpack-rpc-python version: "
        f"{installed_version!r}"
    )

if msgpackrpc.__version__ != "0.5.0":
    raise SystemExit(
        f"Unexpected runtime version: {msgpackrpc.__version__!r}"
    )

extension = Path(speedups.__file__).resolve()
if not extension.is_file():
    raise SystemExit(
        f"Native speedups extension does not exist: {extension}"
    )

if extension.suffix.lower() not in {".so", ".pyd"}:
    raise SystemExit(
        f"speedups is not a native extension: {extension}"
    )

mask = b"\x01\x02\x03\x04"
data = b"hello"
result = speedups.websocket_mask(mask, data)

if result != b"igohn":
    raise SystemExit(
        f"Unexpected websocket_mask result: {result!r}"
    )

try:
    speedups.websocket_mask(b"bad", data)
except ValueError:
    pass
else:
    raise SystemExit(
        "speedups.websocket_mask accepted a non-4-byte mask"
    )

address = msgpackrpc.Address("127.0.0.1", 18800)
if address.unpack() != ("127.0.0.1", 18800):
    raise SystemExit(
        f"Unexpected Address.unpack(): {address.unpack()!r}"
    )

class DummyStream:
    def close(self):
        pass

    def write(self, data, callback=None):
        self.data = data
        if callback is not None:
            callback()

base_socket = BaseSocket(
    DummyStream(),
    ("utf-8", "utf-8"),
)
packed = base_socket._packer.pack(["hello", 42])
unpacked = msgpack.unpackb(packed, raw=False)
if unpacked != ["hello", 42]:
    raise SystemExit(
        f"Modern msgpack compatibility failed: {unpacked!r}"
    )

print("msgpack-rpc-python wheel smoke-test OK")
print("msgpack:", metadata.version("msgpack"))
print("speedups:", extension)
