import httpx
import base64
import asyncio
from typing import List
from core.ports.llm_port import LLMPort

class GeminiAdapter(LLMPort):
    """
    Adaptador para Google Gemini con soporte multimodal asíncrono.
    """
    def __init__(self, api_key: str):
        self.api_key = api_key

    @property
    def name(self) -> str:
        return "Gemini"

    async def list_models(self) -> list:
        return ["gemini-2.0-flash", "gemini-1.5-flash", "gemini-1.5-pro"]

    def _encode_image(self, image_path):
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')

    async def generate_chat(self, history: list, system_prompt: str, model: str, images: list = None, max_tokens: int = None, temperature: float = None) -> str:
        if not self.api_key:
            return "Error: No se ha configurado la API Key de Gemini."
        
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model if model else 'gemini-2.0-flash'}:generateContent?key={self.api_key}"
            
            headers = {"Content-Type": "application/json"}
            
            contents = []
            for msg in history:
                role = "user" if msg["role"] == "user" else "model"
                contents.append({
                    "role": role,
                    "parts": [{"text": msg["content"]}]
                })

            if images and contents:
                 for img_path in images:
                    try:
                        # Nota: codificación de imagen es síncrona pero rápida (I/O local)
                        b64_data = self._encode_image(img_path)
                        contents[-1]["parts"].append({
                            "inline_data": {
                                "mime_type": "image/jpeg",
                                "data": b64_data
                            }
                        })
                    except Exception as e:
                        print(f"[Gemini] Error encoding image: {e}")

            payload = {
                "system_instruction": {
                    "parts": [{"text": system_prompt}]
                },
                "contents": contents
            }
            
            if max_tokens is not None:
                payload["max_tokens"] = max_tokens
            if temperature is not None:
                payload["temperature"] = temperature

            async with httpx.AsyncClient() as client:
                response = await client.post(url, headers=headers, json=payload, timeout=45.0)
            
            if response.status_code == 200:
                return response.json()["candidates"][0]["content"]["parts"][0]["text"]
            else:
                return f"Error Gemini {response.status_code}: {response.text}"
                
        except Exception as e:
            return f"Error de conexión con Gemini: {str(e)}"

    async def generate_response(self, prompt: str, model: str, images: list = None) -> str:
        """Versión simplificada para una sola consulta."""
        if not self.api_key:
            return "Error: No se ha configurado la Gemini API Key."

        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={self.api_key}"
            headers = {"Content-Type": "application/json"}
            
            parts = [{"text": prompt}]
            
            if images:
                for img_path in images:
                    try:
                        base64_image = self._encode_image(img_path)
                        parts.append({
                            "inline_data": {
                                "mime_type": "image/jpeg",
                                "data": base64_image
                            }
                        })
                    except Exception as img_err:
                        print(f"Error procesando imagen {img_path}: {img_err}")

            payload = {
                "contents": [{"parts": parts}]
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(url, headers=headers, json=payload, timeout=45.0)
            
            if response.status_code == 200:
                return response.json()["candidates"][0]["content"]["parts"][0]["text"]
            else:
                return f"Error Gemini: {response.status_code} - {response.text}"
        except Exception as e:
            return f"Error de conexión con Gemini: {str(e)}"
    
    async def generate_chat_stream(self, history: list, system_prompt: str, model: str, images: list = None, max_tokens: int = None, temperature: float = None):
        """Generador asíncrono para streaming con Gemini."""
        if not self.api_key:
            yield "Error: No se ha configurado la API Key de Gemini."
            return
            
        try:
            # Endpoint específico para streaming
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model if model else 'gemini-2.0-flash'}:streamGenerateContent?key={self.api_key}"
            headers = {"Content-Type": "application/json"}
            
            contents = []
            for msg in history:
                role = "user" if msg["role"] == "user" else "model"
                contents.append({"role": role, "parts": [{"text": msg["content"]}]})

            if images and contents:
                 for img_path in images:
                    try:
                        b64_data = self._encode_image(img_path)
                        contents[-1]["parts"].append({
                            "inline_data": { "mime_type": "image/jpeg", "data": b64_data }
                        })
                    except: continue

            payload = {
                "system_instruction": { "parts": [{"text": system_prompt}] },
                "contents": contents
            }
            if max_tokens is not None: payload["max_tokens"] = max_tokens
            if temperature is not None: payload["temperature"] = temperature

            import json
            async with httpx.AsyncClient() as client:
                async with client.stream("POST", url, headers=headers, json=payload, timeout=60.0) as response:
                    if response.status_code != 200:
                        yield f"Error Gemini Stream: {response.status_code}"
                        return
                    
                    async for line in response.aiter_lines():
                        if not line or line.startswith("[") or line.startswith(","): continue
                        if line.startswith("]"): break
                        
                        try:
                            # Gemini stream envía fragmentos JSON en un array
                            chunk = json.loads(line)
                            content = chunk.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                            if content: yield content
                        except: continue
                        
        except Exception as e:
            yield f"Error stream Gemini: {str(e)}"
