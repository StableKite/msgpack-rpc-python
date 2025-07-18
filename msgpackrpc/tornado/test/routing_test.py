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


from __future__ import absolute_import, division, print_function

from msgpackrpc.tornado.httputil import HTTPHeaders, HTTPMessageDelegate, HTTPServerConnectionDelegate, ResponseStartLine
from msgpackrpc.tornado.routing import HostMatches, PathMatches, ReversibleRouter, Router, Rule, RuleRouter
from msgpackrpc.tornado.testing import AsyncHTTPTestCase
from msgpackrpc.tornado.web import Application, HTTPError, RequestHandler
from msgpackrpc.tornado.wsgi import WSGIContainer


class BasicRouter(Router):
    def find_handler(self, request, **kwargs):

        class MessageDelegate(HTTPMessageDelegate):
            def __init__(self, connection):
                self.connection = connection

            def finish(self):
                self.connection.write_headers(
                    ResponseStartLine("HTTP/1.1", 200, "OK"), HTTPHeaders({"Content-Length": "2"}), b"OK"
                )
                self.connection.finish()

        return MessageDelegate(request.connection)


class BasicRouterTestCase(AsyncHTTPTestCase):
    def get_app(self):
        return BasicRouter()

    def test_basic_router(self):
        response = self.fetch("/any_request")
        self.assertEqual(response.body, b"OK")


resources = {}


class GetResource(RequestHandler):
    def get(self, path):
        if path not in resources:
            raise HTTPError(404)

        self.finish(resources[path])


class PostResource(RequestHandler):
    def post(self, path):
        resources[path] = self.request.body


class HTTPMethodRouter(Router):
    def __init__(self, app):
        self.app = app

    def find_handler(self, request, **kwargs):
        handler = GetResource if request.method == "GET" else PostResource
        return self.app.get_handler_delegate(request, handler, path_args=[request.path])


class HTTPMethodRouterTestCase(AsyncHTTPTestCase):
    def get_app(self):
        return HTTPMethodRouter(Application())

    def test_http_method_router(self):
        response = self.fetch("/post_resource", method="POST", body="data")
        self.assertEqual(response.code, 200)

        response = self.fetch("/get_resource")
        self.assertEqual(response.code, 404)

        response = self.fetch("/post_resource")
        self.assertEqual(response.code, 200)
        self.assertEqual(response.body, b"data")


def _get_named_handler(handler_name):
    class Handler(RequestHandler):
        def get(self, *args, **kwargs):
            if self.application.settings.get("app_name") is not None:
                self.write(self.application.settings["app_name"] + ": ")

            self.finish(handler_name + ": " + self.reverse_url(handler_name))

    return Handler


FirstHandler = _get_named_handler("first_handler")
SecondHandler = _get_named_handler("second_handler")


class CustomRouter(ReversibleRouter):
    def __init__(self):
        super(CustomRouter, self).__init__()
        self.routes = {}

    def add_routes(self, routes):
        self.routes.update(routes)

    def find_handler(self, request, **kwargs):
        if request.path in self.routes:
            app, handler = self.routes[request.path]
            return app.get_handler_delegate(request, handler)

    def reverse_url(self, name, *args):
        handler_path = '/' + name
        return handler_path if handler_path in self.routes else None


class CustomRouterTestCase(AsyncHTTPTestCase):
    def get_app(self):
        class CustomApplication(Application):
            def reverse_url(self, name, *args):
                return router.reverse_url(name, *args)

        router = CustomRouter()
        app1 = CustomApplication(app_name="app1")
        app2 = CustomApplication(app_name="app2")

        router.add_routes({
            "/first_handler": (app1, FirstHandler),
            "/second_handler": (app2, SecondHandler),
            "/first_handler_second_app": (app2, FirstHandler),
        })

        return router

    def test_custom_router(self):
        response = self.fetch("/first_handler")
        self.assertEqual(response.body, b"app1: first_handler: /first_handler")
        response = self.fetch("/second_handler")
        self.assertEqual(response.body, b"app2: second_handler: /second_handler")
        response = self.fetch("/first_handler_second_app")
        self.assertEqual(response.body, b"app2: first_handler: /first_handler")


class ConnectionDelegate(HTTPServerConnectionDelegate):
    def start_request(self, server_conn, request_conn):

        class MessageDelegate(HTTPMessageDelegate):
            def __init__(self, connection):
                self.connection = connection

            def finish(self):
                response_body = b"OK"
                self.connection.write_headers(
                    ResponseStartLine("HTTP/1.1", 200, "OK"),
                    HTTPHeaders({"Content-Length": str(len(response_body))}))
                self.connection.write(response_body)
                self.connection.finish()

        return MessageDelegate(request_conn)


class RuleRouterTest(AsyncHTTPTestCase):
    def get_app(self):
        app = Application()

        def request_callable(request):
            request.write(b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\nOK")
            request.finish()

        app.add_handlers(".*", [
            (HostMatches("www.example.com"), [
                (PathMatches("/first_handler"), "msgpackrpc.tornado.test.routing_test.SecondHandler", {}, "second_handler")
            ]),
            Rule(PathMatches("/first_handler"), FirstHandler, name="first_handler"),
            Rule(PathMatches("/request_callable"), request_callable),
            ("/connection_delegate", ConnectionDelegate())
        ])

        return app

    def test_rule_based_router(self):
        response = self.fetch("/first_handler")
        self.assertEqual(response.body, b"first_handler: /first_handler")
        response = self.fetch("/first_handler", headers={'Host': 'www.example.com'})
        self.assertEqual(response.body, b"second_handler: /first_handler")

        response = self.fetch("/connection_delegate")
        self.assertEqual(response.body, b"OK")

        response = self.fetch("/request_callable")
        self.assertEqual(response.body, b"OK")

        response = self.fetch("/404")
        self.assertEqual(response.code, 404)


class WSGIContainerTestCase(AsyncHTTPTestCase):
    def get_app(self):
        wsgi_app = WSGIContainer(self.wsgi_app)

        class Handler(RequestHandler):
            def get(self, *args, **kwargs):
                self.finish(self.reverse_url("tornado"))

        return RuleRouter([
            (PathMatches("/tornado.*"), Application([(r"/tornado/test", Handler, {}, "tornado")])),
            (PathMatches("/wsgi"), wsgi_app),
        ])

    def wsgi_app(self, environ, start_response):
        start_response("200 OK", [])
        return [b"WSGI"]

    def test_wsgi_container(self):
        response = self.fetch("/tornado/test")
        self.assertEqual(response.body, b"/tornado/test")

        response = self.fetch("/wsgi")
        self.assertEqual(response.body, b"WSGI")
