import os
import sys
import io
import json
import asyncio
import threading
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, BackgroundTasks, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Project Root Configuration
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from config import (
    PLATFORMS,
    ENABLE_UPLOAD,
    ASPECT_RATIO,
    CHARACTER,
    THEME,
    DURATION_TARGET,
    TTS_VOICE,
    TTS_RATE,
    INDICF5_SPEED,
    RANDOM_EFFECTS,
    MADE_FOR_KIDS,
)
from pipeline.pre_run_settings import load_config_state, save_config_state
from pipeline.theme_selector import _load_themes
from pipeline.rotation import resolve_video_mode, resolve_duration

# Initialize FastAPI App
app = FastAPI(title="Kids Shorts Factory Studio", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Output directory setup
OUTPUTS_DIR = PROJECT_ROOT / "outputs"
OUTPUTS_DIR.mkdir(exist_ok=True)

# WebSocket Connection Manager for Real-time Streaming Logs
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        for connection in list(self.active_connections):
            try:
                await connection.send_text(message)
            except Exception:
                self.disconnect(connection)

manager = ConnectionManager()

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Thread-safe Log Interceptor that forwards sys.stdout to WebSockets
class LogBroadcastStream(io.StringIO):
    def __init__(self, original_stdout):
        super().__init__()
        self.original_stdout = original_stdout
        self.loop = None

    def set_loop(self, loop):
        self.loop = loop

    def write(self, s):
        try:
            self.original_stdout.write(s)
            self.original_stdout.flush()
        except UnicodeEncodeError:
            try:
                clean_s = s.encode("ascii", "replace").decode("ascii")
                self.original_stdout.write(clean_s)
                self.original_stdout.flush()
            except Exception:
                pass
        except Exception:
            pass

        if s.strip() and self.loop and not self.loop.is_closed():
            try:
                asyncio.run_coroutine_threadsafe(manager.broadcast(s.strip()), self.loop)
            except Exception:
                pass

    def flush(self):
        try:
            self.original_stdout.flush()
        except Exception:
            pass

# Redirect stdout
log_stream = LogBroadcastStream(sys.stdout)
sys.stdout = log_stream

# Models
class GenerateRequest(BaseModel):
    theme: Optional[str] = "auto"
    video_mode: Optional[str] = "auto"
    aspect_ratio: Optional[str] = "9:16"
    duration: Optional[str] = "auto"
    indicf5_speed: Optional[float] = 1.25
    overlay_enabled: Optional[bool] = True
    overlay_transparency: Optional[int] = 10
    caption_style: Optional[str] = "bottom_bold"
    auto_upload: Optional[bool] = False

class UploadRequest(BaseModel):
    platform: str
    video_path: str
    script: Optional[str] = None
    theme: Optional[str] = None
    character: Optional[str] = None

# Routes
@app.on_event("startup")
async def startup_event():
    log_stream.set_loop(asyncio.get_running_loop())
    print("[SERVER] Kids Shorts Factory Studio Web Server Started.")

@app.websocket("/ws/logs")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

@app.get("/api/config")
async def get_config():
    saved_state = load_config_state()
    themes = _load_themes()
    characters = sorted(list({t["character"] for t in themes if "character" in t}))
    return {
        "config": saved_state,
        "themes": themes,
        "characters": characters,
        "platforms": PLATFORMS,
    }

@app.post("/api/config")
async def update_config(config_data: Dict[str, Any]):
    save_config_state(config_data)
    return {"status": "success", "config": load_config_state()}

@app.get("/api/videos")
async def get_videos():
    video_files = []
    if OUTPUTS_DIR.exists():
        for f in OUTPUTS_DIR.glob("*.mp4"):
            stat = f.stat()
            size_mb = round(stat.st_size / (1024 * 1024), 2)
            mod_time = datetime.fromtimestamp(stat.st_mtime).strftime("%d/%m/%Y %I:%M %p")
            video_files.append({
                "name": f.name,
                "path": str(f.resolve()),
                "size_mb": size_mb,
                "modified": mod_time,
                "timestamp": stat.st_mtime
            })
    video_files.sort(key=lambda x: x["timestamp"], reverse=True)
    return {"videos": video_files}

def _run_pipeline_generation(req: GenerateRequest) -> Dict[str, Any]:
    import main as m
    from main import (
        _merge_settings,
        _select_dynamic_job,
        _determine_voice_for_theme,
        _generate_script,
        _render_video,
        _accept_video,
        pick_random_effects,
        spoken_text,
        get_script_metadata,
    )

    settings = load_config_state()
    settings["aspect_ratio"] = req.aspect_ratio or "9:16"
    settings["video_mode"] = req.video_mode or "auto"
    settings["duration"] = req.duration or "auto"
    settings["duration_target"] = req.duration or "auto"
    settings["indicf5_speed"] = req.indicf5_speed or 1.25
    settings["overlay_enabled"] = req.overlay_enabled
    settings["overlay_transparency"] = req.overlay_transparency
    settings["caption_style"] = req.caption_style or "bottom_bold"

    save_config_state(settings)

    resolved_mode = resolve_video_mode(settings.get("video_mode", "auto"))
    settings["video_mode"] = resolved_mode

    resolved_duration = resolve_duration(
        settings.get("duration", settings.get("duration_target", "auto")),
        resolved_mode,
    )
    settings["duration"] = resolved_duration
    settings["duration_target"] = resolved_duration

    effects = pick_random_effects()
    effects["caption_style"] = settings["caption_style"]
    settings["effects"] = effects

    settings = _merge_settings(settings)

    char_override = None if req.theme == "auto" else req.theme

    theme_config = _select_dynamic_job(
        settings,
        character_override=char_override,
        duration_override=settings["duration_target"],
    )
    if not theme_config:
        raise RuntimeError("Theme selection failed.")

    selected_voice = _determine_voice_for_theme(theme_config)
    settings["tts_voice"] = selected_voice

    script = _generate_script(settings)
    audio_path, boundaries_path, video_path, video_info = _render_video(script, settings)

    video_path_obj = Path(video_path)
    video_filename = video_path_obj.name

    metadata_info = get_script_metadata(script)
    theme_val = metadata_info.get("theme") or theme_config.get("theme")
    char_val = metadata_info.get("character") or theme_config.get("character")

    upload_result = None
    if req.auto_upload:
        upload_result = _accept_video(script, video_path, enable_upload_override=True, settings=settings)

    return {
        "success": True,
        "video_filename": video_filename,
        "video_path": str(video_path),
        "script": spoken_text(script),
        "theme": theme_val,
        "character": char_val,
        "upload_result": upload_result,
    }

@app.post("/api/generate")
async def generate_video(req: GenerateRequest):
    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, _run_pipeline_generation, req)
        return result
    except Exception as e:
        print(f"[ERROR] Pipeline generation error: {e}")
        return {"success": False, "error": str(e)}

