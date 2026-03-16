import cv2
import face_recognition
import numpy as np
from database import database
import time
from utils.logger import logger

class FaceEngine:
    def __init__(self, known_encodings, known_names, known_ids):
        """
        Initialize the FaceEngine with known face encodings and corresponding names.
        """
        self.known_encodings = known_encodings
        self.known_names = known_names
        self.known_ids = known_ids
        self.tolerance = 0.6  # Default face_recognition threshold
        
        # Scaling factor for performance
        self.scale_factor = 0.18 

        # Cooldown management: {student_id: {"time": float, "state": str}}
        self.last_seen = {}
        # Configuration
        self.log_capture = True
        self.COOLDOWN = 50 

    def get_encodings(self, frame):
        """
        Expects a BGR frame (from OpenCV).
        Finds all faces in the frame and returns their encodings.
        Uses the hog model for bounding boxes.
        """
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        # We don't resize for registration to get best quality encodings
        face_locations = face_recognition.face_locations(rgb_frame, model="hog")
        face_encodings = face_recognition.face_encodings(rgb_frame, face_locations)
        return face_encodings

    def recognize(self, frame):
        """
        Takes a BGR frame and returns locations and recognized names.
        Resizes the frame for faster processing.
        """
        # Resize frame for faster face recognition processing
        small_frame = cv2.resize(frame, (0, 0), fx=self.scale_factor, fy=self.scale_factor)
        
        # Convert BGR (OpenCV) to RGB (face_recognition)
        rgb_small_frame = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)

        # Find all faces in the current frame
        face_locations = face_recognition.face_locations(rgb_small_frame, model="hog")
        face_encodings = face_recognition.face_encodings(rgb_small_frame, face_locations)

        face_names = []
        face_statuses = []

        for face_encoding in face_encodings:
            name = "Unknown"
            status = ""

            if self.known_encodings:
                # Calculate face distances against all known encodings
                face_distances = face_recognition.face_distance(self.known_encodings, face_encoding)
                
                # Minimum distance gives the best match
                best_match_index = np.argmin(face_distances)
                distance = face_distances[best_match_index]
                
                # Check if it satisfies the tolerance threshold
                if distance <= self.tolerance:
                    name = self.known_names[best_match_index]
                    student_id = self.known_ids[best_match_index]
                    current_time = time.time()
                    
                    # Cooldown and Logging Logic
                    if student_id not in self.last_seen or (current_time - self.last_seen[student_id]['time']) > self.COOLDOWN:
                        # Toggle state: ENTRY if first time or previous was EXIT
                        prev_state = self.last_seen.get(student_id, {}).get('state', 'EXIT')
                        new_state = "ENTRY" if prev_state == "EXIT" else "EXIT"
                        
                        logger.info(f"Student {student_id} recognized")
                        logger.info(f"Face detected: {name}")
                        logger.info(f"{new_state.capitalize()} detected for {student_id}")
                        
                        # Log to database if enabled
                        if self.log_capture:
                            confidence = 1.0 - distance
                            database.insert_log(student_id, confidence)
                        
                        # Update last seen
                        self.last_seen[student_id] = {'time': current_time, 'state': new_state}
                        status = new_state
                    else:
                        # Optional: could show status for a few seconds after logging
                        pass
            if name == "Unknown":
                # Ensure we only log unknown face periodically to avoid spam
                current_time = time.time()
                if "unknown" not in self.last_seen or (current_time - self.last_seen["unknown"]['time']) > self.COOLDOWN:
                    logger.info("Unknown face detected")
                    self.last_seen["unknown"] = {'time': current_time, 'state': 'UNKNOWN'}

            face_names.append(name)
            face_statuses.append(status)

        # Scale back the face locations to original frame size
        scaled_face_locations = []
        for (top, right, bottom, left) in face_locations:
            scaled_face_locations.append((
                int(top / self.scale_factor), 
                int(right / self.scale_factor), 
                int(bottom / self.scale_factor), 
                int(left / self.scale_factor)
            ))

        return scaled_face_locations, face_names, face_statuses
