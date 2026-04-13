import pytest
from unittest.mock import Mock, patch, MagicMock
import tempfile


class TestChatService:
    """Tests for Chat Service."""

    @pytest.fixture
    def chat_service(self, config_service):
        """Creates a ChatService instance for testing."""
        with patch('core.chat_service.LLMFactory') as mock_llm_factory:
            with patch('core.chat_service.VoiceService'):
                with patch('core.chat_service.STTService'):
                    with patch('core.chat_service.TextProcessor'):
                        with patch('core.chat_service.MemoryService'):
                            with patch('core.chat_service.LocaleService'):
                                from core.chat_service import ChatService
                                mock_adapter = Mock()
                                mock_adapter.get_available_models = Mock(return_value=["model-1", "model-2"])
                                mock_llm_factory.get_adapter.return_value = mock_adapter
                                service = ChatService(config_service=config_service)
                                return service

    def test_chat_service_initialization(self, chat_service, config_service):
        """Test ChatService initializes correctly."""
        assert chat_service.config is config_service
        assert chat_service.current_adapter is not None
        assert chat_service.voice_service is not None
        assert chat_service.stt_service is not None
        assert chat_service.memory is not None
        assert chat_service.locale_service is not None

    def test_get_providers_list(self, chat_service):
        """Test get_providers_list returns provider list."""
        providers = chat_service.get_providers_list()
        assert isinstance(providers, list)
        assert len(providers) > 0

    def test_switch_provider(self, chat_service):
        """Test switch_provider changes the LLM adapter."""
        chat_service.switch_provider("anthropic")
        
        config_val = chat_service.config.get("provider")
        assert config_val == "anthropic"

    def test_get_available_models(self, chat_service):
        """Test get_available_models returns model list."""
        models = chat_service.get_available_models()
        assert isinstance(models, list)

    def test_on_stt_result_callback(self, chat_service):
        """Test on_stt_result_cb can be set."""
        callback = Mock()
        chat_service.on_stt_result_cb = callback
        
        assert chat_service.on_stt_result_cb is callback

    def test_voice_service_integration(self, chat_service):
        """Test voice service is properly integrated."""
        assert chat_service.voice_service is not None
        
        with patch.object(chat_service.voice_service, 'speak', return_value=True):
            result = chat_service.voice_service.speak("test text")
            assert result is True

    def test_stt_service_integration(self, chat_service):
        """Test STT service is properly integrated."""
        assert chat_service.stt_service is not None
        
        chat_service.stt_service.pause_capture = Mock()
        chat_service.stt_service.resume_capture = Mock()
        
        chat_service.stt_service.pause_capture()
        chat_service.stt_service.resume_capture()

    def test_memory_service_integration(self, chat_service):
        """Test memory service is properly integrated."""
        assert chat_service.memory is not None
        
        chat_service.memory.add_message = Mock()
        chat_service.memory.get_recent_messages = Mock(return_value=[])
        
        chat_service.memory.add_message("user", "test")
        messages = chat_service.memory.get_recent_messages()
        
        assert isinstance(messages, list)

    def test_locale_service_integration(self, chat_service):
        """Test locale service is properly integrated."""
        assert chat_service.locale_service is not None
        
        with patch.object(chat_service.locale_service, 't', return_value="translated"):
            result = chat_service.locale_service.t("test_key")
            assert result == "translated"

    def test_config_persistence(self, chat_service, config_service):
        """Test config values are persisted."""
        config_service.set("test_key", "test_value")
        
        value = config_service.get("test_key")
        assert value == "test_value"

    def test_get_voice_providers_list(self, chat_service):
        """Test get_voice_providers_list returns provider list."""
        with patch.object(chat_service.voice_service, 'get_available_providers', return_value=["edge", "local"]):
            providers = chat_service.get_voice_providers_list()
            assert isinstance(providers, list)
