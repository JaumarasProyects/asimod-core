import httpx
from typing import Dict, Optional, List
from core.ports.llm_port import LLMPort

class OpenCodeAgentAdapter(LLMPort):
    """
    Adaptador que conecta ASIMOD con OpenCode Agent de forma asíncrona.
    Permite usar OpenCode como agente para ejecutar tareas.
    """

    def __init__(self, base_url: str = "http://localhost:9090", api_key: str = ""):
        self.base_url = base_url
        self.api_key = api_key

    @property
    def name(self) -> str:
        return "OpenCode Agent"

    async def generate_chat(self, history: list, system_prompt: str, model: str, images: list = None, max_tokens: int = None, temperature: float = None) -> str:
        """
        Envía una tarea a OpenCode y retorna el resultado de forma asíncrona.
        """
        full_prompt = ""
        if system_prompt:
            full_prompt = system_prompt + "\n\n"

        for msg in history:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "user":
                full_prompt += f"User: {content}\n"
            elif role == "assistant":
                full_prompt += f"Assistant: {content}\n"

        try:
            url = f"{self.base_url}/api/chat"
            headers = {"Content-Type": "application/json"}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"

            payload = {
                "message": full_prompt,
                "mode": "agent"
            }

            async with httpx.AsyncClient() as client:
                resp = await client.post(url, json=payload, headers=headers, timeout=300.0)
            
            if resp.status_code == 200:
                data = resp.json()
                return data.get("content", data.get("message", str(data)))
            else:
                return f"Error: {resp.status_code} - {resp.text}"

        except httpx.ConnectError:
            return "Error: No se puede conectar a OpenCode. ¿Tienes abierto 'opencode serve'?"
        except Exception as e:
            return f"Error OpenCode: {str(e)}"

    async def generate_chat_stream(self, history: List[dict], system_prompt: str, model: str, images: list = None, max_tokens: int = None, temperature: float = None):
        """
        OpenCode no soporta streaming nativo en esta implementación, 
        fallback a respuesta completa.
        """
        result = await self.generate_chat(history, system_prompt, model, images, max_tokens, temperature)
        yield result

    async def list_models(self) -> List[str]:
        return ["opencode-agent"]

    async def execute_task(self, task: str) -> str:
        """Ejecuta una tarea específica en OpenCode de forma asíncrona."""
        try:
            url = f"{self.base_url}/api/chat"
            headers = {"Content-Type": "application/json"}
            
            payload = {
                "message": task,
                "mode": "agent"
            }

            async with httpx.AsyncClient() as client:
                resp = await client.post(url, json=payload, headers=headers, timeout=300.0)
            
            if resp.status_code == 200:
                data = resp.json()
                return data.get("content", str(data))
            return f"Error: {resp.status_code}"

        except Exception as e:
            return f"Error execute_task: {str(e)}"
