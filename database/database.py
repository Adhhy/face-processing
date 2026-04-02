import os
import sqlite3
import pickle
import numpy as np
import hashlib
from utils.logger import logger

# Path to the database file (in the same directory as this script)
DB_NAME = os.path.join(os.path.dirname(__file__), "attendance.db")

def hash_password(password, salt=None):
    if salt is None:
        salt = os.urandom(16).hex()
    hashed = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000).hex()
    return f"{salt}${hashed}"

def verify_password(password, stored_password):
    try:
        salt, hashed = stored_password.split('$')
        check = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000).hex()
        return check == hashed
    except:
        return False

def check_connection():
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        conn.close()
        return True
    except:
        return False

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # Create students table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS students (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            is_bus_student INTEGER DEFAULT 0
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

    # Create logs table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT,
            timestamp TEXT,
            confidence REAL,
            FOREIGN KEY(student_id) REFERENCES students(id)
        )
    ''')

    # Create policy_logs table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS policy_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            log_id INTEGER,
            student_id TEXT,
            timestamp TEXT,
            date TEXT,
            event_type TEXT,
            period TEXT,
            session TEXT,
            late_approval_required INTEGER DEFAULT 0,
            bus_delay_flag INTEGER DEFAULT 0,
            synced INTEGER DEFAULT 0,
            FOREIGN KEY(log_id) REFERENCES logs(id),
            FOREIGN KEY(student_id) REFERENCES students(id)
        )
    ''')

    # Migration for existing databases
    try:
        cursor.execute("ALTER TABLE policy_logs ADD COLUMN synced INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass # Column already exists

    # Create admin_users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS admin_users (
            username TEXT PRIMARY KEY,
            password TEXT NOT NULL
        )
    ''')
    
    # Create settings table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    ''')
    
    # Default admin
    cursor.execute('SELECT COUNT(*) FROM admin_users')
    if cursor.fetchone()[0] == 0:
        default_pwd = hash_password("admin123")
        cursor.execute('INSERT INTO admin_users (username, password) VALUES (?, ?)', ("admin", default_pwd))

    # Default settings
    default_settings = [
        ("start_time", "08:00"),
        ("end_time", "18:00"),
        ("auto_mode", "1"),
        ("log_capture", "1"),
        ("show_fps", "1"),
        ("show_overlay", "1")
    ]
    for key, val in default_settings:
        cursor.execute('INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)', (key, val))

    conn.commit()
    conn.close()
    logger.info("Database connection established and initialized")

def add_admin_user(username, password):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    hashed_pwd = hash_password(password)
    # Using INSERT OR REPLACE or handle duplicate username
    try:
        cursor.execute('INSERT INTO admin_users (username, password) VALUES (?, ?)', (username, hashed_pwd))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def verify_admin_login(username, password):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT password FROM admin_users WHERE username = ?', (username,))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return verify_password(password, row[0])
    return False

def insert_student(student_id, name, is_bus_student=0):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    # Insert or ignore to handle case where student already exists
    cursor.execute('INSERT OR IGNORE INTO students (id, name, is_bus_student) VALUES (?, ?, ?)', 
                   (student_id, name, is_bus_student))
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

def insert_log(student_id, confidence):
    from datetime import datetime
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        cursor.execute('''
            INSERT INTO logs (student_id, timestamp, confidence)
            VALUES (?, ?, ?)
        ''', (student_id, timestamp, confidence))
        conn.commit()
        logger.info(f"Attendance record saved for {student_id}")
    except Exception as e:
        logger.error(f"Database write failure in insert_log: {e}")
    finally:
        conn.close()

def load_encodings():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute('''
        SELECT students.id, students.name, encodings.encoding 
        FROM encodings 
        JOIN students ON encodings.student_id = students.id
    ''')
    
    rows = cursor.fetchall()
    conn.close()

    known_encodings = []
    known_names = []
    known_ids = []

    for student_id, name, pickled_encoding in rows:
        # Unpickle back to numpy array
        encoding = pickle.loads(pickled_encoding)
        known_encodings.append(encoding)
        known_names.append(name)
        known_ids.append(student_id)

    return known_encodings, known_names, known_ids

def get_student_count():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM students')
    count = cursor.fetchone()[0]
    conn.close()
    return count

    conn.close()
    return count

def get_total_log_count():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM logs')
    count = cursor.fetchone()[0]
    conn.close()
    return count

