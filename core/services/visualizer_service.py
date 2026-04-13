import os
import sys
import importlib.util
import inspect
from core.ports.visualizer_port import VisualizerPort

class VisualizerService:
    """
    Gestor de visualizadores modulares. Permite cargar diferentes vistas de audio
    dinámicamente desde una carpeta de plugins.
    """
    def __init__(self, config_service):
        self.config = config_service
        self.visualizers_dir = self.config.get("visualizers_path", "visualizers")
        self.loaded_visualizers = {} # ID -> Class
        
        # Añadir la carpeta de visualizadores al path si no está
        abs_path = os.path.abspath(self.visualizers_dir)
        if abs_path not in sys.path:
            sys.path.append(abs_path)
            
        # Asegurar que la carpeta existe
        if not os.path.exists(self.visualizers_dir):
            os.makedirs(self.visualizers_dir)
            
        self.scan_visualizers()

    def scan_visualizers(self):
        """Escanea la carpeta de visualizadores en busca de plugins."""
        self.loaded_visualizers = {}
        if not os.path.exists(self.visualizers_dir):
            return

        for entry in os.listdir(self.visualizers_dir):
            full_path = os.path.join(self.visualizers_dir, entry)
            module_file = None
            
            # Detectar si es una carpeta (paquete) o archivo .py
            if os.path.isdir(full_path):
                init_path = os.path.join(full_path, "__init__.py")
                if os.path.exists(init_path):
                    module_file = init_path
            elif entry.endswith(".py") and entry != "__init__.py":
                module_file = full_path

            if module_file:
                try:
                    module_name = entry.replace(".py", "")
                    spec = importlib.util.spec_from_file_location(module_name, module_file)
                    mod = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(mod)

                    # Buscar cualquier clase que implemente VisualizerPort
                    for name, obj in inspect.getmembers(mod):
                        if (inspect.isclass(obj) and 
                            issubclass(obj, VisualizerPort) and 
                            obj is not VisualizerPort):
                            
                            # Usamos el nombre del objeto o el del módulo como ID
                            v_id = entry.replace(".py", "").lower()
                            self.loaded_visualizers[v_id] = obj
                            print(f"[VisualizerService] Visualizador cargado: {v_id}")
                except Exception as e:
                    print(f"[VisualizerService] Error cargando {entry}: {e}")

    def get_visualizer_list(self):
        """Retorna una lista de los IDs de los visualizadores disponibles."""
        return list(self.loaded_visualizers.keys())

    def get_instance(self, v_id, parent, width=600, height=60):
        """Retorna una instancia del visualizador solicitado."""
        if v_id in self.loaded_visualizers:
            return self.loaded_visualizers[v_id](parent, width, height)
        return None
