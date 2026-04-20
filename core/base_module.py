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
        self._main_widget = None # Referencia al widget principal para re-estilado
        
        # Suscribirse a cambios de estilo en tiempo de ejecución
        if hasattr(self.style, "subscribe"):
            self.style.subscribe(self.on_style_changed)

    def on_style_changed(self):
        """Hook que se llama cuando cambia el tema global."""
        print(f"[{self.id}] Recibida notificación de cambio de estilo.")
        if self._main_widget and self._main_widget.winfo_exists():
            self.apply_styles(self._main_widget)

    def apply_styles(self, widget: tk.Widget):
        """
        Re-aplica los colores del tema actual al widget principal.
        Los hijos deben sobreescribir esto si tienen widgets personalizados profundos.
        """
        try:
            widget.config(bg=self.style.get_color("bg_main"))
            for child in widget.winfo_children():
                try:
                    # Intento genérico de re-estilar hijos comunes
                    if isinstance(child, (tk.Label, tk.Button, tk.Checkbutton, tk.Radiobutton)):
                        child.config(bg=self.style.get_color("bg_main"), fg=self.style.get_color("text_main"))
                    elif isinstance(child, tk.Frame):
                        child.config(bg=self.style.get_color("bg_main"))
                except:
                    pass
        except:
            pass

    def get_widget(self, parent: tk.Widget) -> tk.Widget:
        """
        Debe devolver un widget de Tkinter (Frame) que represente la interfaz del módulo.
        """
        self._main_widget = tk.Frame(parent, bg=self.style.get_color("bg_main"))
        label = tk.Label(self._main_widget, text=f"Interfaz de {self.name}", fg=self.style.get_color("text_main"), bg=self.style.get_color("bg_main"))
        label.pack(expand=True)
        return self._main_widget

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
