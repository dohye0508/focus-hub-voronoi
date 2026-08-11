import http.server
import socketserver
import socket
import os

# Set the port
PORT = 8080

# Ensure we serve files from the current directory, but route the root to results/nationwide_analysis.html
class RequestHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            self.path = '/results/nationwide_analysis.html'
        elif self.path == '/index.html':
            self.path = '/results/nationwide_analysis.html'
        
        # Ensure correct MIME type for manifest
        if self.path.endswith('.json'):
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            with open(self.translate_path(self.path), 'rb') as f:
                self.wfile.write(f.read())
            return
            
        return super().do_GET()

def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # doesn't even have to be reachable
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except Exception:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP

if __name__ == '__main__':
    # Make sure we are in the correct directory
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    
    Handler = RequestHandler
    socketserver.ThreadingTCPServer.allow_reuse_address = True
    with socketserver.ThreadingTCPServer(("0.0.0.0", PORT), Handler) as httpd:
        local_ip = get_local_ip()
        print("="*50)
        print("모바일 앱(PWA) 서버가 시작되었습니다!")
        print(f"PC에서 접속: http://localhost:{PORT}")
        print(f"모바일에서 접속: http://{local_ip}:{PORT}")
        print("="*50)
        print("휴대폰 브라우저(Safari/Chrome)로 위 '모바일에서 접속' 주소에 들어간 뒤,")
        print("[홈 화면에 추가]를 누르면 진짜 앱처럼 설치됩니다.")
        print("종료하려면 Ctrl+C를 누르세요.")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n서버를 종료합니다.")
