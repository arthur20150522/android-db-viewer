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
                text=True,
                encoding='utf-8' # Force UTF-8
            )
            if result.returncode != 0:
                print(f"Error running command '{full_command}': {result.stderr}")
                return None
            return result.stdout.strip()
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
        """Pull a database file from the device to local path."""
        # Method 1: Try Root (su)
        # 1. Copy to /sdcard/ (readable)
        temp_remote_path = f"/sdcard/{db_name}"
        cp_cmd = f"cp /data/data/{package_name}/databases/{db_name} {temp_remote_path}"
        # Make sure it's readable
        chmod_cmd = f"chmod 644 {temp_remote_path}"
        
        full_shell_cmd = f"{cp_cmd} && {chmod_cmd}"
        
        command_su = f"-s {device_id} shell \"su -c '{full_shell_cmd}'\""
        self._run_command(command_su)
        
        # 2. Pull from /sdcard/
        pull_cmd = f"-s {device_id} pull {temp_remote_path} \"{local_path}\""
        self._run_command(pull_cmd)
        
        # 3. Clean up remote temp file
        rm_cmd = f"-s {device_id} shell rm {temp_remote_path}"
        self._run_command(rm_cmd)
        
        if os.path.exists(local_path) and os.path.getsize(local_path) > 0:
            return True
            
        # Method 2: Try run-as (Debuggable) using Base64 Streaming
        print(f"Root pull failed, trying run-as for {package_name}...")
        
        # Command: run-as <pkg> cat databases/<db> | base64
        # We wrap in another shell to ensure pipe works
        stream_cmd = f"-s {device_id} shell \"run-as {package_name} cat databases/{db_name} | base64\""
        
        # We need to capture the output carefully (it might be large)
        # Note: self._run_command captures stdout. 
        # Large DBs might be an issue for memory, but for typical mobile DBs it's okay.
        b64_output = self._run_command(stream_cmd)
        
        if b64_output and "package not debuggable" not in b64_output and "No such file" not in b64_output:
            try:
                # Clean up output (remove newlines etc)
                b64_data = b64_output.replace('\n', '').replace('\r', '')
                file_data = base64.b64decode(b64_data)
                
                with open(local_path, 'wb') as f:
                    f.write(file_data)
                
                return os.path.exists(local_path) and os.path.getsize(local_path) > 0
            except Exception as e:
                print(f"Failed to decode base64 stream: {e}")
                return False
                
        return False
