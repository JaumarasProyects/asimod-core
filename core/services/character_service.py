import os
import json
from pathlib import Path

class CharacterService:
    """
    Servicio para gestionar el repositorio global de personajes (Resources/Characters).
    Permite listar, cargar y registrar personajes compartidos entre módulos.
    """
    def __init__(self, base_dir=None):
        if base_dir is None:
            base_dir = Path(__file__).parent.parent.parent
            
        self.reg_dir = os.path.join(base_dir, "Resources", "Characters")
        if not os.path.exists(self.reg_dir):
            os.makedirs(self.reg_dir, exist_ok=True)

    def list_characters(self) -> list:
        """Lista todos los personajes disponibles en el repositorio."""
        if not os.path.exists(self.reg_dir):
            return []
            
        characters = []
        for entry in os.listdir(self.reg_dir):
            char_path = os.path.join(self.reg_dir, entry)
            if os.path.isdir(char_path):
                json_file = os.path.join(char_path, "character.json")
                if os.path.exists(json_file):
                    try:
                        with open(json_file, "r", encoding="utf-8") as f:
                            data = json.load(f)
                            # Asegurar rutas para el frontend (URL Mapping)
                            def to_url(path):
                                if not path: return None
                                if path.startswith("http"): return path
                                return "/" + path.replace("\\", "/")

                            if "avatar" in data and isinstance(data["avatar"], dict):
                                # Usar list() para evitar RuntimeError al modificar el dict durante la iteración
                                for k, v in list(data["avatar"].items()):
                                    data["avatar"][f"{k}_url"] = to_url(v)
                            
                            if "video" in data and isinstance(data["video"], dict):
                                for k, v in list(data["video"].items()):
                                    data["video"][f"{k}_url"] = to_url(v)
                            characters.append(data)
                    except Exception as e:
                        print(f"[CharacterService] Error cargando {entry}: {e}")
        return characters

    def get_character(self, char_id: str) -> dict:
        """Busca un personaje por su ID o Nombre de carpeta."""
        chars = self.list_characters()
        for c in chars:
            if c.get("id") == char_id or c.get("name") == char_id:
                return c
        return None

    def save_character(self, char_data: dict) -> bool:
        """Guarda los datos de un personaje en su archivo JSON correspondiente."""
        char_id = char_data.get("id")
        char_name = char_data.get("name")
        
        # Buscar la carpeta
        folder_name = char_name
        for char in '<>:"/\\|?*':
            folder_name = folder_name.replace(char, "_")
            
        char_path = os.path.join(self.reg_dir, folder_name)
        json_file = os.path.join(char_path, "character.json")
        
        try:
            # Limpiar URLs temporales del frontend antes de guardar si existieran
            clean_data = char_data.copy()
            if "avatar" in clean_data:
                clean_data["avatar"] = {k: v for k, v in clean_data["avatar"].items() if not k.endswith("_url")}
            if "video" in clean_data:
                clean_data["video"] = {k: v for k, v in clean_data["video"].items() if not k.endswith("_url")}
                
            with open(json_file, "w", encoding="utf-8") as f:
                json.dump(clean_data, f, indent=4, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"[CharacterService] Error guardando {char_id}: {e}")
            return False

    def update_character(self, char_id: str, patch_data: dict) -> bool:
        """Actualiza campos específicos de un personaje."""
        char_data = self.get_character(char_id)
        if not char_data: return False
        
        for k, v in patch_data.items():
            char_data[k] = v
            
        return self.save_character(char_data)
