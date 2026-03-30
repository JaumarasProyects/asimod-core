from abc import ABC, abstractmethod
from typing import List

class LLMPort(ABC):
    """
    Abstracción para cualquier motor de lenguaje (Ollama, OpenAI, etc).
    Esto permite que la UI no sepa con qué API está hablando.
    """
    @abstractmethod
    def generate_response(self, prompt: str, model: str) -> str:
        """Envía un prompt y retorna la respuesta del modelo."""
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
