from core.adapters.ollama_adapter import OllamaAdapter
from core.adapters.openai_adapter import OpenAIAdapter
from core.adapters.gemini_adapter import GeminiAdapter
from core.adapters.generic_openai_adapter import GenericOpenAIAdapter

class LLMFactory:
    """
    Factoría única encargada de instanciar los diversos adaptadores de LLM.
    Concentra todo el conocimiento sobre 'cómo' se crea cada proveedor.
    """
    @staticmethod
    def list_providers() -> list:
        return ["Ollama", "OpenAI", "Gemini", "DeepSeek", "Groq", "Perplexity"]

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
                models=["llama3-70b-8192", "mixtral-8x7b-32768", "gemma-7b-it"]
            )

        elif provider_name == "Perplexity":
            key = config.get("perplexity_key", "")
            return GenericOpenAIAdapter(
                name="Perplexity", api_key=key,
                base_url="https://api.perplexity.ai",
                models=["llama-3-sonar-large-32k-online", "llama-3-sonar-small-32k-chat"]
            )
        
        return None
