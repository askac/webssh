import os
import sys
import subprocess
import paramiko
import secrets
import socket
from pathlib import Path
from flask import Flask, render_template, request, abort, make_response
from flask_socketio import SocketIO, emit

ASYNC_MODE = os.getenv('WEBSSH_ASYNC_MODE', '').strip().lower()
if not ASYNC_MODE:
    ASYNC_MODE = 'threading'

if ASYNC_MODE == 'eventlet':
    try:
        import eventlet
        eventlet.monkey_patch()
    except Exception as exc:
        print(f"[!] Eventlet unavailable ({exc}); falling back to threading.", file=sys.stderr)
        ASYNC_MODE = 'threading'

app = Flask(__name__, static_url_path='/static', static_folder='static')
app.config['SECRET_KEY'] = secrets.token_hex(16)
ACCESS_TOKEN = secrets.token_urlsafe(16)

# Default to threading for consistent cross-platform behavior.
socketio = SocketIO(app, cors_allowed_origins="*", async_mode=ASYNC_MODE, logger=False, engineio_logger=False)

# SSH Configuration
SSH_HOST = '127.0.0.1'
SSH_PORT = 22
SSH_USER = os.getenv('USER', 'aska')
DEFAULT_BIND_HOST = os.getenv('WEBSSH_HOST', '').strip()
DEFAULT_PORT = int(os.getenv('WEBSSH_PORT', '5000'))

class SSHBridge:
    def __init__(self, sid):
        self.sid = sid
        self.ssh = None
        self._reset_ssh_client()
        self.channel = None

    def _reset_ssh_client(self):
        if self.ssh:
            self.ssh.close()
        self.ssh = paramiko.SSHClient()
        self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    @staticmethod
    def _is_local_target(host):
        if not host:
            return False
        normalized = host.strip().lower()
        return normalized in {'127.0.0.1', 'localhost', '::1'}

    @staticmethod
    def _iter_local_private_key_files():
        ssh_dir = Path.home() / '.ssh'
        key_names = (
            'id_ed25519',
            'id_ecdsa',
            'id_rsa',
            'id_dsa',
            'id_ed25519_sk',
            'id_ecdsa_sk',
        )
        for key_name in key_names:
            key_path = ssh_dir / key_name
            if key_path.is_file():
                yield key_path

    @staticmethod
    def _load_private_key(key_path, passphrase=None):
        key_types = []
        for key_type_name in ('Ed25519Key', 'ECDSAKey', 'RSAKey', 'DSSKey'):
            key_type = getattr(paramiko, key_type_name, None)
            if key_type is not None:
                key_types.append(key_type)
        last_error = None
        for key_type in key_types:
            try:
                return key_type.from_private_key_file(str(key_path), password=passphrase)
            except paramiko.PasswordRequiredException:
                raise
            except paramiko.SSHException as exc:
                last_error = exc
        if last_error:
            raise last_error
        raise paramiko.SSHException(f"Unsupported key format: {key_path}")

    def _connect_with_local_keys(self, host, port, user, password):
        auth_errors = []
        passphrase = password or None

        try:
            self._reset_ssh_client()
            self.ssh.connect(
                host,
                port=int(port),
                username=user,
                password=None,
                timeout=15,
                allow_agent=True,
                look_for_keys=True,
            )
            print(f"[+] Local key auth succeeded via agent/default keys for {self.sid}")
            return True, None
        except paramiko.AuthenticationException as exc:
            auth_errors.append(f"agent/default keys: {exc}")
        except Exception as exc:
            auth_errors.append(f"agent/default keys: {exc}")

        for key_path in self._iter_local_private_key_files():
            try:
                pkey = self._load_private_key(key_path, passphrase=passphrase)
            except paramiko.PasswordRequiredException:
                auth_errors.append(f"{key_path.name}: passphrase required")
                continue
            except Exception as exc:
                auth_errors.append(f"{key_path.name}: {exc}")
                continue

            try:
                self._reset_ssh_client()
                self.ssh.connect(
                    host,
                    port=int(port),
                    username=user,
                    password=None,
                    pkey=pkey,
                    timeout=15,
                    allow_agent=False,
                    look_for_keys=False,
                )
                print(f"[+] Local key auth succeeded via {key_path.name} for {self.sid}")
                return True, None
            except Exception as exc:
                auth_errors.append(f"{key_path.name}: {exc}")

        return False, '; '.join(auth_errors)

    def connect(self, host, port, user, password=None):
        try:
            pwd = password if password else ""
            print(f"[*] Attempting SSH connection for {user} at {host}:{port}...")

            is_localhost = self._is_local_target(host)
            if is_localhost:
                success, key_error = self._connect_with_local_keys(host, port, user, pwd)
                if not success and pwd:
                    print(f"[*] Local key auth failed for {self.sid}; falling back to password auth.")
                    self._reset_ssh_client()
                    self.ssh.connect(
                        host,
                        port=int(port),
                        username=user,
                        password=pwd,
                        timeout=15,
                        allow_agent=False,
                        look_for_keys=False,
                    )
                elif not success:
                    raise paramiko.AuthenticationException(
                        f"Local public key auth failed: {key_error or 'no usable local key found'}"
                    )
            else:
                self._reset_ssh_client()
                self.ssh.connect(
                    host,
                    port=int(port),
                    username=user,
                    password=pwd,
                    timeout=15,
                    allow_agent=False,
                    look_for_keys=False,
                )

            self.channel = self.ssh.invoke_shell(term='xterm-256color', width=80, height=24)
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
        socketio.emit(
            'ssh_output',
            {
                'data': f'\r\n[ERROR] Connection Failed: {err}\r\n',
                'message_type': 'connection_error',
            },
            room=request.sid,
        )

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

