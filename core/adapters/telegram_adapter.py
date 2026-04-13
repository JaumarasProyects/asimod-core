import os
import httpx
from typing import Dict, Optional
from core.ports.messaging_port import MessagingPort


class TelegramAdapter(MessagingPort):
    """
    Adaptador para Telegram Bot API.
    Gestiona entrada y salida de mensajes de Telegram de forma asíncrona.
    """

    def __init__(self, bot_token: str):
        self.bot_token = bot_token
        self.api_url = f"https://api.telegram.org/bot{bot_token}"

    @property
    def name(self) -> str:
        return "Telegram"

    def get_webhook_verify_token(self) -> str:
        return self.bot_token

    async def receive_message(self, message_data: dict) -> Optional[Dict]:
        """
        Parsea el webhook de Telegram y extrae el mensaje del usuario.
        """
        try:
            message = message_data.get("message") or message_data.get("edited_message")
            if not message:
                return None

            chat = message.get("chat", {})
            user = message.get("from", {})
            text = message.get("text")
            chat_id = str(chat.get("id"))

            if text:
                return {
                    "user_id": chat_id,
                    "text": text,
                    "media_url": None,
                    "media_type": None
                }

            if "voice" in message:
                voice = message.get("voice", {})
                file_id = voice.get("file_id")
                return {
                    "user_id": chat_id,
                    "text": None,
                    "media_url": file_id,
                    "media_type": "voice"
                }

            if "audio" in message:
                audio = message.get("audio", {})
                file_id = audio.get("file_id")
                return {
                    "user_id": chat_id,
                    "text": audio.get("caption"),
                    "media_url": file_id,
                    "media_type": "audio"
                }

            if "photo" in message:
                photo = message.get("photo", [-1])
                file_id = photo[-1].get("file_id") if photo else None
                return {
                    "user_id": chat_id,
                    "text": message.get("caption"),
                    "media_url": file_id,
                    "media_type": "photo"
                }

            return None

        except Exception as e:
            print(f"[TelegramAdapter] Error parsing message: {e}")
            return None

    async def send_text(self, user_id: str, text: str) -> bool:
        """Envía un mensaje de texto a Telegram."""
        try:
            url = f"{self.api_url}/sendMessage"
            payload = {
                "chat_id": user_id,
                "text": text
            }
            async with httpx.AsyncClient() as client:
                resp = await client.post(url, json=payload, timeout=30.0)
                return resp.status_code == 200

        except Exception as e:
            print(f"[TelegramAdapter] Error sending text: {e}")
            return False

    async def send_audio(self, user_id: str, audio_path: str, caption: str = None) -> bool:
        """Envía un audio a Telegram."""
        try:
            url = f"{self.api_url}/sendAudio"
            with open(audio_path, "rb") as f:
                files = {"audio": f}
                data = {"chat_id": user_id}
                if caption:
                    data["caption"] = caption
                async with httpx.AsyncClient() as client:
                    resp = await client.post(url, files=files, data=data, timeout=60.0)
            return resp.status_code == 200

        except Exception as e:
            print(f"[TelegramAdapter] Error sending audio: {e}")
            return False

    async def send_image(self, user_id: str, image_path: str, caption: str = None) -> bool:
        """Envía una imagen a Telegram."""
        try:
            url = f"{self.api_url}/sendPhoto"
            with open(image_path, "rb") as f:
                files = {"photo": f}
                data = {"chat_id": user_id}
                if caption:
                    data["caption"] = caption
                async with httpx.AsyncClient() as client:
                    resp = await client.post(url, files=files, data=data, timeout=60.0)
            return resp.status_code == 200

        except Exception as e:
            print(f"[TelegramAdapter] Error sending image: {e}")
            return False

    async def _download_file(self, file_id: str) -> Optional[bytes]:
        """Descarga un archivo de Telegram."""
        try:
            url = f"{self.api_url}/getFile?file_id={file_id}"
            async with httpx.AsyncClient() as client:
                resp = await client.get(url, timeout=10.0)
                if resp.status_code == 200:
                    file_path = resp.json().get("result", {}).get("file_path")
                    if file_path:
                        dl_url = f"{self.api_url}/file/{file_path}"
                        resp_dl = await client.get(dl_url, timeout=60.0)
                        return resp_dl.content
        except Exception as e:
            print(f"[TelegramAdapter] Error downloading file: {e}")
        return None
