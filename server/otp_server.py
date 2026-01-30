#!/usr/bin/env python3
"""
OTP Receiver Server
Receives OTP codes via HTTP POST and makes them available for automation
"""

import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
import json
from typing import Optional, Dict, Any
from datetime import datetime
from collections import defaultdict
from urllib.parse import parse_qs, urlparse


class OTPStore:
    """Thread-safe OTP storage with waiting capability"""
    
    def __init__(self):
        self._otps: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()
        self._events: Dict[str, threading.Event] = defaultdict(threading.Event)
    
    def set_otp(self, session_id: str, otp: str, metadata: Optional[Dict] = None):
        """Store an OTP for a session"""
        with self._lock:
            self._otps[session_id] = {
                "otp": otp,
                "received_at": datetime.now().isoformat(),
                "metadata": metadata or {},
                "used": False
            }
            # Signal that OTP is available
            self._events[session_id].set()
    
    def get_otp(self, session_id: str, mark_used: bool = True) -> Optional[str]:
        """Get OTP for a session"""
        with self._lock:
            if session_id in self._otps:
                data = self._otps[session_id]
                if mark_used:
                    data["used"] = True
                return data["otp"]
            return None
    
    def wait_for_otp(self, session_id: str, timeout: float = 120) -> Optional[str]:
        """
        Wait for OTP to arrive for a session
        
        Args:
            session_id: Session identifier
            timeout: Maximum wait time in seconds
        
        Returns:
            OTP code if received, None if timeout
        """
        # Clear any previous event
        self._events[session_id].clear()
        
        # Check if already available
        existing = self.get_otp(session_id, mark_used=False)
        if existing:
            return self.get_otp(session_id, mark_used=True)
        
        # Wait for new OTP
        if self._events[session_id].wait(timeout=timeout):
            return self.get_otp(session_id, mark_used=True)
        
        return None
    
    def clear(self, session_id: Optional[str] = None):
        """Clear OTP(s)"""
        with self._lock:
            if session_id:
                self._otps.pop(session_id, None)
                self._events.pop(session_id, None)
            else:
                self._otps.clear()
                self._events.clear()
    
    def status(self) -> Dict:
        """Get current status"""
        with self._lock:
            return {
                "active_sessions": len(self._otps),
                "sessions": {k: {"used": v["used"], "received_at": v["received_at"]} 
                            for k, v in self._otps.items()}
            }


# Global OTP store
otp_store = OTPStore()


