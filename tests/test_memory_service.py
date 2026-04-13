import pytest
import os
import tempfile
import json


class TestMemoryService:
    """Tests for MemoryService."""

    def test_add_message(self, config_service):
        """Test adding a message to memory."""
        from core.services.memory_service import MemoryService
        
        with tempfile.TemporaryDirectory() as tmpdir:
            memory = MemoryService(base_dir=tmpdir)
            
            memory.add_message("user", "Hello, AI!")
            memory.add_message("assistant", "Hello, human!")
            
            messages = memory.get_recent_messages()
            assert len(messages) == 2
            assert messages[0]["role"] == "user"
            assert messages[0]["content"] == "Hello, AI!"

    def test_get_recent_messages_default_limit(self, config_service):
        """Test default message limit."""
        from core.services.memory_service import MemoryService
        
        with tempfile.TemporaryDirectory() as tmpdir:
            memory = MemoryService(base_dir=tmpdir)
            
            for i in range(20):
                memory.add_message("user", f"Message {i}")
            
            messages = memory.get_recent_messages()
            assert len(messages) == 20

    def test_get_recent_messages_with_limit(self, config_service):
        """Test getting messages with custom limit."""
        from core.services.memory_service import MemoryService
        
        with tempfile.TemporaryDirectory() as tmpdir:
            memory = MemoryService(base_dir=tmpdir)
            
            for i in range(10):
                memory.add_message("user", f"Message {i}")
            
            messages = memory.get_recent_messages(limit=3)
            assert len(messages) == 3

    def test_clear_messages(self, config_service):
        """Test clearing messages."""
        from core.services.memory_service import MemoryService
        
        with tempfile.TemporaryDirectory() as tmpdir:
            memory = MemoryService(base_dir=tmpdir)
            
            memory.add_message("user", "Test message")
            memory.clear()
            
            messages = memory.get_recent_messages()
            assert len(messages) == 0

    def test_thread_operations(self, config_service):
        """Test thread creation and message operations."""
        from core.services.memory_service import MemoryService
        
        with tempfile.TemporaryDirectory() as tmpdir:
            memory = MemoryService(base_dir=tmpdir)
            
            thread_id = memory.create_thread("test_thread")
            assert thread_id == "test_thread"
            
            memory.add_message_to_thread("test_thread", "user", "Thread message")
            messages = memory.get_thread_messages("test_thread")
            
            assert len(messages) == 1
            assert messages[0]["content"] == "Thread message"

    def test_get_or_create_thread(self, config_service):
        """Test getting or creating a thread."""
        from core.services.memory_service import MemoryService
        
        with tempfile.TemporaryDirectory() as tmpdir:
            memory = MemoryService(base_dir=tmpdir)
            
            thread_id = memory.get_or_create_thread("new_thread")
            assert thread_id == "new_thread"
            
            thread_id2 = memory.get_or_create_thread("new_thread")
            assert thread_id2 == "new_thread"

    def test_save_and_load_conversation(self, config_service):
        """Test saving and loading conversations."""
        from core.services.memory_service import MemoryService
        
        with tempfile.TemporaryDirectory() as tmpdir:
            memory = MemoryService(base_dir=tmpdir)
            
            memory.add_message("user", "Test message")
            memory.save_conversation("test_conv")
            
            file_path = os.path.join(tmpdir, "conversations", "test_conv.json")
            assert os.path.exists(file_path)
            
            with open(file_path, 'r') as f:
                data = json.load(f)
            
            assert len(data) == 1
            assert data[0]["content"] == "Test message"
