from flask import Flask, render_template, jsonify, request, send_file
import os
import json
import uuid
import time
from config import Config
from modules.adb_interface import ADBInterface
from modules.db_manager import DBManager

import sys

# Determine path to resources (templates/static)
if getattr(sys, 'frozen', False):
    # Running in a PyInstaller bundle
    template_folder = os.path.join(sys._MEIPASS, 'templates')
    static_folder = os.path.join(sys._MEIPASS, 'static')
    app = Flask(__name__, template_folder=template_folder, static_folder=static_folder)
else:
    # Running in normal Python environment
    app = Flask(__name__)

app.config.from_object(Config)

adb = ADBInterface()

# Helper to get DB path from token
def get_db_path(token):
    return os.path.join(app.config['TEMP_DIR'], token)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/devices', methods=['GET'])
def get_devices():
    devices = adb.connect_device()
    # Check root for each device
    for device in devices:
        if device['status'] == 'device':
            device['root'] = adb.check_root(device['id'])
        else:
            device['root'] = False
    return jsonify(devices)

@app.route('/api/packages/<device_id>', methods=['GET'])
def get_packages(device_id):
    filter_type = request.args.get('filter', 'all')
    packages = adb.list_packages(device_id, filter_type)
    return jsonify(packages)

@app.route('/api/package-debuggable/<device_id>/<package_name>', methods=['GET'])
def check_package_debuggable(device_id, package_name):
    is_debuggable = adb.is_package_debuggable(device_id, package_name)
    return jsonify({'debuggable': is_debuggable})

@app.route('/api/databases/<device_id>/<package_name>', methods=['GET'])
def get_databases(device_id, package_name):
    databases = adb.list_databases(device_id, package_name)
    return jsonify(databases)

@app.route('/api/pull', methods=['POST'])
def pull_database():
    data = request.json
    device_id = data.get('device_id')
    package_name = data.get('package_name')
    db_name = data.get('db_name')
    
    if not all([device_id, package_name, db_name]):
        return jsonify({'error': 'Missing parameters'}), 400
        
    # Generate a unique filename to avoid collisions and file locking issues on Windows
    # Format: device_package_dbname_timestamp.sqlite
    safe_pkg = package_name.replace('.', '_')
    base_token = f"{device_id}_{safe_pkg}_{db_name}"
    timestamp = int(time.time() * 1000)
    token = f"{base_token}_{timestamp}"
    
    # Cleanup old files for this specific database to prevent disk filling
    try:
        temp_dir = app.config['TEMP_DIR']
        for filename in os.listdir(temp_dir):
            if filename.startswith(base_token):
                file_path = os.path.join(temp_dir, filename)
                try:
                    # Try to remove. If locked (very unlikely now), ignore.
                    os.remove(file_path)
                except Exception as e:
                    print(f"Cleanup warning for {filename}: {e}")
    except Exception as e:
        print(f"Directory cleanup warning: {e}")

    local_path = get_db_path(token)
    
    success = adb.pull_database(device_id, package_name, db_name, local_path)
    
    if success:
        return jsonify({'success': True, 'token': token})
    else:
        return jsonify({'success': False, 'error': 'Failed to pull database'}), 500

@app.route('/api/tables/<token>', methods=['GET'])
def get_tables(token):
    db_path = get_db_path(token)
    if not os.path.exists(db_path):
        return jsonify({'error': 'Database session expired or invalid'}), 404
        
    db = DBManager(db_path)
    tables = db.get_tables()
    return jsonify(tables)

@app.route('/api/table/<token>/<table_name>', methods=['GET'])
def get_table_data(token, table_name):
    db_path = get_db_path(token)
    if not os.path.exists(db_path):
        return jsonify({'error': 'Database session expired or invalid'}), 404
        
    limit = int(request.args.get('limit', 100))
    offset = int(request.args.get('offset', 0))
    
    db = DBManager(db_path)
    columns, rows, total = db.get_table_data(table_name, limit, offset)
    return jsonify({'columns': columns, 'rows': rows, 'total': total})

@app.route('/api/query/<token>', methods=['POST'])
def execute_query(token):
    db_path = get_db_path(token)
    if not os.path.exists(db_path):
        return jsonify({'error': 'Database session expired or invalid'}), 404
        
    query = request.json.get('query')
    if not query:
        return jsonify({'error': 'No query provided'}), 400
        
    db = DBManager(db_path)
    result = db.execute_query(query)
    return jsonify(result)

if __name__ == '__main__':
    app.run(debug=True, port=5000)
