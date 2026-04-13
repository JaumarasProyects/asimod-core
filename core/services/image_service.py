import os
from typing import List, Dict
from core.ports.image_port import ImagePort
from core.adapters.openai_image_adapter import OpenAIImageAdapter

class ImageService:
    """
    Servicio encargado de gestionar motores de generación de imagen (DALL-E, ComfyUI, etc).
    """
    def __init__(self, config_service):
        self.config = config_service
        self.adapters: Dict[str, ImagePort] = {}
        self._init_adapters()

    def _init_adapters(self):
        # OpenAI Image Adapter (DALL-E)
        openai_key = self.config.get("openai_key", "")
        self.adapters["DALL-E 3"] = OpenAIImageAdapter(api_key=openai_key)
        
        # ComfyUI Adapter (se inicializará bajo demanda o si el sistema es robusto)
        from core.adapters.comfyui_adapter import ComfyUIAdapter
        comfy_url = self.config.get("comfyui_url", "http://localhost:8188")
        self.adapters["ComfyUI"] = ComfyUIAdapter(base_url=comfy_url)

    def get_adapter(self, name: str) -> ImagePort:
        return self.adapters.get(name)

    def get_engines_list(self) -> List[str]:
        return list(self.adapters.keys())

    def scan_workflows(self, base_path: str) -> Dict[str, List[str]]:
        """
        Escanea la estructura de carpetas de workflows y retorna un diccionario jerárquico.
        Ejemplo: {"simple": ["text2img", "img2img"], "compuesta": []}
        """
        workflows = {}
        if not os.path.exists(base_path):
            return workflows

        for entry in os.scandir(base_path):
            if entry.is_dir():
                subfolders = [f.name for f in os.scandir(entry.path) if f.is_dir()]
                workflows[entry.name] = subfolders
        
        return workflows

    def get_workflow_files(self, path: str) -> List[str]:
        """Retorna los archivos .json en una ruta de workflow específica."""
        if not os.path.exists(path):
            return []
        return [f for f in os.listdir(path) if f.endswith(".json")]
