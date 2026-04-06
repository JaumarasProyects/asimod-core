import os
import threading
from typing import List
from llama_cpp import Llama
from core.ports.llm_port import LLMPort

class GGUFAdapter(LLMPort):
    """
    Adaptador para modelos GGUF usando llama-cpp-python.
    No requiere Ollama - carga modelos directamente desde archivo.
    """
    def __init__(self, models_dir=None, n_threads=8, n_ctx=8192, n_gpu_layers=99):
        if models_dir is None:
            models_dir = os.path.join(os.path.expanduser("~"), "Desktop", "ModelosGGUF")
        
        self.models_dir = models_dir
        self.n_threads = n_threads
        self.n_ctx = n_ctx
        self.n_gpu_layers = n_gpu_layers
        
        self.llm = None
        self.current_model_path = None
        
        os.makedirs(self.models_dir, exist_ok=True)

    @property
    def name(self) -> str:
        return "GGUF (Local)"

    def list_models(self) -> List[str]:
        """Lista los modelos disponibles en la carpeta configurada."""
        extensions = ('.gguf', '.bin', '.safetensors')
        models = []
        
        if os.path.exists(self.models_dir):
            for f in os.listdir(self.models_dir):
                if f.lower().endswith(extensions):
                    models.append(f)
        
        return sorted(models)

    def load_model(self, model_name: str):
        """Carga un modelo específico."""
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

    def generate_chat(self, history: List[dict], system_prompt: str, model: str, images: list = None, max_tokens: int = None, temperature: float = None) -> str:
        """
        Genera una respuesta usando el modelo GGUF cargado.
        history: lista de mensajes [{"role": "user", "content": "..."}]
        system_prompt: prompt del sistema
        model: nombre del archivo del modelo (se cargará si es diferente)
        max_tokens: límite de tokens de respuesta (None = usar valor por defecto)
        temperature: temperatura de muestreo (None = usar valor por defecto)
        """
        if not self.llm:
            if not model:
                return "Error: No hay modelo cargado. Especifica un modelo."
            
            success, msg = self.load_model(model)
            if not success:
                return f"Error: {msg}"

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        for msg in history:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role in ["user", "assistant", "system"]:
                messages.append({"role": role, "content": content})

        stop_tokens = [
            "Usuario:", "User:",
            "<|im_end|>", "<|im_start|>",
            "<end_of_turn>", "<end_of_text|>"
        ]
        
        max_tokens_val = max_tokens if max_tokens is not None else 1024
        temperature_val = temperature if temperature is not None else 0.7
        
        try:
            output = self.llm.create_chat_completion(
                messages=messages,
                max_tokens=max_tokens_val,
                temperature=temperature_val,
                stop=stop_tokens
            )
            return output['choices'][0]['message']['content']
        except Exception as e:
            return f"Error generando respuesta: {str(e)}"