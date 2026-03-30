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

    def process_text(self, text: str, voice_id: str = None, voice_provider: str = None):
        # 1. Asegurar sincronización con la configuración global
        global_prov = self.config.get("voice_provider", "None")
        if not self.current_adapter or self.current_adapter.name != global_prov:
            self._set_adapter()

        # 2. Determinar qué motor usar (Personaje > Global)
        target_provider = voice_provider if (voice_provider and voice_provider != "" and voice_provider != "None") else global_prov
        
        # 3. Obtener adaptador para el motor objetivo
        if target_provider == global_prov:
            adapter = self.current_adapter
        else:
            adapter = VoiceFactory.get_adapter(target_provider)
        
        if not adapter:
            # Si el motor deseado no existe, intentar usar el global como último recurso
            adapter = self.current_adapter
            if not adapter: return

        save_dir = self.config.get("voice_save_path", "audio")
        if not os.path.exists(save_dir):
            os.makedirs(save_dir)

        # Usar extensión correcta según adaptador
        ext = ".wav" if "Local" in adapter.name else ".mp3"
        ts = time.strftime("%Y%m%d_%H%M%S")
        filename = f"voice_{ts}{ext}"
        output_path = os.path.join(save_dir, filename)

        # Priorizar voz del personaje si existe y no es "None"/vacío
        # Limpiar espacios en blanco para evitar falsos positivos
        v_id_clean = voice_id.strip() if voice_id else ""
        
        if v_id_clean and v_id_clean != "None" and v_id_clean != "":
            final_voice_id = v_id_clean
        else:
            final_voice_id = self.config.get("voice_id")
        
        success = adapter.generate(text, output_path, voice_id=final_voice_id)
        
        if success:
            mode = self.config.get("voice_mode", "autoplay")
            if mode == "autoplay":
                self._play_audio_threaded(output_path)
            else:
                print(f"Audio guardado en: {output_path}")

    def stop_audio(self):
        """Detiene la reproducción de audio actual y reanuda el micro."""
        try:
            import pygame
            if pygame.mixer.get_init():
                pygame.mixer.music.stop()
            
            if self.stt_service:
                self.stt_service.resume_capture(delay=0.1) # Reanudación rápida tras stop manual
        except Exception as e:
            print(f"Error deteniendo audio: {e}")

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
