import os
from typing import List
from llama_cpp import Llama
from core.ports.llm_port import LLMPort

class GGUFAdapter(LLMPort):
    def __init__(self, models_dir=None, n_threads=None, n_ctx=4096, n_gpu_layers=-1):
        if models_dir is None:
            models_dir = os.path.join(os.path.expanduser("~"), "Desktop", "ModelosGGUF")

        self.models_dir = models_dir
        self.n_threads = n_threads if n_threads is not None else max(1, (os.cpu_count() or 8) - 1)
        self.n_ctx = n_ctx
        self.n_gpu_layers = n_gpu_layers

        self.llm = None
        self.current_model_path = None

        os.makedirs(self.models_dir, exist_ok=True)

    @property
    def name(self) -> str:
        return "GGUF (Local)"

    async def list_models(self) -> List[str]:
        extensions = (".gguf", ".bin", ".safetensors")
        if not os.path.exists(self.models_dir):
            return []
        return sorted([f for f in os.listdir(self.models_dir) if f.lower().endswith(extensions)])

    def load_model(self, model_name: str):
        model_path = os.path.join(self.models_dir, model_name)
        if not os.path.exists(model_path):
            return False, f"Modelo no encontrado: {model_path}"

        try:
            self.llm = Llama(
                model_path=model_path,
                n_gpu_layers=self.n_gpu_layers,
                n_threads=self.n_threads,
                n_ctx=self.n_ctx,
                verbose=False
            )
            self.current_model_path = model_path
            return True, f"Modelo cargado: {model_name}"
        except Exception as e:
            return False, f"Error al cargar: {str(e)}"

    async def generate_chat_stream(self, history: list, system_prompt: str, model: str, images: list = None, max_tokens: int = None, temperature: float = None):
        """
        Generador asíncrono para streaming con GGUF local.
        """
        if model:
            desired_path = os.path.join(self.models_dir, model)
            if self.current_model_path != desired_path:
                success, msg = self.load_model(model)
                if not success:
                    yield f"Error: {msg}"
                    return
        elif not self.llm:
            yield "Error: No hay modelo cargado."
            return

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        for msg in history:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role in ("user", "assistant", "system"):
                messages.append({"role": role, "content": content})
        
        try:
            import asyncio
            
            stream = self.llm.create_chat_completion(
                messages=messages,
                max_tokens=max_tokens or 1024,
                temperature=temperature if temperature is not None else 0.7,
                stream=True,
                stop=["Usuario:", "User:", "<|im_end|>", "<|im_start|>", "<end_of_turn>", "<end_of_text|>"]
            )
            
            for chunk in stream:
                delta = chunk["choices"][0]["delta"]
                if "content" in delta:
                    yield delta["content"]
                await asyncio.sleep(0)

        except Exception as e:
            yield f"Error generando stream GGUF: {str(e)}"

    async def generate_chat(self, history: List[dict], system_prompt: str, model: str, images=None, max_tokens=None, temperature=None) -> str:
        if model:
            desired_path = os.path.join(self.models_dir, model)
            if self.current_model_path != desired_path:
                success, msg = self.load_model(model)
                if not success:
                    return f"Error: {msg}"
        elif not self.llm:
            return "Error: No hay modelo cargado. Especifica un modelo."

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        for msg in history:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role in ("user", "assistant", "system"):
                messages.append({"role": role, "content": content})

        try:
            print(f"[GGUFAdapter] Calling create_chat_completion with {len(messages)} messages...")
            output = self.llm.create_chat_completion(
                messages=messages,
                max_tokens=max_tokens or 1024,
                temperature=temperature if temperature is not None else 0.7,
                stop=["Usuario:", "User:", "<|im_end|>", "<|im_start|>", "<end_of_turn>", "<end_of_text|>"]
            )
            return output["choices"][0]["message"]["content"]
        except Exception as e:
            return f"Error generando respuesta: {str(e)}"