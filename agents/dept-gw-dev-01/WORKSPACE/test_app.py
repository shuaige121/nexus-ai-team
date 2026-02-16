"""Tests for Hello World HTTP API."""
import json
import threading
import urllib.request
from http.server import HTTPServer

from app import HelloHandler


def test_hello_world():
    server = HTTPServer(("localhost", 18080), HelloHandler)
    thread = threading.Thread(target=server.serve_forever)
    thread.daemon = True
    thread.start()

    try:
        req = urllib.request.urlopen("http://localhost:18080/")
        data = json.loads(req.read().decode())
        assert req.status == 200
        assert data == {"message": "Hello World"}
    finally:
        server.shutdown()
