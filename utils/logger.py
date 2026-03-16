import os
import logging
from logging.handlers import RotatingFileHandler

LOGS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logs')
os.makedirs(LOGS_DIR, exist_ok=True)

LOG_FILE = os.path.join(LOGS_DIR, 'system.log')

# Create the logger
logger = logging.getLogger('AttendanceSystem')
logger.setLevel(logging.INFO)

# Clear existing handlers to prevent duplicates
if logger.hasHandlers():
    logger.handlers.clear()

# Create a RotatingFileHandler (Max size: 5MB, Backup Count: 3)
file_handler = RotatingFileHandler(
    LOG_FILE,
    maxBytes=5 * 1024 * 1024,
    backupCount=3
)
file_handler.setLevel(logging.INFO)

# Define the log format
formatter = logging.Formatter('%(asctime)s | %(levelname)s | %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
file_handler.setFormatter(formatter)

# Add handler to the logger
logger.addHandler(file_handler)

# Do NOT add a StreamHandler to keep the console clean
