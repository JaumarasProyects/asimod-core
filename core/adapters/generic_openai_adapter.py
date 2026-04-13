import httpx
import base64
import asyncio
from core.ports.llm_port import LLMPort

class GenericOpenAIAdapter(LLMPort):
    """
    Adaptador genérico para servicios compatibles con el protocolo de OpenAI
    (DeepSeek, Groq, Perplexity, etc) con soporte multimodal asíncrono.
    """
    def __init__(self, name: str, api_key: str, base_url: str, models: list):
        self._name = name
        self.api_key = api_key
        self.base_url = base_url
        self._models = models

    @property
    def name(self) -> str:
        return self._name

    async def list_models(self) -> list:
        return self._models

    def _encode_image(self, image_path):
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')

    async def generate_chat(self, history: list, system_prompt: str, model: str, images: list = None, max_tokens: int = None, temperature: float = None) -> str:
        if not self.api_key:
            return f"Error: No se ha configurado la API Key para {self._name}."
        
        try:
            url = f"{self.base_url}/chat/completions"
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            messages = [{"role": "system", "content": system_prompt}] + history

            target_model = model if model else (self._models[0] if self._models else "default")

            payload = {
                "model": target_model,
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
                return f"Error {self._name} {response.status_code}: {response.text}"
                
        except Exception as e:
            return f"Error de conexión con {self._name}: {str(e)}"

    async def generate_response(self, prompt: str, model: str, images: list = None) -> str:
        if not self.api_key:
            return f"Error: No se ha configurado la API Key para {self._name}."

        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            # Construir contenido del mensaje (texto + imágenes opcionales)
            content = [{"type": "text", "text": prompt}]
            
            if images:
                for img_path in images:
                    try:
                        base64_image = self._encode_image(img_path)
                        content.append({
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}
                        })
                    except Exception as e:
                        print(f"Error encoding image {img_path}: {e}")

            payload = {
                "model": model,
                "messages": [{"role": "user", "content": content}]
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers=headers, 
                    json=payload,
                    timeout=60.0
                )
            
            if response.status_code == 200:
                return response.json()["choices"][0]["message"]["content"]
            else:
                return f"Error {self._name}: {response.status_code} - {response.text}"
        except Exception as e:
            return f"Error de conexión con {self._name}: {str(e)}"
