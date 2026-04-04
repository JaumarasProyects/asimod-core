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

        # Callback para la UI interna de ASIMOD cuando STT trabaja en modo CHAT
        self.on_stt_finished_cb: Optional[Callable[[str], None]] = None

        # Callback para exponer STT a Unity/API cuando trabaja en COMMAND/QUESTION
        self.on_stt_result_cb: Optional[Callable[[str], None]] = None

        # Servicios de voz
        self.voice_service = VoiceService(config_service, self.locale_service)

        # STT con doble callback
        self.stt_service = STTService(
            config_service=config_service,
            on_chat_transcription=self._on_stt_complete,
            on_stt_result=self._on_stt_result
        )

        # Inicializar proveedor LLM
        self.switch_provider(self.config.get("last_provider", "Ollama"))

        # Cargar memoria inicial
        last_thread = self.config.get("active_thread", "None")
        self.memory.load_thread(last_thread)

    def _on_stt_complete(self, text: str):
        """
        Texto reconocido en modo CHAT.
        Va a la UI interna / flujo normal de ASIMOD.
        """
        print(f"[ChatService] STT CHAT recibido: {text}")

        if self.on_stt_finished_cb:
            self.on_stt_finished_cb(text)

    def _on_stt_result(self, text: str):
        """
        Texto reconocido en modo COMMAND / QUESTION.
        Se expone para Unity/API.
        """
        print(f"[ChatService] STT RESULT recibido: {text}")

        if self.on_stt_result_cb:
            self.on_stt_result_cb(text)

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

    def send_message(self, text: str, model: str = None, images: list = None, silent: bool = False) -> Dict:
        """
        Envía un mensaje usando el contexto de memoria activo y procesa la respuesta.

        silent=True:
        - no guarda el mensaje en memoria
        - no guarda la respuesta en memoria
        - no lanza TTS

        Útil para generaciones internas, prompts auxiliares o texto de apoyo.
        """
        if images is None:
            images = []

        if not model or model.strip() == "":
            model = self.config.get("last_model")
            print(f"[ChatService] Using default model: {model}")

        # 1. Obtener contexto e instrucciones
        # Si silent, usamos el contexto actual pero sin contaminar el hilo
        history = self.memory.get_context()
        system_prompt = self.memory.get_system_prompt(self.locale_service)

        # 2. Si NO es silent, guardar mensaje del usuario
        if not silent:
            self.memory.add_message("user", text)

            # refrescar history tras añadir el mensaje del usuario
            history = self.memory.get_context()

        # 3. Generar respuesta
        if self.current_adapter:
            raw_response = self.current_adapter.generate_chat(history, system_prompt, model, images)
        else:
            raw_response = "Error: No hay un motor de LLM configurado."

        # 4. Procesar texto
        self.last_emojis = TextProcessor.extract_emojis(raw_response)
        clean_response = TextProcessor.clean_text_for_tts(raw_response)

        # 5. Si NO es silent, guardar respuesta en memoria
        if not silent:
            self.memory.add_message("assistant", raw_response)

        # 6. Si NO es silent, lanzar TTS con voz de personaje si existe
        if not silent:
            char_voice = self.memory.data.get("voice_id")
            char_provider = self.memory.data.get("voice_provider")

            self.voice_service.process_text(
                clean_response,
                voice_id=char_voice,
                voice_provider=char_provider
            )

        return {
            "response": raw_response,
            "clean_text": clean_response,
            "emojis": self.last_emojis
        }
    def get_history(self) -> List[ChatMessage]:
        raw_history = self.memory.get_context()
        return [
            ChatMessage(
                sender="Tú" if m["role"] == "user" else "AI",
                content=m["content"]
            )
            for m in raw_history
        ]