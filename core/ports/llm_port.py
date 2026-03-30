from abc import ABC, abstractmethod
from typing import List

class LLMPort(ABC):
    """
    Abstracción para cualquier motor de lenguaje (Ollama, OpenAI, etc).
    Esto permite que la UI no sepa con qué API está hablando.
    """
    @abstractmethod
    def generate_chat(self, history: List[dict], system_prompt: str, model: str, images: list = None) -> str:
        """
        Envía un historial de conversación y un prompt de sistema, 
        retornando la respuesta del asistente.
        """
        pass

    @abstractmethod
    def list_models(self) -> List[str]:
        """Retorna una lista de modelos disponibles para este proveedor."""
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Nombre amigable del proveedor."""
        pass
