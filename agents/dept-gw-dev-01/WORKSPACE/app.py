"""Hello World HTTP API server."""
import json
from http.server import HTTPServer, BaseHTTPRequestHandler


class HelloHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            response = json.dumps({"message": "Hello World"})
            self.wfile.write(response.encode())
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass  # Suppress logs during testing


if __name__ == "__main__":
    server = HTTPServer(("localhost", 8080), HelloHandler)
    print("Server running on http://localhost:8080")
    server.serve_forever()
