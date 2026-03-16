import sys
import os

# Add parent directory to path so we can import from database
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import database

def add_admin_cli():
    print("=== Admin User Management ===")
    username = input("Enter new admin username: ").strip()
    if not username:
        print("Error: Username cannot be empty.")
        return

    password = input("Enter password: ").strip()
    if not password:
        print("Error: Password cannot be empty.")
        return

    # Check database connection first
    if not database.check_connection():
        print("Error: Could not connect to database.")
        return

    if database.add_admin_user(username, password):
        print(f"Success: Admin user '{username}' added successfully.")
    else:
        print(f"Error: Admin user '{username}' already exists.")

if __name__ == "__main__":
    add_admin_cli()
