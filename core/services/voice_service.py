import os
import time
import threading
from typing import List, Dict
from core.factories.voice_factory import VoiceFactory

class VoiceService:
    """
    Orquestador de voz que gestiona la generación y reproducción de audio.
    """
    def __init__(self, config_service):
        self.config = config_service
        self.current_adapter = None
        self.stt_service = None # Referencia opcional para sincronización
        self._set_adapter()
    
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

    def process_text(self, text: str):
        if not self.current_adapter:
            return

        save_dir = self.config.get("voice_save_path", "audio")
        if not os.path.exists(save_dir):
            os.makedirs(save_dir)

        ext = ".wav" if "Local" in self.current_adapter.name else ".mp3"
        ts = time.strftime("%Y%m%d_%H%M%S")
        filename = f"voice_{ts}{ext}"
        output_path = os.path.join(save_dir, filename)

        voice_id = self.config.get("voice_id")
        success = self.current_adapter.generate(text, output_path, voice_id=voice_id)
        
        if success:
            mode = self.config.get("voice_mode", "autoplay")
            if mode == "autoplay":
                self._play_audio_threaded(output_path)
            else:
                print(f"Audio guardado en: {output_path}")

    def _play_audio_threaded(self, file_path):
        thread = threading.Thread(target=self._play_audio, args=(file_path,), daemon=True)
        thread.start()

    def _play_audio(self, file_path):
        """Reproduce el audio usando pygame coordinado con el STT."""
        try:
            # 1. PAUSAR MICRO
            if self.stt_service:
                self.stt_service.pause_capture()

            import pygame
            if not pygame.mixer.get_init():
                pygame.mixer.init()
            
            pygame.mixer.music.load(file_path)
            pygame.mixer.music.play()
            
            while pygame.mixer.music.get_busy():
                pygame.time.Clock().tick(10)

            # 2. REANUDAR MICRO (el servicio ya gestiona el delay interno)
            if self.stt_service:
                self.stt_service.resume_capture()

        except Exception as e:
            print(f"Error reproduciendo audio: {e}")
            if self.stt_service:
                self.stt_service.resume_capture()
