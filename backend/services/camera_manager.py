import cv2
import threading
import time
import queue
import base64
from camera import Camera
from face_engine import FaceEngine
from database import database
from utils.logger import logger

class CameraManager:
    def __init__(self):
        self.camera = None
        self.face_engine = None
        self.running = False
        self.stream_thread = None
        self.recognition_thread = None
        
        self.latest_frame = None
        self.processed_frame = None
        self.recognition_results = ([], [], []) # locations, names, statuses
        
        self.clients = set() # WebSocket clients
        self.event_queue = queue.Queue()
        
        self.recognition_active = False
        self.fps = 0
        
        # Scheduling
        self.recheck_schedule = True
        self.recheck_settings = True
        
        # Debug Settings
        self.log_capture = True
        self.show_fps = True
        self.show_overlay = True
        
        self.scheduler_thread = threading.Thread(target=self._scheduler_loop, daemon=True)
        self.scheduler_thread.start()
        
    def is_running(self):
        return self.running
        
    def start_engine(self):
        if self.running:
            return
        
        try:
            # Load encodings from DB
            known_encodings, known_names, known_ids = database.load_encodings()
            
            self.camera = Camera(source=0)
            self.face_engine = FaceEngine(known_encodings, known_names, known_ids)
            self.face_engine.log_capture = self.log_capture
            self.running = True
            self.camera_ok = True
            
            logger.info("Face recognition engine loaded")
            logger.info("Camera initialized")
            
            self.stream_thread = threading.Thread(target=self._stream_loop, daemon=True)
            self.stream_thread.start()
            
            self.recognition_thread = threading.Thread(target=self._recognition_loop, daemon=True)
            self.recognition_thread.start()
        except Exception as e:
            logger.error(f"Camera initialization failed: {e}")
            self.running = False
            self.camera_ok = False
        
    def stop_engine(self):
        self.running = False
        self.recognition_active = False
        if self.stream_thread:
            self.stream_thread.join(timeout=2)
        if self.recognition_thread:
            self.recognition_thread.join(timeout=2)
        if self.camera:
            self.camera.release()
            self.camera = None
            logger.info("Engine stopped")
        self.latest_frame = None
        self.recognition_results = ([], [], [])
            
    def _stream_loop(self):
        frame_count = 0
        start_time = time.time()
        
        while self.running:
            frame = self.camera.get_frame()
            if frame is not None:
                self.latest_frame = frame
                
                # Calculate FPS
                frame_count += 1
                if time.time() - start_time >= 1.0:
                    self.fps = frame_count / (time.time() - start_time)
                    frame_count = 0
                    start_time = time.time()
            
            time.sleep(0.01) # Avoid 100% CPU

    def _recognition_loop(self):
        while self.running:
            if self.recognition_active and self.latest_frame is not None:
                try:
                    frame_to_process = self.latest_frame.copy()
                    locations, names, statuses = self.face_engine.recognize(frame_to_process)
                    self.recognition_results = (locations, names, statuses)
                    
                    # Push events to queue only if logging is enabled
                    if self.log_capture:
                        for name, status in zip(names, statuses):
                            if status:
                                self.event_queue.put({
                                    "type": "recognition",
                                    "name": name,
                                    "status": status,
                                    "timestamp": time.strftime("%H:%M:%S")
                                })
                except Exception as e:
                    logger.error(f"Face recognition failure: {e}")
            
            time.sleep(0.1) # Frequency of recognition (10 FPS max)

    def get_encoded_frame(self, draw_results=True):
        if self.latest_frame is None:
            return None
            
        frame = self.latest_frame.copy()
        
        # Overlay Logic (Debug & Diagnostics)
        if self.show_overlay:
            locations, names, statuses = self.recognition_results
            for (top, right, bottom, left), name, status in zip(locations, names, statuses):
                color = (0, 255, 0)
                label = name
                if status:
                    color = (0, 255, 255)
                    label = f"{name} - {status}"
                
                cv2.rectangle(frame, (left, top), (right, bottom), color, 2)
                cv2.putText(frame, label, (left, top - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
        
        # FPS Logic
        if self.show_fps:
            cv2.putText(frame, f"FPS: {int(self.fps)}", (10, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 1)

        _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
        return base64.b64encode(buffer).decode('utf-8')

    def _scheduler_loop(self):
        """Background thread to manage auto-start/stop based on schedule."""
        while True:
            try:
                # Check settings (immediate response to UI)
                if self.recheck_settings or self.recheck_schedule:
                    self.recheck_settings = False
                    self.recheck_schedule = False
                    self.log_capture = database.get_setting("log_capture", "1") == "1"
                    self.show_fps = database.get_setting("show_fps", "1") == "1"
                    self.show_overlay = database.get_setting("show_overlay", "1") == "1"
                    
                    if self.face_engine:
                        self.face_engine.log_capture = self.log_capture
                
                now = time.localtime()
                current_time_str = time.strftime("%H:%M", now)
                
                start_time = database.get_setting("start_time", "08:00")
                end_time = database.get_setting("end_time", "18:00")
                
                # Check for overnight window support
                if start_time <= end_time:
                    is_within = start_time <= current_time_str < end_time
                else:
                    # Overnight (e.g., 22:00 to 06:00)
                    is_within = current_time_str >= start_time or current_time_str < end_time
                
                if is_within:
                    if not self.running:
                        logger.info(f"Schedule: Auto-starting full engine (In Window: {current_time_str})")
                        self.start_engine()
                        self.recognition_active = True
                    elif not self.recognition_active:
                        self.recognition_active = True
                else:
                    # After duration ends: no more forcing.
                    # User is free to manually start/stop.
                    # We do NOT call stop_engine() here anymore.
                    pass
                        
            except Exception as e:
                logger.error(f"Scheduler error: {e}")
            
            # Faster check loop (2 seconds) for better UI responsiveness in Admin tab
            time.sleep(2)

camera_manager = CameraManager()
