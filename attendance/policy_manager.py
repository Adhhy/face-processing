import sqlite3
import time
from datetime import datetime
import threading
from database.database import DB_NAME
import urllib.request
import json
from utils.logger import logger

class PolicyManager:
    def __init__(self):
        self.running = False
        self.thread = None
        self.last_processed_log_id = self._get_last_processed_log_id()

    def _get_last_processed_log_id(self):
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT MAX(log_id) FROM policy_logs")
            result = cursor.fetchone()[0]
            return result if result is not None else 0
        except sqlite3.OperationalError:
            return 0
        finally:
            conn.close()

    def start(self):
        if not self.running:
            self.running = True
            self.thread = threading.Thread(target=self._process_loop, daemon=True)
            self.thread.start()
            logger.info("Policy Manager started")

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=2)
            logger.info("Policy Manager stopped")

    def _process_loop(self):
        while self.running:
            self._process_new_logs()
            self._sync_logs_to_server()
            time.sleep(1) # Check every 1 second

    def _sync_logs_to_server(self):
        from database.database import get_unsynced_logs, mark_log_synced
        from dashboard_client.api_client import dashboard_client_instance
        
        # Only attempt sync if we are connected and a session is active
        # (Alternatively, always try if connected, but server might 403)
        if dashboard_client_instance.connection_status != "connected":
            return

        unsynced = get_unsynced_logs()
        if not unsynced:
            return

        logger.info(f"Attempting to sync {len(unsynced)} logs to server...")
        
        for log in unsynced:
            payload = {
                "device_id": dashboard_client_instance.device_id,
                "student_id": log["student_id"],
                "student_name": log["student_name"],
                "timestamp": log["timestamp"],
                "recognition_status": log["event_type"],
                "late_entry": 1 if log["late_approval_required"] else 0,
                "bus_delay": 1 if log["bus_delay_flag"] else 0,
                "session_name": log["session"]
            }
            
            try:
                url = f"{dashboard_client_instance.server_url}/api/attendance/log"
                req = urllib.request.Request(
                    url,
                    data=json.dumps(payload).encode("utf-8"),
                    headers={"Content-Type": "application/json"}
                )
                with urllib.request.urlopen(req, timeout=5) as response:
                    if response.status == 200:
                        mark_log_synced(log["id"])
                        logger.info(f"Successfully synced log {log['id']} for student {log['student_id']}")
                    else:
                        logger.warning(f"Failed to sync log {log['id']}. Server returned status: {response.status}")
            except urllib.error.HTTPError as e:
                if e.code == 403:
                    logger.warning(f"Sync rejected by server (Forbidden). Likely no active session.")
                else:
                    logger.error(f"HTTP error during sync: {e}")
                break # Stop processing for this loop if server error
            except Exception as e:
                logger.error(f"Connectivity error during log sync: {e}")
                break # Stop processing for this loop

    def _process_new_logs(self):
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()

        # Fetch new logs
        cursor.execute('''
            SELECT logs.id, logs.student_id, logs.timestamp, students.is_bus_student 
            FROM logs 
            JOIN students ON logs.student_id = students.id
            WHERE logs.id > ? 
            ORDER BY logs.id ASC
        ''', (self.last_processed_log_id,))
        
        new_logs = cursor.fetchall()
        
        for log in new_logs:
            log_id, student_id, ts_str, is_bus_student = log
            self._evaluate_log(cursor, log_id, student_id, ts_str, is_bus_student)
            self.last_processed_log_id = log_id
            
        conn.commit()
        conn.close()

    def _evaluate_log(self, cursor, log_id, student_id, ts_str, is_bus_student):
        # Parse timestamp
        dt = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
        date_str = dt.strftime("%Y-%m-%d")
        time_val = dt.time()

        # Determine Entry/Exit (Toggle state per day per student)
        cursor.execute('''
            SELECT COUNT(*) FROM policy_logs 
            WHERE student_id = ? AND date = ?
        ''', (student_id, date_str))
        count = cursor.fetchone()[0]
        
        event_type = "ENTRY" if count % 2 == 0 else "EXIT"
        
        # Determine Period and Session
        period, session = self._get_period_and_session(time_val)
        
        if period is None:
            return # Ignore logs after 4:00 PM

        late_approval_required = 0
        bus_delay_flag = 0

        # Apply Policy Rules (Only on ENTRY events for P1, P3, P5)
        if event_type == "ENTRY" and period in ["P1", "P3", "P5"]:
            grace_end, late_end = self._get_policy_windows(period)
            
            # Note: time objects can be compared directly
            if time_val > late_end:
                 # Late Entry Cutoff Rule: 
                 # Handled by DB storage but mark context.
                 pass
            elif time_val > grace_end:
                 # Late Approval Window
                 late_approval_required = 1
                 if period == "P1" and is_bus_student:
                     bus_delay_flag = 1
            else:
                 # Grace Window (Normal Entry)
                 pass
                 
        # Insert Processed Event
        cursor.execute('''
            INSERT INTO policy_logs (
                log_id, student_id, timestamp, date, 
                event_type, period, session, 
                late_approval_required, bus_delay_flag
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            log_id, student_id, ts_str, date_str, 
            event_type, period, session, 
            late_approval_required, bus_delay_flag
        ))

    def _get_period_and_session(self, t):
        from datetime import time
        
        # Lower boundary check (Ingore logs before 7:30 AM)
        if t < time(7, 30):
            return None, None

        # Morning Session
        if t < time(9, 25): period, session = "P1", "Morning"
        elif t < time(10, 20): period, session = "P2", "Morning"
        # Break (10:20-10:35) is part of P3 (up to 11:30)
        elif t < time(11, 30): period, session = "P3", "Morning"
        elif t < time(12, 25): period, session = "P4", "Morning"
        # Lunch (12:25-1:15) is part of P5 (up to 14:10)
        elif t < time(14, 10): period, session = "P5", "Afternoon"
        elif t < time(15, 5): period, session = "P6", "Afternoon"
        elif t <= time(16, 0): period, session = "P7", "Afternoon"
        else: period, session = None, None # Classes end at 4:00
        
        return period, session

    def _get_policy_windows(self, period):
        from datetime import time
        # Returns (grace_end_time, late_end_time)
        if period == "P1":
            return time(8, 35), time(8, 45)
        elif period == "P3":
            return time(10, 40), time(10, 50)
        elif period == "P5":
            return time(13, 20), time(13, 30)
        return time(0,0), time(0,0) # Safety fallback
