from typing import List, Callable, Optional, Dict
from core.models import ChatMessage
from core.ports.chat_port import ChatPort
from core.factories.llm_factory import LLMFactory
from core.services.voice_service import VoiceService
from core.services.stt_service import STTService
from core.services.text_processor import TextProcessor

class ChatService(ChatPort):
    """
    Orquestador de chat que maneja múltiples proveedores de LLM e integración de Voz/STT.
    """
    def __init__(self, config_service):
        self.config = config_service
        self.history: List[ChatMessage] = []
        self.current_adapter = None
        
        # Estado actual de emociones para la API externa
        self.last_emojis = []
        
        # Callback para notificar a la interfaz de nuevas transcripciones (STT)
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

    def send_message(self, text: str, model: str = None, images: list = None) -> Dict:
        """
        Envía un mensaje con contexto visual, procesa emociones y retorna un dict enriquecido.
        """
        if images is None: images = []
        
        # 1. Guardar mensaje del usuario
        user_msg = ChatMessage(sender="User", content=text)
        self.history.append(user_msg)
        
        # 2. Generar respuesta usando el adaptador activo (pasando también imágenes)
        if self.current_adapter:
            # Los adaptadores ahora deben aceptar images
            raw_response = self.current_adapter.generate_response(text, model, images)
        else:
            raw_response = "Error: No hay un motor de LLM configurado."

        # 3. Procesamiento de Texto (Emojis y Limpieza TTS)
        self.last_emojis = TextProcessor.extract_emojis(raw_response)
        clean_response = TextProcessor.clean_text_for_tts(raw_response)

        # 4. Guardar respuesta de la IA (Original para historial)
        ai_msg = ChatMessage(sender="AI", content=raw_response)
        self.history.append(ai_msg)
        
        # 5. DISPARAR AUDIO SI ESTÁ ACTIVO (Usando el texto limpio)
        self.voice_service.process_text(clean_response)
        
        return {
            "response": raw_response,
            "clean_text": clean_response,
            "emojis": self.last_emojis
        }

    def get_history(self) -> List[ChatMessage]:
        return self.history
