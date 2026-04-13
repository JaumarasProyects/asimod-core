import pytest
import os
import sys
import tempfile
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture
def temp_config_file():
    """Creates a temporary config file for testing."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump({
            "provider": "openai",
            "model": "gpt-4",
            "max_tokens": 1024,
            "temperature": 0.7,
            "voice_provider": "edge",
            "voice_id": "es-ES-ElenaNeural",
            "stt_mode": "OFF",
            "stt_provider": "None",
            "voice_commands": {},
            "voice_command_enabled": True,
            "api_port": 8000
        }, f)
        temp_path = f.name
    
    yield temp_path
    
    if os.path.exists(temp_path):
        os.remove(temp_path)


@pytest.fixture
def config_service(temp_config_file):
    """Creates a ConfigService instance with temporary config."""
    from core.services.config_service import ConfigService
    return ConfigService(filename=temp_config_file)


@pytest.fixture
def mock_llm_adapter():
    """Creates a mock LLM adapter for testing."""
    class MockLLMAdapter:
        def __init__(self):
            self.call_count = 0
            self.last_messages = None
            self.should_fail = False
            self.name = "MockLLM"
            
        async def generate_chat(self, history, system_prompt, model, images=None, max_tokens=None, temperature=None):
            self.call_count += 1
            self.last_messages = history
            if self.should_fail:
                raise Exception("Mock failure")
            return "This is a mock response from the LLM"
        
        async def list_models(self):
            return ["mock-model-1", "mock-model-2"]
    
    return MockLLMAdapter()


@pytest.fixture
def mock_stt_adapter():
    """Creates a mock STT adapter for testing."""
    class MockSTTAdapter:
        def __init__(self):
            self.transcribe_count = 0
            self.transcribe_texts = []
            self.name = "MockSTT"
            
        def transcribe(self, audio_path):
            self.transcribe_count += 1
            text = self.transcribe_texts.pop(0) if self.transcribe_texts else "mock transcription"
            return text
    
    return MockSTTAdapter()


@pytest.fixture
def mock_voice_adapter():
    """Creates a mock voice adapter for testing."""
    class MockVoiceAdapter:
        def __init__(self):
            self.generate_count = 0
            self.last_text = None
            self.name = "MockVoice"
            
        async def generate(self, text, output_path, voice_id=None):
            self.generate_count += 1
            self.last_text = text
            return True
        
        def list_voices(self):
            return [{"id": "voice-1", "name": "Voice 1"}, {"id": "voice-2", "name": "Voice 2"}]
    
    return MockVoiceAdapter()


@pytest.fixture
def anyio_backend():
    return 'asyncio'
