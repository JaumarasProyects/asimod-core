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
                            # Asegurar rutas relativas para el frontend
                            if "avatar" in data:
                                if data["avatar"].get("idle"):
                                    data["avatar"]["idle_url"] = f"/Resources/Characters/{entry}/idle.png"
                                if data["avatar"].get("talking"):
                                    data["avatar"]["talking_url"] = f"/Resources/Characters/{entry}/idle.png" # Por ahora igual
                            characters.append(data)
                    except Exception as e:
                        print(f"[CharacterService] Error cargando {entry}: {e}")
        return characters

    def get_character(self, char_id: str) -> dict:
        """Busca un personaje por su ID o Nombre de carpeta."""
        chars = self.list_characters()
        for c in chars:
            if c["id"] == char_id or c["name"] == char_id:
                return c
        return None
