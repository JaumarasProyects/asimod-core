from abc import ABC, abstractmethod
from typing import List

class LLMPort(ABC):
    """
    Abstracción para cualquier motor de lenguaje (Ollama, OpenAI, etc).
    Esto permite que la UI no sepa con qué API está hablando.
    """
    @abstractmethod
    async def generate_chat(self, history: List[dict], system_prompt: str, model: str, images: list = None, max_tokens: int = None, temperature: float = None) -> str:
        """
        Envía un historial de conversación y un prompt de sistema, 
        retornando la respuesta del asistente.
        """
        pass

    @abstractmethod
    async def generate_chat_stream(self, history: List[dict], system_prompt: str, model: str, images: list = None, max_tokens: int = None, temperature: float = None):
        """
        Generador asíncrono que envía la respuesta del modelo token a token.
        """
        yield ""

    @abstractmethod
    async def list_models(self) -> List[str]:
        """Retorna una lista de modelos disponibles para este proveedor."""
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Nombre amigable del proveedor."""
        pass
