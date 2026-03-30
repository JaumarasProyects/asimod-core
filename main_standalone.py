import sys
import os
import tkinter as tk

# Ajuste de path para que el ejemplo sea ejecutable desde aquí
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.services.config_service import ConfigService
from core.chat_service import ChatService
from core.api_server import APIServer
from ui.chat_widget import ChatWidget

def main():
    root = tk.Tk()
    root.title("ASIMOD Core")
    root.geometry("450x650")
    root.configure(bg="#2b2b2b")

    # Intentar cargar el icono de la aplicación
    try:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        icon_path = os.path.join(current_dir, "Resources", "logo.ico")
        if os.path.exists(icon_path):
            root.iconbitmap(icon_path)
    except Exception as e:
        print(f"Error cargando icono: {e}")

    # 1. Inicializamos el Servicio de Configuración (Persistencia)
    config_service = ConfigService(filename="settings.json")

    # 2. Inicializamos el CORE (Orquestador de LLMs)
    # Le pasamos la config para que sepa qué adaptador usar al inicio.
    chat_engine = ChatService(config_service=config_service)

    # VINCULACIÓN: Silenciar micro mientras suena audio
    chat_engine.voice_service.set_stt_service(chat_engine.stt_service)

    # 3. Inicializamos el Servidor de API (Puerto dinámico)
    api_port = config_service.get("api_port", 8000)
    api_server = APIServer(chat_service=chat_engine, port=int(api_port))
    api_server.run()

    # 4. Inicializamos la UI inyectando el CORE y la CONFIG
    chat_ui = ChatWidget(root, chat_engine=chat_engine, config_service=config_service)
    chat_ui.pack(fill=tk.BOTH, expand=True)

    root.mainloop()

if __name__ == "__main__":
    main()
