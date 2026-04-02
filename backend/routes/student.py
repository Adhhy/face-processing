from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from database import database
from backend.services.camera_manager import camera_manager
import time
import asyncio
from utils.logger import logger

router = APIRouter()

class StudentRegistration(BaseModel):
    id: str
    name: str
    is_bus_student: bool = False

@router.post("/register")
async def register_student(student: StudentRegistration):
    if not camera_manager.camera:
        camera_manager.start_engine()
        # Wait for camera to warm up and buffer to clear
        await asyncio.sleep(2.0) 
    
    encodings_gathered = []
    samples_target = 5
    attempts = 0
    max_attempts = 100 # Gain more flexibility for slow cameras
    
    logger.info(f"Starting registration for {student.name} ({student.id}). Targets: {samples_target} samples.")
    
    while len(encodings_gathered) < samples_target and attempts < max_attempts:
        frame = camera_manager.latest_frame
        if frame is None:
            attempts += 1
            await asyncio.sleep(0.1)
            continue
            
        encs = camera_manager.face_engine.get_encodings(frame)
        if len(encs) > 0:
            encodings_gathered.append(encs[0])
            logger.info(f"Captured sample {len(encodings_gathered)}/{samples_target} for {student.name}")
            # Brief pause to ensure we capture a slightly different pose
            await asyncio.sleep(0.4)
            
        attempts += 1
        
    if len(encodings_gathered) < samples_target:
        logger.warning(f"Registration for {student.name} timed out with only {len(encodings_gathered)} samples.")
        if len(encodings_gathered) == 0:
            raise HTTPException(status_code=400, detail="Failed to detect face. Registration incomplete.")
        
    try:
        database.insert_student(student.id, student.name, 1 if student.is_bus_student else 0)
        database.insert_encodings(student.id, encodings_gathered)
        
        # Update engine memory (assuming engine is running)
        if camera_manager.face_engine:
            camera_manager.face_engine.known_encodings.extend(encodings_gathered)
            camera_manager.face_engine.known_names.extend([student.name] * len(encodings_gathered))
            camera_manager.face_engine.known_ids.extend([student.id] * len(encodings_gathered))
            
        camera_manager.stop_engine()
        return {"status": "success", "message": f"Registered {student.name} successfully!"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
