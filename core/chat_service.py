import asyncio
import re
import time
import traceback
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
        self.is_processing = False  # Estado de generación LLM actual
        self._last_message_time = 0  # Timestamp del último mensaje procesado
        self._message_cooldown = 1.5  # Segundos de bloqueo forzado tras un mensaje

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
        if self.busy:
            print(f"[ChatService] BUSY: Ignorando STT recibido: {text}")
            return

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

    @property
    def busy(self) -> bool:
        """Indica si el sistema está ocupado generando texto o audio (basado en flags y tiempo)."""
        time_since_last = time.time() - self._last_message_time
        recent_activity = time_since_last < self._message_cooldown
        
        return self.is_processing or \
               self.voice_service.is_generating or \
               self.voice_service.is_playing or \
               recent_activity

    async def get_available_models(self) -> List[str]:
        if self.current_adapter:
            return await self.current_adapter.list_models()
        return []

    async def send_message(self, text: str, model: str = None, images: list = None, silent: bool = False, max_tokens: int = None, temperature: float = None, skip_tts: bool = False, system_prompt: str = None) -> Dict:
        """
        Envía un mensaje usando el contexto de memoria activo y procesa la respuesta de forma asíncrona.
        Permite sobrescribir las instrucciones del sistema con system_prompt.
        """
        if self.busy:
            print("[ChatService] BUSY: Ignoring concurrent message.")
            return {"response": "Error: Sistema ocupado.", "status": "busy"}

        self.is_processing = True
        try:
            if images is None:
                images = []

            if not model or model.strip() == "":
                model = self.config.get("last_model")
                print(f"[ChatService] Using default model: {model}")

            if max_tokens is None:
                max_tokens = self.config.get("max_tokens")
            if temperature is None:
                temperature = self.config.get("temperature")
            
            # 1. Obtener contexto e instrucciones (Priorizar override si existe)
            history = self.memory.get_context()
            if system_prompt is None:
                system_prompt = self.memory.get_system_prompt(self.locale_service)
            else:
                print(f"[ChatService] Overriding generic system prompt with custom instructions.")

            # 2. Si NO es silent, guardar mensaje del usuario
            if not silent:
                self.memory.add_message("user", text)
                # refrescar history tras añadir el mensaje del usuario
                history = self.memory.get_context()

            # 3. Generar respuesta de forma asíncrona
            print(f"[ChatService] Generating response for model {model}...")
            try:
                if self.current_adapter:
                    raw_response = await self.current_adapter.generate_chat(history, system_prompt, model, images, max_tokens, temperature)
                else:
                    raw_response = "Error: No hay un motor de LLM configurado."
            except Exception as e:
                print(f"[ChatService] Error in LLM generation: {e}")
                traceback.print_exc()
                raw_response = f"Error crítico durante la generación: {str(e)}"

            # 4. Procesar texto
            self.last_emojis = TextProcessor.extract_emojis(raw_response)
            clean_response = TextProcessor.clean_text_for_tts(raw_response)

            # 5. Si NO es silent, guardar respuesta en memoria
            if not silent:
                self.memory.add_message("assistant", raw_response)

            # 6. Si NO es silent Y NO saltamos TTS, lanzar TTS con voz de personaje si existe
            if not silent and not skip_tts:
                char_voice = self.memory.data.get("voice_id")
                char_provider = self.memory.data.get("voice_provider")

                # La generación de audio ahora es asíncrona nativa
                # AWAITS para asegurar que el estado 'busy' sea continuo hasta que VoiceService tome el relevo
                try:
                    await self.voice_service.process_text(
                        clean_response,
                        voice_id=char_voice,
                        voice_provider=char_provider
                    )
                except Exception as ve:
                    print(f"[ChatService] Error disparando TTS: {ve}")

            return {
                "response": raw_response,
                "clean_text": clean_response,
                "emojis": self.last_emojis
            }
        finally:
            self.is_processing = False
            self._last_message_time = time.time() # Iniciar cooldown tras finalizar todo el proceso

    async def send_message_stream(self, text: str, model: str = None, images: list = None, silent: bool = False, max_tokens: int = None, temperature: float = None):
        """
        Versión con streaming que procesa audio por fragmentos (frases).
        """
        if self.busy:
            print("[ChatService] BUSY: Ignoring concurrent stream message.")
            yield "Sistema ocupado..."
            return

        self.is_processing = True
        try:
            if images is None:
                images = []

            if not model or model.strip() == "":
                model = self.config.get("last_model")

            # 1. Preparar contexto
            history = self.memory.get_context()
            system_prompt = self.memory.get_system_prompt(self.locale_service)

            if not silent:
                self.memory.add_message("user", text)
                history = self.memory.get_context()

            # 2. Iniciar stream del LLM
            if not self.current_adapter:
                yield "Error: No hay un motor de LLM configurado."
                return

            full_response = ""
            sentence_buffer = ""
            
            char_voice = self.memory.data.get("voice_id")
            char_provider = self.memory.data.get("voice_provider")

            # Regex para detectar finales de frase: . ! ? que no estén seguidos de números o letras inmediatamente
            # Simplificado para streaming: detecta cuando el token actual contiene un signo de puntuación final
            sentence_endings = re.compile(r'[.!?]\s*$')

            async for token in self.current_adapter.generate_chat_stream(history, system_prompt, model, images, max_tokens, temperature):
                full_response += token
                sentence_buffer += token
                
                # 3. Detectar si tenemos una frase completa para el audio
                if not silent and sentence_endings.search(sentence_buffer):
                    # Extraer la frase limpia y enviarla al VoiceService
                    clean_sentence = TextProcessor.clean_text_for_tts(sentence_buffer)
                    if clean_sentence.strip():
                        asyncio.create_task(asyncio.to_thread(
                            self.voice_service.process_text,
                            clean_sentence,
                            voice_id=char_voice,
                            voice_provider=char_provider
                        ))
                    sentence_buffer = ""

                yield token

            # 4. Procesar el resto del buffer si quedó algo sin punto final
            if not silent and sentence_buffer.strip():
                clean_sentence = TextProcessor.clean_text_for_tts(sentence_buffer)
                asyncio.create_task(asyncio.to_thread(
                    self.voice_service.process_text,
                    clean_sentence,
                    voice_id=char_voice,
                    voice_provider=char_provider
                ))

            # 5. Guardar en memoria al finalizar
            if not silent:
                self.memory.add_message("assistant", full_response)
                self.last_emojis = TextProcessor.extract_emojis(full_response)
        finally:
            self.is_processing = False

    def get_history(self) -> List[ChatMessage]:
        raw_history = self.memory.get_context()
        return [
            ChatMessage(
                sender="Tú" if m["role"] == "user" else "AI",
                content=m["content"]
            )
            for m in raw_history
        ]