import sys
import os

# Ajuste de path para que el ejemplo sea ejecutable desde aquí
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.services.config_service import ConfigService
from core.chat_service import ChatService
from core.api_server import APIServer

def main():
    print("--- ASIMOD CORE: MODO SERVIDOR (HEADLESS) ---")
    
    # 1. Inicializamos el Servicio de Configuración
    config_service = ConfigService(filename="settings.json")

    # 2. Inicializamos el CORE (Orquestador)
    chat_engine = ChatService(config_service=config_service)

    # 3. Vincular servicios (Sincronización Silenciosa)
    chat_engine.voice_service.set_stt_service(chat_engine.stt_service)

    # 4. Inicializamos el Servidor de API (Modo Bloqueante)
    api_port = config_service.get("api_port", 8000)
    api_server = APIServer(chat_service=chat_engine, port=int(api_port))
    api_server.run(blocking=True)

if __name__ == "__main__":
    main()
