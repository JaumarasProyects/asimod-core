import os
import threading
import time
from core.factories.stt_factory import STTFactory

class STTService:
    """
    Servicio de Reconocimiento de Voz que gestiona el micrófono y archivos.
    """
    def __init__(self, config_service, on_transcription_complete):
        self.config = config_service
        self.on_complete = on_transcription_complete
        self.adapter = None
        self.is_listening = False
        self._is_paused_by_voice = False # Flag para silenciar mientras suena audio
        self._stop_event = threading.Event()
        self._thread = None
        self.update_adapter()

    def update_adapter(self):
        provider = self.config.get("stt_provider", "None")
        self.adapter = STTFactory.get_adapter(provider)
        self.manage_microphone_thread()

    def manage_microphone_thread(self):
        mode = self.config.get("stt_mode", "none")
        if mode == "micro" and self.adapter:
            if not self.is_listening:
                self.start_listening()
        else:
            self.stop_listening()

    def start_listening(self):
        self.is_listening = True
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._thread.start()

    def stop_listening(self):
        self._stop_event.set()
        self.is_listening = False

    def pause_capture(self):
        """Pausa temporal de la escucha."""
        self._is_paused_by_voice = True

    def resume_capture(self, delay: float = 0.5):
        """Reanuda la escucha con un retraso de seguridad (no bloqueante)."""
        def _delayed():
            if delay > 0:
                time.sleep(delay)
            self._is_paused_by_voice = False
        
        threading.Thread(target=_delayed, daemon=True).start()

    def _listen_loop(self):
        """Hilo de escucha activa usando SpeechRecognition + Whisper."""
        try:
            import speech_recognition as sr
            recognizer = sr.Recognizer()
            mic = sr.Microphone()
            
            with mic as source:
                recognizer.adjust_for_ambient_noise(source)
                
            while not self._stop_event.is_set():
                # SI ESTÁ PAUSADO POR VOZ, SALTAMOS ESTE CICLO
                if self._is_paused_by_voice:
                    time.sleep(0.5)
                    continue

                try:
                    with mic as source:
                        audio = recognizer.listen(source, timeout=3, phrase_time_limit=10)
                        
                    # Comprobar de nuevo antes de procesar por si se pausó durante la escucha
                    if self._is_paused_by_voice:
                        continue

                    temp_path = "temp_recording.wav"
                    with open(temp_path, "wb") as f:
                        f.write(audio.get_wav_data())
                    
                    text = self.adapter.transcribe(temp_path)
                    
                    if text and len(text) > 2:
                        self.on_complete(text)
                        
                    if os.path.exists(temp_path): os.remove(temp_path)
                    
                except sr.WaitTimeoutError:
                    continue
                except Exception as e:
                    print(f"Error en bucle STT: {e}")
                    time.sleep(1)
        except Exception as e:
            print(f"Error inicializando micrófono: {e}")

    def process_file(self, file_path):
        if not self.adapter:
            return
            
        def _worker():
            text = self.adapter.transcribe(file_path)
            if text:
                self.on_complete(text)
        
        threading.Thread(target=_worker, daemon=True).start()
