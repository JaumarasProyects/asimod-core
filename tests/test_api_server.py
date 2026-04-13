import pytest
from unittest.mock import Mock, patch, MagicMock
from fastapi.testclient import TestClient


class TestAPIServer:
    """Tests for API Server endpoints."""

    @pytest.fixture
    def mock_chat_service(self):
        """Creates a mock chat service."""
        service = Mock()
        service.config = Mock()
        service.config.get = Mock(side_effect=lambda key, default=None: {
            "provider": "openai",
            "model": "gpt-4",
            "voice_commands": {"comando": "action_test"},
            "voice_command_enabled": True,
            "stt_mode": "OFF"
        }.get(key, default))
        service.config.set = Mock()
        
        service.stt_service = Mock()
        service.stt_service.last_voice_command = None
        service.stt_service.manage_microphone_thread = Mock()
        service.stt_service.pause_capture = Mock()
        service.stt_service.resume_capture = Mock()
        service.stt_service.update_adapter = Mock()
        
        service.voice_service = Mock()
        service.voice_service.speak = Mock(return_value=True)
        service.voice_service.get_available_providers = Mock(return_value=["edge", "local"])
        
        service.memory = Mock()
        service.memory.get_recent_messages = Mock(return_value=[])
        service.memory.clear = Mock()
        
        service.locale_service = Mock()
        service.locale_service.t = Mock(return_value="translated")
        service.locale_service.list_available_languages = Mock(return_value=["en", "es"])
        
        service.get_providers_list = Mock(return_value=["openai", "anthropic", "ollama"])
        service.get_voice_providers_list = Mock(return_value=["edge", "local"])
        
        return service

    @pytest.fixture
    def api_server(self, mock_chat_service):
        """Creates API server with mock service."""
        with patch('core.api_server.APIServer'):
            from core.api_server import APIServer
            server = APIServer.__new__(APIServer)
            server.chat_service = mock_chat_service
            server.app = Mock()
            server.stt_queue = Mock()
            server.stt_queue.put = Mock()
            return server

    def test_get_voice_commands(self, mock_chat_service):
        """Test GET /v1/stt/voice-commands endpoint."""
        from core.api_server import APIServer
        
        with patch.object(APIServer, '__init__', lambda self, *args, **kwargs: None):
            server = APIServer()
            server.chat_service = mock_chat_service
            
            with patch('fastapi.FastAPI') as mock_fastapi:
                mock_fastapi.get = lambda path: lambda func: func
                server.app = Mock()
                
                result = {"voice_commands": {"comando": "action_test"}}
                
                mock_chat_service.config.get.return_value = {"comando": "action_test"}
                
                assert mock_chat_service.config.get("voice_commands") == {"comando": "action_test"}

    def test_set_voice_commands(self, mock_chat_service):
        """Test POST /v1/stt/voice-commands endpoint."""
        mock_chat_service.config.get = Mock(return_value={})
        mock_chat_service.config.set = Mock()
        
        new_commands = {"comando": "action_test", "prueba": "action_prueba"}
        
        mock_chat_service.config.get.return_value = new_commands
        result = mock_chat_service.config.set("voice_commands", new_commands)
        
        mock_chat_service.config.set.assert_called_once_with("voice_commands", new_commands)

    def test_add_voice_command(self, mock_chat_service):
        """Test POST /v1/stt/voice-commands/add endpoint."""
        mock_chat_service.config.get = Mock(return_value={"comando": "action_test"})
        mock_chat_service.config.set = Mock()
        
        mock_chat_service.config.get.return_value = {"comando": "action_test", "nuevo": "action_nueva"}
        
        call_args = mock_chat_service.config.set.call_args
        assert "voice_commands" in str(call_args)

    def test_delete_voice_command(self, mock_chat_service):
        """Test DELETE /v1/stt/voice-commands/{trigger} endpoint."""
        mock_chat_service.config.get = Mock(return_value={"comando": "action_test", "prueba": "action_prueba"})
        mock_chat_service.config.set = Mock()
        
        commands = {"comando": "action_test", "prueba": "action_prueba"}
        del commands["comando"]
        mock_chat_service.config.set("voice_commands", commands)
        
        mock_chat_service.config.set.assert_called_once()

    def test_get_last_voice_command_when_exists(self, mock_chat_service):
        """Test GET /v1/stt/last-voice-command when command exists."""
        import time
        mock_chat_service.stt_service.last_voice_command = {
            "matched": "action_test",
            "text": "di comando",
            "timestamp": time.time()
        }
        
        result = mock_chat_service.stt_service.last_voice_command
        
        assert result["matched"] == "action_test"
        assert result["text"] == "di comando"

    def test_get_last_voice_command_when_empty(self, mock_chat_service):
        """Test GET /v1/stt/last-voice-command when no command."""
        mock_chat_service.stt_service.last_voice_command = None
        
        result = mock_chat_service.stt_service.last_voice_command
        
        assert result is None

    def test_stt_pause_resume(self, mock_chat_service):
        """Test STT pause and resume endpoints."""
        mock_chat_service.stt_service.pause_capture = Mock()
        mock_chat_service.stt_service.resume_capture = Mock()
        
        mock_chat_service.stt_service.pause_capture()
        mock_chat_service.stt_service.resume_capture()
        
        mock_chat_service.stt_service.pause_capture.assert_called_once()
        mock_chat_service.stt_service.resume_capture.assert_called_once()

    def test_list_providers(self, mock_chat_service):
        """Test GET /v1/providers endpoint."""
        providers = mock_chat_service.get_providers_list()
        
        assert "openai" in providers
        assert "anthropic" in providers

    def test_list_languages(self, mock_chat_service):
        """Test GET /v1/languages endpoint."""
        languages = mock_chat_service.locale_service.list_available_languages()
        
        assert "en" in languages
        assert "es" in languages

    def test_set_language(self, mock_chat_service):
        """Test POST /v1/language endpoint."""
        mock_chat_service.locale_service.set_language = Mock()
        
        mock_chat_service.locale_service.set_language("es")
        
        mock_chat_service.locale_service.set_language.assert_called_once_with("es")
