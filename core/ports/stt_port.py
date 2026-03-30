from abc import ABC, abstractmethod

class STTPort(ABC):
    """
    Abstracción para motores de Reconocimiento de Voz (Speech-to-Text).
    """
    @abstractmethod
    def transcribe(self, audio_path: str) -> str:
        """
        Transcribe un archivo de audio a texto.
        """
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Nombre del proveedor (Whisper, etc)."""
        pass
