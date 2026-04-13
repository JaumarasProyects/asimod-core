import pytest
from unittest.mock import Mock, patch, MagicMock, AsyncMock
import httpx

@pytest.mark.anyio
class TestWhatsAppAdapter:
    """Tests for WhatsApp adapter."""

    @pytest.fixture
    def whatsapp_adapter(self):
        from core.adapters.whatsapp_adapter import WhatsAppAdapter
        return WhatsAppAdapter(
            phone_number_id="1102608142925984",
            access_token="test_token",
            verify_token="test_verify"
        )

    async def test_adapter_initialization(self, whatsapp_adapter):
        assert whatsapp_adapter.phone_number_id == "1102608142925984"
        assert whatsapp_adapter.access_token == "test_token"
        assert whatsapp_adapter.verify_token == "test_verify"
        assert whatsapp_adapter.name == "WhatsApp"

    async def test_get_webhook_verify_token(self, whatsapp_adapter):
        assert whatsapp_adapter.get_webhook_verify_token() == "test_verify"

    async def test_send_text_success(self, whatsapp_adapter):
        # Mocking httpx.AsyncClient.post
        with patch('httpx.AsyncClient.post', new_callable=AsyncMock) as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_post.return_value = mock_response

            result = await whatsapp_adapter.send_text("34699501082", "Hola desde test!")

            assert result is True
            mock_post.assert_awaited_once()

    async def test_send_text_failure(self, whatsapp_adapter):
        with patch('httpx.AsyncClient.post', new_callable=AsyncMock) as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 401
            mock_post.return_value = mock_response

            result = await whatsapp_adapter.send_text("34699501082", "Hola")

            assert result is False

    async def test_send_audio(self, whatsapp_adapter):
        with patch('httpx.AsyncClient.post', new_callable=AsyncMock) as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_post.return_value = mock_response

            # Mock internal upload
            with patch.object(whatsapp_adapter, '_upload_media', new_callable=AsyncMock, return_value="media123"):
                result = await whatsapp_adapter.send_audio("34699501082", "test.ogg")

            assert result is True

    async def test_receive_text_message(self, whatsapp_adapter):
        webhook_data = {
            "entry": [{
                "changes": [{
                    "value": {
                        "messages": [{
                            "from": "34699501082",
                            "type": "text",
                            "text": {"body": "Hola mundo"}
                        }]
                    }
                }]
            }]
        }

        result = await whatsapp_adapter.receive_message(webhook_data)

        assert result is not None
        assert result["user_id"] == "34699501082"
        assert result["text"] == "Hola mundo"
        assert result["media_url"] is None

    async def test_receive_audio_message(self, whatsapp_adapter):
        webhook_data = {
            "entry": [{
                "changes": [{
                    "value": {
                        "messages": [{
                            "from": "34699501082",
                            "type": "audio",
                            "audio": {"id": "audio123"}
                        }]
                    }
                }]
            }]
        }

        with patch.object(whatsapp_adapter, '_get_media_url', new_callable=AsyncMock, return_value="https://example.com/audio.ogg"):
            result = await whatsapp_adapter.receive_message(webhook_data)

        assert result is not None
        assert result["user_id"] == "34699501082"
        assert result["text"] is None
        assert result["media_type"] == "audio"

    async def test_receive_message_no_messages(self, whatsapp_adapter):
        webhook_data = {
            "entry": [{
                "changes": [{
                    "value": {}
                }]
            }]
        }

        result = await whatsapp_adapter.receive_message(webhook_data)
        assert result is None

class TestWhatsAppSendMessage:
    """Integration test to send a real WhatsApp message."""

    @pytest.mark.anyio
    # Usando el mark propio si es necesario o saltando si faltan envs
    async def test_send_whatsapp_message(self):
        """Send a real message to test WhatsApp API."""
        import os
        from core.adapters.whatsapp_adapter import WhatsAppAdapter

        phone_id = os.environ.get("WHATSAPP_PHONE_ID")
        access_token = os.environ.get("WHATSAPP_ACCESS_TOKEN")
        to_number = os.environ.get("WHATSAPP_TEST_TO")

        if not phone_id or not access_token or not to_number:
            pytest.skip("WhatsApp credentials not set in environment")

        adapter = WhatsAppAdapter(phone_id, access_token)
        result = await adapter.send_text(to_number, "🧪 Mensaje de prueba desde ASIMOD")

        assert result is True
