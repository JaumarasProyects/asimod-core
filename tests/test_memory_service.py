import pytest
import os
import tempfile
import json
from pathlib import Path

class TestMemoryService:
    """Tests for MemoryService."""

    def test_add_message(self):
        """Test adding a message to memory."""
        from core.services.memory_service import MemoryService
        
        with tempfile.TemporaryDirectory() as tmpdir:
            # MemoryService handles Path objects or strings
            memory = MemoryService(base_dir=tmpdir)
            
            # Need an active thread to add messages
            memory.create_named_thread("test_thread")
            
            memory.add_message("user", "Hello, AI!")
            memory.add_message("assistant", "Hello, human!")
            
            context = memory.get_context()
            assert len(context) == 2
            assert context[0]["role"] == "user"
            assert context[0]["content"] == "Hello, AI!"

    def test_get_context(self):
        """Test getting context from active thread."""
        from core.services.memory_service import MemoryService
        
        with tempfile.TemporaryDirectory() as tmpdir:
            memory = MemoryService(base_dir=tmpdir)
            memory.create_named_thread("ctx_thread")
            
            for i in range(10):
                memory.add_message("user", f"Message {i}")
            
            context = memory.get_context()
            assert len(context) == 10
            assert context[-1]["content"] == "Message 9"

    def test_clear_thread_history(self):
        """Test clearing messages in a specific thread."""
        from core.services.memory_service import MemoryService
        
        with tempfile.TemporaryDirectory() as tmpdir:
            memory = MemoryService(base_dir=tmpdir)
            memory.create_named_thread("clear_me")
            
            memory.add_message("user", "Test message")
            memory.clear_thread_history("clear_me")
            
            # Verify disk state or reload
            reloaded_data = memory.get_thread_data("clear_me")
            assert len(reloaded_data["history"]) == 0

    def test_thread_operations(self):
        """Test thread creation and message operations."""
        from core.services.memory_service import MemoryService
        
        with tempfile.TemporaryDirectory() as tmpdir:
            memory = MemoryService(base_dir=tmpdir)
            
            thread_id = memory.create_named_thread("test_thread")
            assert thread_id == "test_thread"
            
            memory.add_message_to_thread("test_thread", "user", "Thread message")
            
            # Check file persistence
            file_path = os.path.join(tmpdir, "conversations", "test_thread.json")
            assert os.path.exists(file_path)
            
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            assert len(data["history"]) == 1
            assert data["history"][0]["content"] == "Thread message"

    def test_list_threads(self):
        """Test listing threads."""
        from core.services.memory_service import MemoryService
        
        with tempfile.TemporaryDirectory() as tmpdir:
            memory = MemoryService(base_dir=tmpdir)
            
            memory.create_named_thread("thread_1")
            memory.create_named_thread("thread_2")
            
            threads = memory.list_threads()
            assert "thread_1" in threads
            assert "thread_2" in threads

    def test_save_and_load_persistence(self):
        """Test deep persistence of threads."""
        from core.services.memory_service import MemoryService
        
        with tempfile.TemporaryDirectory() as tmpdir:
            memory1 = MemoryService(base_dir=tmpdir)
            memory1.create_named_thread("persist_thread")
            memory1.add_message("user", "Save me")
            
            # New instance loading same base_dir
            memory2 = MemoryService(base_dir=tmpdir)
            data = memory2.load_thread("persist_thread")
            
            assert data["history"][0]["content"] == "Save me"
            assert memory2.active_thread == "persist_thread"
