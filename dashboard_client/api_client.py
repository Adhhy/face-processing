"""
This module will contain logic to sync or push data to the remote dashboard server.
"""

import os
import json
import uuid
import secrets
import urllib.request
import urllib.error
import threading
import time
from config.config import SERVER_URL, DEVICE_NAME
from utils.logger import logger
import socket

class DashboardClient:
    def __init__(self):
        self.server_url = SERVER_URL.rstrip('/')
        self.device_name = DEVICE_NAME
        self.device_id = self._get_or_create_device_id()
        self.connection_status = "disconnected" # "disconnected", "pending", "connected"
        self.device_key = None
        self.last_command = "idle"
        self.is_session_active = False
        self._polling_thread = None
        self._command_thread = None
        self._stop_polling = threading.Event()

    def _get_or_create_device_id(self):
        # Persistent ID logic
        id_file = os.path.join(os.path.dirname(__file__), "device_id.txt")
        if os.path.exists(id_file):
            with open(id_file, "r") as f:
                return f.read().strip()
        else:
            new_id = str(uuid.uuid4())
            with open(id_file, "w") as f:
                f.write(new_id)
            return new_id

    def get_local_ip(self):
        try:
            # Create a dummy socket to determine the routing IP
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"

    def request_connection(self):
        if self.connection_status != "disconnected":
            return {"status": "error", "message": f"Already in state: {self.connection_status}", "device_key": self.device_key}

        self.device_key = secrets.token_hex(4).upper() # 8 char hex string e.g. "A1B2C3D4"
        
        payload = {
            "device_id": self.device_id,
            "device_name": self.device_name,
            "device_key": self.device_key,
            "ip_address": self.get_local_ip()
        }
       
        try:
            req = urllib.request.Request(
                f"{self.server_url}/api/system/connect",
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=5) as response:
                res_data = json.loads(response.read().decode("utf-8"))
                if res_data.get("status") == "success":
                    self.connection_status = "pending"
                    self._start_polling()
                    return {"status": "success", "device_key": self.device_key}
                else:
                    self.device_key = None
                    return {"status": "error", "message": "Server rejected request."}
        except urllib.error.URLError as e:
            self.device_key = None
            return {"status": "error", "message": f"Unable to reach server: {e}"}

    def disconnect(self):
        if self.connection_status == "disconnected":
            return {"status": "success"}

        payload = {
            "device_id": self.device_id,
            "device_key": self.device_key
        }
        try:
            req = urllib.request.Request(
                f"{self.server_url}/api/system/device-disconnect",
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=5) as response:
                pass # ignore response body here
        except urllib.error.URLError:
            pass # We still mark as disconnected locally

        self.connection_status = "disconnected"
        self.device_key = None
        self._stop_polling.set()
        return {"status": "success"}

    def _start_polling(self):
        self._stop_polling.clear()
        
        # Thread 1: Monitor Connection Status
        self._polling_thread = threading.Thread(target=self._poll_status, daemon=True)
        self._polling_thread.start()
        
        # Thread 2: Monitor Operational Commands (High Speed)
        self._command_thread = threading.Thread(target=self._poll_command_loop, daemon=True)
        self._command_thread.start()

    def _poll_status(self):
        """Monitors connection health and server heartbeats."""
        while not self._stop_polling.is_set():
            # Check for disconnects or approvals every 5 seconds
            poll_interval = 5

            try:
                # Polling /api/system/device-status/<device_id>?device_key=<key>
                url = f"{self.server_url}/api/system/device-status/{self.device_id}?device_key={self.device_key}"
                req = urllib.request.Request(url)
                with urllib.request.urlopen(req, timeout=5) as response:
                    res_data = json.loads(response.read().decode("utf-8"))
                    
                    # Robust Nested Parsing
                    result_data = res_data.get("result") if isinstance(res_data.get("result"), dict) else res_data
                    device_data = result_data.get("device") if isinstance(result_data.get("device"), dict) else result_data
                    status = device_data.get("connection_status") or device_data.get("status")
                    
                    if status in ["connected", "approved"]:
                        if self.connection_status != "connected":
                            logger.info(f"Connection established and approved by server.")
                        self.connection_status = "connected"
                        
                    elif status in ["disconnected", "rejected"]:
                        logger.warning(f"Session terminated by server. Reason: {status}")
                        self.connection_status = "disconnected"
                        self.device_key = None
                        self._stop_polling.set()
            except urllib.error.URLError as e:
                logger.warning(f"Polling connection error for {url}: {e}")
                print(f"DEBUG: Connection error for {url}: {e}")
            except Exception as e:
                logger.error(f"Unexpected polling error Traceback: ", exc_info=True)
                print(f"ERROR in polling: {e}")

            time.sleep(poll_interval)

    def _poll_command_loop(self):
        """Independent high-speed thread to sync remote operational commands."""
        while not self._stop_polling.is_set():
            # Synchronize operational state with the dashboard every 3 seconds
            command_interval = 3
            
            if self.connection_status == "connected":
                try:
                    self._poll_command()
                except Exception as e:
                    logger.debug(f"Sync loop transient error: {e}")
            
            time.sleep(command_interval)

    def _poll_command(self):
        """Fetch and enforce latest command from the server specialized endpoint."""
        try:
            url = f"{self.server_url}/api/device/command/{self.device_id}"
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=5) as response:
                res_data = json.loads(response.read().decode("utf-8"))
                
                # Robust Nested Parsing for operational instructions
                result_data = res_data.get("result") if isinstance(res_data.get("result"), dict) else res_data
                command = result_data.get("command", "idle")
                
                # State-aware synchronization:
                # We compare the server's desired command with the actual hardware state.
                from backend.services.camera_manager import camera_manager
                is_running = camera_manager.is_running()
                
                if command == "start_camera" and not is_running:
                    logger.info("Remote priority sync: Server requires START but engine is IDLE. Forcing start.")
                    self._execute_command("start_camera")
                elif command == "stop_camera" and is_running:
                    logger.info("Remote priority sync: Server requires STOP but engine is RUNNING. Forcing stop.")
                    self._execute_command("stop_camera")
                
                self.is_session_active = (command == "start_camera")
                self.last_command = command
                
        except Exception as e:
            logger.error(f"Error polling command: {e}")

    def _execute_command(self, command):
        """Translate server commands into local engine actions."""
        try:
            from backend.services.camera_manager import camera_manager
            
            if command == "start_camera":
                logger.info("Executing remote command: START")
                camera_manager.start_engine()
                camera_manager.recognition_active = True
            elif command == "stop_camera":
                logger.info("Executing remote command: STOP")
                camera_manager.stop_engine()
            elif command == "idle":
                # Handle idle state if necessary, or just maintain current state
                pass
            else:
                logger.warning(f"Unknown command received: {command}")
                
        except Exception as e:
            logger.error(f"Failed to execute command '{command}': {e}")

dashboard_client_instance = DashboardClient()
