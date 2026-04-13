import httpx
import json
import asyncio
from core.ports.llm_port import LLMPort

class OllamaAdapter(LLMPort):
    """
    Adaptador para Ollama que utiliza la API HTTP local de forma asíncrona.
    """
    def __init__(self, base_url="http://localhost:11434"):
        if base_url.endswith("/api"):
            self.base_url = base_url[:-4]
        elif base_url.endswith("/api/"):
            self.base_url = base_url[:-5]
        else:
            self.base_url = base_url

    @property
    def name(self) -> str:
        return "Ollama"

    async def list_models(self) -> list:
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{self.base_url}/api/tags", timeout=5.0)
                if response.status_code == 200:
                    models = response.json().get("models", [])
                    return [m["name"] for m in models]
        except:
            pass
        return []

    async def generate_chat(self, history: list, system_prompt: str, model: str, images: list = None, max_tokens: int = None, temperature: float = None) -> str:
        """
        Envía un historial completo a Ollama usando el endpoint /api/chat de forma asíncrona.
        """
        try:
            messages = [{"role": "system", "content": system_prompt}] + history
            
            payload = {
                "model": model,
                "messages": messages,
                "stream": False
            }
            
            if max_tokens is not None:
                payload["options"] = {"num_predict": max_tokens}
            if temperature is not None:
                if "options" not in payload:
                    payload["options"] = {}
                payload["options"]["temperature"] = temperature
            
            if images and len(messages) > 0:
                messages[-1]["images"] = images

            async with httpx.AsyncClient() as client:
                response = await client.post(f"{self.base_url}/api/chat", json=payload, timeout=300.0)
            
            if response.status_code == 200:
                return response.json().get("message", {}).get("content", "Error: No hay contenido.")
            
            if response.status_code == 404:
                return f"Error 404 en Ollama: El modelo '{model}' no está instalado."
            
            return f"Error en Ollama: {response.status_code} - {response.text}"
            
        except Exception as e:
            return f"Error de conexión con Ollama: {str(e)}"

    async def generate_chat_stream(self, history: list, system_prompt: str, model: str, images: list = None, max_tokens: int = None, temperature: float = None):
        """
        Generador asíncrono para streaming con Ollama.
        """
        try:
            messages = [{"role": "system", "content": system_prompt}] + history
            
            payload = {
                "model": model,
                "messages": messages,
                "stream": True
            }
            
            if max_tokens is not None:
                payload["options"] = {"num_predict": max_tokens}
            if temperature is not None:
                if "options" not in payload:
                    payload["options"] = {}
                payload["options"]["temperature"] = temperature
            
            if images and len(messages) > 0:
                messages[-1]["images"] = images

            async with httpx.AsyncClient() as client:
                async with client.stream("POST", f"{self.base_url}/api/chat", json=payload, timeout=300.0) as response:
                    if response.status_code != 200:
                        yield f"Error Ollama Stream {response.status_code}"
                        return
                    
                    async for line in response.aiter_lines():
                        if not line:
                            continue
                        try:
                            chunk = json.loads(line)
                            content = chunk.get("message", {}).get("content", "")
                            if content:
                                yield content
                            if chunk.get("done"):
                                break
                        except Exception as json_err:
                            print(f"[Ollama] Error parsing stream line: {json_err}")

        except Exception as e:
            yield f"Error de conexión stream con Ollama: {str(e)}"
