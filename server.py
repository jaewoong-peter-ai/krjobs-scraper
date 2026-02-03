"""Cloud Run HTTP 서버 진입점"""

import asyncio
import json
import os
from http.server import HTTPServer, BaseHTTPRequestHandler

from main import run_scrapers


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        """Cloud Scheduler에서 호출"""
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode('utf-8') if content_length else '{}'

        try:
            params = json.loads(body) if body else {}
            sites = params.get('sites', ['komate', 'klik'])
            deep_scrape = params.get('deep_scrape', True)

            result = asyncio.run(run_scrapers(sites, deep_scrape))

            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(result, default=str).encode())
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'error': str(e)}).encode())

    def do_GET(self):
        """Health check"""
        self.send_response(200)
        self.send_header('Content-Type', 'text/plain')
        self.end_headers()
        self.wfile.write(b'OK')


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    server = HTTPServer(('0.0.0.0', port), Handler)
    print(f'Server running on port {port}')
    server.serve_forever()
