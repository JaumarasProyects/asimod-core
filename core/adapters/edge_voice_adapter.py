import asyncio
import os
from typing import List, Dict
from core.ports.voice_port import VoicePort

class EdgeVoiceAdapter(VoicePort):
    """
    Adaptador para Microsoft Edge TTS (Neural).
    """
    # Voces neurales curadas (Español e Internacionales)
    _VOICES = [
        {"id": "es-MX-DaliaNeural", "name": "Dalia (México) - Femenina"},
        {"id": "es-MX-JorgeNeural", "name": "Jorge (México) - Masculina"},
        {"id": "es-ES-ElviraNeural", "name": "Elvira (España) - Femenina"},
        {"id": "es-ES-AlvaroNeural", "name": "Álvaro (España) - Masculina"},
        {"id": "es-US-PalomaNeural", "name": "Paloma (USA Español) - Femenina"},
        {"id": "es-US-AlonsoNeural", "name": "Alonso (USA Español) - Masculina"},
        {"id": "en-GB-SoniaNeural", "name": "Sonia (UK) - Femenina (Recomendada Lea)"},
        {"id": "en-GB-RyanNeural", "name": "Ryan (UK) - Masculina"},
        {"id": "en-US-AvaNeural", "name": "Ava (USA) - Femenina"},
        {"id": "en-US-AndrewNeural", "name": "Andrew (USA) - Masculina"},
        {"id": "fr-FR-DeniseNeural", "name": "Denise (Francia) - Femenina"}
    ]

    def __init__(self):
        pass

    @property
    def name(self) -> str:
        return "Edge TTS"

    def list_voices(self) -> List[Dict[str, str]]:
        return self._VOICES

    async def generate(self, text: str, output_path: str, voice_id: str = None) -> bool:
        # 1. Validar ID de voz
        default_voice = self._VOICES[3]["id"] # Álvaro por defecto
        
        # Si no viene voice_id, o es vacío, o no está en nuestra lista de soportados... usar default
        voice_to_use = voice_id
        if not voice_to_use or voice_to_use == "None":
            voice_to_use = default_voice
        else:
            # Verificar si el ID existe en nuestra lista curada
            supported_ids = [v["id"] for v in self._VOICES]
            if voice_to_use not in supported_ids:
                print(f"[EdgeVoice] Voice ID '{voice_to_use}' not supported. Falling back to {default_voice}.")
                voice_to_use = default_voice
        
        try:
            import edge_tts
            communicate = edge_tts.Communicate(text, voice_to_use)
            await communicate.save(output_path)
            return os.path.exists(output_path)
        except Exception as e:
            print(f"Error en EdgeTTS con voz {voice_to_use}: {e}")
            return False
