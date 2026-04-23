import os
import sys
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional, Dict

# Añadir raíz al path para importaciones
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.services.config_service import ConfigService
from core.services.data_service import DataService
from core.services.style_service import StyleService
from core.services.lean_chat_service import LeanChatService
from modules.media_generator import MediaGeneratorModule

class GenerateRequest(BaseModel):
    prompt: str
    mode: str  # Imagen, Video, Audio, 3D, Texto
    params: Optional[Dict] = None

class MediaAPIServer:
    def __init__(self, port=8001):
        self.app = FastAPI(title="ASIMOD Media Generator API")
        self.port = port
        
        # Inicializar Servicios
        self.config = ConfigService(filename="settings.json")
        self.data = DataService(config_service=self.config)
        self.style = StyleService(config_service=self.config)
        self.chat = LeanChatService(config_service=self.config)
        
        # Inicializar Módulo
        self.module = MediaGeneratorModule(
            chat_service=self.chat,
            config_service=self.config,
            style_service=self.style,
            data_service=self.data
        )
        
        self._setup_routes()
        self._setup_cors()
        self._mount_statics()

    def _setup_cors(self):
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    def _mount_statics(self):
        # Montar la carpeta de output del módulo
        if os.path.exists(self.module.output_root):
            print(f"[MediaAPI] Mount output: {self.module.output_root}")
            self.app.mount("/output", StaticFiles(directory=self.module.output_root), name="output")

    def _setup_routes(self):
        @self.app.get("/")
        async def root():
            return {"status": "online", "service": "ASIMOD Media Generator API"}

        @self.app.get("/v1/status")
        async def get_status():
            return {
                "module": self.module.id,
                "output_root": self.module.output_root,
                "last_provider": self.config.get("last_provider"),
                "comfyui_defaults": self.config.get("comfyui_defaults")
            }

        @self.app.post("/v1/generate")
        async def generate(req: GenerateRequest):
            """
            Punto de entrada principal para generación de medios.
            """
            try:
                result = await self.module.handle_generate_from_web(
                    prompt=req.prompt,
                    mode=req.mode,
                    params=req.params
                )
                
                # Ajustar las URLs para que apunten a este servidor localmente
                if result.get("status") == "success" and "url" in result:
                    # En el core la URL es /v1/modules/media_generator/output/...
                    # Aquí la montamos directamente en /output/
                    result["url"] = result["url"].replace(f"/v1/modules/{self.module.id}/output/", "/output/")
                
                return result
            except Exception as e:
                import traceback
                traceback.print_exc()
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.get("/v1/workflows")
        async def list_workflows():
            # Reutilizar el escaneo de workflows del módulo o de la API Core
            # Por ahora, simplemente devolvemos lo que el módulo encuentre en su carpeta
            from pathlib import Path
            base_dir = Path(os.path.dirname(self.module.__file__)) / "workflows"
            
            if not base_dir.exists(): return {"workflows": {}}
            
            workflows = {}
            def scan_dir(path: Path, base_rel=""):
                results = {}
                try:
                    items = list(path.iterdir())
                    direct_files = [f.name for f in items if f.is_file() and f.suffix == ".json"]
                    if direct_files:
                        key = base_rel if base_rel else "root"
                        results[key] = direct_files
                    
                    for item in items:
                        if item.is_dir():
                            sub_rel = f"{base_rel}/{item.name}" if base_rel else item.name
                            results.update(scan_dir(item, sub_rel))
                except: pass
                return results

            for sub in ["simple", "compuesta", "audio", "video", "3d"]:
                sub_path = base_dir / sub
                if not sub_path.exists(): continue
                key = "imagen" if sub == "simple" else sub
                workflows[key] = scan_dir(sub_path)
            
            return {"workflows": workflows}
