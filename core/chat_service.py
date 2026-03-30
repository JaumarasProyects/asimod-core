from typing import List, Callable, Optional, Dict
from core.models import ChatMessage
from core.ports.chat_port import ChatPort
from core.factories.llm_factory import LLMFactory
from core.services.voice_service import VoiceService
from core.services.stt_service import STTService
from core.services.text_processor import TextProcessor
from core.services.memory_service import MemoryService
from core.services.locale_service import LocaleService

class ChatService(ChatPort):
    """
    Orquestador de chat que maneja múltiples proveedores de LLM, 
    persistencia de memoria e integración de Voz/STT.
    """
    def __init__(self, config_service):
        self.config = config_service
        self.memory = MemoryService()
        self.locale_service = LocaleService(config_service)
        self.current_adapter = None
        
        # Estado actual de emociones para la API externa
        self.last_emojis = []
        
        # Callback para notificar a la interfaz de nuevas transcripciones (STT)
        self.on_stt_finished_cb: Optional[Callable[[str], None]] = None
        
        # Inyectar servicios de Voz (Salida) y STT (Entrada)
        self.voice_service = VoiceService(config_service, self.locale_service)
        self.stt_service = STTService(config_service, on_transcription_complete=self._on_stt_complete)
        
        # Inicializar con el adaptador guardado usando la Factoría
        self.switch_provider(self.config.get("last_provider", "Ollama"))
        
        # Cargar memoria inicial si existe en config
        last_thread = self.config.get("active_thread", "None")
        self.memory.load_thread(last_thread)

    def _on_stt_complete(self, text: str):
        """Puente entre el servicio de STT y la interfaz de usuario."""
        if self.on_stt_finished_cb:
            self.on_stt_finished_cb(text)

    def switch_provider(self, provider_name: str):
        self.current_adapter = LLMFactory.get_adapter(provider_name, self.config)

    def get_providers_list(self) -> List[str]:
        return LLMFactory.list_providers()

    def get_voice_providers_list(self) -> List[str]:
        from core.factories.voice_factory import VoiceFactory
        return VoiceFactory.list_providers()

    def get_available_models(self) -> List[str]:
        if self.current_adapter:
            return self.current_adapter.list_models()
        return []

    def send_message(self, text: str, model: str = None, images: list = None) -> Dict:
        """
        Envía un mensaje usando el contexto de memoria activo y procesa la respuesta.
        """
        if images is None: images = []
        
        # 1. Guardar mensaje del usuario en la memoria persistente
        self.memory.add_message("user", text)
        
        # 2. Obtener contexto completo y prompt de sistema
        history = self.memory.get_context()
        system_prompt = self.memory.get_system_prompt(self.locale_service)
        
        # 3. Generar respuesta usando el adaptador activo
        if self.current_adapter:
            raw_response = self.current_adapter.generate_chat(history, system_prompt, model, images)
        else:
            raw_response = "Error: No hay un motor de LLM configurado."

        # 4. Procesamiento de Texto (Emojis y Limpieza TTS)
        self.last_emojis = TextProcessor.extract_emojis(raw_response)
        clean_response = TextProcessor.clean_text_for_tts(raw_response)

        # 5. Guardar respuesta de la IA en la memoria persistente
        self.memory.add_message("assistant", raw_response)
        
        # 6. Disparar audio si está activo (usando la voz/motor del personaje si existe)
        char_voice = self.memory.data.get("voice_id")
        char_provider = self.memory.data.get("voice_provider")
        self.voice_service.process_text(clean_response, voice_id=char_voice, voice_provider=char_provider)
        
        return {
            "response": raw_response,
            "clean_text": clean_response,
            "emojis": self.last_emojis
        }

    def get_history(self) -> List[ChatMessage]:
        # Adaptar formato de MemoryService al modelo ChatMessage usado en la UI
        raw_history = self.memory.get_context()
        return [ChatMessage(sender="Tú" if m["role"] == "user" else "AI", content=m["content"]) for m in raw_history]