def clear_session_logs():
    """
    Truncates the logs and policy_logs tracking tables.
    Also resets their auto-increment sequences.
    """
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute('DELETE FROM logs')
    cursor.execute('DELETE FROM policy_logs')

    try:
        cursor.execute("DELETE FROM sqlite_sequence WHERE name='logs'")
        cursor.execute("DELETE FROM sqlite_sequence WHERE name='policy_logs'")
    except sqlite3.OperationalError:
        pass  # sqlite_sequence might not be populated yet

    conn.commit()
    conn.close()

def get_setting(key, default=None):
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('SELECT value FROM settings WHERE key = ?', (key,))
        row = cursor.fetchone()
        conn.close()
        return row[0] if row else default
    except Exception as e:
        logger.error(f"Database error getting setting {key}: {e}")
        return default

def update_setting(key, value):
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)', (key, str(value)))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Database error updating setting {key}: {e}")
        return False

def get_recent_policy_logs(limit=50, since=None):
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        if since:
            cursor.execute('''
                SELECT 'raw' as log_type, l.id, l.timestamp, s.name, s.id as student_id, 
                       NULL as event_type, NULL as period, NULL as session, 
                       0 as late_approval_required, 0 as bus_delay_flag, l.confidence
                FROM logs l JOIN students s ON l.student_id = s.id
                WHERE l.timestamp >= ?
                UNION ALL
                SELECT 'policy' as log_type, pl.id, pl.timestamp, s.name, s.id as student_id,
                       pl.event_type, pl.period, pl.session,
                       pl.late_approval_required, pl.bus_delay_flag, NULL as confidence
                FROM policy_logs pl JOIN students s ON pl.student_id = s.id
                WHERE pl.timestamp >= ?
                ORDER BY timestamp DESC, log_type ASC
                LIMIT ?
            ''', (since, since, limit))
        else:
            cursor.execute('''
                SELECT 'raw' as log_type, l.id, l.timestamp, s.name, s.id as student_id, 
                       NULL as event_type, NULL as period, NULL as session, 
                       0 as late_approval_required, 0 as bus_delay_flag, l.confidence
                FROM logs l JOIN students s ON l.student_id = s.id
                UNION ALL
                SELECT 'policy' as log_type, pl.id, pl.timestamp, s.name, s.id as student_id,
                       pl.event_type, pl.period, pl.session,
                       pl.late_approval_required, pl.bus_delay_flag, NULL as confidence
                FROM policy_logs pl JOIN students s ON pl.student_id = s.id
                ORDER BY timestamp DESC, log_type ASC
                LIMIT ?
            ''', (limit,))
        
        rows = cursor.fetchall()
        conn.close()
        
        logs = []
        for row in rows:
            logs.append({
                "type": row[0],
                "id": row[1],
                "timestamp": row[2],
                "name": row[3],
                "student_id": row[4],
                "event_type": row[5],
                "period": row[6],
                "session": row[7],
                "late_approval_required": bool(row[8]),
                "bus_delay_flag": bool(row[9]),
                "confidence": row[10]
            })
        return logs
    except Exception as e:
        logger.error(f"Database error retrieving policy logs: {e}")
        return []
def get_unsynced_logs():
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT pl.id, pl.log_id, pl.student_id, s.name, pl.timestamp, pl.date, pl.event_type, pl.period, pl.session, 
                   pl.late_approval_required, pl.bus_delay_flag 
            FROM policy_logs pl
            LEFT JOIN students s ON pl.student_id = s.id
            WHERE pl.synced = 0
        ''')
        rows = cursor.fetchall()
        conn.close()
        
        logs = []
        for row in rows:
            logs.append({
                "id": row[0],
                "log_id": row[1],
                "student_id": row[2],
                "student_name": row[3] if row[3] else "Unknown",
                "timestamp": row[4],
                "date": row[5],
                "event_type": row[6],
                "period": row[7],
                "session": row[8],
                "late_approval_required": bool(row[9]),
                "bus_delay_flag": bool(row[10])
            })
        return logs
    except Exception as e:
        logger.error(f"Database error fetching unsynced logs: {e}")
        return []

def mark_log_synced(log_id):
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('UPDATE policy_logs SET synced = 1 WHERE id = ?', (log_id,))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Database error marking log as synced: {e}")
        return False
