import asyncio
import os
from typing import List, Dict
from core.ports.voice_port import VoicePort

class EdgeVoiceAdapter(VoicePort):
    """
    Adaptador para Microsoft Edge TTS (Neural).
    """
    # Voces neurales curadas en español
    _VOICES = [
        {"id": "es-MX-DaliaNeural", "name": "Dalia (México)"},
        {"id": "es-MX-JorgeNeural", "name": "Jorge (México)"},
        {"id": "es-ES-ElviraNeural", "name": "Elvira (España)"},
        {"id": "es-ES-AlvaroNeural", "name": "Álvaro (España)"},
        {"id": "es-US-PalomaNeural", "name": "Paloma (USA)"},
        {"id": "es-US-AlonsoNeural", "name": "Alonso (USA)"}
    ]

    def __init__(self):
        pass

    @property
    def name(self) -> str:
        return "Edge TTS"

    def list_voices(self) -> List[Dict[str, str]]:
        return self._VOICES

    def generate(self, text: str, output_path: str, voice_id: str = None) -> bool:
        # Usar voz por defecto si no se pasa ID
        voice = voice_id if voice_id else self._VOICES[3]["id"] # Álvaro por defecto
        
        try:
            import edge_tts
            
            async def _save():
                communicate = edge_tts.Communicate(text, voice)
                await communicate.save(output_path)
            
            asyncio.run(_save())
            return os.path.exists(output_path)
        except Exception as e:
            print(f"Error en EdgeTTS: {e}")
            return False
