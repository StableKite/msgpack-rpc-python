import unittest

import msgpackrpc
from msgpackrpc.tornado.httputil import HTTPHeaders
from msgpackrpc.tornado.netutil import SSLCertificateError, ssl_match_hostname
from msgpackrpc.tornado.util import _websocket_mask


class TestModernCompatibility(unittest.TestCase):
    def test_package_version(self):
        self.assertEqual(msgpackrpc.__version__, "0.5.0")

    def test_http_headers_uses_modern_mapping_api(self):
        headers = HTTPHeaders({"content-type": "application/json"})
        self.assertEqual(headers["Content-Type"], "application/json")

    def test_websocket_mask(self):
        self.assertEqual(
            _websocket_mask(b"\x01\x02\x03\x04", b"hello"),
            b"igohn",
        )

    def test_ssl_hostname_compatibility(self):
        cert = {
            "subjectAltName": (
                ("DNS", "example.com"),
                ("DNS", "*.example.org"),
            )
        }
        ssl_match_hostname(cert, "example.com")
        ssl_match_hostname(cert, "api.example.org")
        with self.assertRaises(SSLCertificateError):
            ssl_match_hostname(cert, "bad.example.net")


if __name__ == "__main__":
    unittest.main()