class OTPHandler(BaseHTTPRequestHandler):
    """HTTP request handler for OTP server"""
    
    def log_message(self, format, *args):
        """Custom logging"""
        print(f"[OTP Server] {args[0]}")
    
    def _send_json(self, data: dict, status: int = 200):
        """Send JSON response"""
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())
    
    def do_OPTIONS(self):
        """Handle CORS preflight"""
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
    
    def do_GET(self):
        """Handle GET requests"""
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)
        
        if path == "/status":
            self._send_json(otp_store.status())
        
        elif path.startswith("/otp/"):
            session_id = path.split("/otp/")[1]
            otp = otp_store.get_otp(session_id, mark_used=False)
            if otp:
                self._send_json({"status": "ok", "otp": otp})
            else:
                self._send_json({"status": "not_found"}, 404)
        
        elif path == "/clipboard":
            # Receive clipboard via GET query params
            session_id = query.get("session", ["clipboard"])[0]
            data = query.get("data", [""])[0]
            
            if data:
                otp_store.set_otp(session_id, data)
                print(f"[Clipboard] Received for session '{session_id}': {data[:20]}...")
                # Return success page that closes immediately
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(b"""<!DOCTYPE html><html><body>
                    <h1>OK</h1>
                    <script>window.close();</script>
                </body></html>""")
            else:
                self._send_json({"error": "Missing 'data' parameter"}, 400)
        
        elif path == "/paste":
            # Serve HTML page that reads clipboard and sends to server
            session_id = query.get("session", ["clipboard"])[0]
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            html = f'''<!DOCTYPE html>
<html>
<head><title>Clipboard Capture</title></head>
<body style="font-family: sans-serif; text-align: center; padding-top: 50px;">
    <h2>Reading clipboard...</h2>
    <p id="status">Please wait...</p>
    <script>
        async function captureClipboard() {{
            const statusEl = document.getElementById("status");
            try {{
                // Try to read clipboard
                const text = await navigator.clipboard.readText();
                if (text && text.length > 0) {{
                    statusEl.textContent = "Sending: " + text.substring(0, 20) + "...";
                    // Send to server
                    const url = "/clipboard?session={session_id}&data=" + encodeURIComponent(text);
                    window.location.href = url;
                }} else {{
                    statusEl.textContent = "Clipboard is empty. Please copy something first.";
                }}
            }} catch (err) {{
                statusEl.textContent = "Cannot read clipboard: " + err.message;
                // Fallback: show input field with Button for User Gesture Trigger
                document.body.innerHTML += `
                    <br><br>
                    <div id="manualArea" style="border: 2px dashed #ccc; padding: 15px; margin: 10px;">
                        
                        <!-- Main Button for JS Clipboard API (User Gesture) -->
                        <button onclick="userPaste()" style="width: 100%; padding: 15px; background: #28a745; color: white; border: none; font-size: 18px; margin-bottom: 20px; font-weight: bold; border-radius: 5px;">
                            📋 PASTE CLIPBOARD
                        </button>
                        
                        <hr style="margin: 20px 0; border: 0; border-top: 1px solid #eee;">
                        
                        <!-- Manual Fallback -->
                        <h3 onclick="document.getElementById('manualInput').focus()" style="color: #666; font-size: 14px;">OR MANUAL PASTE:</h3>
                        <input type="text" id="manualInput" placeholder="Paste here manually" style="width: 90%; padding: 10px; font-size: 16px; border: 1px solid #ddd;">
                        <br><br>
                        <button onclick="sendManual()" style="padding: 10px 20px; background: #007bff; color: white; border: none; font-size: 16px; border-radius: 5px;">Send Manual</button>
                    </div>
                    
                    <script>
                    async function userPaste() {
                        const statusEl = document.getElementById("status");
                        statusEl.textContent = "Requesting clipboard access...";
                        try {
                            const text = await navigator.clipboard.readText();
                            if (text && text.length > 0) {
                                statusEl.textContent = "Sending...";
                                window.location.href = "/clipboard?session={session_id}&data=" + encodeURIComponent(text);
                            } else {
                                statusEl.textContent = "Clipboard is empty!";
                            }
                        } catch (err) {
                            statusEl.textContent = "Error: " + err.message;
                            document.getElementById('manualInput').focus();
                        }
                    }
                    </script>
                `;
            }}
        }}
        
        function sendManual() {{
            const text = document.getElementById("manualInput").value;
            if (text) {{
                window.location.href = "/clipboard?session={session_id}&data=" + encodeURIComponent(text);
            }}
        }}
        
        // Auto-run on load
        captureClipboard();
    </script>
</body>
</html>'''
            self.wfile.write(html.encode())
        
        elif path == "/":
            self._send_json({
                "service": "OTP Receiver",
                "endpoints": {
                    "POST /otp": "Send OTP - body: {session_id, otp, [metadata]}",
                    "GET /otp/<session_id>": "Get OTP for session",
                    "GET /clipboard?session=X&data=Y": "Receive clipboard data",
                    "GET /paste?session=X": "HTML page to capture clipboard",
                    "GET /status": "Server status",
                    "POST /clear": "Clear all OTPs"
                }
            })
        
        else:
            self._send_json({"error": "Not found"}, 404)
    
    def do_POST(self):
        """Handle POST requests"""
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode()
        
        try:
            data = json.loads(body) if body else {}
        except json.JSONDecodeError:
            self._send_json({"error": "Invalid JSON"}, 400)
            return
        
        if self.path == "/otp":
            # Receive OTP
            session_id = data.get("session_id", "default")
            otp = data.get("otp")
            
            if not otp:
                self._send_json({"error": "Missing 'otp' field"}, 400)
                return
            
            otp_store.set_otp(session_id, otp, data.get("metadata"))
            print(f"[OTP] Received for session '{session_id}': {otp}")
            
            self._send_json({
                "status": "ok",
                "message": f"OTP stored for session: {session_id}"
            })
        
        elif self.path == "/clear":
            session_id = data.get("session_id")
            otp_store.clear(session_id)
            self._send_json({"status": "ok", "message": "Cleared"})
        
        else:
            self._send_json({"error": "Not found"}, 404)


