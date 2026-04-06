import threading
import uvicorn
import queue
import time
import os

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from typing import Optional
from fastapi.middleware.cors import CORSMiddleware

from core.factories.messaging_factory import MessagingFactory


class ChatRequest(BaseModel):
    text: str
    model: Optional[str] = None
    silent: Optional[bool] = False
    max_tokens: Optional[int] = None
    temperature: Optional[float] = None

class SpeakRequest(BaseModel):
            text: str
            voice_id: Optional[str] = None
            voice_provider: Optional[str] = None
class APIServer:
    """
    Servidor API para exponer las funcionalidades de ASIMOD Core.
    """

    def __init__(self, chat_service, port=8000, host="0.0.0.0"):
        self.chat_service = chat_service
        self.port = port
        self.host = host
        self.app = FastAPI(title="ASIMOD Core API")

        # Cola y estado STT para Unity / integraciones externas
        self.stt_results = queue.Queue()
        self.last_stt_text = ""
        self.last_stt_timestamp = 0.0

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

    # =========================================================
    # STT QUEUE / BUFFER
    # =========================================================
    def push_stt_result(self, text: str):
        if not text:
            return

        text = text.strip()
        if not text:
            return

        ts = time.time()
        self.last_stt_text = text
        self.last_stt_timestamp = ts

        self.stt_results.put({
            "text": text,
            "timestamp": ts
        })

        print(f"[API][STT] Queued transcription: {text}")

    # =========================================================
    # ROUTES
    # =========================================================
    def _setup_routes(self):
        @self.app.get("/")
        async def root():
            return {"status": "online", "message": "ASIMOD Core API is active"}

        @self.app.get("/v1/status")
        def get_status():
            # Determinar qué voz real se usaría (Personaje > Global)
            char_voice = self.chat_service.memory.data.get("voice_id")
            char_provider = self.chat_service.memory.data.get("voice_provider")

            global_provider = self.chat_service.config.get("voice_provider", "Edge TTS")
            global_voice = self.chat_service.config.get("voice_id", "es-ES-AlvaroNeural")

            actual_voice = (
                char_voice
                if (char_voice and char_voice != "None" and str(char_voice).strip() != "")
                else global_voice
            )

            actual_provider = (
                char_provider
                if (char_provider and char_provider != "None" and str(char_provider).strip() != "")
                else global_provider
            )

            return {
                "provider": self.chat_service.config.get("last_provider", "Ollama"),
                "model": self.chat_service.config.get("last_model", ""),
                "active_thread": self.chat_service.memory.active_thread,
                "language": self.chat_service.locale_service.get_current_language(),
                "voice_provider": actual_provider if actual_provider else "None",
                "voice_mode": self.chat_service.config.get("voice_mode", "autoplay"),
                "voice_path": self.chat_service.config.get("voice_save_path", "audio"),
                "voice_id": actual_voice if actual_voice else "es-ES-AlvaroNeural",
                "stt_provider": self.chat_service.config.get("stt_provider", "None"),
                "stt_mode": self.chat_service.config.get("stt_mode", "OFF")
            }

        # =====================================================
        # MEMORY MANAGEMENT
        # =====================================================
        @self.app.get("/v1/memories")
        def list_memories():
            return {"memories": self.chat_service.memory.list_threads()}

        @self.app.get("/v1/memories/exists/{thread_id}")
        def check_thread_exists(thread_id: str):
            all_threads = self.chat_service.memory.list_threads()
            exists = thread_id in all_threads
            return {"thread_id": thread_id, "exists": exists}

        @self.app.get("/v1/memories/current")
        def get_current_memory():
            return {
                "thread_id": self.chat_service.memory.active_thread,
                "data": self.chat_service.memory.data
            }

        @self.app.post("/v1/memories")
        def switch_or_create_memory(data: dict):
            target = data.get("thread_id", "None")
            name = data.get("name")
            pers = data.get("personality")
            hist = data.get("history")
            voice = data.get("voice_id")
            v_prov = data.get("voice_provider")

            if target == "New":
                new_id = self.chat_service.memory.create_new_thread()
                self.chat_service.memory.load_thread(new_id)

                if name or pers or hist or voice or v_prov:
                    self.chat_service.memory.update_profile(
                        name=name,
                        personality=pers,
                        history=hist,
                        voice_id=voice,
                        voice_provider=v_prov
                    )

                self.chat_service.config.set("active_thread", new_id)
                return {"status": "success", "thread_id": new_id}

            all_threads = self.chat_service.memory.list_threads()

            if target not in all_threads:
                self.chat_service.memory.create_named_thread(target)

            self.chat_service.memory.load_thread(target)

            if name or pers or hist or voice or v_prov:
                self.chat_service.memory.update_profile(
                    name=name,
                    personality=pers,
                    history=hist,
                    voice_id=voice,
                    voice_provider=v_prov
                )

            self.chat_service.config.set("active_thread", target)
            return {"status": "success", "thread_id": target}

        @self.app.patch("/v1/memories/profile")
        def update_memory_profile(data: dict):
            """
            Actualiza el perfil de la memoria activa.
            Payload:
            {
                "name": "...",
                "personality": "...",
                "character_history": "...",
                "voice_id": "...",
                "voice_provider": "..."
            }
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

        # =====================================================
        # AUDIO
        # =====================================================
        @self.app.post("/v1/audio/pause")
        def audio_pause():
            if self.chat_service.stt_service:
                self.chat_service.stt_service.pause_capture()
                return {"status": "success", "message": "Microphone paused"}
            return {"status": "error", "message": "STT Service not available"}

        @self.app.post("/v1/audio/resume")
        def audio_resume():
            if self.chat_service.stt_service:
                self.chat_service.stt_service.resume_capture()
                return {"status": "success", "message": "Microphone resuming with safety delay"}
            return {"status": "error", "message": "STT Service not available"}

        @self.app.post("/v1/audio/stop")
        def audio_stop():
            self.chat_service.voice_service.stop_audio()
            return {"status": "success", "message": "Audio stopped remotely"}
        
        @self.app.post("/v1/audio/speak")
        def audio_speak(request: SpeakRequest):
            try:
                text = (request.text or "").strip()
                if not text:
                    return {"status": "error", "message": "Text is empty"}

                if not hasattr(self.chat_service, "voice_service") or not self.chat_service.voice_service:
                    return {"status": "error", "message": "Voice service not available"}

                self.chat_service.voice_service.speak_text(
                    text=text,
                    voice_id=request.voice_id,
                    voice_provider=request.voice_provider
                )

                return {"status": "success", "message": "Speech launched"}

            except Exception as e:
                print(f"[API] Speak error: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.get("/v1/audio/status")
        def audio_status():
            is_playing = False
            audio_start_time = None
            audio_duration = None

            if hasattr(self.chat_service, "voice_service") and self.chat_service.voice_service:
                vs = self.chat_service.voice_service
                is_playing = bool(getattr(vs, "is_playing", False))
                audio_start_time = getattr(vs, "audio_start_time", None)
                audio_duration = getattr(vs, "audio_duration", None)

            return {
                "status": "success",
                "is_playing": is_playing,
                "audio_start_time": audio_start_time,
                "audio_duration": audio_duration,
                "playback_mode": self.chat_service.config.get("voice_playback_mode", "interrupt")
            }

        @self.app.post("/v1/audio/playback_mode")
        def set_playback_mode(request: dict):
            mode = request.get("mode", "interrupt")
            if mode not in ("interrupt", "wait"):
                return {"status": "error", "message": "Mode must be 'interrupt' or 'wait'"}
            self.chat_service.config.set("voice_playback_mode", mode)
            return {"status": "success", "playback_mode": mode}

        # =====================================================
        # STT
        # =====================================================
        @self.app.get("/v1/stt/latest")
        def get_latest_stt():
            return {
                "status": "success",
                "text": self.last_stt_text,
                "timestamp": self.last_stt_timestamp
            }

        @self.app.get("/v1/stt/next")
        def get_next_stt():
            try:
                item = self.stt_results.get_nowait()
                return {
                    "status": "success",
                    "has_result": True,
                    "text": item["text"],
                    "timestamp": item["timestamp"]
                }
            except queue.Empty:
                return {
                    "status": "success",
                    "has_result": False,
                    "text": "",
                    "timestamp": 0.0
                }

        @self.app.post("/v1/stt/clear")
        def clear_stt_queue():
            while not self.stt_results.empty():
                try:
                    self.stt_results.get_nowait()
                except Exception:
                    break

            self.last_stt_text = ""
            self.last_stt_timestamp = 0.0

            return {"status": "success", "message": "STT queue cleared"}

        @self.app.post("/v1/stt/mode")
        def set_stt_mode(data: dict):
            """
            Cambia el modo STT:
            OFF / CHAT / COMMAND / QUESTION
            """
            mode = str(data.get("mode", "OFF")).upper()

            self.chat_service.config.set("stt_mode", mode)

            if self.chat_service.stt_service:
                self.chat_service.stt_service.manage_microphone_thread()

            return {"status": "success", "mode": mode}

        # =====================================================
        # CONFIG / CATALOGS
        # =====================================================
        @self.app.get("/v1/providers")
        def list_providers():
            return {"providers": self.chat_service.get_providers_list()}

        @self.app.get("/v1/languages")
        def list_languages():
            return {"languages": self.chat_service.locale_service.list_available_languages()}

        @self.app.post("/v1/language")
        def set_language(data: dict):
            lang = data.get("language")
            if lang:
                self.chat_service.locale_service.set_language(lang)
                return {"status": "success", "language": lang}
            return {"status": "error", "message": "Language not specified"}

        @self.app.get("/v1/voice_providers")
        def list_voice_providers():
            return {"voice_providers": self.chat_service.get_voice_providers_list()}

        @self.app.get("/v1/models")
        def list_models(provider: Optional[str] = None):
            if provider:
                self.chat_service.switch_provider(provider)
            return {"models": self.chat_service.get_available_models()}

        @self.app.get("/v1/voices")
        def list_voices():
            return {"voices": self.chat_service.voice_service.get_available_voices()}

        @self.app.post("/v1/config")
        def update_config(config_data: dict):
            """
            Actualiza configuración global.
            """
            for key, value in config_data.items():
                self.chat_service.config.set(key, value)

            if "last_provider" in config_data:
                self.chat_service.switch_provider(config_data["last_provider"])

            if "voice_provider" in config_data:
                self.chat_service.voice_service.update_provider()

            if "stt_provider" in config_data or "stt_mode" in config_data:
                if self.chat_service.stt_service:
                    self.chat_service.stt_service.update_adapter()

            return {"status": "success", "message": "Configuration updated"}

        # =====================================================
        # CHAT
        # =====================================================
        

        @self.app.post("/v1/chat")
        def chat(request: ChatRequest):
            try:
                model = request.model
                if not model or model.strip() == "":
                    model = self.chat_service.config.get("last_model")

                silent = bool(request.silent)

                print(f"[API] Chat request - text: {request.text[:50]}..., model: {model}, silent: {silent}, max_tokens: {request.max_tokens}, temp: {request.temperature}")

                result = self.chat_service.send_message(
                    request.text,
                    model=model,
                    silent=silent,
                    max_tokens=request.max_tokens,
                    temperature=request.temperature
                )

                return {
                    "response": result["response"],
                    "clean_text": result["clean_text"],
                    "emojis": result["emojis"],
                    "status": "success"
                }

            except Exception as e:
                print(f"[API] Chat error: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.get("/v1/webhook/whatsapp")
        def whatsapp_verify():
            mode = self.app.query_params.get("hub.mode")
            token = self.app.query_params.get("hub.verify_token")
            challenge = self.app.query_params.get("hub.challenge")

            expected_token = self.chat_service.config.get("whatsapp_verify_token", "asimod_verify_token")

            if mode == "subscribe" and token == expected_token:
                return PlainTextResponse(content=challenge, status_code=200)
            return PlainTextResponse(content="Forbidden", status_code=403)

        @self.app.post("/v1/webhook/whatsapp")
        async def whatsapp_webhook(request: Request):
            try:
                body = await request.json()
                adapter = MessagingFactory.get_adapter("WhatsApp", self.chat_service.config)
                if not adapter:
                    return {"status": "error", "message": "WhatsApp not configured"}

                msg = adapter.receive_message(body)
                if not msg or not msg.get("text"):
                    return {"status": "ok"}

                user_id = msg["user_id"]
                user_text = msg["text"]

                print(f"[WhatsApp] Received from {user_id}: {user_text[:50]}")

                result = self.chat_service.send_message(user_text, silent=False)
                response_text = result.get("response", "")

                voice_mode = self.chat_service.config.get("voice_mode", "autoplay")
                if voice_mode == "autoplay":
                    audio_path = self._generate_voice(response_text)
                    if audio_path:
                        adapter.send_audio(user_id, audio_path)
                    else:
                        adapter.send_text(user_id, response_text)
                else:
                    adapter.send_text(user_id, response_text)

                return {"status": "ok"}

            except Exception as e:
                print(f"[WhatsApp] Webhook error: {e}")
                return {"status": "error", "message": str(e)}

        @self.app.post("/v1/webhook/telegram")
        async def telegram_webhook(request: Request):
            try:
                body = await request.json()
                adapter = MessagingFactory.get_adapter("Telegram", self.chat_service.config)
                if not adapter:
                    return {"status": "error", "message": "Telegram not configured"}

                msg = adapter.receive_message(body)
                if not msg or not msg.get("text"):
                    return {"status": "ok"}

                user_id = msg["user_id"]
                user_text = msg["text"]

                print(f"[Telegram] Received from {user_id}: {user_text[:50]}")

                result = self.chat_service.send_message(user_text, silent=False)
                response_text = result.get("response", "")

                voice_mode = self.chat_service.config.get("voice_mode", "autoplay")
                if voice_mode == "autoplay":
                    audio_path = self._generate_voice(response_text)
                    if audio_path:
                        adapter.send_audio(user_id, audio_path)
                    else:
                        adapter.send_text(user_id, response_text)
                else:
                    adapter.send_text(user_id, response_text)

                return {"status": "ok"}

            except Exception as e:
                print(f"[Telegram] Webhook error: {e}")
                return {"status": "error", "message": str(e)}

        def _generate_voice(self, text: str) -> str:
            try:
                self.chat_service.voice_service.speak_text(text)
                save_dir = self.chat_service.config.get("voice_save_path", "audio")
                files = []
                if os.path.exists(save_dir):
                    files = [f for f in os.listdir(save_dir) if f.startswith("voice_")]
                if files:
                    latest = sorted(files)[-1]
                    return os.path.join(save_dir, latest)
            except Exception as e:
                print(f"[API] Voice generation error: {e}")
            return None

    # =========================================================
    # RUN
    # =========================================================
    def run(self, blocking=False):
        def start_uvicorn():
            uvicorn.run(self.app, host=self.host, port=self.port, log_level="info")

        if blocking:
            print(f"API Server (Headless) started on http://{self.host}:{self.port}")
            start_uvicorn()
        else:
            self._thread = threading.Thread(target=start_uvicorn, daemon=True)
            self._thread.start()
            print(f"API Server (Background) started on http://{self.host}:{self.port}")