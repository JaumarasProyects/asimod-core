import threading
import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from fastapi.middleware.cors import CORSMiddleware

class ChatRequest(BaseModel):
    text: str
    model: Optional[str] = None

class APIServer:
    """
    Servidor API para exponer las funcionalidades de ASIMOD Core.
    """
    def __init__(self, chat_service, port=8000, host="0.0.0.0"):
        self.chat_service = chat_service
        self.port = port
        self.host = host
        self.app = FastAPI(title="ASIMOD Core API")
        self._setup_routes()
        self._setup_cors()
        self._thread = None

    def _setup_cors(self):
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    def _setup_routes(self):
        @self.app.get("/")
        async def root():
            return {"status": "online", "message": "ASIMOD Core API is active"}

        @self.app.get("/v1/status")
        async def get_status():
            return {
                "provider": self.chat_service.config.get("last_provider"),
                "model": self.chat_service.config.get("last_model"),
                "voice_provider": self.chat_service.config.get("voice_provider"),
                "stt_provider": self.chat_service.config.get("stt_provider")
            }

        @self.app.get("/v1/history")
        async def get_history():
            history = self.chat_service.get_history()
            return [{"sender": msg.sender, "content": msg.content} for msg in history]

        @self.app.post("/v1/audio/pause")
        async def audio_pause():
            """Silencia el micrófono (llamado desde Unity/Unreal)."""
            if self.chat_service.stt_service:
                self.chat_service.stt_service.pause_capture()
                return {"status": "success", "message": "Microphone paused"}
            return {"status": "error", "message": "STT Service not available"}

        @self.app.post("/v1/audio/resume")
        async def audio_resume():
            """Reactiva el micrófono con delay de seguridad (llamado desde Unity/Unreal)."""
            if self.chat_service.stt_service:
                self.chat_service.stt_service.resume_capture()
                return {"status": "success", "message": "Microphone resuming with safety delay"}
            return {"status": "error", "message": "STT Service not available"}

        @self.app.post("/v1/chat")
        async def chat(request: ChatRequest):
            try:
                # El servicio de chat ya maneja historial, LLM y audio
                response = self.chat_service.send_message(request.text, model=request.model)
                return {
                    "response": response,
                    "status": "success"
                }
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))

    def run(self, blocking=False):
        """Inicia el servidor. Si blocking=True, lo hace en el hilo principal."""
        def start_uvicorn():
            uvicorn.run(self.app, host=self.host, port=self.port, log_level="info")

        if blocking:
            print(f"API Server (Headless) started on http://{self.host}:{self.port}")
            start_uvicorn()
        else:
            self._thread = threading.Thread(target=start_uvicorn, daemon=True)
            self._thread.start()
            print(f"API Server (Background) started on http://{self.host}:{self.port}")
