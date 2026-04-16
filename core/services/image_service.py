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
        Escanea la estructura de carpetas de workflows recursivamente.
        Retorna un diccionario donde cada clave es una ruta de carpeta que contiene JSONs.
        """
        workflows = {}
        if not os.path.exists(base_path):
            return workflows

        def _recursive_scan(current_path, rel_prefix=""):
            # Buscar archivos JSON directos en esta carpeta
            json_files = [f for f in os.listdir(current_path) if f.endswith(".json")]
            if json_files:
                workflows[rel_prefix if rel_prefix else "root"] = [] # Inicializar
            
            # Buscar subcarpetas
            for entry in os.scandir(current_path):
                if entry.is_dir():
                    new_rel = os.path.join(rel_prefix, entry.name) if rel_prefix else entry.name
                    # Añadir la carpeta como un 'subtipo' para que aparezca en el select de la UI
                    if rel_prefix: # Es una sub-sub carpeta
                        if rel_prefix not in workflows: workflows[rel_prefix] = []
                        workflows[rel_prefix].append(entry.name)
                    else: # Es una categoría top-level (simple, compuesta, etc)
                        if entry.name not in workflows: workflows[entry.name] = []
                    
                    # Seguir bajando
                    _recursive_scan(entry.path, new_rel)

        _recursive_scan(base_path)
        return workflows

    def get_workflow_files(self, path: str) -> List[str]:
        """Retorna los archivos .json en una ruta de workflow específica."""
        if not os.path.exists(path):
            return []
        return [f for f in os.listdir(path) if f.endswith(".json")]
