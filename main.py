import tkinter as tk
from database import database
from gui import FaceRecognitionApp
from attendance.policy_manager import PolicyManager

def main():
    # Initialize the database and create tables if they don't exist
    database.init_db()

    # Load existing face encodings, names and IDs from the database
    known_encodings, known_names, known_ids = database.load_encodings()
    
    # Initialize Tkinter
    root = tk.Tk()
    # Initialize and start Policy Manager
    policy_manager = PolicyManager()
    policy_manager.start()

    try:
        # Start the GUI application
        app = FaceRecognitionApp(root, known_encodings, known_names, known_ids)
        root.mainloop()
    finally:
        # Ensure policy manager stops when GUI is closed
        policy_manager.stop()

if __name__ == "__main__":
    main()