@app.post("/api/upload")
async def upload_video(req: UploadRequest):
    try:
        v_path = Path(req.video_path)
        if not v_path.is_file():
            raise HTTPException(status_code=404, detail="Video file not found")

        if req.platform.lower() == "youtube":
            from uploaders.youtube import api_uploader as yt
            res = yt.upload(
                str(v_path),
                script=req.script,
                theme=req.theme,
                character=req.character,
            )
            return {"success": True, "platform": "youtube", "url": res.get("url") if isinstance(res, dict) else str(res)}

        elif req.platform.lower() == "facebook":
            from uploaders.facebook import graph_api as fb
            res = fb.upload(
                str(v_path),
                script=req.script,
                theme=req.theme,
                character=req.character,
            )
            return {"success": True, "platform": "facebook", "url": res.get("url") if isinstance(res, dict) else str(res)}

        else:
            raise HTTPException(status_code=400, detail="Unsupported platform")

    except Exception as e:
        print(f"[ERROR] Upload error: {e}")
        return {"success": False, "error": str(e)}

# Static File Mounts
app.mount("/outputs", StaticFiles(directory=str(OUTPUTS_DIR)), name="outputs")
app.mount("/", StaticFiles(directory=str(PROJECT_ROOT / "web"), html=True), name="web")

if __name__ == "__main__":
    import uvicorn
    import socket

    def get_local_ip():
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"

    local_ip = get_local_ip()
    port = 8000
    print("\n" + "=" * 60)
    print("    [STUDIO] KIDS SHORTS FACTORY STUDIO WEB APP")
    print(f"    [PC URL]    http://localhost:{port}")
    print(f"    [PHONE URL] http://{local_ip}:{port}")
    print("=" * 60 + "\n")

    uvicorn.run("web_server:app", host="0.0.0.0", port=port, reload=False)
