from flask import Flask, render_template, jsonify, request, send_file
import os
import json
import uuid
from config import Config
from modules.adb_interface import ADBInterface
from modules.db_manager import DBManager

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
    packages = adb.list_packages(device_id)
    return jsonify(packages)

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
        
    # Generate a unique filename to avoid collisions
    # Format: device_package_dbname.sqlite (sanitized)
    safe_pkg = package_name.replace('.', '_')
    token = f"{device_id}_{safe_pkg}_{db_name}"
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
