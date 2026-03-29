# Raspberry Pi Client Integration Guide

This document specifies the communication protocol between the Raspberry Pi (Client) and the Attendance Dashboard (Server) for the **Session Control & Command Dispatch** system.

---

## 1. Authentication & Identity
The server identifies your device using a unique `device_id`. Ensure your client program knows its own ID (e.g., `PI-01`) as it appears in the **Dashboard Devices List**.

---

## 2. Command Polling API
Since the server cannot "push" commands to the Pi, the Pi must **poll** the server at regular intervals (e.g., every 5 seconds).

### Endpoint
`GET /api/device/command/<device_id>`

### Example Request
```http
GET http://your-server-address/api/device/command/PI-01
```

### Response Format (JSON)
The server returns the current instruction for the device:

```json
{
  "device_id": "PI-01",
  "command": "start_camera",
  "timestamp": "2026-03-30 00:05:00"
}
```

---

## 3. Command Definitions
The `command` field in the response will contain one of the following strings:

| Command | Action to perform on Pi |
| :--- | :--- |
| **`start_camera`** | Open the camera and begin the face recognition process. |
| **`stop_camera`** | Gracefully shut down the camera and stop recognition. |
| **`idle`** | The system is waiting. Maintain current state (usually camera off). |

> [!TIP]
> **Idempotency**: Your client should track its own current state. If you receive `start_camera` but the camera is **already running**, you should do nothing.

---

## 4. Connection State Persistence
The Dashboard only allows session control if the device is marked as **"Connected"**.

- The server considers a device connected if a record exists in the `devices` table with `connection_status = 'connected'`.
- You must ensure your client registration/heartbeat process keeps this record active.

---

## 5. Implementation Logic (Pseudocode)

```python
import time
import requests

DEVICE_ID = "PI-01"
SERVER_URL = "http://your-server-address"
camera_active = False

def poll_command():
    global camera_active
    try:
        response = requests.get(f"{SERVER_URL}/api/device/command/{DEVICE_ID}")
        if response.status_code == 200:
            data = response.json()
            command = data.get("command")

            if command == "start_camera" and not camera_active:
                start_recognition_system()
                camera_active = True
            elif command == "stop_camera" and camera_active:
                stop_recognition_system()
                camera_active = False
                
    except Exception as e:
        print(f"Connection Error: {e}")

# Main loop
while True:
    poll_command()
    time.sleep(5) # Poll every 5 seconds
```

---

## 6. Success Indicators
- **Dashboard Start**: Sends `start_camera` → Pi starts camera → Dashboard shows `ACTIVE`.
- **Dashboard Stop**: Sends `stop_camera` → Pi stops camera → Dashboard shows `STOPPED`.
