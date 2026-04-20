import threading
import uvicorn
import queue
import time
import os
import uuid

from fastapi import FastAPI, HTTPException, Request, UploadFile, File
from fastapi.responses import PlainTextResponse, StreamingResponse
import json
from pydantic import BaseModel
from typing import Optional
from fastapi.middleware.cors import CORSMiddleware
from fastapi import Form, Response
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path
import base64
import mimetypes

from core.factories.messaging_factory import MessagingFactory


class ChatRequest(BaseModel):
    text: str
    model: Optional[str] = None
    silent: Optional[bool] = False
    max_tokens: Optional[int] = None
    temperature: Optional[float] = None
    play_audio: Optional[bool] = None

class DirectLLMRequest(BaseModel):
    prompt: str
    system_prompt: Optional[str] = ""
    model: Optional[str] = None
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

    def __init__(self, chat_service, port=8000, host="0.0.0.0", module_service=None, style_service=None):
        self.chat_service = chat_service
        self.module_service = module_service
        self.style_service = style_service
        
        # Nuevo Servicio de Personajes (NUEVO)
        from core.services.character_service import CharacterService
        self.character_service = CharacterService()
        
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

    def _mount_module_assets(self):
        """Escanea todos los módulos y monta sus carpetas /web como rutas estáticas."""
        if not self.module_service:
            return
            
        modules_dir = self.module_service.modules_dir
        if not os.path.exists(modules_dir):
            return
            
        for entry in sorted(os.listdir(modules_dir)):
            module_web_path = os.path.join(modules_dir, entry, "web")
            if os.path.isdir(module_web_path):
                # Montamos en la ruta que espera el frontend (/modules/id)
                mount_path = f"/modules/{entry}"
                print(f"[API] Montando interfaz web para módulo '{entry}' en {mount_path}")
                self.app.mount(mount_path, StaticFiles(directory=module_web_path, html=True), name=f"web_{entry}")
                
                # Mantenemos compatibilidad con la ruta vieja si es necesario
                old_mount = f"/v1/modules/{entry}/assets"
                self.app.mount(old_mount, StaticFiles(directory=module_web_path), name=f"legacy_web_{entry}")
                
            # --- NUEVO: Montaje de Output del Módulo ---
            module_output_path = os.path.join(modules_dir, entry, "output")
            if os.path.isdir(module_output_path):
                out_mount = f"/v1/modules/{entry}/output"
                print(f"[API] Montando Output para módulo '{entry}': {out_mount}")
                self.app.mount(out_mount, StaticFiles(directory=module_output_path), name=f"module_output_{entry}")

            # --- NUEVO: Montaje de Recursos del Módulo (Imágenes, Audio, etc) ---
            module_resources_path = os.path.join(modules_dir, entry, "Resources")
            if os.path.isdir(module_resources_path):
                res_mount = f"/v1/modules/{entry}/resources"
                print(f"[API] Montando Recursos para módulo '{entry}': {res_mount}")
                self.app.mount(res_mount, StaticFiles(directory=module_resources_path), name=f"module_res_{entry}")

    # =========================================================
    # ROUTES
    # =========================================================
    def _setup_routes(self):
        @self.app.get("/")
        async def root():
            from starlette.responses import RedirectResponse
            return RedirectResponse(url="/web/")

        @self.app.get("/web_remote")
        async def web_remote():
            """Redirige la ruta vieja al nuevo sistema web."""
            from starlette.responses import RedirectResponse
            return RedirectResponse(url="/web/")

        # --- SISTEMA WEB MODULAR ---
        # Calculamos la ruta absoluta basada en la ubicación de este archivo
        from pathlib import Path
        base_dir = Path(__file__).parent.parent
        web_path = base_dir / "web"
        
        if web_path.exists():
            self.app.mount("/web", StaticFiles(directory=str(web_path), html=True), name="web")
        
        # --- NUEVO: Montaje dinámico de recursos de módulos ---
        self._mount_module_assets()

        # Montaje de Widgets Globales
        widgets_path = web_path / "widgets"
        if not widgets_path.exists(): os.makedirs(widgets_path)
        self.app.mount("/v1/widgets", StaticFiles(directory=str(widgets_path)), name="global_widgets")

        # Servir carpetas de datos para visualización en web
        for static_folder in ["Resources", "output"]:
            abs_path = base_dir / static_folder
            if abs_path.exists():
                self.app.mount(f"/{static_folder}", StaticFiles(directory=str(abs_path)), name=static_folder)

        @self.app.get("/v1/modules")
        def list_modules():
            """Retorna la lista de módulos con detección de interfaz modular."""
            if not self.module_service:
                return {"modules": []}
            
            modules_data = []
            for mod in self.module_service.get_modules():
                # Detectar si el módulo tiene una interfaz web propia (Usando ruta absoluta)
                abs_modules_dir = os.path.abspath(self.module_service.modules_dir)
                module_dir = os.path.join(abs_modules_dir, mod.id)
                web_ui_path = os.path.join(module_dir, "web", "index.html")
                has_web_ui = os.path.exists(web_ui_path)
                
                modules_data.append({
                    "id": mod.id,
                    "name": mod.name,
                    "icon": mod.icon,
                    "show_menu": getattr(mod, "show_menu", False),
                    "show_gallery": getattr(mod, "show_gallery", False),
                    "show_controllers": getattr(mod, "show_controllers", False),
                    "menu_items": getattr(mod, "menu_items", []),
                    "gallery_title": getattr(mod, "gallery_title", "Galería"),
                    "has_web_ui": has_web_ui
                })
            return {"modules": modules_data}

        @self.app.post("/v1/modules/{module_id}/action")
        async def module_action(module_id: str, request: Request):
            """Ejecuta una acción específica en un módulo (ej: generar imagen)."""
            if not self.module_service:
                raise HTTPException(status_code=500, detail="Servicio de módulos no disponible")
            
            # Buscar el módulo
            target_mod = None
            for mod in self.module_service.get_modules():
                if mod.id == module_id:
                    target_mod = mod
                    break
            
            if not target_mod:
                raise HTTPException(status_code=404, detail="Módulo no encontrado")
                
            try:
                data = await request.json()
                action = data.get("action")
                params = data.get("params", {})
                
                # 1. Intentar llamar al método directo (ej: mod.generar_imagen)
                if hasattr(target_mod, action) and callable(getattr(target_mod, action)):
                    method = getattr(target_mod, action)
                    
                    import inspect
                    if inspect.iscoroutinefunction(method):
                        result = await method(**params)
                    else:
                        result = method(**params)
                
                # 2. Fallback: Usar dispatcher handle_action si existe
                elif hasattr(target_mod, "handle_action") and callable(getattr(target_mod, "handle_action")):
                    method = getattr(target_mod, "handle_action")
                    
                    import inspect
                    if inspect.iscoroutinefunction(method):
                        result = await method(action=action, params=params)
                    else:
                        result = method(action=action, params=params)
                else:
                    return {"status": "error", "message": f"Acción '{action}' no soportada por el módulo"}

                # Procesar resultado
                if isinstance(result, (dict, list)):
                    return {"status": "success", "result": result}
                    
                return {"status": "success", "result": str(result) if result else "Ejecutado"}
            except Exception as e:
                return {"status": "error", "message": str(e)}

        @self.app.get("/v1/gallery")
        async def list_gallery(module_id: str = None, path: str = ""):
            """Retorna la lista de archivos o carpetas contextuales."""
            from pathlib import Path
            
            # Caso 1: Si el módulo tiene su propia galería lógica
            if module_id:
                mod = self.module_service.get_module(module_id)
                if mod and hasattr(mod, "handle_get_gallery"):
                    print(f"[API] Forzando galería exclusiva para módulo: {module_id}")
                    import asyncio
                    try:
                        kwargs = {"path": path} if path else {}
                        if asyncio.iscoroutinefunction(mod.handle_get_gallery):
                            return await mod.handle_get_gallery(**kwargs)
                        else:
                            return mod.handle_get_gallery(**kwargs)
                    except Exception as e:
                        print(f"[API] Error en galería delegada {module_id}: {e}")
                        return {"status": "error", "message": str(e), "items": []}
                
                # Si se pidió un módulo pero no existe o no tiene galería, no saltamos a la raíz.
                # Devolvemos vacío para mantener la integridad del módulo.
                print(f"[API] Advertencia: El módulo {module_id} no soporta galería delegada.")
                return {"items": [], "current_path": path, "message": "Módulo sin galería"}

            # Caso 2: Navegación jerárquica física desde 'output'
            output_root = Path("output").resolve()
            
            # Limpiar y validar el path para evitar Path Traversal
            safe_path = Path(path.strip("/\\")).resolve()
            if not str(safe_path).startswith(str(output_root)) and path:
                target_dir = (output_root / path.strip("/\\")).resolve()
            else:
                target_dir = output_root if not path else safe_path

            # Asegurar que no nos salimos de output
            if not str(target_dir).startswith(str(output_root)):
                target_dir = output_root

            if not target_dir.exists():
                return {"items": [], "current_path": path}
            
            items = []
            valid_exts = {'.png', '.jpg', '.jpeg', '.gif', '.wav', '.mp3', '.mp4', '.txt', '.pdf', '.json', '.glb', '.obj'}
            
            try:
                for item in target_dir.iterdir():
                    rel_path = item.relative_to(output_root).as_posix()
                    
                    if item.is_dir():
                        items.append({
                            "name": item.name,
                            "type": "folder",
                            "path": rel_path,
                            "icon": "📁"
                        })
                    elif item.is_file() and item.suffix.lower() in valid_exts:
                        ext = item.suffix.lower()
                        # Categoría de media
                        f_type = "file"
                        if ext in {'.png', '.jpg', '.jpeg', '.gif'}: f_type = "image"
                        elif ext in {'.wav', '.mp3'}: f_type = "audio"
                        elif ext in {'.mp4', '.avi', '.mov'}: f_type = "video"
                        elif ext in {'.glb', '.obj'}: f_type = "3d"
                        
                        items.append({
                            "name": item.name,
                            "type": f_type,
                            "url": f"/output/{rel_path}",
                            "path": rel_path,
                            "size": item.stat().st_size,
                            "date": item.stat().st_mtime
                        })
                
                # Ordenar: Carpetas primero, luego archivos por fecha
                items.sort(key=lambda x: (x['type'] != 'folder', -x.get('date', 0)))
                
                return {
                    "items": items,
                    "current_path": path,
                    "can_go_back": path != ""
                }
            except Exception as e:
                print(f"[API] Error listando galería en {target_dir}: {e}")
                return {"items": [], "error": str(e)}

        @self.app.get("/v1/modules/{module_id}/workflows")
        async def list_workflows(module_id: str):
            """Retorna la lista de workflows disponibles para un módulo."""
            if module_id != "media_generator":
                return {"workflows": []}
            
            from pathlib import Path
            base_dir = Path("modules/media_generator/workflows").resolve()
            if not base_dir.exists(): return {"workflows": {}}
            
            workflows = {}
            
            def scan_dir(path: Path, base_rel=""):
                """Escanea una carpeta recursivamente y retorna carpetas que contienen archivos JSON."""
                results = {}
                direct_files = [f.name for f in path.iterdir() if f.is_file() and f.suffix == ".json"]
                if direct_files:
                    key = base_rel if base_rel else "root"
                    results[key] = direct_files
                
                for item in path.iterdir():
                    if item.is_dir():
                        sub_rel = f"{base_rel}/{item.name}" if base_rel else item.name
                        results.update(scan_dir(item, sub_rel))
                return results

            for sub in ["simple", "compuesta", "audio", "video", "3d"]:
                sub_path = base_dir / sub
                if not sub_path.exists(): continue
                
                # Mapear 'simple' a 'imagen' para el frontend
                key = "imagen" if sub == "simple" else sub
                workflows[key] = scan_dir(sub_path)
            
            return {"workflows": workflows}

        @self.app.get("/v1/style")
        def get_style():
            """Retorna el esquema de colores actual."""
            if not self.style_service:
                return {"colors": {}}
            return self.style_service.current_theme

        @self.app.get("/v1/status")
        async def get_status():
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
                "max_tokens": self.chat_service.config.get("max_tokens", 1024),
                "temperature": self.chat_service.config.get("temperature", 0.7),
                "active_thread": self.chat_service.memory.active_thread,
                "language": self.chat_service.locale_service.get_current_language(),
                "voice_provider": actual_provider if actual_provider else "None",
                "voice_mode": self.chat_service.config.get("voice_mode", "autoplay"),
                "voice_path": self.chat_service.config.get("voice_save_path", "audio"),
                "voice_id": actual_voice if actual_voice else "es-ES-AlvaroNeural",
                "stt_provider": self.chat_service.config.get("stt_provider", "None"),
                "stt_mode": self.chat_service.config.get("stt_mode", "OFF"),
                "stt_captured_by_module": getattr(self.chat_service, "stt_captured_by_module", False),
                "char_name": self.chat_service.memory.data.get("name", ""),
                "char_personality": self.chat_service.memory.data.get("personality", ""),
                "char_avatar": self.chat_service.memory.data.get("avatar", {}),
                "char_video": self.chat_service.memory.data.get("video", {}),
                "char_stats": self.chat_service.memory.data.get("stats", {}),
                "calibration": self.chat_service.memory.data.get("calibration", {}), # NUEVO
                "current_style": self.chat_service.config.get("current_style", "dark_carbon") # NUEVO
            }

        @self.app.get("/v1/fs/get")
        async def get_filesystem_file(path: str):
            """Sirve un archivo local desde cualquier ruta (Usado por SistemaModule)."""
            from fastapi.responses import FileResponse
            import mimetypes
            
            if not os.path.exists(path):
                raise HTTPException(status_code=404, detail="Archivo no encontrado")
            
            if os.path.isdir(path):
                raise HTTPException(status_code=400, detail="La ruta es un directorio")
                
            mime_type, _ = mimetypes.guess_type(path)
            return FileResponse(path, media_type=mime_type or "application/octet-stream")

        @self.app.get("/v1/characters")
        async def list_registry_characters():
            """Retorna la lista de personajes en el Repositorio Global."""
            return {"characters": self.character_service.list_characters()}

        @self.app.get("/v1/characters/{char_id}")
        async def get_character_details(char_id: str):
            """Retorna los detalles de un personaje específico."""
            char = self.character_service.get_character(char_id)
            if not char:
                raise HTTPException(status_code=404, detail="Personaje no encontrado")
            return char

        @self.app.patch("/v1/characters/{char_id}/stats")
        async def update_character_stats(char_id: str, stats: dict):
            """Actualiza las estadísticas emocionales de un personaje."""
            char = self.character_service.get_character(char_id)
            if not char:
                raise HTTPException(status_code=404, detail="Personaje no encontrado")
            
            # Combinar stats existentes con los nuevos
            current_stats = char.get("stats", {})
            for k, v in stats.items():
                current_stats[k] = v
            
            success = self.character_service.update_character(char_id, {"stats": current_stats})
            
            # Si el personaje actual es el que estamos editando, actualizar memoria activa también
            if success and self.chat_service.memory.data.get("id") == char_id:
                self.chat_service.memory.data["stats"] = current_stats
                # Forzar actualización de UI si hay visualizador activo
                # (A través del mecanismo de sondeo de la UI o mediante un evento disparado aquí)
                
            return {"status": "success" if success else "error", "stats": current_stats}

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
            avatar = data.get("avatar") # NUEVO
            video = data.get("video") # NUEVO
            calibration = data.get("calibration") # NUEVO

            if target == "New" or (not target or target == "None"):
                # Si target es None/New, intentar usar name como ID
                actual_id = name if name else self.chat_service.memory.create_new_thread()
                
                all_threads = self.chat_service.memory.list_threads()
                if actual_id not in all_threads:
                    self.chat_service.memory.create_named_thread(actual_id)
                
                self.chat_service.memory.load_thread(actual_id)

                if name or pers or hist or voice or v_prov or avatar:
                    self.chat_service.memory.update_profile(
                        name=name,
                        personality=pers,
                        history=hist,
                        voice_id=voice,
                        voice_provider=v_prov,
                        avatar=avatar, # NUEVO
                        video=video, # NUEVO
                        calibration=calibration # NUEVO
                    )

                self.chat_service.config.set("active_thread", actual_id)
                return {"status": "success", "thread_id": actual_id}

            all_threads = self.chat_service.memory.list_threads()

            if target not in all_threads:
                self.chat_service.memory.create_named_thread(target)

            self.chat_service.memory.load_thread(target)

            if name or pers or hist or voice or v_prov or avatar or video:
                self.chat_service.memory.update_profile(
                    name=name,
                    personality=pers,
                    history=hist,
                    voice_id=voice,
                    voice_provider=v_prov,
                    avatar=avatar,
                    video=video,
                    calibration=calibration # NUEVO
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

        @self.app.get("/v1/memories/{thread_id}")
        def get_thread(thread_id: str):
            """Obtiene los datos de un hilo específico."""
            data = self.chat_service.memory.get_thread_data(thread_id)
            if data is None:
                return {"status": "error", "message": "Thread not found"}
            return {"thread_id": thread_id, "data": data}

        @self.app.delete("/v1/memories/{thread_id}")
        def delete_thread(thread_id: str):
            """Borra un hilo completamente."""
            result = self.chat_service.memory.delete_thread(thread_id)
            return result

        @self.app.post("/v1/memories/{thread_id}/messages")
        def add_message_to_thread(thread_id: str, data: dict):
            """Añade un mensaje a un hilo."""
            role = data.get("role", "user")
            content = data.get("content", "")
            result = self.chat_service.memory.add_message_to_thread(thread_id, role, content)
            return result

        @self.app.patch("/v1/memories/{thread_id}/messages/{message_index}")
        def edit_message_in_thread(thread_id: str, message_index: int, data: dict):
            """Edita un mensaje en un hilo."""
            new_content = data.get("content", "")
            result = self.chat_service.memory.edit_message_in_thread(thread_id, message_index, new_content)
            return result

        @self.app.delete("/v1/memories/{thread_id}/messages/{message_index}")
        def delete_message_in_thread(thread_id: str, message_index: int):
            """Borra un mensaje de un hilo."""
            result = self.chat_service.memory.delete_message_in_thread(thread_id, message_index)
            return result

        @self.app.delete("/v1/memories/{thread_id}/history")
        def clear_thread_history(thread_id: str):
            """Limpia el historial de un hilo."""
            result = self.chat_service.memory.clear_thread_history(thread_id)
            return result

        @self.app.patch("/v1/memories/{thread_id}/profile")
        def update_thread_profile(thread_id: str, data: dict):
            """Actualiza el perfil de un hilo específico."""
            result = self.chat_service.memory.update_thread_profile(
                thread_id,
                name=data.get("name"),
                personality=data.get("personality"),
                character_history=data.get("character_history"),
                voice_id=data.get("voice_id"),
                voice_provider=data.get("voice_provider")
            )
            return result

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
        async def speak(request: SpeakRequest):
            try:
                await self.chat_service.voice_service.process_text(
                    text=request.text,
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

        @self.app.get("/v1/fs/get")
        async def get_fs_file(path: str):
            """Sirve un archivo local para el explorador del sistema."""
            from pathlib import Path
            from starlette.responses import FileResponse
            import mimetypes

            file_path = Path(path)
            if not file_path.exists() or not file_path.is_file():
                raise HTTPException(status_code=404, detail="Archivo no encontrado")

            # Mimetypes suele resolver bien .png, .jpg, .pdf, .mp4, etc.
            mime, _ = mimetypes.guess_type(path)
            headers = {"Cache-Control": "public, max-age=3600"} # Cache de 1 hora para assets estáticos
            return FileResponse(str(file_path), media_type=mime or "application/octet-stream", headers=headers)

        @self.app.get("/v1/audio/file/{filename}")
        async def get_audio_file(filename: str):
            audio_dir = self.chat_service.config.get("voice_save_path", "audio")
            file_path = Path(audio_dir) / filename
            
            if file_path.exists() and file_path.is_file():
                media_type = "audio/mpeg" if filename.endswith(".mp3") else "audio/wav"
                return FileResponse(str(file_path), media_type=media_type)
            return {"error": "File not found"}

        @self.app.post("/v1/audio/playback_mode")
        def set_playback_mode(request: dict):
            mode = request.get("mode", "interrupt")
            if mode not in ("interrupt", "wait"):
                return {"status": "error", "message": "Mode must be 'interrupt' or 'wait'"}
            self.chat_service.config.set("voice_playback_mode", mode)
            return {"status": "success", "playback_mode": mode}

        @self.app.get("/v1/audio/destreaming")
        def get_destreaming_status():
            return {
                "status": "success",
                "destreaming_enabled": self.chat_service.config.get("destreaming_enabled", False),
                "destreaming_chunk_size": self.chat_service.config.get("destreaming_chunk_size", 500)
            }

        @self.app.post("/v1/audio/destreaming")
        def set_destreaming(request: dict):
            enabled = request.get("enabled")
            chunk_size = request.get("chunk_size")
            
            if enabled is not None:
                self.chat_service.config.set("destreaming_enabled", bool(enabled))
            
            if chunk_size is not None and isinstance(chunk_size, int) and chunk_size > 0:
                self.chat_service.config.set("destreaming_chunk_size", chunk_size)
            
            return {
                "status": "success",
                "destreaming_enabled": self.chat_service.config.get("destreaming_enabled", False),
                "destreaming_chunk_size": self.chat_service.config.get("destreaming_chunk_size", 500)
            }


        # =====================================================
        # VISION
        # =====================================================
        @self.app.post("/v1/vision/capture")
        async def capture_vision(request: dict):
            from core.services.vision_service import VisionService
            import base64
            
            mode = request.get("mode", "OFF")
            vision = VisionService()
            path = None
            
            if mode == "CAMERA":
                path = vision.capture_cam()
            elif mode == "SCREEN":
                path = vision.capture_screen()
            
            if path and os.path.exists(path):
                with open(path, "rb") as image_file:
                    encoded = base64.b64encode(image_file.read()).decode('utf-8')
                return {"status": "success", "image": encoded, "path": os.path.basename(path)}
            
            return {"status": "error", "message": "No se pudo capturar la imagen."}

        @self.app.post("/v1/vision/upload")
        async def upload_vision(file: UploadFile = File(...)):
            import base64
            contents = await file.read()
            encoded = base64.b64encode(contents).decode("utf-8")
            return {"status": "success", "image": encoded}

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
            OFF / CHAT / COMMAND / QUESTION / VOICE_COMMAND
            """
            mode = str(data.get("mode", "OFF")).upper()

            self.chat_service.config.set("stt_mode", mode)
            return {"status": "success", "mode": mode}

        @self.app.post("/v1/stt/process")
        async def process_audio(file: UploadFile = File(...)):
            """Procesa un archivo de audio y devuelve el texto."""
            if not self.chat_service.stt_service:
                return {"status": "error", "message": "STT Service not initialized"}
            
            try:
                # Guardar temporalmente
                temp_filename = f"web_upload_{int(time.time())}.wav"
                content = await file.read()
                with open(temp_filename, "wb") as f:
                    f.write(content)
                
                # Transcribir de forma asíncrona usando el adaptador
                # NOTA: STTService.adapter.transcribe es bloqueante normalmente
                import asyncio
                text = await asyncio.to_thread(self.chat_service.stt_service.adapter.transcribe, temp_filename)
                
                # Limpiar
                if os.path.exists(temp_filename):
                    os.remove(temp_filename)
                
                return {"status": "success", "text": text}
            except Exception as e:
                return {"status": "error", "message": str(e)}

            if self.chat_service.stt_service:
                self.chat_service.stt_service.manage_microphone_thread()

            return {"status": "success", "mode": mode}

        @self.app.get("/v1/stt/voice-commands")
        def get_voice_commands():
            """Obtiene el diccionario de comandos de voz."""
            commands = self.chat_service.config.get("voice_commands", {})
            return {"voice_commands": commands}

        @self.app.post("/v1/stt/voice-commands")
        def set_voice_commands(data: dict):
            """
            Configura el diccionario de comandos de voz.
            Formato: {"trigger1": "action1", "trigger2": "action2"}
            Ejemplo: {"jugar": "start_game", "parar": "stop_audio"}
            """
            commands = data.get("commands", {})
            self.chat_service.config.set("voice_commands", commands)
            return {"status": "success", "voice_commands": commands}

        @self.app.post("/v1/stt/voice-commands/add")
        def add_voice_command(data: dict):
            """Añade un comando de voz al diccionario."""
            trigger = data.get("trigger", "")
            action = data.get("action", "")
            
            if not trigger or not action:
                return {"status": "error", "message": "trigger and action required"}
            
            commands = self.chat_service.config.get("voice_commands", {})
            commands[trigger] = action
            self.chat_service.config.set("voice_commands", commands)
            
            return {"status": "success", "voice_commands": commands}

        @self.app.delete("/v1/stt/voice-commands/{trigger}")
        def delete_voice_command(trigger: str):
            """Borra un comando de voz."""
            commands = self.chat_service.config.get("voice_commands", {})
            if trigger in commands:
                del commands[trigger]
                self.chat_service.config.set("voice_commands", commands)
                return {"status": "success", "voice_commands": commands}
            return {"status": "error", "message": "Trigger not found"}

        @self.app.get("/v1/stt/last-voice-command")
        def get_last_voice_command():
            """Devuelve el último comando de voz reconocido."""
            if self.chat_service.stt_service and self.chat_service.stt_service.last_voice_command:
                return {"status": "success", **self.chat_service.stt_service.last_voice_command}
            return {"status": "success", "matched": None, "text": None, "timestamp": None}

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
        async def list_models(provider: Optional[str] = None):
            if provider:
                self.chat_service.switch_provider(provider)
            models = await self.chat_service.get_available_models()
            return {"models": models}

        @self.app.get("/v1/voices")
        def list_voices(provider: Optional[str] = None):
            if provider and provider != "None":
                from core.factories.voice_factory import VoiceFactory
                adapter = VoiceFactory.get_adapter(provider)
                if adapter:
                    return {"voices": adapter.list_voices()}
            return {"voices": self.chat_service.voice_service.get_available_voices()}

        @self.app.post("/v1/config")
        def update_config(config_data: dict):
            """
            Actualiza configuración global.
            Soporta tanto {"key": "...", "value": "..."} como {"param": "valor"}.
            """
            # Caso 1: {"key": "param", "value": "valor"}
            if "key" in config_data and "value" in config_data:
                self.chat_service.config.set(config_data["key"], config_data["value"])
            else:
                # Caso 2: {"param": "valor", ...}
                for key, value in config_data.items():
                    self.chat_service.config.set(key, value)

            # Acciones post-configuración
            if "last_provider" in config_data or config_data.get("key") == "last_provider":
                prov = config_data.get("last_provider") or config_data.get("value")
                self.chat_service.switch_provider(prov)

            if "voice_provider" in config_data or config_data.get("key") == "voice_provider":
                self.chat_service.voice_service.update_provider()

            if "stt_provider" in config_data or "stt_mode" in config_data or config_data.get("key") in ["stt_provider", "stt_mode"]:
                if self.chat_service.stt_service:
                    self.chat_service.stt_service.update_adapter()

            return {"status": "success", "message": "Configuration updated"}

        # =====================================================
        # CHAT
        # =====================================================
        @self.app.post("/v1/chat")
        async def chat(
            request: Request,
            text: str = Form(...),
            model: Optional[str] = Form(None),
            silent: Optional[bool] = Form(False),
            max_tokens: Optional[int] = Form(None),
            temperature: Optional[float] = Form(None),
            play_audio: Optional[str] = Form(None),
            image: Optional[UploadFile] = File(None),
            image_b64: Optional[str] = Form(None),
            stt_mode: Optional[str] = Form(None)
        ):
            try:
                import asyncio
                print(f"\n[API] >>> PETICIÓN RECIBIDA: '{text[:50]}...'")
                
                if not model or str(model).strip() == "" or model == "None":
                    model = self.chat_service.config.get("last_model")

                silent = str(silent).lower() == "true" if silent is not None else False
                play_audio_val = str(play_audio).lower() == "true" if play_audio is not None else False
                
                # Procesar imagen si existe (archivo o base64)
                images = []
                if image:
                    try:
                        import base64
                        contents = await image.read()
                        encoded = base64.b64encode(contents).decode("utf-8")
                        images.append(encoded)
                    except Exception as e:
                        print(f"[API] Error decoding image: {e}")
                
                if image_b64:
                    images.append(image_b64)

                # 1. GENERAR TEXTO (TIMEOUT 90s)
                print(f"[API] 1/3 Generando respuesta de texto (Modelo: {model})...")
                try:
                    result = await asyncio.wait_for(
                        self.chat_service.send_message(
                            text,
                            model=model,
                            images=[], # Por ahora simplificado
                            silent=silent,
                            max_tokens=max_tokens,
                            temperature=temperature,
                            skip_tts=True,
                            mode=stt_mode
                        ),
                        timeout=90.0
                    )
                    print(f"[API] 2/3 Texto generado con éxito.")
                except asyncio.TimeoutError:
                    print(f"[API] !!! TIMEOUT en generación de texto.")
                    return {"status": "error", "message": "El motor de IA (Ollama/LLM) tardó demasiado en responder."}

                response_data = {
                    "response": result["response"],
                    "clean_text": result.get("clean_text", ""),
                    "emojis": result.get("emojis", []),
                    "status": "success"
                }

                # 2. GENERAR AUDIO (TIMEOUT 30s)
                if play_audio_val:
                    print(f"[API] 3/3 Generando audio...")
                    try:
                        char_voice = self.chat_service.memory.data.get("voice_id")
                        char_provider = self.chat_service.memory.data.get("voice_provider")
                        
                        audio_path = await asyncio.wait_for(
                            self.chat_service.voice_service.generate_audio_only(
                                result["clean_text"] if result.get("clean_text") else result["response"],
                                voice_id=char_voice,
                                voice_provider=char_provider
                            ),
                            timeout=30.0
                        )
                        if audio_path:
                            # ATOMIC DELIVERY: Codificar audio en Base64 para envío directo
                            try:
                                with open(audio_path, "rb") as f:
                                    response_data["audio_b64"] = base64.b64encode(f.read()).decode('utf-8')
                                print(f"[API] >>> PROCESO COMPLETADO EXITO (Audio B64 incluido).")
                            except Exception as be:
                                print(f"[API] Error codificando B64: {be}")
                            
                            response_data["audio_path"] = os.path.basename(audio_path)
                        else:
                            print(f"[API] --- Audio fallido pero enviando texto.")
                            response_data["audio_path"] = None
                            response_data["audio_error"] = "Generation failed"
                    except asyncio.TimeoutError:
                        print(f"[API] --- Timeout en audio, enviando solo texto.")
                        response_data["audio_path"] = None
                        response_data["audio_error"] = "Timeout"

                return response_data

            except Exception as e:
                print(f"[API] !!! ERROR CRÍTICO EN CHAT: {e}")
                import traceback
                traceback.print_exc()
                return {"status": "error", "message": str(e)}

        @self.app.post("/v1/chat/stream")
        async def chat_stream(request: ChatRequest):
            """
            Endpoint para streaming de chat con audio fragmentado por frases.
            """
            model = request.model
            text = request.text
            silent = request.silent
            max_tokens = request.max_tokens
            temperature = request.temperature

            async def event_generator():
                try:
                    async for token in self.chat_service.send_message_stream(
                        text,
                        model=model,
                        images=None,
                        silent=silent,
                        max_tokens=max_tokens,
                        temperature=temperature
                    ):
                        # Enviar token en formato SSE
                        data = json.dumps({"token": token})
                        yield f"data: {data}\n\n"
                    
                    # Enviar evento de finalización
                    yield "data: [DONE]\n\n"
                except Exception as e:
                    yield f"data: {json.dumps({'error': str(e)})}\n\n"

            return StreamingResponse(event_generator(), media_type="text/event-stream")

        @self.app.post("/v1/llm/direct")
        async def llm_direct(request: DirectLLMRequest):
            """
            Genera una respuesta directa del LLM sin usar hilo de conversación.
            No guarda en memoria, no usa TTS, es una consulta aislada.
            """
            try:
                model = request.model
                if not model or model.strip() == "":
                    model = self.chat_service.config.get("last_model")
                
                max_tokens = request.max_tokens or self.chat_service.config.get("max_tokens")
                temperature = request.temperature or self.chat_service.config.get("temperature")
                system_prompt = request.system_prompt or ""
                
                print(f"[API] Direct LLM - prompt: {request.prompt[:50]}..., model: {model}")
                
                if not self.chat_service.current_adapter:
                    return {"response": "Error: No hay un motor de LLM configurado.", "status": "error"}
                
                history = [{"role": "user", "content": request.prompt}]
                raw_response = await self.chat_service.current_adapter.generate_chat(
                    history, system_prompt, model, None, max_tokens, temperature
                )
                
                return {
                    "response": raw_response,
                    "status": "success"
                }
                
            except Exception as e:
                print(f"[API] Direct LLM error: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.post("/v1/stt/transcribe")
        async def stt_transcribe(file: UploadFile = File(...)):
            """
            Recibe un archivo de audio desde la web, lo transcribe y devuelve el texto.
            """
            if not self.chat_service.stt_service or not self.chat_service.stt_service.adapter:
                raise HTTPException(status_code=500, detail="Servicio STT no disponible o no configurado.")
            
            # 1. Guardar archivo temporalmente
            temp_id = str(uuid.uuid4())
            file_ext = os.path.splitext(file.filename)[1] if file.filename else ".wav"
            temp_path = os.path.join("output", "temp", f"web_stt_{temp_id}{file_ext}")
            
            try:
                # Asegurar que el directorio de destino existe
                os.makedirs(os.path.dirname(temp_path), exist_ok=True)
                
                with open(temp_path, "wb") as buffer:
                    content = await file.read()
                    buffer.write(content)
                
                # 2. Transcribir
                print(f"[API][STT] Transcribiendo archivo web: {temp_path}")
                text = self.chat_service.stt_service.adapter.transcribe(temp_path)
                
                return {
                    "status": "success",
                    "text": text,
                    "filename": file.filename
                }
                
            except Exception as e:
                print(f"[API][STT] Error en transcripción web: {e}")
                return {"status": "error", "message": str(e)}
            finally:
                # 3. Limpieza
                if os.path.exists(temp_path):
                    try:
                        os.remove(temp_path)
                    except: pass

        @self.app.get("/v1/webhook/whatsapp")
        async def whatsapp_verify(request: Request):
            mode = request.query_params.get("hub.mode")
            token = request.query_params.get("hub.verify_token")
            challenge = request.query_params.get("hub.challenge")

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

                msg = await adapter.receive_message(body)
                if not msg or not msg.get("text"):
                    return {"status": "ok"}

                user_id = msg["user_id"]
                user_text = msg["text"]

                print(f"[WhatsApp] Received from {user_id}: {user_text[:50]}")

                # Procesar en segundo plano para responder 200 OK inmediatamente a Meta
                import asyncio
                async def process_whatsapp():
                    result = await self.chat_service.send_message(user_text, silent=False)
                    response_text = result.get("response", "")
                    await adapter.send_text(user_id, response_text)

                asyncio.create_task(process_whatsapp())

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

                msg = await adapter.receive_message(body)
                if not msg or not msg.get("text"):
                    return {"status": "ok"}

                user_id = msg["user_id"]
                user_text = msg["text"]

                print(f"[Telegram] Received from {user_id}: {user_text[:50]}")

                import asyncio
                async def process_telegram():
                    result = await self.chat_service.send_message(user_text, silent=False)
                    response_text = result.get("response", "")
                    await adapter.send_text(user_id, response_text)

                asyncio.create_task(process_telegram())

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