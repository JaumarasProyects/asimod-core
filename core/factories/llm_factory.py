from core.adapters.anthropic_adapter import AnthropicAdapter
from core.adapters.ollama_adapter import OllamaAdapter
from core.adapters.openai_adapter import OpenAIAdapter
from core.adapters.gemini_adapter import GeminiAdapter
from core.adapters.generic_openai_adapter import GenericOpenAIAdapter

class LLMFactory:
    """
    Factoría única encargada de instanciar los diversos adaptadores de LLM.
    """
    @staticmethod
    def list_providers() -> list:
        return ["Ollama", "OpenAI", "Anthropic", "Gemini", "DeepSeek", "Groq", "Perplexity"]

    @staticmethod
    def get_adapter(provider_name, config):
        """
        Retorna el motor de IA adecuado según la configuración guardada.
        """
        if provider_name == "Ollama":
            url = config.get("ollama_url", "http://localhost:11434")
            return OllamaAdapter(base_url=url)
            
        elif provider_name == "OpenAI":
            key = config.get("openai_key", "")
            return OpenAIAdapter(api_key=key)

        elif provider_name == "Anthropic":
            key = config.get("anthropic_key", "")
            return AnthropicAdapter(api_key=key)

        elif provider_name == "Gemini":
            key = config.get("gemini_key", "")
            return GeminiAdapter(api_key=key)

        elif provider_name == "DeepSeek":
            key = config.get("deepseek_key", "")
            return GenericOpenAIAdapter(
                name="DeepSeek", api_key=key,
                base_url="https://api.deepseek.com",
                models=["deepseek-chat", "deepseek-coder"]
            )

        elif provider_name == "Groq":
            key = config.get("groq_key", "")
            return GenericOpenAIAdapter(
                name="Groq", api_key=key,
                base_url="https://api.groq.com/openai/v1",
                models=["llama-3.3-70b-versatile", "llama-3.1-8b-instant", "gemma2-9b-it"]
            )

        elif provider_name == "Perplexity":
            key = config.get("perplexity_key", "")
            return GenericOpenAIAdapter(
                name="Perplexity", api_key=key,
                base_url="https://api.perplexity.ai",
                models=["sonar-reasoning-pro", "sonar-reasoning", "sonar"]
            )
        
        return None
