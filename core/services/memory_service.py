import os
import json
from datetime import datetime
from pathlib import Path

class MemoryService:
    """
    Servicio encargado de la persistencia de hilos de conversación y perfiles de personaje.
    Almacena cada hilo como un archivo JSON en la carpeta 'conversations/'.
    """
    def __init__(self, base_dir=None):
        if base_dir is None:
            # Subir 3 niveles desde core/services/memory_service.py para llegar al root
            base_dir = Path(__file__).parent.parent.parent
            
        self.conv_dir = os.path.join(base_dir, "conversations")
        if not os.path.exists(self.conv_dir):
            os.makedirs(self.conv_dir)
            
        self.active_thread = "None"
        self.data = self._get_empty_thread()

    def _get_empty_thread(self):
        return {
            "name": "Asimod",
            "personality": "Asistente servicial y educado.",
            "character_history": "Eres un asistente virtual avanzado diseñado para ayudar al usuario.",
            "voice_provider": "",
            "voice_id": "",
            "avatar": {
                "idle": "Resources/logoAzul.png"
            },
            "video": {
                "idle": "",
                "talking": ""
            },
            "history": []
        }

    def list_threads(self) -> list:
        """Lista todos los archivos JSON en la carpeta de conversaciones."""
        files = [f for f in os.listdir(self.conv_dir) if f.endswith(".json")]
        # Retornar nombres sin la extensión .json, ordenados por fecha
        return sorted([f[:-5] for f in files], reverse=True)

    def load_thread(self, thread_id: str):
        """Carga un hilo específico desde el disco."""
        if thread_id == "None":
            self.active_thread = "None"
            self.data = self._get_empty_thread()
            return self.data
            
        file_path = os.path.join(self.conv_dir, f"{thread_id}.json")
        if os.path.exists(file_path):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    self.data = json.load(f)
                self.active_thread = thread_id
                return self.data
            except Exception as e:
                print(f"Error cargando memoria {thread_id}: {e}")
        
        # Si no existe o falla, cargamos vacío
        self.active_thread = "None"
        self.data = self._get_empty_thread()
        return self.data

    def create_new_thread(self, thread_id: str = None) -> str:
        """Crea un hilo nuevo con un ID específico o basado en la fecha."""
        if not thread_id:
            now = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            thread_id = f"Thread_{now}"
            
        # Inicializar con valores por defecto
        self.data = self._get_empty_thread()
        self.active_thread = thread_id
        self.save_current()
        return thread_id

    def save_current(self):
        """Guarda la memoria activa en el disco."""
        if self.active_thread == "None":
            return
            
        file_path = os.path.join(self.conv_dir, f"{self.active_thread}.json")
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"Error guardando memoria {self.active_thread}: {e}")

    def add_message(self, role: str, content: str):
        """Añade un mensaje al historial y guarda automáticamente."""
        self.data["history"].append({"role": role, "content": content})
        self.save_current()

    def update_profile(self, name: str = None, personality: str = None, history: str = None, 
                       voice_id: str = None, voice_provider: str = None, avatar: dict = None,
                       video: dict = None):
        """Actualiza el perfil del asistente en la memoria activa."""
        if name is not None: self.data["name"] = name
        if personality is not None: self.data["personality"] = personality
        if history is not None: self.data["character_history"] = history
        if voice_id is not None: self.data["voice_id"] = voice_id
        if voice_provider is not None: self.data["voice_provider"] = voice_provider
        if avatar is not None: self.data["avatar"] = avatar
        if video is not None: self.data["video"] = video
        self.save_current()

    def get_context(self) -> list:
        """Retorna el historial para pasar al LLM."""
        return self.data.get("history", [])

    def get_system_prompt(self, locale_service=None) -> str:
        """Construye el system prompt basado en el perfil actual."""
        name = self.data.get("name", "Asimod")
        pers = self.data.get("personality", "")
        hist = self.data.get("character_history", "")
        
        lang_instruction = ""
        lang = "es"
        if locale_service:
            lang = locale_service.get_current_language()
            if lang == "es":
                lang_instruction = "Responde siempre en español."
            elif lang == "en":
                lang_instruction = "Always respond in English."
        
        prompt = f"Tu nombre es {name}. \n"
        if pers: prompt += f"Tu personalidad: {pers} \n"
        if hist: prompt += f"Tu historia/contexto: {hist} \n"
        if lang_instruction:
            prompt += f"\n{lang_instruction}"
        
        if lang == "es":
            prompt += "\nResponde siempre manteniendo este personaje."
        elif lang == "en":
            prompt += "\nAlways respond maintaining this character."
        
        return prompt
    def create_named_thread(self, thread_id: str):
        """
        Crea un hilo nuevo con un ID explícito si no existe.
        """
        all_threads = self.list_threads()

        if thread_id in all_threads:
            return thread_id

        self.active_thread = thread_id
        self.data = self._get_empty_thread()
        self.save_current()
        return thread_id

    def get_thread_data(self, thread_id: str) -> dict:
        """Obtiene los datos de un hilo sin modificar el activo."""
        if thread_id == "None":
            return self._get_empty_thread()
        
        file_path = os.path.join(self.conv_dir, f"{thread_id}.json")
        if os.path.exists(file_path):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print(f"Error cargando hilo {thread_id}: {e}")
        return None

    def edit_message_in_thread(self, thread_id: str, message_index: int, new_content: str) -> dict:
        """Edita un mensaje específico en un hilo."""
        target_data = self.get_thread_data(thread_id)
        if not target_data:
            return {"status": "error", "message": "Thread not found"}
        
        history = target_data.get("history", [])
        if message_index < 0 or message_index >= len(history):
            return {"status": "error", "message": "Invalid message index"}
        
        history[message_index]["content"] = new_content
        target_data["history"] = history
        
        file_path = os.path.join(self.conv_dir, f"{thread_id}.json")
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(target_data, f, indent=4, ensure_ascii=False)
        
        return {"status": "success", "message": f"Message {message_index} updated"}

    def delete_message_in_thread(self, thread_id: str, message_index: int) -> dict:
        """Borra un mensaje específico en un hilo."""
        target_data = self.get_thread_data(thread_id)
        if not target_data:
            return {"status": "error", "message": "Thread not found"}
        
        history = target_data.get("history", [])
        if message_index < 0 or message_index >= len(history):
            return {"status": "error", "message": "Invalid message index"}
        
        del history[message_index]
        target_data["history"] = history
        
        file_path = os.path.join(self.conv_dir, f"{thread_id}.json")
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(target_data, f, indent=4, ensure_ascii=False)
        
        return {"status": "success", "message": f"Message {message_index} deleted"}

    def add_message_to_thread(self, thread_id: str, role: str, content: str) -> dict:
        """Añade un mensaje a un hilo."""
        target_data = self.get_thread_data(thread_id)
        if not target_data:
            return {"status": "error", "message": "Thread not found"}
        
        target_data["history"].append({"role": role, "content": content})
        
        file_path = os.path.join(self.conv_dir, f"{thread_id}.json")
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(target_data, f, indent=4, ensure_ascii=False)
        
        return {"status": "success", "message": "Message added"}

    def clear_thread_history(self, thread_id: str) -> dict:
        """Limpia el historial de un hilo."""
        target_data = self.get_thread_data(thread_id)
        if not target_data:
            return {"status": "error", "message": "Thread not found"}
        
        target_data["history"] = []
        
        file_path = os.path.join(self.conv_dir, f"{thread_id}.json")
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(target_data, f, indent=4, ensure_ascii=False)
        
        return {"status": "success", "message": "History cleared"}

    def delete_thread(self, thread_id: str) -> dict:
        """Borra un hilo completamente."""
        if thread_id == "None":
            return {"status": "error", "message": "Cannot delete None thread"}
        
        file_path = os.path.join(self.conv_dir, f"{thread_id}.json")
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
                return {"status": "success", "message": f"Thread {thread_id} deleted"}
            except Exception as e:
                return {"status": "error", "message": str(e)}
        
        return {"status": "error", "message": "Thread not found"}

    def update_thread_profile(self, thread_id: str, name: str = None, personality: str = None, character_history: str = None, voice_id: str = None, voice_provider: str = None) -> dict:
        """Actualiza el perfil de un hilo sin modificar el activo."""
        target_data = self.get_thread_data(thread_id)
        if not target_data:
            return {"status": "error", "message": "Thread not found"}
        
        if name is not None: target_data["name"] = name
        if personality is not None: target_data["personality"] = personality
        if character_history is not None: target_data["character_history"] = character_history
        if voice_id is not None: target_data["voice_id"] = voice_id
        if voice_provider is not None: target_data["voice_provider"] = voice_provider
        
        file_path = os.path.join(self.conv_dir, f"{thread_id}.json")
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(target_data, f, indent=4, ensure_ascii=False)
        
        return {"status": "success", "message": "Profile updated"}