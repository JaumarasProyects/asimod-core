import pytest
from unittest.mock import Mock, patch, MagicMock


class TestLLMAdapters:
    """Tests for LLM Adapters."""

    def test_openai_adapter_complete(self, config_service):
        """Test OpenAI adapter completion."""
        from core.adapters.openai_adapter import OpenAIAdapter
        
        with patch('requests.post') as mock_post:
            mock_response = Mock()
            mock_response.json.return_value = {
                'choices': [{'message': {'content': 'Test response'}}]
            }
            mock_response.raise_for_status = Mock()
            mock_post.return_value = mock_response
            
            adapter = OpenAIAdapter(config_service)
            result = adapter.complete([{"role": "user", "content": "Hello"}], 1024, 0.7)
            
            assert result == "Test response"
            mock_post.assert_called_once()

    def test_openai_adapter_get_models(self, config_service):
        """Test OpenAI adapter get_available_models."""
        from core.adapters.openai_adapter import OpenAIAdapter
        
        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.json.return_value = {
                'data': [{'id': 'gpt-4'}, {'id': 'gpt-3.5-turbo'}]
            }
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response
            
            adapter = OpenAIAdapter(config_service)
            models = adapter.get_available_models()
            
            assert "gpt-4" in models

    def test_ollama_adapter_complete(self, config_service):
        """Test Ollama adapter completion."""
        from core.adapters.ollama_adapter import OllamaAdapter
        
        with patch('requests.post') as mock_post:
            mock_response = Mock()
            mock_response.json.return_value = {
                'response': 'Ollama response'
            }
            mock_response.raise_for_status = Mock()
            mock_post.return_value = mock_response
            
            adapter = OllamaAdapter(config_service)
            result = adapter.complete([{"role": "user", "content": "Hello"}], 1024, 0.7)
            
            assert result == "Ollama response"

    def test_anthropic_adapter_complete(self, config_service):
        """Test Anthropic adapter completion."""
        from core.adapters.anthropic_adapter import AnthropicAdapter
        
        with patch('requests.post') as mock_post:
            mock_response = Mock()
            mock_response.json.return_value = {
                'content': [{'text': 'Anthropic response'}]
            }
            mock_response.raise_for_status = Mock()
            mock_post.return_value = mock_response
            
            adapter = AnthropicAdapter(config_service)
            result = adapter.complete([{"role": "user", "content": "Hello"}], 1024, 0.7)
            
            assert result == "Anthropic response"

    def test_llm_factory_returns_correct_adapter(self, config_service):
        """Test LLMFactory returns correct adapter type."""
        from core.factories.llm_factory import LLMFactory
        
        config_service.set("provider", "openai")
        adapter = LLMFactory.get_adapter("openai", config_service)
        assert adapter is not None
        
        config_service.set("provider", "ollama")
        adapter = LLMFactory.get_adapter("ollama", config_service)
        assert adapter is not None

    @patch('core.adapters.gguf_adapter.Llama')
    def test_gguf_adapter_complete(self, mock_llama, config_service):
        """Test GGUF adapter completion."""
        from core.adapters.gguf_adapter import GGUFAdapter
        
        mock_instance = MagicMock()
        mock_instance.create_chat_completion.return_value = {
            'choices': [{'message': {'content': 'GGUF response'}}]
        }
        mock_llama.return_value = mock_instance
        
        adapter = GGUFAdapter(config_service)
        result = adapter.complete([{"role": "user", "content": "Hello"}], 1024, 0.7)
        
        assert result == "GGUF response"

    def test_adapter_handles_empty_messages(self, config_service):
        """Test adapter handles empty messages list."""
        from core.adapters.openai_adapter import OpenAIAdapter
        
        with patch('requests.post') as mock_post:
            mock_response = Mock()
            mock_response.json.return_value = {
                'choices': [{'message': {'content': 'Response'}}]
            }
            mock_response.raise_for_status = Mock()
            mock_post.return_value = mock_response
            
            adapter = OpenAIAdapter(config_service)
            result = adapter.complete([], 1024, 0.7)
            
            assert result == "Response"

    def test_adapter_respects_temperature(self, config_service):
        """Test adapter passes temperature parameter."""
        from core.adapters.openai_adapter import OpenAIAdapter
        
        with patch('requests.post') as mock_post:
            mock_response = Mock()
            mock_response.json.return_value = {
                'choices': [{'message': {'content': 'Response'}}]
            }
            mock_response.raise_for_status = Mock()
            mock_post.return_value = mock_response
            
            adapter = OpenAIAdapter(config_service)
            adapter.complete([{"role": "user", "content": "Hello"}], 1024, 0.9)
            
            call_args = mock_post.call_args
            json_data = call_args.kwargs.get('json', {})
            assert json_data.get('temperature') == 0.9
