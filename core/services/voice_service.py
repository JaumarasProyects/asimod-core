import os
import time
import threading
import traceback
import pygame
from typing import List, Dict, Optional
from core.factories.voice_factory import VoiceFactory


class VoiceService:
    """
    Orquestador de voz que gestiona la generación y reproducción de audio.
    """

    def __init__(self, config_service, locale_service=None):
        self.config = config_service
        self.locale_service = locale_service
        self.current_adapter = None
        self.stt_service = None  # Referencia opcional para sincronización
        self.is_playing = False  # Estado de reproducción actual
        self.is_generating = False # Estado de síntesis actual
        self.audio_start_time = None  # Timestamp cuando empieza
        self.audio_duration = None  # Duración del audio
        self._audio_queue = []  # Cola de audio para modo "wait"
        self._queue_lock = threading.Lock()
        self._destreaming_queue = []  # Cola para destreaming (texto completo -> chunks)
        self._destreaming_lock = threading.Lock()
        self._destreaming_active = False  # Flag para indicar si hay destreaming en proceso
        self.on_audio_start = None  # Callback para inicio de audio
        self.on_audio_end = None    # Callback para fin de audio
        self._init_mixer()
        self._set_adapter()

    def _init_mixer(self):
        """Inicializa el mixer de pygame una sola vez."""
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init()
            print("[VoiceService] Pygame mixer initialized.")
        except Exception as e:
            print(f"[VoiceService] Error initializing pygame mixer: {e}")

    def set_stt_service(self, stt_service):
        """Establece la conexión con el servicio de reconocimiento de voz."""
        self.stt_service = stt_service

    def _set_adapter(self):
        provider = self.config.get("voice_provider", "None")
        self.current_adapter = VoiceFactory.get_adapter(provider)

    def update_provider(self):
        self._set_adapter()

    def get_available_voices(self) -> List[Dict[str, str]]:
        if self.current_adapter:
            return self.current_adapter.list_voices()
        return []
    def speak_text(self, text: str, voice_id: str = None, voice_provider: str = None):
        clean_text = (text or "").strip()
        print(f"[VoiceService] speak_text called for: \"{clean_text[:50]}...\"")
        if not clean_text:
            return

        import asyncio
        import threading

        def _run_async_task():
            print("[VoiceService] Starting async task in background thread")
            new_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(new_loop)
            try:
                new_loop.run_until_complete(self.process_text(clean_text, voice_id, voice_provider))
                print("[VoiceService] async task finished successfully")
            except Exception as e:
                print(f"[VoiceService] Error in async background task: {e}")
            finally:
                new_loop.close()

        # Siempre ejecutamos en un hilo separado para evitar conflictos de event loop
        # con FastAPI/Uvicorn cuando se llama desde un endpoint síncrono.
        thread = threading.Thread(target=_run_async_task, daemon=True)
        thread.start()

    async def process_text(self, text: str, voice_id: str = None, voice_provider: str = None):
        """
        Punto de entrada principal para procesar texto a voz.
        """
        if not text or text.strip() == "":
            return

        # Pausar STT mientras generamos y eventualmente reproducimos
        if self.stt_service:
            self.stt_service.pause_capture()

        self.is_generating = True
        try:
            is_streaming = self.config.get("destreaming_enabled", False)
            
            if is_streaming:
                # Para streaming, dividimos en frases
                await self._process_text_single(text, voice_id, voice_provider)
            else:
                await self._process_text_single(text, voice_id, voice_provider)
        finally:
            self.is_generating = False
            # Solo reanudar aquí si NO se disparó una reproducción asíncrona (thread)
            # Nota: _play_audio_threaded lanzará un hilo si success=True, 
            # pero self.is_playing no será True hasta que el hilo empiece.
            # Sin embargo, agregamos un pequeño delay o delegamos a _play_audio.
            if not self.is_playing and self.stt_service:
                self.stt_service.resume_capture(delay=0.1)

    async def generate_audio_only(self, text: str, voice_id: str = None, voice_provider: str = None):
        """
        Genera audio sin reproducirlo. Retorna la ruta del archivo.
        """
        global_prov = self.config.get("voice_provider", "None")
        if not self.current_adapter or self.current_adapter.name != global_prov:
            self._set_adapter()

        target_provider = (
            voice_provider
            if (voice_provider and voice_provider != "" and voice_provider != "None")
            else global_prov
        )

        if target_provider == global_prov:
            adapter = self.current_adapter
        else:
            adapter = VoiceFactory.get_adapter(target_provider)

        if not adapter:
            adapter = self.current_adapter
            if not adapter:
                print("[VoiceService] No hay adaptador de voz disponible.")
                return None

        save_dir = self.config.get("voice_save_path", "audio")
        if not os.path.exists(save_dir):
            os.makedirs(save_dir)

        ext = ".wav" if "Local" in adapter.name else ".mp3"
        import time
        ts = time.strftime("%Y%m%d_%H%M%S")
        filename = f"voice_{ts}{ext}"
        output_path = os.path.join(save_dir, filename)

        if not text or text.strip() == "":
            print("[VoiceService] No hay texto para generar audio.")
            return None

        v_id_clean = voice_id.strip() if voice_id else ""

        if v_id_clean and v_id_clean != "None":
            final_voice_id = v_id_clean
        else:
            final_voice_id = self.config.get("voice_id")
            if not final_voice_id and self.locale_service:
                default_voice = self.locale_service.get_default_voice()
                final_voice_id = default_voice.get("voice_id")

        # LLAMADA ASÍNCRONA AL ADAPTADOR
        success = await adapter.generate(text, output_path, voice_id=final_voice_id)

        if success:
            return output_path
        return None

    async def _process_text_single(self, text: str, voice_id: str = None, voice_provider: str = None):
        """
        Procesa un texto único (sin destreaming).
        """
        # 1. Asegurar sincronización con la configuración global
        global_prov = self.config.get("voice_provider", "None")
        if not self.current_adapter or self.current_adapter.name != global_prov:
            self._set_adapter()

        # 2. Determinar qué motor usar (Personaje > Global)
        target_provider = (
            voice_provider
            if (voice_provider and voice_provider != "" and voice_provider != "None")
            else global_prov
        )

        # 3. Obtener adaptador para el motor objetivo
        if target_provider == global_prov:
            adapter = self.current_adapter
        else:
            adapter = VoiceFactory.get_adapter(target_provider)

        if not adapter:
            adapter = self.current_adapter
            if not adapter:
                print("[VoiceService] No hay adaptador de voz disponible.")
                return

        # 3. Generar archivo temporal
        save_dir = self.config.get("voice_save_path", "audio")
        if not os.path.exists(save_dir):
            os.makedirs(save_dir)

        ext = ".wav" if "Local" in adapter.name else ".mp3"
        import time
        ts = time.strftime("%Y%m%d_%H%M%S")
        filename = f"voice_{ts}{ext}"
        output_path = os.path.join(save_dir, filename)

        # 4. Obtener Voice ID adecuado
        v_id_clean = voice_id.strip() if voice_id else ""
        if v_id_clean and v_id_clean != "None":
            final_voice_id = v_id_clean
        else:
            final_voice_id = self.config.get("voice_id")
            if not final_voice_id and self.locale_service:
                default_voice = self.locale_service.get_default_voice()
                final_voice_id = default_voice.get("voice_id")
                if target_provider == global_prov:
                    self.config.set("voice_id", final_voice_id)

        print(f"[VoiceService] Generando audio con {adapter.name}... (ID: {final_voice_id})")
        
        # 5. Llamada asíncrona al generador
        success = await adapter.generate(text, output_path, voice_id=final_voice_id)

        if success:
            mode = self.config.get("voice_mode", "autoplay")
            if mode == "autoplay":
                self._play_audio_threaded(output_path)
            else:
                print(f"[VoiceService] Audio guardado en: {output_path}")
        else:
            print("[VoiceService] Falló la generación de audio.")

    def _process_text_destreaming(self, text: str, voice_id: str = None, voice_provider: str = None):
        """
        Procesa texto largo dividiéndolo en chunks sin romper frases.
        """
        chunks = self._split_text_into_chunks(text)
        print(f"[VoiceService] Destreaming: {len(chunks)} chunks generated from {len(text)} chars")
        
        # Forzar modo wait para reproducción secuencial
        self.config.set("voice_playback_mode", "wait")
        
        for i, chunk in enumerate(chunks):
            print(f"[VoiceService] Destreaming: Processing chunk {i+1}/{len(chunks)}")
            self._process_text_single(chunk, voice_id, voice_provider)

    def _split_text_into_chunks(self, text: str, chunk_size: int = None) -> list:
        """
        Divide el texto en chunks sin romper frases.
        """
        if chunk_size is None:
            chunk_size = self.config.get("destreaming_chunk_size", 500)
        
        import re
        
        # Separadores de oraciones
        sentence_endings = re.compile(r'(?<=[.!?])\s+')
        sentences = sentence_endings.split(text)
        
        chunks = []
        current_chunk = ""
        
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
            
            # Si una oración excede el chunk_size, la dividimos por comas/puntos y coma
            if len(sentence) > chunk_size:
                # Primero guardar lo que tenemos
                if current_chunk:
                    chunks.append(current_chunk)
                    current_chunk = ""
                
                # Dividir por frases más pequeñas (comas, puntos y coma, dos puntos)
                sub_sentences = re.split(r'(?<=[,;:])\s+', sentence)
                sub_current = ""
                
                for sub in sub_sentences:
                    sub = sub.strip()
                    if not sub:
                        continue
                    
                    if len(sub_current) + len(sub) + 1 <= chunk_size:
                        sub_current = (sub_current + " " + sub).strip()
                    else:
                        if sub_current:
                            chunks.append(sub_current)
                        sub_current = sub
                
                if sub_current:
                    current_chunk = sub_current
            else:
                # Verificar si al agregar la oración excedemos el límite
                if len(current_chunk) + len(sentence) + 1 <= chunk_size:
                    current_chunk = (current_chunk + " " + sentence).strip()
                else:
                    if current_chunk:
                        chunks.append(current_chunk)
                    current_chunk = sentence
        
        if current_chunk:
            chunks.append(current_chunk)
        
        return chunks

    def stop_audio(self):
        """
        Detiene la reproducción de audio actual, limpia la cola de destreaming
        y reanuda el micro.
        """
        try:
            if pygame.mixer.get_init():
                pygame.mixer.music.stop()

            self.is_playing = False

            with self._queue_lock:
                self._audio_queue.clear()
            
            with self._destreaming_lock:
                self._destreaming_queue.clear()
                self._destreaming_active = False

            if self.stt_service:
                self.stt_service.resume_capture(delay=0.1)

            print("[VoiceService] Audio stopped. Cleared destreaming queue.")

        except Exception as e:
            print(f"[VoiceService] Error deteniendo audio: {e}")
            self.is_playing = False
            with self._destreaming_lock:
                self._destreaming_active = False
            if self.stt_service:
                self.stt_service.resume_capture(delay=0.1)

    def _play_audio_threaded(self, file_path):
        playback_mode = self.config.get("voice_playback_mode", "interrupt")
        
        if playback_mode == "wait":
            with self._queue_lock:
                self._audio_queue.append(file_path)
                if not self.is_playing:
                    self.is_playing = True # Marcamos como ocupado antes de lanzar el hilo
                    next_file = self._audio_queue.pop(0)
                    thread = threading.Thread(target=self._play_audio, args=(next_file,), daemon=True)
                    thread.start()
        else:
            with self._queue_lock:
                self._audio_queue.clear()
            self.is_playing = True # Marcamos como ocupado
            thread = threading.Thread(target=self._play_audio, args=(file_path,), daemon=True)
            thread.start()

    def _play_audio(self, file_path):
        """
        Reproduce el audio usando pygame coordinado con el STT.
        """
        start_time = time.time()
        
        try:
            # 1. PAUSAR MICRO ANTES DE LA LOCUCIÓN
            if self.stt_service:
                self.stt_service.pause_capture()

            if not pygame.mixer.get_init():
                pygame.mixer.init()

            if not os.path.exists(file_path):
                print(f"[VoiceService] ERROR: Audio file not found: {file_path}")
                return

            print(f"[VoiceService] Loading audio: {file_path}")
            pygame.mixer.music.load(file_path)

            self.is_playing = True
            self.audio_start_time = start_time
            print(f"[VoiceService] Playing audio: {file_path}")
            
            if self.on_audio_start:
                self.on_audio_start()

            pygame.mixer.music.play()

            while pygame.mixer.music.get_busy():
                pygame.time.Clock().tick(10)

            print("[VoiceService] Audio playback finished.")

        except Exception as e:
            print(f"[VoiceService] Error reproduciendo audio '{file_path}': {e}")
            traceback_msg = traceback.format_exc()
            print(traceback_msg)

        finally:
            self.is_playing = False
            self.audio_duration = time.time() - start_time

            if self.on_audio_end:
                self.on_audio_end()

            if self.stt_service:
                self.stt_service.resume_capture()

            playback_mode = self.config.get("voice_playback_mode", "interrupt")
            if playback_mode == "wait":
                with self._queue_lock:
                    if self._audio_queue:
                        next_file = self._audio_queue.pop(0)
                        thread = threading.Thread(target=self._play_audio, args=(next_file,), daemon=True)
                        thread.start()