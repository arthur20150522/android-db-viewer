from modules.adb_interface import ADBInterface
from modules.db_manager import DBManager
import os
import time

def test_pull_and_read():
    adb = ADBInterface()
    
    # 1. Connect
    devices = adb.connect_device()
    print(f"Devices: {devices}")
    if not devices:
        print("No devices found.")
        return

    device_id = devices[0]['id']
    pkg = "com.xmcy.hykb"
    db_name = "ok-download.db"
    table_name = "task_list"
    
    print(f"Target: Device={device_id}, Pkg={pkg}, DB={db_name}")
    
    # 2. Check files on device (Debug info)
    print("\n--- Checking remote files ---")
    # We use run-as ls -l to see sizes
    cmd = f"-s {device_id} shell \"run-as {pkg} ls -l databases/\""
    print(adb._run_command(cmd))
    
    # 3. Pull
    print("\n--- Pulling Database ---")
    local_path = os.path.abspath(f"temp/test_{int(time.time())}.db")
    os.makedirs("temp", exist_ok=True)
    
    success = adb.pull_database(device_id, pkg, db_name, local_path)
    
    if success:
        print(f"Pull success! Saved to {local_path}")
        
        # Check local files
        print(f"Local DB size: {os.path.getsize(local_path)} bytes")
        wal_path = local_path + "-wal"
        if os.path.exists(wal_path):
            print(f"Local WAL size: {os.path.getsize(wal_path)} bytes")
        else:
            print("Local WAL does not exist.")
            
        # 4. Read Data
        print("\n--- Reading Data ---")
        db = DBManager(local_path)
        # Checkpoint is done inside get_connection() now
        
        conn = db.get_connection()
        if conn:
            try:
                cursor = conn.cursor()
                cursor.execute(f"SELECT count(*) as count FROM {table_name}")
                count = cursor.fetchone()['count']
                print(f"Total Rows in '{table_name}': {count}")
                
                cursor.execute(f"SELECT * FROM {table_name}")
                rows = cursor.fetchall()
                for row in rows:
                    print(dict(row))
            except Exception as e:
                print(f"Query failed: {e}")
            finally:
                conn.close()
    else:
        print("Pull failed.")

if __name__ == "__main__":
    test_pull_and_read()
