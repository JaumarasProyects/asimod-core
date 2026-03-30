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
        def get_status():
            # Determinar qué voz y motor se usaría realmente (Personaje > Global)
            char_voice = self.chat_service.memory.data.get("voice_id")
            char_provider = self.chat_service.memory.data.get("voice_provider")
            
            global_provider = self.chat_service.config.get("voice_provider", "Edge TTS")
            global_voice = self.chat_service.config.get("voice_id", "es-ES-AlvaroNeural")

            actual_voice = char_voice if (char_voice and char_voice != "None" and char_voice.strip() != "") else global_voice
            actual_provider = char_provider if (char_provider and char_provider != "None" and char_provider != "") else global_provider
            
            return {
                "provider": self.chat_service.config.get("last_provider", "Ollama"),
                "model": self.chat_service.config.get("last_model", ""),
                "active_thread": self.chat_service.memory.active_thread,
                "voice_provider": actual_provider if actual_provider and actual_provider != "None" else "None",
                "voice_mode": self.chat_service.config.get("voice_mode", "autoplay"),
                "voice_id": actual_voice if actual_voice else "es-ES-AlvaroNeural",
                "stt_provider": self.chat_service.config.get("stt_provider", "None"),
                "stt_mode": self.chat_service.config.get("stt_mode", "OFF")
            }

        # --- MEMORY MANAGEMENT ---

        @self.app.get("/v1/memories")
        def list_memories():
            """Lista todos los hilos de conversación guardados."""
            return {"memories": self.chat_service.memory.list_threads()}

        @self.app.get("/v1/memories/current")
        def get_current_memory():
            """Retorna la configuración y el historial de la memoria activa."""
            return {
                "thread_id": self.chat_service.memory.active_thread,
                "data": self.chat_service.memory.data
            }

        @self.app.post("/v1/memories")
        def switch_or_create_memory(data: dict):
            """
            Cambia a una memoria o crea una nueva.
            Payload: {"thread_id": "New", "name": "...", "personality": "...", "history": "...", "voice_id": "..."}
            """
            target = data.get("thread_id", "None")
            name = data.get("name")
            pers = data.get("personality")
            hist = data.get("history")
            voice = data.get("voice_id")
            v_prov = data.get("voice_provider")

            if target == "New":
                new_id = self.chat_service.memory.create_new_thread()
                if name or pers or hist or voice or v_prov:
                    self.chat_service.memory.update_profile(name=name, personality=pers, history=hist, voice_id=voice, voice_provider=v_prov)
                self.chat_service.config.set("active_thread", new_id)
                return {"status": "success", "thread_id": new_id}
            else:
                self.chat_service.memory.load_thread(target)
                self.chat_service.config.set("active_thread", target)
                return {"status": "success", "thread_id": target}

        @self.app.patch("/v1/memories/profile")
        def update_memory_profile(data: dict):
            """
            Actualiza el perfil (nombre, personalidad, historia, voz, motor) de la memoria activa.
            Payload: {"name": "...", "personality": "...", "character_history": "...", "voice_id": "...", "voice_provider": "..."}
            """
            self.chat_service.memory.update_profile(
                name=data.get("name"),
                personality=data.get("personality"),
                history=data.get("character_history"),
                voice_id=data.get("voice_id"),
                voice_provider=data.get("voice_provider")
            )
            return {"status": "success", "message": "Memory profile updated"}

        @self.app.get("/v1/history")
        async def get_history():
            history = self.chat_service.get_history()
            return [{"sender": msg.sender, "content": msg.content} for msg in history]

        @self.app.post("/v1/audio/pause")
        def audio_pause():
            """Silencia el micrófono (llamado desde Unity/Unreal)."""
            if self.chat_service.stt_service:
                self.chat_service.stt_service.pause_capture()
                return {"status": "success", "message": "Microphone paused"}
            return {"status": "error", "message": "STT Service not available"}

        @self.app.post("/v1/audio/resume")
        def audio_resume():
            """Reactiva el micrófono con delay de seguridad (llamado desde Unity/Unreal)."""
            if self.chat_service.stt_service:
                self.chat_service.stt_service.resume_capture()
                return {"status": "success", "message": "Microphone resuming with safety delay"}
            return {"status": "error", "message": "STT Service not available"}

        @self.app.post("/v1/audio/stop")
        def audio_stop():
            """Detiene el audio actual y reanuda el micro (llamado desde Unity/Unreal)."""
            self.chat_service.voice_service.stop_audio()
            return {"status": "success", "message": "Audio stopped remotely"}

        # --- NUEVOS ENDPOINTS DE CONFIGURACIÓN ---

        @self.app.get("/v1/providers")
        def list_providers():
            """Lista todos los proveedores de LLM disponibles."""
            return {"providers": self.chat_service.get_providers_list()}

        @self.app.get("/v1/voice_providers")
        def list_voice_providers():
            """Lista todos los proveedores de Voz disponibles."""
            return {"voice_providers": self.chat_service.get_voice_providers_list()}

        @self.app.get("/v1/models")
        def list_models(provider: Optional[str] = None):
            """Lista los modelos del proveedor actual o de uno específico."""
            if provider:
                # Cambiar temporalmente de adaptador para listar si es necesario
                self.chat_service.switch_provider(provider)
            return {"models": self.chat_service.get_available_models()}

        @self.app.get("/v1/voices")
        def list_voices():
            """Lista todas las voces disponibles para el motor de TTS activo."""
            return {"voices": self.chat_service.voice_service.get_available_voices()}

        @self.app.post("/v1/config")
        def update_config(config_data: dict):
            """
            Actualiza la configuración (provider, model, voice_id, etc) vía API.
            Formato: {"last_provider": "Ollama", "voice_id": "8", ...}
            """
            for key, value in config_data.items():
                self.chat_service.config.set(key, value)
            
            # Notificar cambios a los servicios
            if "last_provider" in config_data:
                self.chat_service.switch_provider(config_data["last_provider"])
            if "voice_provider" in config_data:
                self.chat_service.voice_service.update_provider()
            if "stt_provider" in config_data or "stt_mode" in config_data:
                if self.chat_service.stt_service:
                    self.chat_service.stt_service.update_adapter()
                
            return {"status": "success", "message": "Configuration updated"}

        @self.app.post("/v1/chat")
        def chat(request: ChatRequest):
            try:
                # El servicio de chat ahora devuelve un dict con {response, clean_text, emojis}
                result = self.chat_service.send_message(request.text, model=request.model)
                return {
                    "response": result["response"],
                    "clean_text": result["clean_text"],
                    "emojis": result["emojis"],
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
