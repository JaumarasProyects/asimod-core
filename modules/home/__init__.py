import tkinter as tk
import json
import os
from core.standard_module import StandardModule
from modules.widgets import CalendarWidget, EventListWidget

class HomeModule(StandardModule):
    """
    Módulo de Inicio que utiliza la plantilla StandardModule con navegación por JSON.
    """
    def __init__(self, chat_service, config_service, style_service, data_service=None):
        super().__init__(chat_service, config_service, style_service, data_service=data_service)
        self.name = "Inicio"
        self.id = "home"
        self.icon = "🏠"
        
        self.config_file = os.path.join(os.path.dirname(__file__), "config.json")
        self.layout_config = self._load_home_config()
        
        # Configuración de Plantilla dinámica basada en JSON
        layout = self.layout_config.get("layout", {})
        tabs_config = layout.get("tabs", {"Dashboard": ["calendar"]})
        
        self.show_menu = True
        self.menu_items = list(tabs_config.keys())
        self.show_gallery = layout.get("show_gallery", True)
        self.gallery_title = "ACCESOS RÁPIDOS"
        self.current_mode = self.menu_items[0] if self.menu_items else "Inicio"
        
        # Mapeo de nombres de widgets a clases
        self.widget_registry = {
            "calendar": CalendarWidget,
            "events": EventListWidget
        }

    def _load_home_config(self):
        default_config = {
            "layout": {
                "show_gallery": True,
                "tabs": {
                    "Dashboard": ["calendar"],
                    "Agenda": ["events"]
                }
            }
        }
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"[HomeModule] Error cargando config.json: {e}")
        return default_config

    def on_menu_change(self, mode):
        """Callback cuando se cambia de pestaña en el menú superior."""
        if self.current_mode == mode:
            return
            
        self.current_mode = mode
        print(f"[HomeModule] Navegando a pestaña: {mode}")
        
        # Redibujar solo el área de trabajo (workspace)
        self.refresh_workspace()

    def render_workspace(self, parent):
        """Renderiza los widgets de la pestaña activa."""
        layout = self.layout_config.get("layout", {})
        tabs_config = layout.get("tabs", {})
        
        # Obtener widgets para la pestaña actual
        widgets_to_load = tabs_config.get(self.current_mode, [])
        
        if not widgets_to_load:
            tk.Label(parent, text=f"Pestaña vacía: {self.current_mode}", 
                     bg=self.style.get_color("bg_main"), fg=self.style.get_color("text_dim")).pack(pady=20)
        
        for widget_name in widgets_to_load:
            if widget_name in self.widget_registry:
                widget_class = self.widget_registry[widget_name]
                try:
                    instance = widget_class(parent, bg=self.style.get_color("bg_main"))
                    instance.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
                except Exception as e:
                    print(f"[HomeModule] Error instanciando widget '{widget_name}': {e}")
                    try:
                        instance = widget_class(parent)
                        instance.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
                    except: pass
            else:
                tk.Label(parent, text=f"Widget no encontrado: {widget_name}", 
                         bg=self.style.get_color("bg_main"), fg="orange").pack()

        # Llenar Galería (Global o Local - de momento global)
        if self.gallery:
            self.gallery.clear()
            self.gallery.add_item("Bienvenido", f"Sección: {self.current_mode}", icon="🎯")
            self.gallery.add_item("Notas Rápidas", "Ver últimos recordatorios", icon="📝")

    def get_voice_commands(self):
        # Generar comandos para las pestañas dinámicamente
        cmds = {"inicio": "show_home", "dashboard": "show_home"}
        for tab in self.menu_items:
            cmds[f"ver {tab.lower()}"] = f"tab_{tab}"
        return cmds

    def on_voice_command(self, action_slug, text):
        if action_slug.startswith("tab_"):
            tab_name = action_slug.replace("tab_", "")
            if tab_name in self.menu_items:
                if self.menu: self.menu.select(tab_name)
