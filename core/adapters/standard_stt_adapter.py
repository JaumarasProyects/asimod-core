import speech_recognition as sr
from core.ports.stt_port import STTPort

class StandardSTTAdapter(STTPort):
    """
    Adaptador de Reconocimiento de Voz estándar (Google Speech Recognition).
    Es el sistema que usa ASIMOD por defecto para una respuesta rápida.
    """
    def __init__(self, language="es-ES"):
        self.language = language

    @property
    def name(self) -> str:
        return "Standard (Google)"

    def transcribe(self, audio_path: str) -> str:
        recognizer = sr.Recognizer()
        try:
            with sr.AudioFile(audio_path) as source:
                audio_data = recognizer.record(source)
                # Usar el servicio de Google (requiere internet)
                text = recognizer.recognize_google(audio_data, language=self.language)
                return text.strip()
        except sr.UnknownValueError:
            # No se entendió nada
            return ""
        except sr.RequestError as e:
            print(f"Error en el servicio Google STT: {e}")
            return ""
        except Exception as e:
            print(f"Error transcribiendo audio (Standard): {e}")
            return ""
