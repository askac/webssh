# WebSSH

A lightweight, web-based SSH terminal with advanced features, designed to run on both **WSL2** and **Native Windows**.

## Features

- **Cross-Platform**:
  - **WSL2 Support**: Run and access your WSL terminal from a Windows browser.
  - **Native Windows Support**: Connect to any SSH server (including local OpenSSH) directly from Windows.
- **URL Overlay**: Select a URL or image link in the terminal, right-click (or left-click on selection), and open it in a resizable, draggable overlay window without leaving the terminal.
- **Terminal PiP (Picture-in-Picture)**: Pop the entire terminal into a system-level floating window to keep an eye on tasks while working in other apps.
- **Security**:
  - **Random Token Authentication**: Each session generates a unique token to prevent unauthorized access.
  - **Local Binding**: The server binds specifically to the WSL IP or Localhost.
- **Performance**:
  - **Fast Startup**: Uses flag files to skip redundant dependency checks.
  - **Offline Ready**: Includes local fallbacks for `xterm.js` and `socket.io`.

## Prerequisites

- **Python 3.10+**
- **WSL2** (optional, for WSL mode)
- **OpenSSH Server** (for connecting to localhost)

## Quick Start

### For WSL2 Users
1. Clone the repository into your WSL environment.
2. Run the automated starter:
   ```bash
   ./run.sh
   ```
3. Copy the generated URL (e.g., `http://172.x.x.x:5000/?token=...`) into your Windows browser.

### For Native Windows Users
1. Clone the repository.
2. Run the automated batch file:
   ```batch
   run.bat
   ```
3. Open the generated URL in your browser.
4. Enter the **Host** (default `127.0.0.1`) and **Port** (default `22`) to connect.

## Project Structure

- `app.py`: Flask-SocketIO backend bridging WebSocket and Paramiko SSH.
- `templates/index.html`: Frontend using xterm.js with custom overlay and PiP logic.
- `static/`: Local assets for offline support.
- `tools/`: Python virtual environments (separated for Windows and WSL).

## License

MIT
