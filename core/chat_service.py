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

        # Flag para que la UI sepa si el STT está siendo capturado por un módulo
        # Si es True, la UI de chat no debería mostrar el texto en el input field
        self.stt_captured_by_module = False

        # Estado actual de emociones para la API externa
        self.last_emojis = []

        # Callback para la UI interna de ASIMOD cuando STT trabaja en modo CHAT
        self.on_stt_finished_cb: Optional[Callable[[str], None]] = None

        # Callback para exponer STT a Unity/API cuando trabaja en COMMAND/QUESTION
        self.on_stt_result_cb: Optional[Callable[[str], None]] = None

        # Callback para notificar mensajes locales/sistema a la UI
        self.on_system_msg_cb: Optional[Callable[[str, str], None]] = None

        # Servicios de voz
        self.voice_service = VoiceService(config_service, self.locale_service)
        
        # STT con doble callback
        self.stt_service = STTService(
            config_service=config_service,
            on_chat_transcription=self._on_stt_complete,
            on_stt_result=self._on_stt_result
        )

        # Vinculación con Módulos (para modo AGENTE)
        self.module_service = None

        # --- INICIALIZACIÓN DE ESTADO ---
        # Inicializar proveedor LLM
        self.switch_provider(self.config.get("last_provider", "Ollama"))
        # Cargar memoria inicial
        last_thread = self.config.get("active_thread", "None")
        self.memory.load_thread(last_thread)

    def set_module_service(self, module_service):
        """Asocia el servicio de módulos para el contexto de herramientas."""
        self.module_service = module_service

    def notify_system_msg(self, text: str, color: str = None):
        """Notifica un mensaje para ser mostrado en la UI de chat sin TTS."""
        if self.on_system_msg_cb:
            self.on_system_msg_cb(text, color)

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
        if self.current_adapter and self.current_adapter.name == provider_name:
            return
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

    async def send_message(self, text: str, model: str = None, images: list = None, silent: bool = False, max_tokens: int = None, temperature: float = None, skip_tts: bool = False, system_prompt: str = None, mode: str = None) -> Dict:
        """
        Envía un mensaje usando el contexto de memoria activo y procesa la respuesta de forma asíncrona.
        Permite sobrescribir las instrucciones del sistema con system_prompt y el modo con mode.
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
            
            # --- Lógica de MODO AGENTE ---
            effective_mode = mode if mode else self.config.get("stt_mode")
            is_agent_mode = effective_mode in ["AGENT", "AGENT_AUDIO"]
            if is_agent_mode and self.module_service:
                agent_context = self.module_service.get_agent_tools_context()
                if system_prompt is None:
                    system_prompt = self.memory.get_system_prompt(self.locale_service)
                system_prompt = f"{system_prompt}\n\n{agent_context}"
                print("[ChatService] MODO AGENTE ACTIVO: Inyectando contexto de herramientas.")
            else:
                if system_prompt is None:
                    system_prompt = self.memory.get_system_prompt(self.locale_service)

            # 2. Si NO es silent, guardar mensaje del usuario
            if not silent:
                self.memory.add_message("user", text)
                history = self.memory.get_context()

            # 3. Generar respuesta de forma asíncrona (con Reintentos para Agente)
            max_attempts = 3 if is_agent_mode else 1
            best_block = None
            current_system_prompt = system_prompt
            
            for attempt in range(max_attempts):
                if attempt > 0:
                    # Inyectar aviso de reintento en el sistema para guiar al modelo
                    if attempt == 1:
                        current_system_prompt += "\n\nAVISO DE REINTENTO: Tu respuesta anterior no contenía un JSON procesable o faltaban campos. Responde ÚNICAMENTE con el bloque JSON solicitado en ESPAÑOL: { \"thought\": \"...\", \"response\": \"...\", \"action\": \"...\", \"params\": \"...\" }"
                    else:
                        current_system_prompt += "\n\nREINTENTO FINAL: El formato sigue siendo incorrecto. Por favor, envía SOLO el bloque JSON sin texto adicional, introducciones ni explicaciones fuera de él."
                    print(f"[ChatService] Reintentando generación de Agente (Intento {attempt + 1})...")

                print(f"[ChatService] Generating response for model {model}...")
                try:
                    if self.current_adapter:
                        raw_response = await self.current_adapter.generate_chat(history, current_system_prompt, model, images, max_tokens, temperature)
                    else:
                        raw_response = "Error: No hay un motor de LLM configurado."
                        break
                except Exception as e:
                    print(f"[ChatService] Error en generación de LLM: {e}")
                    traceback.print_exc()
                    raw_response = f"Error crítico durante la generación: {str(e)}"
                    break

                # --- Post-procesado AGENTE (Parseador JSON) ---
                agent_action = None
                agent_params = None
                if is_agent_mode:
                    try:
                        import json
                        # 1. Función interna de limpieza agresiva para residuos técnicos
                        def deep_clean(text):
                            if not text: return ""
                            t = text
                            # Eliminar bloques de código markdown
                            t = re.sub(r'```(?:json)?\s*.*?\s*```', '', t, flags=re.DOTALL)
                            # Eliminar etiquetas técnicas de modelos
                            tags = [r'<\|tool_call\|>', r'</?thought>', r'<\|.*?\|>', r'\[thought\]', r'\[/thought\]', r'---']
                            for tag in tags:
                                t = re.sub(tag, '', t, flags=re.IGNORECASE | re.DOTALL)
                            # Eliminar guías de razonamiento típicas de modelos (I need to, Step 1, etc)
                            narratives = [r'I need to.*?\n', r'Step \d+:.*?\n', r'Para continuar:.*?\n']
                            for nar in narratives:
                                t = re.sub(nar, '', t, flags=re.IGNORECASE | re.DOTALL)
                            # Eliminar JSONs sueltos del texto
                            t = re.sub(r'\{[^{}]*\}', '', t)
                            t = re.sub(r'\{.*\}', '', t, flags=re.DOTALL)
                            return t.strip()

                        # 2. Buscar TODOS los bloques JSON y quedarnos con el que tenga 'action'
                        json_blocks = re.findall(r'\{.*?\}', raw_response, re.DOTALL)
                        if json_blocks:
                            # Intentar encontrar el bloque que tenga contenido útil
                            for block in reversed(json_blocks):
                                try:
                                    candidate = json.loads(block)
                                    if "action" in candidate and candidate["action"] and candidate["action"] != "null":
                                        best_block = candidate
                                        break
                                except: continue
                            
                            # Si ninguno tiene acción, coger el último válido
                            if not best_block:
                                for block in reversed(json_blocks):
                                    try:
                                        best_block = json.loads(block)
                                        break
                                    except: continue
                        
                        if best_block:
                            thought = best_block.get("thought", "")
                            clean_text_from_json = best_block.get("response", "")
                            agent_action = best_block.get("action")
                            agent_params = best_block.get("params")

                            # Limpiar el texto extraído del JSON
                            raw_response = deep_clean(clean_text_from_json)
                            # Fallback si la limpieza borró demasiado o el campo estaba vacío
                            if not raw_response or len(raw_response) < 2:
                                raw_response = deep_clean(clean_text_from_json) or "Acción procesada."

                            if thought:
                                print(f"[Agente Pensamiento]: {thought}")
                            
                            # Si tenemos un bloque válido, salimos del bucle de reintentos
                            break
                        else:
                            print(f"[ChatService] Advertencia: No se encontró JSON válido en intento {attempt + 1}")
                            # Si es el último intento, limpiamos lo que haya para mostrarlo
                            if attempt == max_attempts - 1:
                                raw_response = deep_clean(raw_response)
                    except Exception as je:
                        print(f"[ChatService] Error parseando respuesta de Agente: {je}")
                else:
                    # Modo normal, un solo intento
                    break

            # 4. Procesar texto (TTS y Limpieza final)
            self.last_emojis = TextProcessor.extract_emojis(raw_response)
            clean_response = TextProcessor.clean_text_for_tts(raw_response)
            
            # --- Ejecutar acción de AGENTE si existe ---
            if agent_action and self.module_service:
                print(f"[Agente Ejecución]: Accionando herramienta '{agent_action}'...")
                # Usamos el despachador de comandos existente
                self.module_service.handle_voice_command(agent_action, agent_params or "")

            # 5. Si NO es silent, guardar respuesta en memoria
            if not silent:
                self.memory.add_message("assistant", raw_response)

            # 6. Si NO es silent Y NO saltamos TTS, lanzar TTS
            # Verificación extra: si es modo Agente, respetar el flag 'audio_agent' de configuración
            skip_agent_audio = is_agent_mode and not self.config.get("audio_agent", True)
            
            if not silent and not skip_tts and not skip_agent_audio:
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