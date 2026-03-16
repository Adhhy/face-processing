from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import json
from backend.services.camera_manager import camera_manager
from backend.services.system_monitor import SystemMonitor
from backend.routes import engine, student, system, admin
from contextlib import asynccontextmanager
from database import database
from attendance.policy_manager import PolicyManager
from utils.logger import logger

# Global policy manager instance
policy_manager = PolicyManager()

# Initialize database tables
database.init_db()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start the policy manager on startup
    logger.info("FastAPI server started")
    policy_manager.start()
    yield
    # Stop the policy manager on shutdown
    logger.info("System shutting down")
    policy_manager.stop()

app = FastAPI(title="Face Recognition Attendance Dashboard", lifespan=lifespan)

# CORS for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(engine.router, prefix="/api/engine", tags=["engine"])
app.include_router(student.router, prefix="/api/student", tags=["student"])
app.include_router(system.router, prefix="/api/system", tags=["system"])
app.include_router(admin.router, prefix="/api/admin", tags=["admin"])

# Serve static files
app.mount("/static", StaticFiles(directory="frontend/static"), name="static")

@app.get("/")
async def read_index():
    from fastapi.responses import FileResponse
    return FileResponse("frontend/index.html")

# WebSocket for real-time data
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    camera_manager.clients.add(websocket)
    try:
        while True:
            # Send system stats every 2 seconds
            stats = SystemMonitor.get_stats()
            frame = camera_manager.get_encoded_frame()
            
            # Check for events
            events = []
            while not camera_manager.event_queue.empty():
                events.append(camera_manager.event_queue.get())
            
            from dashboard_client.api_client import dashboard_client_instance

            payload = {
                "stats": stats,
                "frame": frame,
                "events": events,
                "engine_running": camera_manager.is_running(),
                "camera_ok": getattr(camera_manager, 'camera_ok', True),
                "connection_status": dashboard_client_instance.connection_status,
                "device_key": dashboard_client_instance.device_key
            }
            
            await websocket.send_text(json.dumps(payload))
            await asyncio.sleep(0.1) # 10 FPS for the WS stream
            
    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
        camera_manager.clients.remove(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        camera_manager.clients.remove(websocket)
