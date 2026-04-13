import httpx
from typing import List
from core.ports.llm_port import LLMPort

class LLMStudioAdapter(LLMPort):
    """
    Adaptador para LLM Studio (API compatible con OpenAI en localhost:1234) asíncrono.
    """

    def __init__(self, base_url: str = "http://localhost:1234/v1", api_key: str = "not-needed"):
        self.base_url = base_url
        self.api_key = api_key

    @property
    def name(self) -> str:
        return "LLM Studio"

    async def generate_chat(self, history: List[dict], system_prompt: str, model: str, images: list = None, max_tokens: int = None, temperature: float = None) -> str:
        """
        Genera una respuesta usando LLM Studio de forma asíncrona.
        """
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        for msg in history:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role in ["user", "assistant", "system"]:
                messages.append({"role": role, "content": content})

        payload = {
            "model": model or "local-model",
            "messages": messages
        }

        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        if temperature is not None:
            payload["temperature"] = temperature

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{self.base_url}/chat/completions",
                    json=payload,
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {self.api_key}"
                    },
                    timeout=120.0
                )

            if resp.status_code == 200:
                data = resp.json()
                return data["choices"][0]["message"]["content"]
            else:
                return f"Error: {resp.status_code} - {resp.text}"

        except Exception as e:
            return f"Error conectando a LLM Studio: {str(e)}"

    async def generate_chat_stream(self, history: List[dict], system_prompt: str, model: str, images: list = None, max_tokens: int = None, temperature: float = None):
        """
        Generador asíncrono para streaming con LLM Studio.
        """
        # Implementación similar a OpenAI por ser compatible
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        for msg in history:
            messages.append({"role": msg.get("role", "user"), "content": msg.get("content", "")})

        payload = {
            "model": model or "local-model",
            "messages": messages,
            "stream": True
        }
        
        try:
            import json
            async with httpx.AsyncClient() as client:
                async with client.stream("POST", f"{self.base_url}/chat/completions", 
                                       json=payload, 
                                       headers={"Authorization": f"Bearer {self.api_key}"},
                                       timeout=120.0) as response:
                    async for line in response.aiter_lines():
                        if line.startswith("data: "):
                            data_str = line[6:]
                            if data_str.strip() == "[DONE]":
                                break
                            try:
                                chunk = json.loads(data_str)
                                content = chunk["choices"][0]["delta"].get("content", "")
                                if content:
                                    yield content
                            except:
                                continue
        except Exception as e:
            yield f"Error stream LLM Studio: {str(e)}"

    async def list_models(self) -> List[str]:
        """Lista los modelos disponibles en LLM Studio de forma asíncrona."""
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(f"{self.base_url}/models", timeout=10.0)
            if resp.status_code == 200:
                data = resp.json()
                return [m["id"] for m in data.get("data", [])]
        except:
            pass
        return []
