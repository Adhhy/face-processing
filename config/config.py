"""
This module will load constants and configuration variables from environment or files.
"""
import os

SERVER_URL = os.getenv("SERVER_URL", "http://localhost:5000")
DEVICE_NAME = os.getenv("DEVICE_NAME", "Classroom Pi")
