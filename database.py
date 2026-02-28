import sqlite3
import pickle
import numpy as np

DB_NAME = "attendance.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # Create students table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS students (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL
        )
    ''')

    # Create encodings table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS encodings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT,
            encoding BLOB,
            FOREIGN KEY(student_id) REFERENCES students(id)
        )
    ''')

    conn.commit()
    conn.close()

def insert_student(student_id, name):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    # Insert or ignore to handle case where student already exists
    cursor.execute('INSERT OR IGNORE INTO students (id, name) VALUES (?, ?)', (student_id, name))
    conn.commit()
    conn.close()

def insert_encodings(student_id, encodings_list):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    for encoding in encodings_list:
        # Pickle the numpy array encoding
        pickled_encoding = pickle.dumps(encoding)
        cursor.execute('INSERT INTO encodings (student_id, encoding) VALUES (?, ?)', (student_id, pickled_encoding))

    conn.commit()
    conn.close()

def load_encodings():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute('''
        SELECT students.name, encodings.encoding 
        FROM encodings 
        JOIN students ON encodings.student_id = students.id
    ''')
    
    rows = cursor.fetchall()
    conn.close()

    known_encodings = []
    known_names = []

    for name, pickled_encoding in rows:
        # Unpickle back to numpy array
        encoding = pickle.loads(pickled_encoding)
        known_encodings.append(encoding)
        known_names.append(name)

    return known_encodings, known_names
