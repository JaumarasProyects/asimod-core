from typing import List, Callable, Optional
from core.models import ChatMessage
from core.ports.chat_port import ChatPort
from core.factories.llm_factory import LLMFactory
from core.services.voice_service import VoiceService
from core.services.stt_service import STTService

class ChatService(ChatPort):
    """
    Orquestador de chat que maneja múltiples proveedores de LLM e integración de Voz/STT.
    """
    def __init__(self, config_service):
        self.config = config_service
        self.history: List[ChatMessage] = []
        self.current_adapter = None
        
        # Callback para notificar a la interfaz de nuevas transcripciones
        self.on_stt_finished_cb: Optional[Callable[[str], None]] = None
        
        # Inyectar servicios de Voz (Salida) y STT (Entrada)
        self.voice_service = VoiceService(config_service)
        self.stt_service = STTService(config_service, on_transcription_complete=self._on_stt_complete)
        
        # Inicializar con el adaptador guardado usando la Factoría
        self.switch_provider(self.config.get("last_provider", "Ollama"))

    def _on_stt_complete(self, text: str):
        """Puente entre el servicio de STT y la interfaz de usuario."""
        if self.on_stt_finished_cb:
            self.on_stt_finished_cb(text)

    def switch_provider(self, provider_name: str):
        self.current_adapter = LLMFactory.get_adapter(provider_name, self.config)

    def get_providers_list(self) -> List[str]:
        return LLMFactory.list_providers()

    def get_available_models(self) -> List[str]:
        if self.current_adapter:
            return self.current_adapter.list_models()
        return []

    def send_message(self, text: str, model: str = None) -> str:
        # 1. Guardar mensaje del usuario
        user_msg = ChatMessage(sender="User", content=text)
        self.history.append(user_msg)
        
        # 2. Generar respuesta usando el adaptador activo
        if self.current_adapter:
            response_text = self.current_adapter.generate_response(text, model)
        else:
            response_text = "Error: No hay un motor de LLM configurado."

        # 3. Guardar respuesta de la IA
        ai_msg = ChatMessage(sender="AI", content=response_text)
        self.history.append(ai_msg)
        
        # 4. DISPARAR AUDIO SI ESTÁ ACTIVO
        self.voice_service.process_text(response_text)
        
        return response_text

    def get_history(self) -> List[ChatMessage]:
        return self.history
