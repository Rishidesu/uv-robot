from fastapi import FastAPI, APIRouter, WebSocket, WebSocketDisconnect
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
import asyncio
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Dict, Optional
import uuid
from datetime import datetime, timedelta
import json

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Create the main app without a prefix
app = FastAPI()

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# Robot state management
class RobotState:
    def __init__(self):
        self.status = "idle"  # idle, mopping, spraying, uv_disinfecting, paused
        self.progress = 0
        self.is_cleaning = False
        self.obstacle_detected = False
        self.start_time = None
        self.current_mode = None
        self.pause_reason = None
        self.connected_clients = set()
    
    def to_dict(self):
        return {
            "status": self.status,
            "progress": self.progress,
            "is_cleaning": self.is_cleaning,
            "obstacle_detected": self.obstacle_detected,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "current_mode": self.current_mode,
            "pause_reason": self.pause_reason
        }

robot_state = RobotState()

# Models
class CleaningLog(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    start_time: datetime
    end_time: Optional[datetime] = None
    duration: Optional[int] = None  # in seconds
    mode: str
    status: str = "completed"  # completed, interrupted
    progress: int = 0

class CleaningLogCreate(BaseModel):
    mode: str

class RobotCommand(BaseModel):
    command: str  # start, stop, pause, resume
    mode: Optional[str] = "full_clean"  # full_clean, mop_only, spray_only, uv_only

class RobotStatusUpdate(BaseModel):
    robot_id: str
    status: str
    progress: int
    is_cleaning: bool
    obstacle_detected: bool
    current_mode: Optional[str] = None
    uptime: Optional[int] = None
    sensors: Optional[Dict] = None

# WebSocket manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def send_personal_message(self, message: str, websocket: WebSocket):
        try:
            await websocket.send_text(message)
        except:
            self.disconnect(websocket)

    async def broadcast(self, message: dict):
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_text(json.dumps(message))
            except:
                disconnected.append(connection)
        
        # Remove disconnected clients
        for conn in disconnected:
            self.disconnect(conn)

manager = ConnectionManager()

# Robot simulation task
async def robot_simulation():
    """Simulate robot cleaning cycle and obstacle detection"""
    while True:
        if robot_state.is_cleaning and robot_state.status != "paused":
            # Simulate progress
            if robot_state.progress < 100:
                robot_state.progress += 2  # 2% every 5 seconds = ~4 minutes total
                
                # Simulate mode changes during cleaning cycle
                if robot_state.progress < 30:
                    robot_state.status = "mopping"
                elif robot_state.progress < 60:
                    robot_state.status = "spraying" 
                elif robot_state.progress < 90:
                    robot_state.status = "uv_disinfecting"
                else:
                    robot_state.status = "mopping"  # Final mop
                
                # Random obstacle detection (10% chance every 5 seconds)
                import random
                if random.random() < 0.1 and not robot_state.obstacle_detected:
                    robot_state.obstacle_detected = True
                    robot_state.status = "paused"
                    robot_state.pause_reason = "obstacle_detected"
                    await manager.broadcast({
                        "type": "alert",
                        "message": "Obstacle detected! Robot paused for safety.",
                        "robot_state": robot_state.to_dict()
                    })
                    
                    # Auto-resume after 3 seconds
                    await asyncio.sleep(3)
                    robot_state.obstacle_detected = False
                    robot_state.pause_reason = None
                    await manager.broadcast({
                        "type": "info", 
                        "message": "Path clear. Resuming cleaning...",
                        "robot_state": robot_state.to_dict()
                    })
                
                await manager.broadcast({
                    "type": "status_update",
                    "robot_state": robot_state.to_dict()
                })
            else:
                # Cleaning complete
                robot_state.is_cleaning = False
                robot_state.status = "idle"
                robot_state.progress = 100
                end_time = datetime.utcnow()
                duration = int((end_time - robot_state.start_time).total_seconds())
                
                # Save cleaning log
                log = CleaningLog(
                    start_time=robot_state.start_time,
                    end_time=end_time,
                    duration=duration,
                    mode=robot_state.current_mode,
                    status="completed",
                    progress=100
                )
                await db.cleaning_logs.insert_one(log.dict())
                
                await manager.broadcast({
                    "type": "cleaning_complete",
                    "message": "Cleaning cycle completed successfully!",
                    "robot_state": robot_state.to_dict(),
                    "duration": duration
                })
                
        await asyncio.sleep(5)  # Update every 5 seconds

# Start simulation task
@app.on_event("startup")
async def startup_event():
    asyncio.create_task(robot_simulation())

# WebSocket endpoint
@app.websocket("/api/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        # Send initial state
        await websocket.send_text(json.dumps({
            "type": "status_update",
            "robot_state": robot_state.to_dict()
        }))
        
        while True:
            data = await websocket.receive_text()
            # Handle any websocket commands if needed
            
    except WebSocketDisconnect:
        manager.disconnect(websocket)

# API Routes
@api_router.get("/")
async def root():
    return {"message": "Robot Control API"}

@api_router.post("/robot/command")
async def send_robot_command(command: RobotCommand):
    if command.command == "start":
        if not robot_state.is_cleaning:
            robot_state.is_cleaning = True
            robot_state.status = "mopping"
            robot_state.progress = 0
            robot_state.start_time = datetime.utcnow()
            robot_state.current_mode = command.mode
            
            await manager.broadcast({
                "type": "info",
                "message": f"Starting {command.mode.replace('_', ' ')} cycle...",
                "robot_state": robot_state.to_dict()
            })
            
            return {"success": True, "message": "Cleaning started", "robot_state": robot_state.to_dict()}
        else:
            return {"success": False, "message": "Robot is already cleaning"}
            
    elif command.command == "stop":
        if robot_state.is_cleaning:
            robot_state.is_cleaning = False
            robot_state.status = "idle"
            end_time = datetime.utcnow()
            duration = int((end_time - robot_state.start_time).total_seconds())
            
            # Save interrupted cleaning log
            log = CleaningLog(
                start_time=robot_state.start_time,
                end_time=end_time,
                duration=duration,
                mode=robot_state.current_mode,
                status="interrupted",
                progress=robot_state.progress
            )
            await db.cleaning_logs.insert_one(log.dict())
            
            robot_state.progress = 0
            robot_state.start_time = None
            robot_state.current_mode = None
            
            await manager.broadcast({
                "type": "info",
                "message": "Cleaning stopped by user",
                "robot_state": robot_state.to_dict()
            })
            
            return {"success": True, "message": "Cleaning stopped", "robot_state": robot_state.to_dict()}
        else:
            return {"success": False, "message": "Robot is not cleaning"}
    
    elif command.command == "pause":
        if robot_state.is_cleaning and robot_state.status != "paused":
            robot_state.status = "paused"
            robot_state.pause_reason = "user_request"
            
            await manager.broadcast({
                "type": "info",
                "message": "Cleaning paused by user",
                "robot_state": robot_state.to_dict()
            })
            
            return {"success": True, "message": "Cleaning paused", "robot_state": robot_state.to_dict()}
        else:
            return {"success": False, "message": "Cannot pause robot"}
            
    elif command.command == "resume":
        if robot_state.is_cleaning and robot_state.status == "paused":
            robot_state.status = "mopping"  # Resume with appropriate status
            robot_state.pause_reason = None
            
            await manager.broadcast({
                "type": "info",
                "message": "Cleaning resumed",
                "robot_state": robot_state.to_dict()
            })
            
            return {"success": True, "message": "Cleaning resumed", "robot_state": robot_state.to_dict()}
        else:
            return {"success": False, "message": "Cannot resume robot"}

@api_router.get("/robot/status")
async def get_robot_status():
    return {"robot_state": robot_state.to_dict()}

@api_router.get("/cleaning-logs", response_model=List[CleaningLog])
async def get_cleaning_logs():
    logs = await db.cleaning_logs.find().sort("start_time", -1).to_list(100)
    return [CleaningLog(**log) for log in logs]

# Include the router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()