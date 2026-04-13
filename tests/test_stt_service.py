import pytest
from unittest.mock import Mock, patch, MagicMock


class TestSTTService:
    """Tests for STT Service and Voice Commands."""

    def test_stt_service_initialization(self, config_service):
        """Test STT service initializes correctly."""
        from core.services.stt_service import STTService
        
        with patch('core.services.stt_service.STTFactory'):
            stt_service = STTService(config_service)
            
            assert stt_service.config is not None
            assert stt_service.is_listening is False
            assert stt_service.last_voice_command is None

    def test_check_voice_commands_matching(self, config_service):
        """Test voice command matching."""
        from core.services.stt_service import STTService
        
        config_service.set("voice_commands", {
            "comando": "action_test",
            "prueba": "action_prueba"
        })
        
        with patch('core.services.stt_service.STTFactory'):
            stt_service = STTService(config_service)
            
            result = stt_service._check_voice_commands("di comando")
            assert result == "action_test"
            
            result = stt_service._check_voice_commands("esto es una prueba")
            assert result == "action_prueba"

    def test_check_voice_commands_case_insensitive(self, config_service):
        """Test voice command matching is case insensitive."""
        from core.services.stt_service import STTService
        
        config_service.set("voice_commands", {
            "comando": "action_test"
        })
        
        with patch('core.services.stt_service.STTFactory'):
            stt_service = STTService(config_service)
            
            result = stt_service._check_voice_commands("COMANDO")
            assert result == "action_test"
            
            result = stt_service._check_voice_commands("ComAnDo")
            assert result == "action_test"

    def test_check_voice_commands_no_match(self, config_service):
        """Test voice command returns None when no match."""
        from core.services.stt_service import STTService
        
        config_service.set("voice_commands", {
            "comando": "action_test"
        })
        
        with patch('core.services.stt_service.STTFactory'):
            stt_service = STTService(config_service)
            
            result = stt_service._check_voice_commands("hola mundo")
            assert result is None

    def test_check_voice_commands_empty_dict(self, config_service):
        """Test voice command with empty dictionary."""
        from core.services.stt_service import STTService
        
        config_service.set("voice_commands", {})
        
        with patch('core.services.stt_service.STTFactory'):
            stt_service = STTService(config_service)
            
            result = stt_service._check_voice_commands("comando")
            assert result is None

    def test_voice_command_callback_triggered(self, config_service):
        """Test that voice command callback is triggered."""
        from core.services.stt_service import STTService
        
        config_service.set("voice_commands", {
            "comando": "action_test"
        })
        
        callback_triggered = {"called": False, "matched": None, "text": None}
        
        def callback(matched, text):
            callback_triggered["called"] = True
            callback_triggered["matched"] = matched
            callback_triggered["text"] = text
        
        with patch('core.services.stt_service.STTFactory'):
            stt_service = STTService(config_service)
            stt_service.on_voice_command = callback
            
            stt_service._dispatch_text("dice comando ahora")
            
            assert callback_triggered["called"] is True
            assert callback_triggered["matched"] == "action_test"
            assert callback_triggered["text"] == "dice comando ahora"

    def test_last_voice_command_stored(self, config_service):
        """Test that last voice command is stored."""
        from core.services.stt_service import STTService
        
        config_service.set("voice_commands", {
            "comando": "action_test"
        })
        
        with patch('core.services.stt_service.STTFactory'):
            import time
            stt_service = STTService(config_service)
            stt_service._dispatch_text("mi comando")
            
            assert stt_service.last_voice_command is not None
            assert stt_service.last_voice_command["matched"] == "action_test"
            assert stt_service.last_voice_command["text"] == "mi comando"
            assert "timestamp" in stt_service.last_voice_command

    def test_stt_mode_changes(self, config_service):
        """Test STT mode changes affect listening."""
        from core.services.stt_service import STTService
        
        with patch('core.services.stt_service.STTFactory'):
            stt_service = STTService(config_service)
            
            config_service.set("stt_mode", "CHAT")
            stt_service.manage_microphone_thread()
            
            config_service.set("stt_mode", "VOICE_COMMAND")
            stt_service.manage_microphone_thread()

    def test_voice_command_enabled_setting(self, config_service):
        """Test voice_command_enabled setting."""
        from core.services.stt_service import STTService
        
        with patch('core.services.stt_service.STTFactory'):
            stt_service = STTService(config_service)
            
            assert config_service.get("voice_command_enabled") is True
            
            config_service.set("voice_command_enabled", False)
            assert config_service.get("voice_command_enabled") is False

    def test_dispatch_text_short_text_ignored(self, config_service):
        """Test that short text (<=2 chars) is ignored."""
        from core.services.stt_service import STTService
        
        callback_triggered = {"called": False}
        
        def callback(matched, text):
            callback_triggered["called"] = True
        
        with patch('core.services.stt_service.STTFactory'):
            stt_service = STTService(config_service)
            stt_service.on_voice_command = callback
            config_service.set("stt_mode", "VOICE_COMMAND")
            
            stt_service._dispatch_text("ab")
            
            assert callback_triggered["called"] is False
