from abc import ABC, abstractmethod
from typing import List
from core.models import ChatMessage

class ChatPort(ABC):
    """
    Interfaz que define cómo debe comportarse un servicio de chat.
    Esta clase es 'agnóstica' a la UI (PyQt) y a la implementación (Ollama/OpenAI).
    """
    @abstractmethod
    def send_message(self, message: str) -> str:
        """Envía un mensaje y retorna la respuesta."""
        pass

    @abstractmethod
    def get_history(self) -> List[ChatMessage]:
        """Obtiene el historial de la conversación."""
        pass
