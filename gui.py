import tkinter as tk
from tkinter import messagebox
import cv2
from PIL import Image, ImageTk
import threading
import time
from datetime import datetime, time as t_time
from database import database
from camera import Camera
from face_engine import FaceEngine
from attendance.session_manager import SessionManager

class FaceRecognitionApp:
    def __init__(self, root, known_encodings, known_names, known_ids):
        self.root = root
        self.root.title("Face Recognition System")

        self.camera = Camera(source=0)
        self.face_engine = FaceEngine(known_encodings, known_names, known_ids)

        self.recognition_running = False
        self.camera_thread = None
        self.recognition_thread = None
        
        # Shared states
        self.latest_frame = None
        self.last_locations = []
        self.last_names = []
        self.last_statuses = []
        self.status_clear_times = [] # To clear old statuses
        
        # FPS Tracking
        self.fps_start_time = 0
        self.fps_frame_count = 0
        self.current_fps = 0
        
        # GUI Elements (initialized in setup_gui)
        self.status_label: tk.Label = None  # type: ignore
        self.id_entry: tk.Entry = None  # type: ignore
        self.name_entry: tk.Entry = None  # type: ignore
        self.is_bus_student_var: tk.IntVar = None  # type: ignore
        self.bus_student_cb: tk.Checkbutton = None  # type: ignore
        self.register_btn: tk.Button = None  # type: ignore
        self.start_btn: tk.Button = None  # type: ignore
        self.stop_btn: tk.Button = None  # type: ignore
        self.exit_btn: tk.Button = None  # type: ignore
        self.video_label: tk.Label = None  # type: ignore
        self.calc_dialog: tk.Toplevel = None  # type: ignore
        self.calc_lbl_main: tk.Label = None  # type: ignore
        self.calc_lbl_sub: tk.Label = None  # type: ignore

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

        self.is_bus_student_var = tk.IntVar()
        self.bus_student_cb = tk.Checkbutton(reg_frame, text="Bus Student", variable=self.is_bus_student_var)
        self.bus_student_cb.grid(row=2, column=1, pady=5, sticky="w")

        self.register_btn = tk.Button(reg_frame, text="Register Student", command=self.register_student)
        self.register_btn.grid(row=3, column=0, columnspan=2, pady=10)

        # Recognition Frame
        rec_frame = tk.LabelFrame(self.root, text="Recognition", padx=10, pady=10)
        rec_frame.pack(padx=20, pady=10, fill="both", expand=True)

        self.start_btn = tk.Button(rec_frame, text="Start Recognition", command=self.start_recognition, bg="green", fg="white")
        self.start_btn.pack(side="left", padx=10)

        self.stop_btn = tk.Button(rec_frame, text="Stop Recognition", command=self.stop_recognition, bg="red", fg="white", state=tk.DISABLED)
        self.stop_btn.pack(side="left", padx=10)

        self.exit_btn = tk.Button(rec_frame, text="Exit", command=self.exit_app)
        self.exit_btn.pack(side="right", padx=10)
        
        # Status Label
        self.status_label = tk.Label(rec_frame, text="", fg="blue", font=("Helvetica", 10, "italic"))
        self.status_label.pack(side="bottom", pady=5)

        # Video Frame
        self.video_label = tk.Label(self.root)
        self.video_label.pack(padx=20, pady=10)

    def register_student(self):
        student_id = self.id_entry.get().strip()
        student_name = self.name_entry.get().strip()
        is_bus_student = self.is_bus_student_var.get()

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
            database.insert_student(student_id, student_name, is_bus_student)
            database.insert_encodings(student_id, encodings_gathered)

            # Update engine's in-memory encodings, names and IDs
            self.face_engine.known_encodings.extend(encodings_gathered)
            self.face_engine.known_names.extend([student_name] * len(encodings_gathered))
            self.face_engine.known_ids.extend([student_id] * len(encodings_gathered))

            messagebox.showinfo("Success", f"Registered {student_name} successfully!")
        except Exception as e:
            messagebox.showerror("Database Error", str(e))

        # Clear label and entries
        self.video_label.config(image='')
        self.id_entry.delete(0, tk.END)
        self.name_entry.delete(0, tk.END)
        self.is_bus_student_var.set(0)

    def start_recognition(self):
        self.recognition_running = True
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.register_btn.config(state=tk.DISABLED)
        self.status_label.config(text="Attendance capture active")

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
                for (top, right, bottom, left), name, status in zip(self.last_locations, self.last_names, self.last_statuses):
                    color = (0, 255, 0) # Default Green
                    
                    # If status is ENTRY or EXIT, highlight it
                    if status:
                        label = f"{name} - {status}"
                        # Yellow for status changes
                        color = (0, 255, 255)
                    else:
                        label = name

                    cv2.rectangle(display_frame, (left, top), (right, bottom), color, 2)
                    cv2.putText(display_frame, label, (left, top - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.75, color, 2)
                
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
                    if self.latest_frame is not None:
                        try:
                            # process copy of latest_frame
                            frame_to_process = self.latest_frame.copy()
                            locations, names, statuses = self.face_engine.recognize(frame_to_process)
                            self.last_locations = locations
                            self.last_names = names
                            self.last_statuses = statuses
                        except Exception as e:
                            print(f"Face processing error: {e}")
            
            # Very small sleep to prevent 100% CPU on this thread
            time.sleep(0.01)

    def stop_recognition(self):
        self.recognition_running = False
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.register_btn.config(state=tk.NORMAL)
        self.status_label.config(text="")

    def exit_app(self):
        # 1. Pause face recognition capture
        self.stop_recognition()
        
        now_time = datetime.now().time()
        
        # Determine Session (Wait for end specifically)
        session_to_close = None
        if t_time(12, 25) <= now_time < t_time(13, 15):
            session_to_close = 'Morning'
        elif now_time >= t_time(16, 0):
            session_to_close = 'Afternoon'
            
        if not session_to_close:
            # Direct shutdown, not the end of a session
            self._force_quit()
            return
            
        # 2. Display a session calculation message Modal
        self._show_calculation_dialog()
        
        # 3. Execute the session manager attendance calculation in a thread
        threading.Thread(target=self._run_session_calculation, args=(session_to_close,), daemon=True).start()

    def _show_calculation_dialog(self):
        self.calc_dialog = tk.Toplevel(self.root)
        self.calc_dialog.title("System Shutdown")
        self.calc_dialog.geometry("350x150")
        self.calc_dialog.resizable(False, False)
        
        # User Interaction Lock
        self.calc_dialog.protocol("WM_DELETE_WINDOW", lambda: None) # Ignore X button
        self.calc_dialog.transient(self.root)
        self.calc_dialog.grab_set()

        self.calc_lbl_main = tk.Label(self.calc_dialog, text="Calculating session attendance. Please wait...", font=("Helvetica", 10, "bold"), pady=20)
        self.calc_lbl_main.pack()
        
        self.calc_lbl_sub = tk.Label(self.calc_dialog, text="Initializing...", fg="gray")
        self.calc_lbl_sub.pack()

    def _update_dialog_text(self, text):
        # Must be called thread-safe via root
        if hasattr(self, 'calc_lbl_sub'):
            self.calc_lbl_sub.config(text=text)
            
    def _run_session_calculation(self, session_to_close):
        sm = SessionManager()
        
        # Bridge the sub thread strings into the UI main thread
        def progress_cb(msg):
            self.root.after(0, self._update_dialog_text, msg)
            
        try:
            success = sm.finalize_session(session_to_close, progress_callback=progress_cb)
            
            if success:
                self.root.after(0, lambda: self.calc_lbl_main.config(text="Session attendance successfully calculated.", fg="green"))
                time.sleep(1.5)
                self.root.after(0, lambda: self.calc_lbl_sub.config(text="Preparing system shutdown...", fg="gray"))
                time.sleep(1.0)
            else:
                 # It probably wasn't time yet, direct drop
                 pass
        except Exception as e:
            msg = f"Attendance calculation encountered a problem. Please review system logs."
            self.root.after(0, lambda: self.calc_lbl_main.config(text=msg, fg="red"))
            self.root.after(0, lambda: self.calc_lbl_sub.config(text=str(e)[:100]))
            
            # Unlock the GUI so they can look around
            self.root.after(100, self.calc_dialog.grab_release)
            self.root.after(100, lambda: self.calc_dialog.protocol("WM_DELETE_WINDOW", self.calc_dialog.destroy))
            return # Abort force quit
            
        # 5. Perform system cleanup and shutdown.
        self.root.after(0, self._force_quit)

    def _force_quit(self):
        self.camera.release()
        self.root.quit()
        self.root.destroy()
