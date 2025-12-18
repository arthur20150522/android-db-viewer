import subprocess
import os
import time
import base64

class ADBInterface:
    def __init__(self, adb_path='adb'):
        self.adb_path = adb_path

    def _run_command(self, command):
        """Run an ADB command and return the output."""
        full_command = f"{self.adb_path} {command}"
        try:
            result = subprocess.run(
                full_command,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                # text=True,  <-- REMOVED: We need binary output for base64
                # encoding='utf-8' <-- REMOVED
            )
            if result.returncode != 0:
                # Need to decode stderr for logging
                try:
                    err = result.stderr.decode('utf-8', errors='ignore')
                except:
                    err = str(result.stderr)
                print(f"Error running command '{full_command}': {err}")
                return None
            
            # For list_packages and others that expect string, we try to decode.
            # For base64 output, we need to handle it carefully in caller, 
            # BUT here we are a generic runner.
            # To avoid breaking existing code, we try to decode as utf-8 by default.
            # If it fails (binary garbage?), we return bytes?
            # Or better: We change _run_command to ALWAYS return bytes, and let callers decode?
            # That's a big refactor.
            # 
            # Alternative: Add a 'binary' flag to this method.
            # But we can't easily change signature everywhere.
            
            # Let's try to decode. Base64 IS valid utf-8 text (it's ASCII).
            # The problem with 'text=True' in subprocess on Windows is \r\n translation.
            # By reading bytes and decoding manually, we avoid automatic newline translation?
            # Python's decode() usually handles newlines fine, but subprocess text mode does more.
            
            try:
                return result.stdout.decode('utf-8').strip()
            except UnicodeDecodeError:
                # If it's not text, return raw bytes? 
                # Existing code expects string (e.g. split('\n')).
                # If we return bytes, code like "if 'Permission' in output" will fail.
                # Base64 output IS text. So decode() should work.
                # The fix is that we REMOVED text=True, so we get raw bytes from pipe, 
                # avoiding Windows CRLF mangling of the stream BEFORE we get it.
                return result.stdout.decode('utf-8', errors='ignore').strip()
                
        except Exception as e:
            print(f"Exception running command '{full_command}': {e}")
            return None

    def connect_device(self):
        """Check for connected devices."""
        output = self._run_command("devices")
        devices = []
        if output:
            lines = output.split('\n')
            for line in lines[1:]: # Skip "List of devices attached"
                if line.strip():
                    parts = line.split()
                    if len(parts) >= 2:
                        devices.append({'id': parts[0], 'status': parts[1]})
        return devices

    def check_root(self, device_id):
        """Check if the device has root access."""
        print(f"Checking root for {device_id}...")
        
        # Method 1: Check if adbd is already running as root (e.g. emulator)
        cmd1 = f"-s {device_id} shell id"
        out1 = self._run_command(cmd1)
        if out1 and 'uid=0(root)' in out1:
            print(f"Device {device_id} is root (adbd running as root)")
            return True

        # Method 2: su -c id (Standard)
        # Note: On some devices/versions 'su 0 id' might work better, or quotes might be an issue.
        # Trying without inner quotes for Windows compatibility if simple
        cmd2 = f"-s {device_id} shell su -c id"
        out2 = self._run_command(cmd2)
        if out2 and 'uid=0(root)' in out2:
            print(f"Device {device_id} has root access (su -c id)")
            return True
            
        # Method 3: su 0 id (Alternative)
        cmd3 = f"-s {device_id} shell su 0 id"
        out3 = self._run_command(cmd3)
        if out3 and 'uid=0(root)' in out3:
            print(f"Device {device_id} has root access (su 0 id)")
            return True
        
        # Method 4: With quotes (original method)
        cmd4 = f"-s {device_id} shell \"su -c 'id'\""
        out4 = self._run_command(cmd4)
        if out4 and 'uid=0(root)' in out4:
            print(f"Device {device_id} has root access (quoted)")
            return True

        print(f"Device {device_id} does NOT appear to have root access. Outputs: [{out1}], [{out2}], [{out3}], [{out4}]")
        return False

    def list_packages(self, device_id, filter_type='all'):
        """List packages with filtering.
        filter_type: 'all', '-3' (third party), '-s' (system)
        """
        # Build command based on filter
        cmd_args = ""
        if filter_type == '-3':
            cmd_args = "-3"
        elif filter_type == '-s':
            cmd_args = "-s"
            
        command = f"-s {device_id} shell pm list packages {cmd_args}"
        output = self._run_command(command)
        
        packages = []
        if not output:
            return []

        package_names = []
        for line in output.split('\n'):
            if line.startswith('package:'):
                package_names.append(line.replace('package:', '').strip())
        
        return [{'name': p, 'debuggable': None} for p in sorted(package_names)]

    def is_package_debuggable(self, device_id, package_name):
        """Check if a specific package is debuggable using run-as."""
        # This is accurate but slow if run 100 times.
        cmd = f"-s {device_id} shell \"run-as {package_name} id\""
        output = self._run_command(cmd)
        return output and "uid=" in output and "package not debuggable" not in output

    def list_databases(self, device_id, package_name):
        """List database files for a package."""
        # Try method 1: Root (su)
        cmd = f"ls /data/data/{package_name}/databases"
        command_su = f"-s {device_id} shell \"su -c '{cmd}'\""
        output = self._run_command(command_su)
        
        databases = []
        
        # If root failed or permission denied, try Method 2: run-as (Debuggable)
        if not output or "Permission denied" in output or "not found" in output:
            print(f"Root access failed for {package_name}, trying run-as...")
            command_run_as = f"-s {device_id} shell \"run-as {package_name} ls databases\""
            output = self._run_command(command_run_as)
            
        if output:
            # Check for common run-as errors
            if "package not debuggable" in output:
                print(f"Package {package_name} is not debuggable.")
                return []
            if "No such file" in output or "Permission denied" in output:
                return []
                
            for line in output.split('\n'):
                line = line.strip()
                # Clean up potential carriage returns
                line = line.replace('\r', '')
                if line and not line.endswith('-journal') and not line.endswith('-wal') and not line.endswith('-shm'):
                    databases.append(line)
        return databases

    def pull_database(self, device_id, package_name, db_name, local_path):
        """Pull a database file and its auxiliary files (WAL/SHM) from the device."""
        
        # Helper to pull a single file
        def pull_file(filename, target_path):
            # Method 1: Try Root (su)
            temp_remote_path = f"/sdcard/{filename}"
            cp_cmd = f"cp /data/data/{package_name}/databases/{filename} {temp_remote_path}"
            chmod_cmd = f"chmod 644 {temp_remote_path}"
            full_shell_cmd = f"{cp_cmd} && {chmod_cmd}"
            
            command_su = f"-s {device_id} shell \"su -c '{full_shell_cmd}'\""
            self._run_command(command_su)
            
            pull_cmd = f"-s {device_id} pull {temp_remote_path} \"{target_path}\""
            self._run_command(pull_cmd)
            
            rm_cmd = f"-s {device_id} shell rm {temp_remote_path}"
            self._run_command(rm_cmd)
            
            if os.path.exists(target_path) and os.path.getsize(target_path) > 0:
                return True
                
            # Method 2: Try run-as (Debuggable) using Base64 Streaming
            print(f"Root pull failed/not available, trying run-as for {filename}...")
            
            # Use 'cp' to cache to avoid file locking issues with 'cat' on live WAL files
            # 1. Copy to cache/temp_<filename>
            # 2. Cat from cache
            # 3. Remove from cache
            temp_cache_file = f"cache/temp_{filename}_{int(time.time())}"
            
            # Step 1: Copy (cp preserves content better than cat for locked files)
            cp_cmd = f"-s {device_id} shell \"run-as {package_name} cp databases/{filename} {temp_cache_file}\""
            self._run_command(cp_cmd)
            
            # Step 2: Cat | base64
            stream_cmd = f"-s {device_id} shell \"run-as {package_name} cat {temp_cache_file} | base64\""
            b64_output = self._run_command(stream_cmd)
            
            # Step 3: Cleanup (always try)
            rm_cmd = f"-s {device_id} shell \"run-as {package_name} rm {temp_cache_file}\""
            self._run_command(rm_cmd)
            
            if b64_output and "package not debuggable" not in b64_output and "No such file" not in b64_output:
                try:
                    # Clean up output (remove newlines etc)
                    b64_data = b64_output.replace('\n', '').replace('\r', '')
                    
                    # Debug log
                    print(f"Run-as pull {filename}: {len(b64_data)} bytes base64")

                    # If empty
                    if not b64_data:
                        print(f"File {filename} is empty or not found via run-as.")
                        if filename == db_name:
                             return False
                        return False 

                    file_data = base64.b64decode(b64_data)
                    with open(target_path, 'wb') as f:
                        f.write(file_data)
                    return True
                except Exception as e:
                    print(f"Failed to decode base64 stream for {filename}: {e}")
                    return False
            else:
                print(f"Run-as failed for {filename}. Output: {b64_output[:100] if b64_output else 'None'}")
            return False

        # 1. First, try to pull WAL and SHM files (The "Incrementals")
        # We pull them BEFORE the main DB.
        # Rationale: If checkpoint happens during pull:
        #   Case A: Pull WAL (has data) -> Checkpoint -> Pull DB (has data). Result: WAL+DB both have data. SQLite handles this.
        #   Case B: Pull DB (old) -> Checkpoint -> Pull WAL (empty). Result: Old DB + Empty WAL. DATA LOST!
        # So, pulling WAL first is safer.
        
        wal_file = f"{db_name}-wal"
        shm_file = f"{db_name}-shm"
        
        # Important: The local filename must match the tokenized DB name + suffix
        local_wal = f"{local_path}-wal"
        local_shm = f"{local_path}-shm"
        
        # Remove old aux files if they exist locally to avoid staleness
        if os.path.exists(local_wal): os.remove(local_wal)
        if os.path.exists(local_shm): os.remove(local_shm)
        
        # Best effort pull for aux files
        pull_file(wal_file, local_wal)
        pull_file(shm_file, local_shm)

        # 2. Pull the main DB file (The "Base")
        main_success = pull_file(db_name, local_path)
        
        if main_success:
            return True
            
        return False
