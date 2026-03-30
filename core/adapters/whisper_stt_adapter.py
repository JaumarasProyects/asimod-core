import os
from core.ports.stt_port import STTPort

class WhisperSTTAdapter(STTPort):
    """
    Adaptador para transcribir audio usando OpenAI Whisper.
    """
    def __init__(self, model_size="tiny"):
        self.model_size = model_size
        self._model = None

    @property
    def name(self) -> str:
        return f"Whisper ({self.model_size})"

    def _get_model(self):
        if not self._model:
            try:
                # Usar faster-whisper si está disponible por velocidad
                from faster_whisper import WhisperModel
                self._model = WhisperModel(self.model_size, device="cpu", compute_type="int8")
            except ImportError:
                # Fallback a whisper estándar
                import whisper
                self._model = whisper.load_model(self.model_size)
        return self._model

    def transcribe(self, audio_path: str) -> str:
        if not os.path.exists(audio_path):
            return ""
            
        try:
            model = self._get_model()
            
            # Detección de tipo de modelo para llamar al método correcto
            if hasattr(model, "transcribe") and not hasattr(model, "segments"):
                # Whisper estándar
                result = model.transcribe(audio_path, language="es")
                return result["text"].strip()
            else:
                # Faster-whisper
                segments, info = model.transcribe(audio_path, beam_size=5, language="es")
                return " ".join([segment.text for segment in segments]).strip()
                
        except Exception as e:
            print(f"Error transcribiendo con Whisper: {e}")
            return ""