class OTPServer:
    """OTP Server wrapper with start/stop control"""
    
    def __init__(self, host: str = "0.0.0.0", port: int = 5000):
        self.host = host
        self.port = port
        self.server: Optional[HTTPServer] = None
        self.thread: Optional[threading.Thread] = None
    
    def start(self):
        """Start the server in a background thread"""
        self.server = HTTPServer((self.host, self.port), OTPHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        print(f"[OTP Server] Running on http://{self.host}:{self.port}")
    
    def stop(self):
        """Stop the server"""
        if self.server:
            self.server.shutdown()
            print("[OTP Server] Stopped")
    
    def wait_for_otp(self, session_id: str = "default", timeout: float = 120) -> Optional[str]:
        """Wait for OTP to arrive"""
        return otp_store.wait_for_otp(session_id, timeout)
    
    def get_otp(self, session_id: str = "default") -> Optional[str]:
        """Get stored OTP"""
        return otp_store.get_otp(session_id)
    
    def clear(self, session_id: Optional[str] = None):
        """Clear OTP(s)"""
        otp_store.clear(session_id)


# Global server instance
_server: Optional[OTPServer] = None


def start_server(port: int = 5000) -> OTPServer:
    """Start the OTP server"""
    global _server
    if _server is None:
        _server = OTPServer(port=port)
        _server.start()
    return _server


def get_server() -> Optional[OTPServer]:
    """Get the running server instance"""
    return _server


def wait_otp(session_id: str = "default", timeout: float = 120, 
             otp_server_url: str = "http://127.0.0.1:5000") -> Optional[str]:
    """Wait for OTP by polling the OTP server HTTP API"""
    import urllib.request
    import urllib.error
    
    start_time = time.time()
    poll_interval = 1.0  # Poll every 1 second
    
    while time.time() - start_time < timeout:
        try:
            url = f"{otp_server_url}/otp/{session_id}"
            with urllib.request.urlopen(url, timeout=5) as response:
                data = json.loads(response.read().decode())
                if data.get("status") == "ok" and data.get("otp"):
                    return data["otp"]
        except urllib.error.HTTPError as e:
            if e.code == 404:
                # OTP not yet available, wait and retry
                pass
            else:
                print(f"  ⚠ OTP server error: {e}")
        except urllib.error.URLError as e:
            print(f"  ⚠ Cannot connect to OTP server: {e}")
        except Exception as e:
            print(f"  ⚠ Error fetching OTP: {e}")
        
        time.sleep(poll_interval)
    
    return None


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="OTP Receiver Server")
    parser.add_argument("-p", "--port", type=int, default=5000, help="Port to listen on")
    args = parser.parse_args()
    
    print(f"""
╔═══════════════════════════════════════════════════════════╗
║              OTP Receiver Server                          ║
╠═══════════════════════════════════════════════════════════╣
║  POST /otp                                                ║
║    Body: {{"session_id": "xxx", "otp": "123456"}}          ║
║                                                           ║
║  GET /otp/<session_id>  - Get stored OTP                  ║
║  GET /status            - Server status                   ║
╚═══════════════════════════════════════════════════════════╝
""")
    
    server = OTPServer(port=args.port)
    server.start()
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down...")
        server.stop()
