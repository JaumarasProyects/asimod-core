from abc import ABC, abstractmethod
from typing import List, Optional

class ImagePort(ABC):
    """
    Abstracción para motores de generación de imagen.
    """
    @abstractmethod
    async def generate_image(self, prompt: str, resolution: str = "1024x1024", **kwargs) -> str:
        """
        Genera una imagen y retorna la ruta del archivo generado o la URL.
        """
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Nombre amigable del motor."""
        pass
