import pytest
from unittest.mock import Mock, patch, MagicMock
import requests


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

    def test_adapter_initialization(self, whatsapp_adapter):
        assert whatsapp_adapter.phone_number_id == "1102608142925984"
        assert whatsapp_adapter.access_token == "test_token"
        assert whatsapp_adapter.verify_token == "test_verify"
        assert whatsapp_adapter.name == "WhatsApp"

    def test_get_webhook_verify_token(self, whatsapp_adapter):
        assert whatsapp_adapter.get_webhook_verify_token() == "test_verify"

    @patch('core.adapters.whatsapp_adapter.requests.post')
    def test_send_text_success(self, mock_post, whatsapp_adapter):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        result = whatsapp_adapter.send_text("34699501082", "Hola desde test!")

        assert result is True
        mock_post.assert_called_once()
        call_args = mock_post.call_args[0]
        assert "messages" in call_args[0]

    @patch('core.adapters.whatsapp_adapter.requests.post')
    def test_send_text_failure(self, mock_post, whatsapp_adapter):
        mock_response = Mock()
        mock_response.status_code = 401
        mock_post.return_value = mock_response

        result = whatsapp_adapter.send_text("34699501082", "Hola")

        assert result is False

    @patch('core.adapters.whatsapp_adapter.requests.post')
    def test_send_audio(self, mock_post, whatsapp_adapter):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        with patch.object(whatsapp_adapter, '_upload_media', return_value="media123"):
            result = whatsapp_adapter.send_audio("34699501082", "test.ogg")

        assert result is True

    @patch('core.adapters.whatsapp_adapter.requests.post')
    def test_send_image(self, mock_post, whatsapp_adapter):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        with patch.object(whatsapp_adapter, '_upload_media', return_value="media123"):
            result = whatsapp_adapter.send_image("34699501082", "test.jpg", "Caption test")

        assert result is True

    def test_receive_text_message(self, whatsapp_adapter):
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

        result = whatsapp_adapter.receive_message(webhook_data)

        assert result is not None
        assert result["user_id"] == "34699501082"
        assert result["text"] == "Hola mundo"
        assert result["media_url"] is None

    def test_receive_audio_message(self, whatsapp_adapter):
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

        with patch.object(whatsapp_adapter, '_get_media_url', return_value="https://example.com/audio.ogg"):
            result = whatsapp_adapter.receive_message(webhook_data)

        assert result is not None
        assert result["user_id"] == "34699501082"
        assert result["text"] is None
        assert result["media_type"] == "audio"

    def test_receive_image_message(self, whatsapp_adapter):
        webhook_data = {
            "entry": [{
                "changes": [{
                    "value": {
                        "messages": [{
                            "from": "34699501082",
                            "type": "image",
                            "image": {"id": "image123", "caption": "Una imagen"}
                        }]
                    }
                }]
            }]
        }

        with patch.object(whatsapp_adapter, '_get_media_url', return_value="https://example.com/image.jpg"):
            result = whatsapp_adapter.receive_message(webhook_data)

        assert result is not None
        assert result["user_id"] == "34699501082"
        assert result["text"] == "Una imagen"
        assert result["media_type"] == "image"

    def test_receive_message_no_messages(self, whatsapp_adapter):
        webhook_data = {
            "entry": [{
                "changes": [{
                    "value": {}
                }]
            }]
        }

        result = whatsapp_adapter.receive_message(webhook_data)
        assert result is None


class TestWhatsAppSendMessage:
    """Integration test to send a real WhatsApp message."""

    @pytest.mark.integration
    def test_send_whatsapp_message(self):
        """Send a real message to test WhatsApp API."""
        import os
        from core.adapters.whatsapp_adapter import WhatsAppAdapter

        phone_id = os.environ.get("WHATSAPP_PHONE_ID")
        access_token = os.environ.get("WHATSAPP_ACCESS_TOKEN")
        to_number = os.environ.get("WHATSAPP_TEST_TO")

        if not phone_id or not access_token or not to_number:
            pytest.skip("WhatsApp credentials not set in environment")

        adapter = WhatsAppAdapter(phone_id, access_token)
        result = adapter.send_text(to_number, "🧪 Mensaje de prueba desde ASIMOD")

        assert result is True
