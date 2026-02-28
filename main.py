import tkinter as tk
import database
from gui import FaceRecognitionApp

def main():
    # Initialize the database and create tables if they don't exist
    database.init_db()

    # Load existing face encodings and names from the database
    known_encodings, known_names = database.load_encodings()
    
    # Initialize Tkinter
    root = tk.Tk()
    
    # Start the GUI application
    app = FaceRecognitionApp(root, known_encodings, known_names)
    
    root.mainloop()

if __name__ == "__main__":
    main()
