from core.adapters.standard_stt_adapter import StandardSTTAdapter

class STTFactory:
    """
    Factoría para gestionar motores de Reconocimiento de Voz.
    """
    @staticmethod
    def list_providers():
        return ["None", "Standard (Google)"]

    @staticmethod
    def get_adapter(provider_name):
        if provider_name == "Standard (Google)":
            return StandardSTTAdapter()
        return None
