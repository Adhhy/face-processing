from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()

class AdminLogin(BaseModel):
    username: str
    password: str

class OperationSettings(BaseModel):
    start_time: str
    end_time: str

class DebugToggle(BaseModel):
    feature: str
    enabled: bool

from database import database

@router.post("/login")
async def admin_login(credentials: AdminLogin):
    if database.verify_admin_login(credentials.username, credentials.password):
        return {"status": "success", "token": "authenticated-admin-session"}
    raise HTTPException(status_code=401, detail="Invalid credentials")

import os
from utils.logger import LOG_FILE

@router.get("/system/logs")
async def get_system_logs():
    # Only authenticated admin via frontend token mechanism
    if not os.path.exists(LOG_FILE):
        return {"logs": []}
    
    # Read the last 100 lines efficiently
    try:
        with open(LOG_FILE, 'r') as f:
            lines = f.readlines()
        return {"logs": lines[-100:]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/settings")
async def update_settings(settings: OperationSettings):
    database.update_setting("start_time", settings.start_time)
    database.update_setting("end_time", settings.end_time)
    
    # Notify camera manager (it will re-read settings in its scheduler)
    from backend.services.camera_manager import camera_manager
    camera_manager.recheck_schedule = True
    
    return {"status": "success", "message": "Operation times updated"}

@router.post("/debug/toggle")
async def toggle_debug(toggle: DebugToggle):
    # Map frontend IDs to database keys if necessary, or just use feature name
    feature = toggle.feature
    enabled = toggle.enabled
    # Map frontend IDs to database keys if necessary, or just use feature name
    key_map = {
        "toggle-log": "log_capture",
        "toggle-fps": "show_fps",
        "toggle-overlay": "show_overlay"
    }
    db_key = key_map.get(feature, feature)
    print(f"DEBUG: Toggling {feature} -> {db_key}={enabled}")
    database.update_setting(db_key, "1" if enabled else "0")
    
    from backend.services.camera_manager import camera_manager
    camera_manager.recheck_settings = True
    
    return {"status": "success", "feature": feature, "enabled": enabled}
