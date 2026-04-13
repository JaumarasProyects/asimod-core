import os
import threading
import time
from core.factories.stt_factory import STTFactory

class STTService:
    """
    Servicio de Reconocimiento de Voz que gestiona el micrófono y archivos.

    Modos soportados:
    - OFF
    - CHAT
    - COMMAND
    - QUESTION
    - VOICE_COMMAND (reconoce comandos del diccionario)
    """

    def __init__(self, config_service, on_chat_transcription=None, on_stt_result=None):
        self.config = config_service
        self.on_chat_transcription = on_chat_transcription
        self.on_stt_result = on_stt_result
        self.voice_command_callbacks = []  # Lista de funciones a llamar
        self.last_voice_command = None
        self.contextual_commands = {}  # Comandos inyectados por módulos activos
        self.base_module_commands = {} # Comandos globales de activación de módulos

        self.adapter = None
        self.is_listening = False
        self._is_paused_by_voice = False
        self._stop_event = threading.Event()
        self._thread = None

        self.update_adapter()

    def update_adapter(self):
        provider = self.config.get("stt_provider", "None")
        self.adapter = STTFactory.get_adapter(provider)
        self.manage_microphone_thread()

    def manage_microphone_thread(self):
        mode = str(self.config.get("stt_mode", "OFF")).upper()

        if mode in ("CHAT", "COMMAND", "QUESTION", "VOICE_COMMAND") and self.adapter:
            if not self.is_listening:
                self.start_listening()
        else:
            self.stop_listening()

    def set_mode(self, mode: str):
        self.config.set("stt_mode", mode.upper())
        self.manage_microphone_thread()

    def start_listening(self):
        if self.is_listening:
            return

        self.is_listening = True
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._thread.start()
        print("[STTService] Listening started.")

    def stop_listening(self):
        self._stop_event.set()
        self.is_listening = False
        print("[STTService] Listening stopped.")

    def pause_capture(self):
        self._is_paused_by_voice = True
        print("[STTService] Capture paused.")

    def resume_capture(self, delay: float = 0.5):
        def _delayed():
            if delay > 0:
                time.sleep(delay)
            self._is_paused_by_voice = False
            print("[STTService] Capture resumed.")

        threading.Thread(target=_delayed, daemon=True).start()

    def _dispatch_text(self, text: str):
        if not text or len(text.strip()) <= 2:
            return

        mode = str(self.config.get("stt_mode", "OFF")).upper()
        text = text.strip().lower()

        print(f"[STTService] Recognized text in mode {mode}: {text}")

        if mode == "CHAT":
            if self.on_chat_transcription:
                self.on_chat_transcription(text)

        elif mode in ("COMMAND", "QUESTION"):
            if self.on_stt_result:
                self.on_stt_result(text)

            if mode == "QUESTION":
                self.config.set("stt_mode", "COMMAND")

        elif mode == "VOICE_COMMAND":
            command_matched = self._check_voice_commands(text)
            if command_matched:
                print(f"[STTService] Voice command recognized: {command_matched}")
                self.last_voice_command = {"matched": command_matched, "text": text, "timestamp": time.time()}
            else:
                print(f"[STTService] No command matched for: {text}")
            
            for callback in self.voice_command_callbacks:
                try:
                    callback(command_matched, text)
                except Exception as e:
                    print(f"[STTService] Error in voice command callback: {e}")

    def _check_voice_commands(self, text: str) -> str:
        """
        Evalúa el texto contra los diccionarios de comandos con prioridad:
        Contextual (Módulo) > Base (Navegación) > Global (Configuración).
        Usa coincidencia de la frase más larga para evitar ambigüedades.
        """
        text_lower = text.lower()
        
        # 1. Preparar lista de comandos ordenados por longitud del trigger (descendente)
        # Esto asegura que "crear 3d" se evalúe antes que "3".
        all_priorities = [
            self.contextual_commands,         # Prioridad 1: Módulo activo
            self.base_module_commands,        # Prioridad 2: Navegación de paneles
            dict(self.config.get("voice_commands", {})) # Prioridad 3: Configuración global
        ]

        for cmd_dict in all_priorities:
            if not cmd_dict:
                continue
            
            # Ordenar triggers por longitud para máxima precisión en este nivel de prioridad
            sorted_triggers = sorted(cmd_dict.items(), key=lambda x: len(x[0]), reverse=True)
            
            for trigger, action in sorted_triggers:
                if trigger.lower() in text_lower:
                    return action
        
        return None

    def set_contextual_commands(self, commands: dict):
        """Establece los comandos específicos del módulo activo."""
        self.contextual_commands = commands
        if commands:
            print(f"[STTService] Contextual commands injected: {list(commands.keys())}")

    def clear_contextual_commands(self):
        """Limpia los comandos del módulo."""
        self.contextual_commands = {}
        print("[STTService] Contextual commands cleared.")

    def set_base_module_commands(self, commands: dict):
        """Establece los comandos permanentes de los módulos (ej: sus nombres)."""
        self.base_module_commands = commands
        if commands:
            print(f"[STTService] Base module commands registered: {list(commands.keys())}")

    def add_voice_command_callback(self, callback):
        """Añade un suscriptor a los eventos de comando de voz."""
        if callback not in self.voice_command_callbacks:
            self.voice_command_callbacks.append(callback)

    def set_voice_command_callback(self, callback):
        """Mantenemos este método por compatibilidad, pero ahora usa la lista."""
        self.add_voice_command_callback(callback)

    def _listen_loop(self):
        try:
            import speech_recognition as sr

            recognizer = sr.Recognizer()
            mic = sr.Microphone()

            with mic as source:
                recognizer.adjust_for_ambient_noise(source)

            while not self._stop_event.is_set():
                if self._is_paused_by_voice:
                    time.sleep(0.2)
                    continue

                try:
                    with mic as source:
                        audio = recognizer.listen(source, timeout=3, phrase_time_limit=10)

                    if self._is_paused_by_voice:
                        continue

                    temp_path = f"temp_recording_{id(threading.current_thread())}.wav"
                    try:
                        with open(temp_path, "wb") as f:
                            f.write(audio.get_wav_data())
                    except IOError as e:
                        print(f"[STTService] Error writing temp file: {e}")
                        continue

                    text = self.adapter.transcribe(temp_path)

                    try:
                        if os.path.exists(temp_path):
                            os.remove(temp_path)
                    except IOError as e:
                        print(f"[STTService] Could not remove temp file: {e}")

                    self._dispatch_text(text)

                except sr.WaitTimeoutError:
                    continue
                except Exception as e:
                    print(f"[STTService] Error in listen loop: {e}")
                    time.sleep(1)

        except Exception as e:
            print(f"[STTService] Error initializing microphone: {e}")

    def process_file(self, file_path):
        if not self.adapter:
            return

        def _worker():
            text = self.adapter.transcribe(file_path)
            self._dispatch_text(text)

        threading.Thread(target=_worker, daemon=True).start()