from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from database import database
from backend.services.camera_manager import camera_manager
import time

router = APIRouter()

class StudentRegistration(BaseModel):
    id: str
    name: str
    is_bus_student: bool = False

@router.post("/register")
async def register_student(student: StudentRegistration):
    if not camera_manager.camera:
        camera_manager.start_engine()
        time.sleep(1) # Wait for camera to warm up
    
    encodings_gathered = []
    samples_target = 5
    attempts = 0
    max_attempts = 30
    
    while len(encodings_gathered) < samples_target and attempts < max_attempts:
        frame = camera_manager.latest_frame
        if frame is None:
            attempts += 1
            time.sleep(0.1)
            continue
            
        encs = camera_manager.face_engine.get_encodings(frame)
        if len(encs) > 0:
            encodings_gathered.append(encs[0])
            time.sleep(0.5)
            
        attempts += 1
        
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
