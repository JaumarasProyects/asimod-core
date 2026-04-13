import pytest
from unittest.mock import Mock, patch, MagicMock, AsyncMock
import httpx

@pytest.mark.anyio
class TestLLMAdapters:
    """Tests for LLM Adapters."""

    async def test_openai_adapter_generate_chat(self):
        """Test OpenAI adapter generation."""
        from core.adapters.openai_adapter import OpenAIAdapter
        
        # Mocking httpx.AsyncClient.post
        with patch('httpx.AsyncClient.post', new_callable=AsyncMock) as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                'choices': [{'message': {'content': 'Test response'}}]
            }
            mock_post.return_value = mock_response
            
            adapter = OpenAIAdapter(api_key="test-key")
            result = await adapter.generate_chat(
                history=[{"role": "user", "content": "Hello"}],
                system_prompt="Be helpful",
                model="gpt-4o-mini"
            )
            
            assert result == "Test response"
            mock_post.assert_called_once()

    async def test_openai_adapter_list_models(self):
        """Test OpenAI adapter list_models."""
        from core.adapters.openai_adapter import OpenAIAdapter
        
        adapter = OpenAIAdapter(api_key="test-key")
        models = await adapter.list_models()
        
        assert "gpt-4o" in models
        assert isinstance(models, list)

    async def test_ollama_adapter_generate_chat(self):
        """Test Ollama adapter generation."""
        from core.adapters.ollama_adapter import OllamaAdapter
        
        with patch('httpx.AsyncClient.post', new_callable=AsyncMock) as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                'message': {'content': 'Ollama response'}
            }
            mock_post.return_value = mock_response
            
            adapter = OllamaAdapter(base_url="http://localhost:11434/api")
            result = await adapter.generate_chat(
                history=[{"role": "user", "content": "Hello"}],
                system_prompt="Be helpful",
                model="llama3"
            )
            
            assert result == "Ollama response"

    async def test_anthropic_adapter_generate_chat(self):
        """Test Anthropic adapter generation."""
        from core.adapters.anthropic_adapter import AnthropicAdapter
        
        with patch('httpx.AsyncClient.post', new_callable=AsyncMock) as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                'content': [{'text': 'Anthropic response'}]
            }
            mock_post.return_value = mock_response
            
            adapter = AnthropicAdapter(api_key="test-key")
            result = await adapter.generate_chat(
                history=[{"role": "user", "content": "Hello"}],
                system_prompt="Be helpful",
                model="claude-3-haiku"
            )
            
            assert result == "Anthropic response"

    def test_llm_factory_returns_correct_adapter(self, config_service):
        """Test LLMFactory returns correct adapter type."""
        from core.factories.llm_factory import LLMFactory
        
        # Factory now uses config_service internally
        adapter_openai = LLMFactory.get_adapter("OpenAI", config_service)
        assert adapter_openai is not None
        assert adapter_openai.name == "OpenAI"
        
        adapter_ollama = LLMFactory.get_adapter("Ollama", config_service)
        assert adapter_ollama is not None
        assert adapter_ollama.name == "Ollama"

    @patch('core.adapters.gguf_adapter.Llama')
    async def test_gguf_adapter_generate_chat(self, mock_llama):
        """Test GGUF adapter generation."""
        from core.adapters.gguf_adapter import GGUFAdapter
        
        mock_instance = MagicMock()
        mock_instance.create_chat_completion.return_value = {
            'choices': [{'message': {'content': 'GGUF response'}}]
        }
        mock_llama.return_value = mock_instance
        
        # Mocking os.makedirs and os.path.exists to avoid side effects
        with patch('os.makedirs'), patch('os.path.exists', return_value=True):
            adapter = GGUFAdapter(models_dir="C:/Models", n_ctx=2048)
            result = await adapter.generate_chat(
                history=[{"role": "user", "content": "Hello"}],
                system_prompt="Be helpful",
                model="test.gguf"
            )
            
            assert result == "GGUF response"

    async def test_adapter_respects_temperature(self):
        """Test adapter passes temperature parameter."""
        from core.adapters.openai_adapter import OpenAIAdapter
        
        with patch('httpx.AsyncClient.post', new_callable=AsyncMock) as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                'choices': [{'message': {'content': 'Response'}}]
            }
            mock_post.return_value = mock_response
            
            adapter = OpenAIAdapter(api_key="test-key")
            await adapter.generate_chat(
                history=[{"role": "user", "content": "Hello"}],
                system_prompt="Be helpful",
                model="gpt-4",
                temperature=0.9
            )
            
            call_args = mock_post.call_args
            json_data = call_args.kwargs.get('json', {})
            assert json_data.get('temperature') == 0.9
