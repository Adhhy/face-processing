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
        self._polling_thread = None
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
            with urllib.request.urlopen(req) as response:
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
            with urllib.request.urlopen(req) as response:
                pass # ignore response body here
        except urllib.error.URLError:
            pass # We still mark as disconnected locally

        self.connection_status = "disconnected"
        self.device_key = None
        self._stop_polling.set()
        return {"status": "success"}

    def _start_polling(self):
        self._stop_polling.clear()
        self._polling_thread = threading.Thread(target=self._poll_status, daemon=True)
        self._polling_thread.start()

    def _poll_status(self):
        while not self._stop_polling.is_set():
            # We now poll even when connected to detect server-initiated disconnects
            poll_interval = 3 if self.connection_status == "pending" else 10

            try:
                # Polling /api/system/device-status/<device_id>?device_key=<key>
                url = f"{self.server_url}/api/system/device-status/{self.device_id}?device_key={self.device_key}"
                req = urllib.request.Request(url)
                with urllib.request.urlopen(req) as response:
                    raw_res = response.read().decode("utf-8")
                    res_data = json.loads(raw_res)
                    
                    logger.info(f"Dashboard polling response for {self.device_id}: {res_data}")
                    print(f"Dashboard polling response: {res_data}") # Immediate console visibility
                    
                    # Check for status in different possible locations
                    # 1. Inside 'result' (Real server format)
                    # 2. Inside 'device' object
                    # 3. Top level
                    result_data = res_data.get("result") if isinstance(res_data.get("result"), dict) else res_data
                    device_data = result_data.get("device") if isinstance(result_data.get("device"), dict) else result_data
                    
                    status = device_data.get("connection_status") or device_data.get("status")
                    
                    if status in ["connected", "approved"]:
                        logger.info(f"Device connection approved! Status: {status}")
                        print(f"DEBUG: Status '{status}' matched 'connected/approved'")
                        self.connection_status = "connected"
                    elif status in ["disconnected", "rejected"]:
                        logger.info(f"Device connection {status}")
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

dashboard_client_instance = DashboardClient()
