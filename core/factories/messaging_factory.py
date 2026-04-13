from core.adapters.whatsapp_adapter import WhatsAppAdapter
from core.adapters.telegram_adapter import TelegramAdapter


class MessagingFactory:
    """
    Factoría para instanciar adaptadores de mensajería.
    """
    @staticmethod
    def list_providers():
        return ["WhatsApp", "Telegram", "Discord", "Email"]

    @staticmethod
    def get_adapter(provider_name, config):
        """
        Retorna el adaptador de mensajería configurado.
        """
        if provider_name == "WhatsApp":
            phone_id = config.get("whatsapp_phone_id", "")
            token = config.get("whatsapp_access_token", "")
            verify = config.get("whatsapp_verify_token", "asimod_verify_token")
            if not phone_id or not token:
                return None
            return WhatsAppAdapter(phone_id, token, verify)

        elif provider_name == "Telegram":
            bot_token = config.get("telegram_bot_token", "")
            if not bot_token:
                return None
            return TelegramAdapter(bot_token)

        return None
