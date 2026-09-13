import json, sqlite3, os, threading, hmac, hashlib
from http.server import HTTPServer, BaseHTTPRequestHandler

class DebugHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(length)
        
        # Logar todos os headers e o body em um arquivo para auditoria
        log_entry = {
            "path": self.path,
            "headers": dict(self.headers),
            "body": body.decode('utf-8', errors='ignore')
        }
        with open("/opt/data/digital_store_bot/webhook_last_request.json", "w") as f:
            json.dump(log_entry, f, indent=2)
            
        print(">>> WEBHOOK RECEBIDO!")
        print("Path:", self.path)
        print("Headers:", self.headers)
        
        # Responde 200 imediatamente para vermos exatamente como veio
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(b'{"received": true}')

if __name__ == "__main__":
    server = HTTPServer(('', 8099), DebugHandler)
    print("Servidor debug ouvindo na 8099...")
    server.serve_forever()
