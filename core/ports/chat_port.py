from abc import ABC, abstractmethod
from typing import List
from core.models import ChatMessage

class ChatPort(ABC):
    """
    Interfaz que define cómo debe comportarse un servicio de chat.
    Esta clase es 'agnóstica' a la UI (PyQt) y a la implementación (Ollama/OpenAI).
    """
    @abstractmethod
    async def send_message(self, text: str, model: str = None, images: list = None, silent: bool = False, max_tokens: int = None, temperature: float = None, system_prompt: str = None) -> dict:
        """Envía un mensaje con contexto visual opcional y retorna un dict enriquecido."""
        pass

    @abstractmethod
    def get_history(self) -> List[ChatMessage]:
        """Obtiene el historial de la conversación."""
        pass
