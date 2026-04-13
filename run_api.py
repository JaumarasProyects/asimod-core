import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.services.config_service import ConfigService
from core.chat_service import ChatService
from core.api_server import APIServer
import uvicorn
import threading

def start_api():
    config_service = ConfigService(filename="settings.json")
    chat_engine = ChatService(config_service=config_service)
    api_server = APIServer(chat_service=chat_engine, port=8000)
    
    # Run uvicorn on the app
    uvicorn.run(api_server.app, host="0.0.0.0", port=8000)

if __name__ == "__main__":
    start_api()
