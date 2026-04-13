import tkinter as tk
from typing import Dict, Callable

class BaseModule:
    """
    Clase base para todos los módulos de ASIMOD.
    Permite extender la funcionalidad con UI y comandos de voz contextuales.
    """
    def __init__(self, chat_service, config_service, style_service, data_service=None):
        self.chat_service = chat_service
        self.config_service = config_service
        self.style = style_service
        self.data_service = data_service
        self.name = "Abstract Module"
        self.id = "abstract_module"
        self.icon = "📦"

    def get_widget(self, parent: tk.Widget) -> tk.Widget:
        """
        Debe devolver un widget de Tkinter (Frame) que represente la interfaz del módulo.
        """
        frame = tk.Frame(parent, bg=self.style.get_color("bg_main"))
        label = tk.Label(frame, text=f"Interfaz de {self.name}", fg=self.style.get_color("text_main"), bg=self.style.get_color("bg_main"))
        label.pack(expand=True)
        return frame

    def get_voice_commands(self) -> Dict[str, str]:
        """
        Devuelve un diccionario de {disparador: acción_slug}.
        Estas acciones serán enviadas al callback de comandos de voz cuando el módulo esté activo.
        """
        return {}

    def on_voice_command(self, action_slug: str, text: str):
        """
        Se llama cuando se reconoce un comando de voz que pertenece a este módulo.
        """
        print(f"[{self.name}] Comando de voz recibido: {action_slug} ({text})")

    def on_activate(self):
        """
        Llamado cuando el usuario selecciona el módulo.
        """
        pass

    def on_deactivate(self):
        """
        Llamado cuando el usuario cambia a otro módulo o cierra el panel.
        """
        pass
