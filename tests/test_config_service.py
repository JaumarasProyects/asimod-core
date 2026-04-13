import pytest
import os
import json
import tempfile


class TestConfigService:
    """Tests for ConfigService."""

    def test_get_default_values(self, config_service):
        """Test default configuration values."""
        assert config_service.get("provider") == "openai"
        assert config_service.get("model") == "gpt-4"
        assert config_service.get("max_tokens") == 1024
        assert config_service.get("temperature") == 0.7

    def test_get_nonexistent_key(self, config_service):
        """Test getting a non-existent key returns None."""
        assert config_service.get("nonexistent_key") is None

    def test_get_with_default_fallback(self, config_service):
        """Test getting a key with default fallback."""
        assert config_service.get("nonexistent", "default_value") == "default_value"

    def test_set_and_get_value(self, config_service):
        """Test setting and getting a value."""
        config_service.set("test_key", "test_value")
        assert config_service.get("test_key") == "test_value"

    def test_set_overwrites_existing(self, config_service):
        """Test that set overwrites existing value."""
        config_service.set("provider", "anthropic")
        assert config_service.get("provider") == "anthropic"

    def test_persist_config(self, config_service):
        """Test that config is persisted to file."""
        config_service.set("test_key", "test_value")
        config_service.save()
        
        with open(config_service.filename, 'r') as f:
            data = json.load(f)
        
        assert data["test_key"] == "test_value"

    def test_voice_commands_default(self, config_service):
        """Test default voice_commands is empty dict."""
        assert config_service.get("voice_commands") == {}
        assert config_service.get("voice_command_enabled") is True

    def test_stt_mode_default(self, config_service):
        """Test default stt_mode is OFF."""
        assert config_service.get("stt_mode") == "OFF"
        assert config_service.get("stt_provider") == "None"

    def test_api_port_default(self, config_service):
        """Test default api_port."""
        assert config_service.get("api_port") == 8000
