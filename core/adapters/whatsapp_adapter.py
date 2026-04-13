import os
import httpx
import asyncio
from typing import Dict, Optional
from core.ports.messaging_port import MessagingPort


class WhatsAppAdapter(MessagingPort):
    """
    Adaptador para WhatsApp Business API (Meta Cloud API).
    Gestiona entrada y salida de mensajes de WhatsApp de forma asíncrona.
    """

    def __init__(self, phone_number_id: str, access_token: str, verify_token: str = None):
        self.phone_number_id = phone_number_id
        self.access_token = access_token
        self.verify_token = verify_token or "asimod_verify_token"
        self.api_url = f"https://graph.facebook.com/v22.0/{phone_number_id}"

    @property
    def name(self) -> str:
        return "WhatsApp"

    def get_webhook_verify_token(self) -> str:
        return self.verify_token

    async def receive_message(self, message_data: dict) -> Optional[Dict]:
        """
        Parsea el webhook de Meta y extrae el mensaje del usuario.
        """
        try:
            entry = message_data.get("entry", [{}])[0]
            changes = entry.get("changes", [{}])[0]
            value = changes.get("value", {})

            if "messages" not in value:
                return None

            messages = value.get("messages", [{}])[0]
            from_num = messages.get("from")
            msg_type = messages.get("type")

            if msg_type == "text":
                text = messages.get("text", {}).get("body", "")
                return {
                    "user_id": from_num,
                    "text": text,
                    "media_url": None,
                    "media_type": None
                }

            elif msg_type == "audio":
                audio = messages.get("audio", {})
                media_id = audio.get("id")
                media_url = await self._get_media_url(media_id) if media_id else None
                return {
                    "user_id": from_num,
                    "text": None,
                    "media_url": media_url,
                    "media_type": "audio"
                }

            elif msg_type == "image":
                image = messages.get("image", {})
                media_id = image.get("id")
                media_url = await self._get_media_url(media_id) if media_id else None
                caption = image.get("caption")
                return {
                    "user_id": from_num,
                    "text": caption,
                    "media_url": media_url,
                    "media_type": "image"
                }

            elif msg_type == "voice":
                audio = messages.get("audio", {})
                media_id = audio.get("id")
                media_url = await self._get_media_url(media_id) if media_id else None
                return {
                    "user_id": from_num,
                    "text": None,
                    "media_url": media_url,
                    "media_type": "voice"
                }

            return None

        except Exception as e:
            print(f"[WhatsAppAdapter] Error parsing message: {e}")
            return None

    async def _get_media_url(self, media_id: str) -> Optional[str]:
        """Obtiene la URL de descarga del media."""
        try:
            url = f"https://graph.facebook.com/v22.0/{media_id}"
            headers = {"Authorization": f"Bearer {self.access_token}"}
            async with httpx.AsyncClient() as client:
                resp = await client.get(url, headers=headers, timeout=10.0)
                if resp.status_code == 200:
                    return resp.json().get("url")
        except Exception as e:
            print(f"[WhatsAppAdapter] Error getting media URL: {e}")
        return None

    async def send_text(self, user_id: str, text: str) -> bool:
        """Envía un mensaje de texto a WhatsApp."""
        try:
            url = f"{self.api_url}/messages"
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }
            payload = {
                "messaging_product": "whatsapp",
                "messaging_type": "RESPONSE",
                "to": user_id,
                "text": {"body": text}
            }
            async with httpx.AsyncClient() as client:
                resp = await client.post(url, json=payload, headers=headers, timeout=30.0)
                return resp.status_code == 200

        except Exception as e:
            print(f"[WhatsAppAdapter] Error sending text: {e}")
            return False

    async def send_template(self, user_id: str, template_name: str, language_code: str = "en_US") -> bool:
        """Envía un mensaje de template (requerido para iniciar conversación)."""
        try:
            url = f"{self.api_url}/messages"
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }
            payload = {
                "messaging_product": "whatsapp",
                "to": user_id,
                "type": "template",
                "template": {
                    "name": template_name,
                    "language": {"code": language_code}
                }
            }
            async with httpx.AsyncClient() as client:
                resp = await client.post(url, json=payload, headers=headers, timeout=30.0)
                return resp.status_code == 200

        except Exception as e:
            print(f"[WhatsAppAdapter] Error sending template: {e}")
            return False

    async def send_audio(self, user_id: str, audio_path: str, caption: str = None) -> bool:
        """Envía un audio (voice note) a WhatsApp."""
        try:
            media_id = await self._upload_media(audio_path)
            if not media_id:
                return False

            url = f"{self.api_url}/messages"
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }
            payload = {
                "messaging_product": "whatsapp",
                "messaging_type": "RESPONSE",
                "to": user_id,
                "audio": {"id": media_id}
            }
            async with httpx.AsyncClient() as client:
                resp = await client.post(url, json=payload, headers=headers, timeout=30.0)
                return resp.status_code == 200

        except Exception as e:
            print(f"[WhatsAppAdapter] Error sending audio: {e}")
            return False

    async def send_image(self, user_id: str, image_path: str, caption: str = None) -> bool:
        """Envía una imagen a WhatsApp."""
        try:
            media_id = await self._upload_media(image_path)
            if not media_id:
                return False

            url = f"{self.api_url}/messages"
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }
            payload = {
                "messaging_product": "whatsapp",
                "messaging_type": "RESPONSE",
                "to": user_id,
                "image": {"id": media_id}
            }
            if caption:
                payload["image"]["caption"] = caption

            async with httpx.AsyncClient() as client:
                resp = await client.post(url, json=payload, headers=headers, timeout=30.0)
                return resp.status_code == 200

        except Exception as e:
            print(f"[WhatsAppAdapter] Error sending image: {e}")
            return False

    async def _upload_media(self, file_path: str) -> Optional[str]:
        """Sube un archivo a Meta y retorna el media_id."""
        try:
            url = f"https://graph.facebook.com/v22.0/{self.phone_number_id}/media"
            headers = {"Authorization": f"Bearer {self.access_token}"}

            with open(file_path, "rb") as f:
                files = {"file": f}
                data = {"type": "audio/ogg"}
                async with httpx.AsyncClient() as client:
                    resp = await client.post(url, files=files, data=data, headers=headers, timeout=60.0)

            if resp.status_code == 200:
                return resp.json().get("id")
        except Exception as e:
            print(f"[WhatsAppAdapter] Error uploading media: {e}")
        return None
