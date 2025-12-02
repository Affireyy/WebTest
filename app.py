from flask import Flask, request, jsonify, send_from_directory
import json
import os
import secrets
from datetime import datetime, timedelta

app = Flask(__name__)

# -----------------------------
# File paths
# -----------------------------
LIBRARY_FILE = 'library_data.json'
ADMIN_FILE = 'admin.json'

# Session token storage (in-memory, resets on server restart)
active_tokens = {}
TOKEN_EXPIRY_HOURS = 24

# Logs storage (in-memory)
server_logs = []
MAX_LOGS = 1000


# -----------------------------
# Token management functions
# -----------------------------
def generate_token():
    return secrets.token_urlsafe(32)


def is_token_valid(token):
    if token in active_tokens:
        expiry = active_tokens[token]
        if datetime.now() < expiry:
            return True
        else:
            # Token expired, remove it
            del active_tokens[token]
    return False


def create_session_token():
    token = generate_token()
    expiry = datetime.now() + timedelta(hours=TOKEN_EXPIRY_HOURS)
    active_tokens[token] = expiry
    return token


def revoke_token(token):
    if token in active_tokens:
        del active_tokens[token]


# -----------------------------
# Logging functions
# -----------------------------
def add_log(message):
    """Add a log entry with timestamp"""
    from datetime import datetime
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    log_entry = f"[{timestamp}] {message}"
    server_logs.append(log_entry)
    
    # Keep only the last MAX_LOGS entries
    if len(server_logs) > MAX_LOGS:
        server_logs.pop(0)
    
    # Also print to console
    print(log_entry)


# -----------------------------
# Library load/save functions
# -----------------------------
def load_library():
    if os.path.exists(LIBRARY_FILE):
        with open(LIBRARY_FILE, 'r') as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                print("library_data.json corrupted. Starting empty.")
                return []
    return []


def save_library(links):
    with open(LIBRARY_FILE, 'w') as f:
        json.dump(links, f, indent=2)


library_links = load_library()


# -----------------------------
# Admin load function
# -----------------------------
def load_admin():
    if os.path.exists(ADMIN_FILE):
        with open(ADMIN_FILE, 'r') as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                print("admin.json is corrupted.")
                return None
    else:
        print("admin.json missing!")
        return None


# -----------------------------
# Routes (pages)
# -----------------------------
@app.route('/')
def home():
    return send_from_directory('.', 'index.html')


@app.route('/library')
def library_page():
    return send_from_directory('.', 'library.html')


@app.route('/library/admin/login')
def library_admin_login_page():
    return send_from_directory('.', 'admin_login.html')


@app.route('/library/admin')
def library_admin_page():
    return send_from_directory('.', 'admin.html')


# -----------------------------
# IP Logging
# -----------------------------
@app.route('/log-ip', methods=['POST'])
def log_ip():
    user_ip = request.remote_addr

    # Check for proxies
    forwarded = request.headers.get('X-Forwarded-For')
    if forwarded:
        user_ip = forwarded.split(',')[0]

    add_log(f"IP logged: {user_ip}")
    return jsonify({'status': 'success', 'ip': user_ip})


# -----------------------------
# Admin Login API
# -----------------------------
@app.route('/api/admin/login', methods=['POST'])
def admin_login():
    data = request.json
    username = data.get("username")
    password = data.get("password")

    admin_data = load_admin()

    if admin_data and username == admin_data.get("username") and password == admin_data.get("password"):
        token = create_session_token()
        add_log(f"Admin login successful - Token: {token[:10]}...")
        return jsonify({"status": "success", "token": token})

    add_log("Admin login failed: Invalid credentials")
    return jsonify({"status": "error", "message": "Invalid username or password"}), 401


# -----------------------------
# Admin Token Verification API
# -----------------------------
@app.route('/api/admin/verify', methods=['POST'])
def verify_token():
    auth_header = request.headers.get('Authorization')
    
    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({"status": "error", "message": "No token provided"}), 401
    
    token = auth_header.split('Bearer ')[1]
    
    if is_token_valid(token):
        return jsonify({"status": "success"})
    else:
        return jsonify({"status": "error", "message": "Invalid or expired token"}), 401


# -----------------------------
# Admin Logout API
# -----------------------------
@app.route('/api/admin/logout', methods=['POST'])
def admin_logout():
    auth_header = request.headers.get('Authorization')
    
    if auth_header and auth_header.startswith('Bearer '):
        token = auth_header.split('Bearer ')[1]
        revoke_token(token)
        add_log("Admin logged out")
    
    return jsonify({"status": "success"})


# -----------------------------
# Logs API
# -----------------------------
@app.route('/api/admin/logs', methods=['GET'])
def get_logs():
    """Get all server logs"""
    return jsonify({"logs": server_logs})


@app.route('/api/admin/logs', methods=['DELETE'])
def clear_logs():
    """Clear all server logs"""
    global server_logs
    server_logs = []
    add_log("Logs cleared by admin")
    return jsonify({"status": "success"})


# -----------------------------
# Library API
# -----------------------------
@app.route('/api/library', methods=['GET'])
def get_library():
    return jsonify({'links': library_links})


@app.route('/api/library', methods=['POST'])
def add_library_link():
    data = request.json
    name = data.get('name')
    url = data.get('url')

    if name and url:
        library_links.append({'name': name, 'url': url, 'pinned': False})
        save_library(library_links)
        add_log(f"Added to library: {name} - {url}")
        return jsonify({'status': 'success', 'links': library_links})

    return jsonify({'status': 'error', 'message': 'Name and URL required'}), 400


@app.route('/api/library/<int:index>', methods=['DELETE'])
def delete_library_link(index):
    if 0 <= index < len(library_links):
        removed = library_links.pop(index)
        save_library(library_links)
        add_log(f"Removed from library: {removed['name']}")
        return jsonify({'status': 'success', 'links': library_links})

    return jsonify({'status': 'error', 'message': 'Invalid index'}), 400


# -----------------------------
# Pin/Unpin API
# -----------------------------
@app.route('/api/library/<int:index>/pin', methods=['POST'])
def toggle_pin(index):
    if 0 <= index < len(library_links):
        # Ensure the link has a 'pinned' field
        if 'pinned' not in library_links[index]:
            library_links[index]['pinned'] = False
        
        library_links[index]['pinned'] = not library_links[index]['pinned']
        save_library(library_links)
        status = "pinned" if library_links[index]['pinned'] else "unpinned"
        add_log(f"Link {status}: {library_links[index]['name']}")
        return jsonify({'status': 'success', 'links': library_links})

    return jsonify({'status': 'error', 'message': 'Invalid index'}), 400


# -----------------------------
# Pinned Links API (for index page)
# -----------------------------
@app.route('/api/pinned', methods=['GET'])
def get_pinned():
    pinned = [link for link in library_links if link.get('pinned', False)]
    return jsonify({'links': pinned})


# -----------------------------
# Start server
# -----------------------------
if __name__ == '__main__':
    # Debug print to confirm routes are loaded
    add_log("Server starting...")
    add_log("Routes loaded:")
    for rule in app.url_map.iter_rules():
        add_log(f" • {rule}")

    add_log("Server ready on http://0.0.0.0:5000")
    app.run(debug=True, host='0.0.0.0', port=5000)