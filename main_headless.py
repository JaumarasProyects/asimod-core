import sys
import os

# Ajuste de path para que el ejemplo sea ejecutable desde aquí
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.services.config_service import ConfigService
from core.services.module_service import ModuleService
from core.services.style_service import StyleService
from core.services.data_service import DataService
from core.chat_service import ChatService
from core.api_server import APIServer

def main():
    print("--- ASIMOD CORE: MODO SERVIDOR (HEADLESS) ---")
    
    # 1. Inicializamos el Servicio de Configuración
    config_service = ConfigService(filename="settings.json")

    # 2. Inicializar servicios base (Datos y Estilos)
    data_service = DataService(config_service=config_service)
    style_service = StyleService(config_service=config_service)

    # 3. Inicializamos el CORE (Orquestador)
    chat_engine = ChatService(config_service=config_service)

    # 4. Inicializar Servicio de Módulos
    module_service = ModuleService(
        chat_service=chat_engine, 
        config_service=config_service, 
        style_service=style_service,
        data_service=data_service
    )
    
    # Sincronizar el motor de chat con el de módulos para modo AGENTE
    chat_engine.set_module_service(module_service)

    # 5. Vincular servicios (Sincronización Silenciosa STT/TTS)
    chat_engine.voice_service.set_stt_service(chat_engine.stt_service)

    # 6. Inicializamos el Servidor de API (Modo Bloqueante) con inyección completa
    api_port = config_service.get("api_port", 8000)
    api_server = APIServer(
        chat_service=chat_engine, 
        port=int(api_port),
        module_service=module_service,
        style_service=style_service
    )
    
    # Conectar resultados STT a la cola de la API
    chat_engine.on_stt_result_cb = api_server.push_stt_result
    
    api_server.run(blocking=True)

if __name__ == "__main__":
    main()
