import eventlet
eventlet.monkey_patch()

import os
import threading
import paramiko
import secrets
import socket
import sys
from flask import Flask, render_template, request, abort, make_response
from flask_socketio import SocketIO, emit

app = Flask(__name__, static_url_path='/static', static_folder='static')
app.config['SECRET_KEY'] = secrets.token_hex(16)
ACCESS_TOKEN = secrets.token_urlsafe(16)

# Use eventlet for concurrency - disabled noisy loggers
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet', logger=False, engineio_logger=False)

# SSH Configuration
SSH_HOST = '127.0.0.1'
SSH_PORT = 22
SSH_USER = os.getenv('USER', 'aska')

class SSHBridge:
    def __init__(self, sid):
        self.sid = sid
        self.ssh = paramiko.SSHClient()
        self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.channel = None

    def connect(self, host, port, user, password=None):
        try:
            print(f"[*] Attempting SSH connection for {user} at {host}:{port}...")
            self.ssh.connect(host, port=int(port), username=user, password=password, timeout=10)
            self.channel = self.ssh.invoke_shell(term='xterm', width=80, height=24)
            self.channel.setblocking(0)
            print(f"[+] SSH connection established for {self.sid}")
            return True, None
        except Exception as e:
            error_msg = str(e)
            print(f"[!] SSH Connection Error: {error_msg}")
            return False, error_msg

    def read_from_ssh(self):
        print(f"[*] Starting SSH read loop for {self.sid}")
        while True:
            # Short sleep to prevent CPU hogging while allowing high responsiveness
            socketio.sleep(0.01)
            if not self.channel:
                break
            
            try:
                if self.channel.recv_ready():
                    data = self.channel.recv(4096).decode('utf-8', errors='ignore')
                    if data:
                        socketio.emit('ssh_output', {'data': data}, room=self.sid)
                
                if self.channel.exit_status_ready():
                    print(f"[*] SSH session exited for {self.sid}")
                    socketio.emit('ssh_output', {'data': '\r\n[SSH Session Closed]\r\n'}, room=self.sid)
                    break
            except Exception as e:
                print(f"[!] Read error: {e}")
                break
        print(f"[*] SSH read loop terminated for {self.sid}")

    def write_to_ssh(self, data):
        if self.channel:
            try:
                self.channel.send(data)
            except Exception as e:
                print(f"[!] Write error: {e}")

    def resize_ssh(self, cols, rows):
        if self.channel:
            try:
                self.channel.resize_pty(width=cols, height=rows)
            except Exception as e:
                print(f"[!] Resize error: {e}")

bridges = {}

@app.route('/')
def index():
    token = request.args.get('token')
    if not token or token.strip() != ACCESS_TOKEN:
        return abort(403, description="Invalid or missing access token.")

    # Add no-cache headers to ensure the browser always gets the latest token
    response = make_response(render_template('index.html', token=token))
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    return response

@socketio.on('connect')
def on_connect():
    # Use 'token' instead of 't' to avoid collision with Socket.IO's cache buster
    token = request.args.get('token')

    # If the token from client doesn't match the current server token
    if not token or token.strip() != ACCESS_TOKEN:
        print(f"[!] Unauthorized WebSocket attempt: {request.sid}")
        print(f"    Expected: {ACCESS_TOKEN}")
        print(f"    Received: {token}")
        return False 
    print(f"[+] Client connected: {request.sid}")


@socketio.on('start_ssh')
def on_start_ssh(data):
    host = data.get('host', '127.0.0.1')
    port = data.get('port', 22)
    user = data.get('username', SSH_USER)
    password = data.get('password')
    
    bridge = SSHBridge(request.sid)
    success, err = bridge.connect(host, port, user, password)
    if success:
        bridges[request.sid] = bridge
        socketio.start_background_task(target=bridge.read_from_ssh)
    else:
        socketio.emit('ssh_output', {'data': f'\r\n[ERROR] Connection Failed: {err}\r\n'}, room=request.sid)

@socketio.on('ssh_input')
def on_ssh_input(data):
    bridge = bridges.get(request.sid)
    if bridge:
        bridge.write_to_ssh(data.get('data'))

@socketio.on('resize')
def on_resize(data):
    bridge = bridges.get(request.sid)
    if bridge:
        bridge.resize_ssh(data.get('cols'), data.get('rows'))

@socketio.on('disconnect')
def on_disconnect():
    bridge = bridges.pop(request.sid, None)
    if bridge:
        print(f"[*] Cleaning up SSH session for {request.sid}")
        if bridge.channel:
            bridge.channel.close()
        bridge.ssh.close()
    print(f"[-] Client disconnected: {request.sid}")

def get_wsl_ip():
    try:
        # Use hostname -I to get all IPs, pick the first one which is usually the main WSL interface
        import subprocess
        result = subprocess.run(['hostname', '-I'], capture_output=True, text=True)
        ips = result.stdout.strip().split()
        if ips:
            return ips[0]
        
        # Fallback to socket method
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

if __name__ == '__main__':
    wsl_ip = get_wsl_ip()
    port = 5000
    print("\n" + "="*60)
    print(f"WebSSH Server Starting...")
    print(f"Access URL: http://{wsl_ip}:{port}/?token={ACCESS_TOKEN}")
    print(f"Listening on: {wsl_ip}:{port}")
    print("="*60 + "\n")
    
    sys.stdout.flush()
    
    # Bind only to the specific WSL IP as requested
    socketio.run(app, host=wsl_ip, port=port)
