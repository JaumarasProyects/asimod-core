import httpx
import base64
import asyncio
from core.ports.llm_port import LLMPort

class OpenAIAdapter(LLMPort):
    """
    Adaptador para OpenAI que utiliza la API REST con soporte multimodal asíncrono.
    """
    def __init__(self, api_key: str):
        self.api_key = api_key

    @property
    def name(self) -> str:
        return "OpenAI"

    async def list_models(self) -> list:
        return ["gpt-4o", "gpt-4-turbo", "gpt-3.5-turbo", "gpt-4o-mini"]

    def _encode_image(self, image_path):
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')

    async def generate_chat(self, history: list, system_prompt: str, model: str, images: list = None, max_tokens: int = None, temperature: float = None) -> str:
        if not self.api_key:
            return "Error: No se ha configurado la API Key de OpenAI."
        
        try:
            url = "https://api.openai.com/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            messages = [{"role": "system", "content": system_prompt}] + history
            
            if images:
                for msg in reversed(messages):
                    if msg["role"] == "user":
                        orig_content = msg["content"]
                        new_content = [{"type": "text", "text": orig_content}]
                        for img_path in images:
                            try:
                                b64 = self._encode_image(img_path)
                                new_content.append({
                                    "type": "image_url",
                                    "image_url": {"url": f"data:image/jpeg;base64,{b64}"}
                                })
                            except Exception as e:
                                print(f"[OpenAI] Error encoding image: {e}")
                        msg["content"] = new_content
                        break

            payload = {
                "model": model if model else "gpt-4o-mini",
                "messages": messages
            }
            
            if max_tokens is not None:
                payload["max_tokens"] = max_tokens
            if temperature is not None:
                payload["temperature"] = temperature

            async with httpx.AsyncClient() as client:
                response = await client.post(url, headers=headers, json=payload, timeout=45.0)
            
            if response.status_code == 200:
                return response.json()["choices"][0]["message"]["content"]
            else:
                return f"Error OpenAI: {response.status_code} - {response.text}"
        except Exception as e:
            return f"Error de conexión con OpenAI: {str(e)}"

    async def generate_chat_stream(self, history: list, system_prompt: str, model: str, images: list = None, max_tokens: int = None, temperature: float = None):
        """Generador asíncrono para streaming con OpenAI."""
        if not self.api_key:
            yield "Error: No se ha configurado la API Key de OpenAI."
            return
            
        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        messages = [{"role": "system", "content": system_prompt}] + history
        
        # Inyectar imágenes si existen (en el último mensaje del usuario)
        if images:
            for msg in reversed(messages):
                if msg["role"] == "user":
                    orig_content = msg["content"]
                    new_content = [{"type": "text", "text": orig_content}]
                    for img_path in images:
                        try:
                            b64 = self._encode_image(img_path)
                            new_content.append({
                                "type": "image_url",
                                "image_url": {"url": f"data:image/jpeg;base64,{b64}"}
                            })
                        except: continue
                    msg["content"] = new_content
                    break

        payload = {
            "model": model if model else "gpt-4o-mini",
            "messages": messages,
            "stream": True
        }
        
        if max_tokens is not None: payload["max_tokens"] = max_tokens
        if temperature is not None: payload["temperature"] = temperature
        
        try:
            import json
            async with httpx.AsyncClient() as client:
                async with client.stream("POST", url, headers=headers, json=payload, timeout=60.0) as response:
                    if response.status_code != 200:
                        yield f"Error OpenAI Stream: {response.status_code}"
                        return
                    
                    async for line in response.aiter_lines():
                        if not line.startswith("data: "): continue
                        data_str = line[6:].strip()
                        if data_str == "[DONE]": break
                        try:
                            chunk = json.loads(data_str)
                            content = chunk["choices"][0].get("delta", {}).get("content", "")
                            if content:
                                yield content
                        except: continue
        except Exception as e:
            yield f"Error stream OpenAI: {str(e)}"
