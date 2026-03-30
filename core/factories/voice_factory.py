from core.adapters.edge_voice_adapter import EdgeVoiceAdapter
from core.adapters.local_voice_adapter import LocalVoiceAdapter

class VoiceFactory:
    """
    Factoría para instanciar diversos adaptadores de TTS.
    """
    @staticmethod
    def list_providers() -> list:
        return ["None", "Edge TTS", "Local TTS"]

    @staticmethod
    def get_adapter(provider_name):
        if provider_name == "Edge TTS":
            return EdgeVoiceAdapter()
        elif provider_name == "Local TTS":
            return LocalVoiceAdapter()
        return None
