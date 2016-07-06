import socket
import time
import unittest
import uuid
from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer
from threading import Thread

from requests.exceptions import HTTPError

from golem.http.stream import StreamMonitor, ChunkStream, StreamFileObject


class MockHttpServer(BaseHTTPRequestHandler):
    wait = 5
    port = 22333
    server_version = "BaseHTTP/1.1"
    default_request_version = "HTTP/1.1"

    def _set_headers(self):
        self.send_response(200)
        self.send_header('Content-type', 'application/octet-stream')
        self.end_headers()

    def do_GET(self):
        time.sleep(self.wait)
        self._set_headers()
        self.wfile.write("GET")

    def do_HEAD(self):
        time.sleep(self.wait)
        self._set_headers()

    def do_POST(self):
        time.sleep(self.wait)
        self._set_headers()
        self.wfile.write("POST")

    @staticmethod
    def serve():
        server_address = ('', MockHttpServer.port)
        httpd = HTTPServer(server_address, MockHttpServer)
        thread = Thread(target=httpd.serve_forever)
        thread.daemon = True
        thread.start()
        return httpd


class MockIterator:
    def __init__(self, src, chunk):
        self.src = src
        self.len = len(src)
        self.chunk = chunk
        self.pos = 0

    def __iter__(self):
        return self

    def next(self):
        prev_pos = self.pos
        self.pos += self.chunk

        if prev_pos > self.len:
            raise StopIteration
        else:
            new_pos = max(prev_pos, self.len - self.pos)
            return self.src[prev_pos:new_pos]


class MockIterable:
    def __init__(self, src):
        self.iterator = None
        self.src = src

    def iter_content(self, chunk, *args):
        if not self.iterator:
            self.iterator = MockIterator(self.src, chunk)
        return self.iterator


class TestStreamMonitor(unittest.TestCase):

    def test(self):
        httpd = MockHttpServer.serve()

        start = time.time()

        stream = ChunkStream(('127.0.0.1', 0), '/')

        default_timeout = StreamMonitor.stream_timeout
        StreamMonitor.stream_timeout = 0.1
        StreamMonitor.monitor(stream)

        try:
            while True:
                if not stream.read(1):
                    break
        except:
            pass

        StreamMonitor.stream_timeout = default_timeout

        # make sure that no loop has passed
        assert time.time() - start < MockHttpServer.wait
        httpd.shutdown()
        httpd.server_close()


class TestSocketStream(unittest.TestCase):

    def testFailedConnection(self):
        stream = ChunkStream(('127.0.0.1', 0), '/')

        with self.assertRaises(socket.error):
            stream.connect()

        stream.disconnect()
        assert stream.done

    def testHeaders(self):
        rn = "\r\n"

        with self.assertRaises(HTTPError):
            ChunkStream._assert_headers(
                rn.join([
                    'HTTP/1.0 200 ok'
                ])
            )
        with self.assertRaises(HTTPError):
            ChunkStream._assert_headers(
                rn.join([
                    'HTTP/1.1 404 Not Found'
                ])
            )
        with self.assertRaises(HTTPError):
            ChunkStream._assert_headers(
                rn.join([
                    'HTTP/1.1 200'
                ])
            )
        with self.assertRaises(HTTPError):
            ChunkStream._assert_headers(
                rn.join([
                    'HTTP/1.1 200 ok'
                ])
            )
        with self.assertRaises(HTTPError):
            ChunkStream._assert_headers(
                rn.join([
                    'HTTP/1.1 200 OK',
                    'Transfer-Encoding: qwerty'
                ])
            )
        ChunkStream._assert_headers(
            rn.join([
                'hTTp/1.1 200 OK',
                'Ignored: property',
                'Transfer-Encoding: Chunked'
            ])
        )

    def testFailedRead(self):
        httpd = MockHttpServer.serve()
        stream = ChunkStream(('127.0.0.1', MockHttpServer.port), '/')

        stream.connect()

        with self.assertRaises(HTTPError):
            stream.read(1024)

        stream.disconnect()

        httpd.shutdown()
        httpd.server_close()


class TestStreamFileObject(unittest.TestCase):

    def test(self):
        src = ''
        for _ in xrange(1, 100):
            src = str(uuid.uuid4())

        iterable = MockIterable(src)
        so = StreamFileObject(iterable)

        try:
            so.read(32)
        except StopIteration:
            pass
