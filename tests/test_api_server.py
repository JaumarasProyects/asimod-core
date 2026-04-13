import pytest
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient

@pytest.mark.anyio
class TestAPIServer:
    """Tests for API Server endpoints."""

    @pytest.fixture
    def mock_chat_service(self):
        """Creates a mock chat service."""
        service = MagicMock()
        service.config = MagicMock()
        service.config.get.side_effect = lambda key, default=None: {
            "provider": "openai",
            "model": "gpt-4",
            "voice_commands": {"comando": "action_test"},
            "voice_command_enabled": True,
            "stt_mode": "OFF"
        }.get(key, default)
        
        service.stt_service = MagicMock()
        service.stt_service.last_voice_command = None
        
        service.voice_service = MagicMock()
        # VoiceService.process_text is async
        service.voice_service.process_text = AsyncMock(return_value=True)
        
        service.memory = MagicMock()
        service.memory.active_thread = "test_thread"
        service.memory.data = {"history": [], "name": "Asimod", "personality": "Helpful"}
        service.memory.list_threads.return_value = ["test_thread", "another"]
        
        service.locale_service = MagicMock()
        service.locale_service.get_current_language.return_value = "es"
        service.locale_service.list_available_languages.return_value = ["en", "es"]
        
        return service

    @pytest.fixture
    def api_client(self, mock_chat_service):
        """Creates a TestClient for APIServer."""
        from core.api_server import APIServer
        # Initialize APIServer with mocks
        server = APIServer(chat_service=mock_chat_service)
        return TestClient(server.app)

    async def test_get_status(self, api_client, mock_chat_service):
        """Test GET /v1/status endpoint."""
        response = api_client.get("/v1/status")
        assert response.status_code == 200
        data = response.json()
        assert data["stt_mode"] == "OFF"
        assert data["language"] == "es"

    async def test_list_memories(self, api_client, mock_chat_service):
        """Test GET /v1/memories endpoint."""
        response = api_client.get("/v1/memories")
        assert response.status_code == 200
        assert "test_thread" in response.json()["memories"]

    async def test_audio_pause_resume(self, api_client, mock_chat_service):
        """Test audio control endpoints."""
        response_pause = api_client.post("/v1/audio/pause")
        assert response_pause.status_code == 200
        mock_chat_service.stt_service.pause_capture.assert_called_once()

        response_resume = api_client.post("/v1/audio/resume")
        assert response_resume.status_code == 200
        mock_chat_service.stt_service.resume_capture.assert_called_once()

    async def test_speak_endpoint(self, api_client, mock_chat_service):
        """Test POST /v1/audio/speak endpoint."""
        payload = {"text": "Hola mundo", "voice_id": "test_voice"}
        response = api_client.post("/v1/audio/speak", json=payload)
        
        assert response.status_code == 200
        assert response.json()["status"] == "success"
        # Verify it awaited the voice service
        mock_chat_service.voice_service.process_text.assert_awaited_once_with(
            text="Hola mundo",
            voice_id="test_voice",
            voice_provider=None
        )

    async def test_get_history(self, api_client, mock_chat_service):
        """Test GET /v1/history endpoint."""
        # Setup mock history
        msg = Mock()
        msg.sender = "user"
        msg.content = "hello"
        mock_chat_service.get_history.return_value = [msg]
        
        response = api_client.get("/v1/history")
        assert response.status_code == 200
        assert response.json()[0]["content"] == "hello"

    async def test_list_languages(self, api_client, mock_chat_service):
        """Test GET /v1/languages endpoint."""
        response = api_client.get("/v1/languages")
        assert response.status_code == 200
        assert "es" in response.json()["languages"]
