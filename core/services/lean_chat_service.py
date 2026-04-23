import asyncio
import os
from typing import List, Dict, Optional
from core.factories.llm_factory import LLMFactory
from core.factories.voice_factory import VoiceFactory

class LeanChatService:
    """
    Versión ligera de ChatService diseñada para satisfacer las dependencias de los módulos
    en entornos de API independiente (como el Media API).
    """
    def __init__(self, config_service):
        self.config = config_service
        self.current_adapter = None
        self.stt_captured_by_module = False
        
        # Inicializar proveedor LLM
        self.switch_provider(self.config.get("last_provider", "Ollama"))
        
        # Mock de memoria (solo lo necesario para lectura)
        self.memory = type('obj', (object,), {
            'data': {},
            'add_message': lambda role, content: print(f"[LeanChat][Memory] Add: {role}: {content}"),
            'update_profile': lambda **kwargs: print(f"[LeanChat][Memory] Update profile: {kwargs}")
        })()
        
        # Mock de VoiceService para generación técnica
        self.voice_service = LeanVoiceService(config_service)
        
        # Mock de ModuleService (opcional)
        self.module_service = None

    def switch_provider(self, provider_name: str):
        print(f"[LeanChat] Switching LLM provider to: {provider_name}")
        self.current_adapter = LLMFactory.get_adapter(provider_name, self.config)

    def get_providers_list(self) -> List[str]:
        return LLMFactory.list_providers()

    async def get_available_models(self) -> List[str]:
        if self.current_adapter:
            return await self.current_adapter.list_models()
        return []

    def notify_system_msg(self, text: str, color: str = None, beep: bool = False):
        print(f"[LeanChat][SystemMsg] {text}")

    def notify_character_changed(self):
        print("[LeanChat] Character changed notification.")

    async def send_message(self, text: str, **kwargs) -> Dict:
        """Mock de envío de mensaje para procesamiento de texto técnico."""
        if not self.current_adapter:
            return {"response": "Error: No adapter", "status": "error"}
        
        model = kwargs.get("model") or self.config.get("last_model")
        history = [{"role": "user", "content": text}]
        system_prompt = kwargs.get("system_prompt", "Eres un asistente técnico.")
        
        print(f"[LeanChat] Sending technical message to {self.current_adapter.name}...")
        try:
            response = await self.current_adapter.generate_chat(history, system_prompt, model)
            return {"response": response, "status": "success"}
        except Exception as e:
            return {"response": str(e), "status": "error"}

class LeanVoiceService:
    """Implementación mínima de VoiceService para generación de audio sin reproducción."""
    def __init__(self, config_service):
        self.config = config_service

    async def generate_audio_only(self, text: str, voice_id: str = None, voice_provider: str = None):
        """Genera audio usando la lógica real pero sin mixer/reproducción."""
        provider = voice_provider or self.config.get("voice_provider", "Edge TTS")
        adapter = VoiceFactory.get_adapter(provider)
        
        if not adapter:
            print(f"[LeanVoice] Provider {provider} not found.")
            return None

        save_dir = self.config.get("voice_save_path", "audio")
        os.makedirs(save_dir, exist_ok=True)
        
        import time
        ts = time.strftime("%Y%m%d_%H%M%S")
        ext = ".wav" if "Local" in adapter.name else ".mp3"
        output_path = os.path.join(save_dir, f"voice_{ts}{ext}")
        
        v_id = voice_id or self.config.get("voice_id")
        
        print(f"[LeanVoice] Generating audio: {output_path}")
        success = await adapter.generate(text, output_path, voice_id=v_id)
        return output_path if success else None
