import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.services.config_service import ConfigService
from core.services.module_service import ModuleService
from core.services.style_service import StyleService
from core.services.data_service import DataService
from core.chat_service import ChatService
from core.api_server import APIServer
import uvicorn
import threading

def start_api():
    config_service = ConfigService(filename="settings.json")
    
    # Inicializar servicios base
    data_service = DataService(config_service=config_service)
    style_service = StyleService(config_service=config_service)
    
    # Inicializar Motor de Chat
    chat_engine = ChatService(config_service=config_service)
    
    # Inicializar Servicio de Módulos
    module_service = ModuleService(
        chat_service=chat_engine, 
        config_service=config_service, 
        style_service=style_service,
        data_service=data_service
    )
    
    # Sincronizar el motor de chat con el de módulos para modo AGENTE
    chat_engine.set_module_service(module_service)
    
    # Vincular servicios STT/TTS
    chat_engine.voice_service.set_stt_service(chat_engine.stt_service)
    
    # Inicializar Servidor API con inyección de dependencias completa
    api_server = APIServer(
        chat_service=chat_engine, 
        port=8000,
        module_service=module_service,
        style_service=style_service
    )
    
    # Conectar resultados STT a la cola de la API
    chat_engine.on_stt_result_cb = api_server.push_stt_result
    
    # Mostrar información de Tailscale si está disponible
    try:
        from check_tailscale import get_tailscale_ip
        ts_ip = get_tailscale_ip()
        if ts_ip:
            print("\n" + "="*50)
            print(f" [NET] TAILSCALE DETECTADO: {ts_ip}")
            print(f" [URL] http://{ts_ip}:8000/web/")
            print("="*50 + "\n")
    except ImportError:
        pass
    except Exception as e:
        print(f"[NET] Error al comprobar Tailscale: {e}")

    # Run uvicorn on the app
    uvicorn.run(api_server.app, host="0.0.0.0", port=8000)

if __name__ == "__main__":
    start_api()
