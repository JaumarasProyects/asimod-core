import os
from typing import List, Dict
from core.ports.voice_port import VoicePort

class LocalVoiceAdapter(VoicePort):
    """
    Adaptador para TTS Local usando 'pyttsx3'.
    """
    def __init__(self):
        pass

    @property
    def name(self) -> str:
        return "Local TTS"

    def list_voices(self) -> List[Dict[str, str]]:
        try:
            import pyttsx3
            engine = pyttsx3.init()
            voices = engine.getProperty('voices')
            return [{"id": v.id, "name": v.name} for v in voices]
        except Exception as e:
            print(f"Error listando voces locales: {e}")
            return [{"id": "0", "name": "Voz del sistema"}]

    def generate(self, text: str, output_path: str, voice_id: str = None) -> bool:
        try:
            import pyttsx3
            engine = pyttsx3.init()
            
            if voice_id:
                engine.setProperty('voice', voice_id)
            
            engine.save_to_file(text, output_path)
            engine.runAndWait()
            return os.path.exists(output_path)
        except Exception as e:
            print(f"Error en LocalTTS: {e}")
            return False
