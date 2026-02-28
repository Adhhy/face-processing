import cv2
import face_recognition
import numpy as np

class FaceEngine:
    def __init__(self, known_encodings, known_names):
        """
        Initialize the FaceEngine with known face encodings and corresponding names.
        """
        self.known_encodings = known_encodings
        self.known_names = known_names
        self.tolerance = 0.6  # Default face_recognition threshold
        
        # Scaling factor for performance
        self.scale_factor = 0.18 

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

        for face_encoding in face_encodings:
            name = "Unknown"

            if self.known_encodings:
                # Calculate face distances against all known encodings
                face_distances = face_recognition.face_distance(self.known_encodings, face_encoding)
                
                # Minimum distance gives the best match
                best_match_index = np.argmin(face_distances)
                
                # Check if it satisfies the tolerance threshold
                if face_distances[best_match_index] <= self.tolerance:
                    name = self.known_names[best_match_index]

            face_names.append(name)

        # Scale back the face locations to original frame size
        scaled_face_locations = []
        for (top, right, bottom, left) in face_locations:
            scaled_face_locations.append((
                int(top / self.scale_factor), 
                int(right / self.scale_factor), 
                int(bottom / self.scale_factor), 
                int(left / self.scale_factor)
            ))

        return scaled_face_locations, face_names
