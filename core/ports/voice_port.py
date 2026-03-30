from abc import ABC, abstractmethod
from typing import List, Dict

class VoicePort(ABC):
    """
    Abstracción para cualquier motor de Texto-a-Voz (TTS).
    """
    @abstractmethod
    def generate(self, text: str, output_path: str, voice_id: str = None) -> bool:
        """
        Genera un archivo de audio a partir de texto con una voz específica.
        Retorna True si tuvo éxito.
        """
        pass

    @abstractmethod
    def list_voices(self) -> List[Dict[str, str]]:
        """
        Retorna la lista de voces disponibles: [{"id": "...", "name": "..."}, ...]
        """
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Nombre del proveedor (Edge, Local, etc)."""
        pass
