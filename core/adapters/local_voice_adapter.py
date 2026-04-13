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

    async def generate(self, text: str, output_path: str, voice_id: str = None) -> bool:
        import asyncio
        return await asyncio.to_thread(self._generate_sync, text, output_path, voice_id)

    def _generate_sync(self, text: str, output_path: str, voice_id: str = None) -> bool:
        try:
            import pyttsx3
            engine = pyttsx3.init()
            
            # Validar si el ID de voz existe en el sistema local
            voices = engine.getProperty('voices')
            supported_ids = [v.id for v in voices]
            
            if voice_id and voice_id in supported_ids:
                engine.setProperty('voice', voice_id)
            else:
                if voice_id: print(f"[LocalVoice] Voice ID '{voice_id}' not found. Using system default.")
            
            engine.save_to_file(text, output_path)
            engine.runAndWait()
            # Una pequeña pausa para asegurar que el archivo se ha cerrado
            import time
            time.sleep(0.1)
            return os.path.exists(output_path)
        except Exception as e:
            print(f"Error en LocalTTS: {e}")
            return False
