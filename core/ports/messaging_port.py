from abc import ABC, abstractmethod
from typing import Dict, Optional


class MessagingPort(ABC):
    """
    Interfaz abstracta para adaptadores de mensajería (WhatsApp, Telegram, Discord, Email).
    Implementa el patrón Adapter para soportar múltiples plataformas de entrada/salida.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Nombre del proveedor de mensajería."""
        pass

    @abstractmethod
    async def receive_message(self, message_data: dict) -> Optional[Dict]:
        """
        Procesa un mensaje entrante del webhook.
        Retorna dict con {user_id, text, media_url, media_type} o None si no es procesable.
        """
        pass

    @abstractmethod
    async def send_text(self, user_id: str, text: str) -> bool:
        """Envía un mensaje de texto al usuario."""
        pass

    @abstractmethod
    async def send_audio(self, user_id: str, audio_path: str, caption: str = None) -> bool:
        """Envía un archivo de audio (voice note) al usuario."""
        pass

    @abstractmethod
    async def send_image(self, user_id: str, image_path: str, caption: str = None) -> bool:
        """Envía una imagen al usuario."""
        pass

    @abstractmethod
    def get_webhook_verify_token(self) -> str:
        """Token para verificar el webhook (GET request)."""
        pass

    def format_outgoing_message(self, text: str) -> str:
        """Formatea el mensaje de salida (opcional, para limpiar/emojis)."""
        return text
