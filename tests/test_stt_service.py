import pytest
from unittest.mock import Mock, patch, MagicMock
import time

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

    def test_voice_command_callback_triggered(self, config_service):
        """Test that voice command callback is triggered."""
        from core.services.stt_service import STTService
        
        config_service.set("voice_commands", {
            "comando": "action_test"
        })
        config_service.set("stt_mode", "VOICE_COMMAND")
        
        callback_triggered = {"called": False, "matched": None, "text": None}
        
        def callback(matched, text):
            callback_triggered["called"] = True
            callback_triggered["matched"] = matched
            callback_triggered["text"] = text
        
        with patch('core.services.stt_service.STTFactory'):
            stt_service = STTService(config_service)
            stt_service.add_voice_command_callback(callback)
            
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
        config_service.set("stt_mode", "VOICE_COMMAND")
        
        with patch('core.services.stt_service.STTFactory'):
            stt_service = STTService(config_service)
            stt_service._dispatch_text("mi comando")
            
            assert stt_service.last_voice_command is not None
            assert stt_service.last_voice_command["matched"] == "action_test"
            assert stt_service.last_voice_command["text"] == "mi comando"
            assert "timestamp" in stt_service.last_voice_command

    def test_stt_mode_changes(self, config_service):
        """Test STT mode changes affect listening thread management."""
        from core.services.stt_service import STTService
        
        with patch('core.services.stt_service.STTFactory') as mock_factory:
            # Need a mock adapter for the thread to start
            mock_factory.get_adapter.return_value = MagicMock()
            stt_service = STTService(config_service)
            
            with patch.object(stt_service, 'start_listening') as mock_start:
                with patch.object(stt_service, 'stop_listening') as mock_stop:
                    stt_service.set_mode("CHAT")
                    mock_start.assert_called()
                    
                    stt_service.set_mode("OFF")
                    mock_stop.assert_called()

    def test_dispatch_text_short_text_ignored(self, config_service):
        """Test that short text (<=2 chars) is ignored."""
        from core.services.stt_service import STTService
        
        callback_triggered = {"called": False}
        
        def callback(matched, text):
            callback_triggered["called"] = True
        
        config_service.set("stt_mode", "VOICE_COMMAND")
        
        with patch('core.services.stt_service.STTFactory'):
            stt_service = STTService(config_service)
            stt_service.add_voice_command_callback(callback)
            
            stt_service._dispatch_text("ab")
            
            assert callback_triggered["called"] is False
