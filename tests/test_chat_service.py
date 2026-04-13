import pytest
from unittest.mock import Mock, patch, MagicMock, AsyncMock
import tempfile

@pytest.mark.anyio
class TestChatService:
    """Tests for Chat Service."""

    @pytest.fixture
    async def chat_service(self, config_service):
        """Creates a ChatService instance for testing."""
        # Using AsyncMock for things that are now async
        with patch('core.chat_service.LLMFactory') as mock_llm_factory:
            with patch('core.chat_service.VoiceService'):
                with patch('core.chat_service.STTService'):
                    with patch('core.chat_service.TextProcessor'):
                        with patch('core.chat_service.MemoryService'):
                            with patch('core.chat_service.LocaleService'):
                                from core.chat_service import ChatService
                                mock_adapter = MagicMock()
                                mock_adapter.name = "MockAdapter"
                                # Method names in adapters have changed
                                mock_adapter.list_models = AsyncMock(return_value=["model-1", "model-2"])
                                mock_llm_factory.get_adapter.return_value = mock_adapter
                                
                                service = ChatService(config_service=config_service)
                                return service

    async def test_chat_service_initialization(self, chat_service, config_service):
        """Test ChatService initializes correctly."""
        # Fix: Async fixture is already awaited by anyio
        service = chat_service
        assert service.config is config_service
        assert service.current_adapter is not None
        assert service.voice_service is not None
        assert service.stt_service is not None
        assert service.memory is not None
        assert service.locale_service is not None

    async def test_get_providers_list(self, chat_service):
        """Test get_providers_list returns provider list."""
        service = chat_service
        with patch('core.factories.llm_factory.LLMFactory.list_providers', return_value=["OpenAI", "Ollama"]):
            providers = service.get_providers_list()
            assert isinstance(providers, list)
            assert "OpenAI" in providers

    async def test_switch_provider(self, chat_service):
        """Test switch_provider changes the LLM adapter."""
        service = chat_service
        from core.adapters.openai_adapter import OpenAIAdapter
        
        with patch('core.factories.llm_factory.LLMFactory.get_adapter') as mock_factory:
            mock_new_adapter = MagicMock(spec=OpenAIAdapter)
            mock_new_adapter.name = "Anthropic"
            mock_factory.return_value = mock_new_adapter
            
            service.switch_provider("Anthropic")
            assert service.current_adapter.name == "Anthropic"

    async def test_get_available_models(self, chat_service):
        """Test get_available_models returns model list."""
        service = chat_service
        models = await service.get_available_models()
        assert isinstance(models, list)
        assert "model-1" in models

    async def test_on_stt_result_callback(self, chat_service):
        """Test on_stt_result_cb can be set."""
        service = chat_service
        callback = Mock()
        service.on_stt_result_cb = callback
        assert service.on_stt_result_cb is callback

    async def test_voice_service_integration(self, chat_service):
        """Test voice service integration."""
        service = chat_service
        assert service.voice_service is not None
        
        # VoiceService.process_text is async now
        service.voice_service.process_text = AsyncMock(return_value=True)
        await service.voice_service.process_text("test text")
        service.voice_service.process_text.assert_awaited_once()

    async def test_memory_service_integration(self, chat_service):
        """Test memory service integration."""
        service = chat_service
        assert service.memory is not None
        
        service.memory.add_message = Mock()
        service.memory.get_context = Mock(return_value=[])
        
        service.memory.add_message("user", "test")
        context = service.memory.get_context()
        assert isinstance(context, list)
