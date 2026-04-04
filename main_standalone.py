import sys
import os
import tkinter as tk

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

    try:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        icon_path = os.path.join(current_dir, "Resources", "logo.ico")
        if os.path.exists(icon_path):
            root.iconbitmap(icon_path)
    except Exception as e:
        print(f"Error cargando icono: {e}")

    config_service = ConfigService(filename="settings.json")
    chat_engine = ChatService(config_service=config_service)

    # sincronización TTS <-> STT
    chat_engine.voice_service.set_stt_service(chat_engine.stt_service)

    api_port = config_service.get("api_port", 8000)
    api_server = APIServer(chat_service=chat_engine, port=int(api_port))

    # conectar resultados STT de juego a la cola expuesta por API
    chat_engine.on_stt_result_cb = api_server.push_stt_result

    api_server.run()

    chat_ui = ChatWidget(root, chat_engine=chat_engine, config_service=config_service)
    chat_ui.pack(fill=tk.BOTH, expand=True)

    root.mainloop()

if __name__ == "__main__":
    main()