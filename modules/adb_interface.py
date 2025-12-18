import subprocess
import os
import time

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

    def list_packages(self, device_id):
        """List all installed packages."""
        command = f"-s {device_id} shell pm list packages"
        output = self._run_command(command)
        packages = []
        if output:
            for line in output.split('\n'):
                if line.startswith('package:'):
                    packages.append(line.replace('package:', '').strip())
        return sorted(packages)

    def list_databases(self, device_id, package_name):
        """List database files for a package."""
        # Need root to access /data/data
        # ls -R /data/data/package_name/databases
        cmd = f"ls /data/data/{package_name}/databases"
        command = f"-s {device_id} shell \"su -c '{cmd}'\""
        output = self._run_command(command)
        
        databases = []
        if output:
            # Check if directory exists or permission denied
            if "No such file" in output or "Permission denied" in output:
                return []
                
            for line in output.split('\n'):
                line = line.strip()
                if line and not line.endswith('-journal') and not line.endswith('-wal') and not line.endswith('-shm'):
                    databases.append(line)
        return databases

    def pull_database(self, device_id, package_name, db_name, local_path):
        """Pull a database file from the device to local path."""
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
        result = self._run_command(pull_cmd)
        
        # 3. Clean up remote temp file
        rm_cmd = f"-s {device_id} shell rm {temp_remote_path}"
        self._run_command(rm_cmd)
        
        return os.path.exists(local_path)