def is_wsl():
    if not sys.platform.startswith('linux'):
        return False

    if os.getenv('WSL_DISTRO_NAME'):
        return True

    try:
        with open('/proc/version', 'r', encoding='utf-8') as version_file:
            return 'microsoft' in version_file.read().lower()
    except OSError:
        return False

def get_primary_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

def get_wsl_ip():
    try:
        result = subprocess.run(['hostname', '-I'], capture_output=True, text=True, check=False)
        ips = result.stdout.strip().split()
        if ips:
            return ips[0]
    except Exception:
        pass

    return get_primary_ip()

def get_bind_host():
    if DEFAULT_BIND_HOST:
        return DEFAULT_BIND_HOST

    if is_wsl():
        return get_wsl_ip()

    return "127.0.0.1"

def get_access_host(bind_host):
    if bind_host in {"0.0.0.0", "::"}:
        return get_primary_ip()

    return bind_host

def get_runtime_name():
    if is_wsl():
        return "WSL"
    if sys.platform == 'darwin':
        return "macOS"
    if sys.platform.startswith('win'):
        return "Windows"
    return "Linux"

if __name__ == '__main__':
    bind_host = get_bind_host()
    access_host = get_access_host(bind_host)
    port = DEFAULT_PORT
    print("\n" + "="*60)
    print(f"WebSSH Server Starting...")
    print(f"Runtime: {get_runtime_name()}")
    print(f"Async Mode: {ASYNC_MODE}")
    print(f"Access URL: http://{access_host}:{port}/?token={ACCESS_TOKEN}")
    print(f"Listening on: {bind_host}:{port}")
    if sys.platform == 'darwin':
        print("Tip: Enable Remote Login in macOS if you want localhost SSH access.")
    print("="*60 + "\n")
    
    sys.stdout.flush()

    run_kwargs = {'host': bind_host, 'port': port}
    if ASYNC_MODE == 'threading':
        run_kwargs['allow_unsafe_werkzeug'] = True

    socketio.run(app, **run_kwargs)
