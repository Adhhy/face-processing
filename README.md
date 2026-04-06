# Remote Face Attendance Client (`cam_`)

## Overview

This repository contains the `cam_` client component of the Smart Attendance Management System. 

> **Note:** The central `attendance-dashboard` repository explicitly refers to this client directory as `cam_`.

This client is a lightweight, edge-deployed system (typically running on a Raspberry Pi or a local machine attached to a camera) that performs live facial recognition. It communicates with the central server to sync attendance data, receive session commands, and report hardware status. It also exposes a local FastAPI dashboard for direct monitoring, student enrollment, and administrative controls.

## Tech Stack

- **Backend Framework**: FastAPI (Python)
- **Computer Vision**: OpenCV (`cv2`) and Facial Recognition logic (`face_engine.py`)
- **Database**: SQLite3
- **Frontend (Local Dashboard)**: HTML5, CSS3, Vanilla JavaScript (utilizing WebSockets for real-time video streaming & telemetry)
- **Communication**: REST APIs, WebSockets (for local UI), Long Polling/REST (syncing with the Central Dashboard via `dashboard_client`)

## Core Working Logic & Flow

The system is designed to run autonomously while honoring session commands from the central server. 

### 1. Startup & Initialization
When the main FastAPI application (`backend/app.py`) is started, the following happens automatically:
- **Database Setup**: The SQLite database (`database/attendance.db`) and its internal tables automatically initialize upon server startup via `database.init_db()`.
- **Policy Manager Activation**: The system's `PolicyManager` is instantiated and started, preparing background threads for attendance processing.
- **Server Discovery**: The `dashboard_client` initiates communication using the `device_id.txt` configuration to register and poll the central server securely.

### 2. Facial Recognition Engine
- **Camera Capture**: `camera.py` securely interfaces with the connected hardware camera to capture rapid frames.
- **Face Processing**: `face_engine.py` processes these frame streams in real-time, encoding identified faces and matching them against locally stored biometrics.
- **Raw Logging**: Successful matches denote "hits", dropping raw logs internally before further validation.

### 3. Policy Tracking & Server Synchronization
- **Local Attendance Policies**: The `PolicyManager` verifies incoming raw hits against set local time boundaries, ensuring spam/redundant logging is minimized.
- **Central Event Sync**: Fully validated attendance events are pushed from the client unit to the `attendance-dashboard` central data lakes.
- **Command Polling**: The client continuously queries the remote server (via `dashboard_client/api_client.py`). If an authorized Advisor strictly initiates a session on the main dashboard, the client receives the command and automatically starts or stops camera polling.

### 4. Local UI Feedback & Control
For on-premise interaction, the client hosts its own responsive dashboard, accessible locally or securely over LAN. Features include:
- **Live Feed & Telemetry**: Uses WebSockets to deliver a high-framerate real-time camera feed. It renders diagnostic bounds (FPS, ID numbers) and device health metrics (CPU temperature, network speed).
- **Enrollment Interface**: Endpoints to register new students by capturing biometric encoding photos right at the terminal.
- **Administrative Settings**: Offers controls to manually bootstrap/halt the engine, verify network linkages, and restrict operation timeframes.

## Project Structure

This directory has been optimized to strictly contain the production-ready architecture. Previous development iterations involving Tkinter-based GUIs and placeholder logic have been cleaned up.

- **`backend/`**: Main FastAPI routers, websocket handlers, background tasks, and application registry.
- **`frontend/`**: The modern web-based monitoring interface deployed by the FastApi server.
- **`dashboard_client/`**: External API integration layer to connect and sync with `attendance-dashboard`.
- **`database/`**: Internal database schemas and connection wrappers.
- **`attendance/`**: Policy managers and threshold logic.

---

### Starting the Client

Ensure you have your virtual environment running and all dependencies installed, then deploy the server:

```bash
uvicorn backend.app:app --host 0.0.0.0 --port 8000
```
This will automatically seed the database and expose the web dashboard on `http://localhost:8000`.
