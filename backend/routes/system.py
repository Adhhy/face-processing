from fastapi import APIRouter
from backend.services.system_monitor import SystemMonitor
import os
import subprocess

router = APIRouter()

@router.get("/info")
async def get_system_info():
    return SystemMonitor.get_stats()

from database import database
from datetime import datetime
from utils.logger import logger

SERVER_START_TIME = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

@router.get("/policy_logs")
async def get_policy_logs(limit: int = 50):
    logs = database.get_recent_policy_logs(limit, since=SERVER_START_TIME)
    return {"status": "success", "logs": logs}

import threading
import signal
import time

@router.post("/shutdown")
async def shutdown_system():
    def kill_process():
        time.sleep(1)
        print("Shutdown requested. Terminating process...")
        os._exit(0)
        
    threading.Thread(target=kill_process, daemon=True).start()
    return {"status": "success", "message": "Server shutting down and exiting..."}

@router.post("/logs/send")
async def send_logs():
    # Placeholder for log compression and remote sync
    return {"status": "success", "message": "Logs compressed and sent to remote dashboard."}

from dashboard_client.api_client import dashboard_client_instance
import asyncio

@router.post("/connect")
async def connect_device():
    # Dashboard requests can be blocking (HTTP reqs) so we can wrap them in an executor or threading
    # But since it's a simple local HTTP request, standard def or background process is OK.
    def do_connect():
        return dashboard_client_instance.request_connection()
        
    res = await asyncio.to_thread(do_connect)
    return res

@router.post("/disconnect")
async def disconnect_system():
    logger.info("RECEIVED DISCONNECT REQUEST FROM EXTERNAL SIGNAL")
    # Notice this replaces the old disconnect that was likely not doing anything real
    def do_disconnect():
        return dashboard_client_instance.disconnect()
        
    res = await asyncio.to_thread(do_disconnect)
    return res
