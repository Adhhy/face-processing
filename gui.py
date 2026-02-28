import tkinter as tk
from tkinter import messagebox
import cv2
from PIL import Image, ImageTk
import threading
import time
import database
from camera import Camera
from face_engine import FaceEngine

class FaceRecognitionApp:
    def __init__(self, root, known_encodings, known_names):
        self.root = root
        self.root.title("Face Recognition System")

        self.camera = Camera(source=0)
        self.face_engine = FaceEngine(known_encodings, known_names)

        self.recognition_running = False
        self.camera_thread = None
        self.recognition_thread = None
        
        # Shared states
        self.latest_frame = None
        self.last_locations = []
        self.last_names = []
        
        # FPS Tracking
        self.fps_start_time = 0
        self.fps_frame_count = 0
        self.current_fps = 0

        self.setup_gui()

    def setup_gui(self):
        # Registration Frame
        reg_frame = tk.LabelFrame(self.root, text="Registration", padx=10, pady=10)
        reg_frame.pack(padx=20, pady=10, fill="x")

        tk.Label(reg_frame, text="Student ID:").grid(row=0, column=0, pady=5, sticky="e")
        self.id_entry = tk.Entry(reg_frame)
        self.id_entry.grid(row=0, column=1, pady=5)

        tk.Label(reg_frame, text="Student Name:").grid(row=1, column=0, pady=5, sticky="e")
        self.name_entry = tk.Entry(reg_frame)
        self.name_entry.grid(row=1, column=1, pady=5)

        self.register_btn = tk.Button(reg_frame, text="Register Student", command=self.register_student)
        self.register_btn.grid(row=2, column=0, columnspan=2, pady=10)

        # Recognition Frame
        rec_frame = tk.LabelFrame(self.root, text="Recognition", padx=10, pady=10)
        rec_frame.pack(padx=20, pady=10, fill="both", expand=True)

        self.start_btn = tk.Button(rec_frame, text="Start Recognition", command=self.start_recognition, bg="green", fg="white")
        self.start_btn.pack(side="left", padx=10)

        self.stop_btn = tk.Button(rec_frame, text="Stop Recognition", command=self.stop_recognition, bg="red", fg="white", state=tk.DISABLED)
        self.stop_btn.pack(side="left", padx=10)

        self.exit_btn = tk.Button(rec_frame, text="Exit", command=self.exit_app)
        self.exit_btn.pack(side="right", padx=10)

        # Video Frame
        self.video_label = tk.Label(self.root)
        self.video_label.pack(padx=20, pady=10)

    def register_student(self):
        student_id = self.id_entry.get().strip()
        student_name = self.name_entry.get().strip()

        if not student_id or not student_name:
            messagebox.showerror("Error", "Student ID and Name are required.")
            return

        messagebox.showinfo("Instructions", "Please look at the camera. Capturing 5 snapshots...")

        encodings_gathered = []
        samples_target = 5
        attempts = 0
        max_attempts = 30 # So it doesn't loop forever if no face found

        while len(encodings_gathered) < samples_target and attempts < max_attempts:
            # Re-initialize or flush buffers if reusing the same camera wrapper
            frame = self.camera.get_frame()
            if frame is None:
                attempts += 1
                continue

            # Display the frame in GUI so user sees what is happening
            cv2image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(cv2image)
            imgtk = ImageTk.PhotoImage(image=img)
            self.video_label.imgtk = imgtk # keep reference
            self.video_label.configure(image=imgtk)
            self.root.update()

            encs = self.face_engine.get_encodings(frame)
            
            if len(encs) > 0:
                # Assuming the primary face is the one to register
                encodings_gathered.append(encs[0])
                time.sleep(0.5) # Slight delay between valid captures

            attempts += 1

        if len(encodings_gathered) == 0:
            messagebox.showerror("Error", "Failed to detect face. Registration incomplete.")
            self.video_label.config(image='')
            return

        if len(encodings_gathered) < samples_target:
            messagebox.showwarning("Warning", f"Only {len(encodings_gathered)} samples captured out of {samples_target}.")

        # Save to database
        try:
            database.insert_student(student_id, student_name)
            database.insert_encodings(student_id, encodings_gathered)

            # Update engine's in-memory encodings and names
            self.face_engine.known_encodings.extend(encodings_gathered)
            self.face_engine.known_names.extend([student_name] * len(encodings_gathered))

            messagebox.showinfo("Success", f"Registered {student_name} successfully!")
        except Exception as e:
            messagebox.showerror("Database Error", str(e))

        # Clear label and entries
        self.video_label.config(image='')
        self.id_entry.delete(0, tk.END)
        self.name_entry.delete(0, tk.END)

    def start_recognition(self):
        self.recognition_running = True
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.register_btn.config(state=tk.DISABLED)

        self.latest_frame = None
        self.last_locations = []
        self.last_names = []
        self.fps_start_time = time.time()
        self.fps_frame_count = 0

        # Thread A: Camera Producer
        self.camera_thread = threading.Thread(target=self.camera_producer_loop, daemon=True)
        self.camera_thread.start()
        
        # Thread B: Face Engine Consumer
        self.recognition_thread = threading.Thread(target=self.face_consumer_loop, daemon=True)
        self.recognition_thread.start()
        
        # GUI Loop
        self.update_gui_display()

    def update_gui_display(self):
        if self.recognition_running:
            if self.latest_frame is not None:
                # Work on a copy to avoid threading conflicts with CV2 drawing
                display_frame = self.latest_frame.copy()

                # Overlay Results
                for (top, right, bottom, left), name in zip(self.last_locations, self.last_names):
                    cv2.rectangle(display_frame, (left, top), (right, bottom), (0, 255, 0), 2)
                    cv2.putText(display_frame, name, (left, top - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (0, 255, 0), 2)
                
                # Overlay FPS
                cv2.putText(display_frame, f"FPS: {int(self.current_fps)}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)

                # Convert to Tkinter format
                cv2image = cv2.cvtColor(display_frame, cv2.COLOR_BGR2RGB)
                img = Image.fromarray(cv2image)
                imgtk = ImageTk.PhotoImage(image=img)
                self.video_label.imgtk = imgtk # keep reference
                self.video_label.configure(image=imgtk)

            # Schedule next UI update (~60 FPS target max for drawing)
            self.root.after(15, self.update_gui_display)
        else:
            self.video_label.config(image='')

    def camera_producer_loop(self):
        """Continuously pulls frames without blocking or buffering."""
        while self.recognition_running:
            frame = self.camera.get_frame()
            if frame is not None:
                self.latest_frame = frame

                # FPS tracking per camera pull
                self.fps_frame_count += 1
                elapsed = time.time() - self.fps_start_time
                if elapsed >= 1.0:
                    self.current_fps = self.fps_frame_count / elapsed
                    self.fps_frame_count = 0
                    self.fps_start_time = time.time()

    def face_consumer_loop(self):
        """Periodically runs heavy face recognition on the latest frame only."""
        recognition_frames_passed = 0
        while self.recognition_running:
            if self.latest_frame is not None:
                recognition_frames_passed += 1
                
                # Process every 4th read to reduce load
                if recognition_frames_passed % 4 == 0:
                    try:
                        # process copy of latest_frame
                        frame_to_process = self.latest_frame.copy()
                        locations, names = self.face_engine.recognize(frame_to_process)
                        self.last_locations = locations
                        self.last_names = names
                    except Exception as e:
                        print(f"Face processing error: {e}")
            
            # Very small sleep to prevent 100% CPU on this thread
            time.sleep(0.01)

    def stop_recognition(self):
        self.recognition_running = False
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.register_btn.config(state=tk.NORMAL)

    def exit_app(self):
        self.stop_recognition()
        self.camera.release()
        self.root.quit()
        self.root.destroy()
