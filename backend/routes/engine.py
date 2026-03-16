from fastapi import APIRouter
from backend.services.camera_manager import camera_manager

router = APIRouter()

@router.post("/start")
async def start_engine():
    try:
        camera_manager.start_engine()
        camera_manager.recognition_active = True
        return {"status": "success", "message": "Engine started"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@router.post("/stop")
async def stop_engine():
    try:
        camera_manager.stop_engine()
        return {"status": "success", "message": "Engine stopped"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@router.post("/toggle_recognition")
async def toggle_recognition(active: bool):
    camera_manager.recognition_active = active
    return {"status": "success", "recognition_active": active}
