import tkinter as tk
from core.base_module import BaseModule
from modules.widgets import HorizontalMenu, ControllerPanel, GalleryWidget

class StandardModule(BaseModule):
    """
    Clase base avanzada que implementa el layout estándar de ASIMOD:
    - Menú Superior
    - Panel de Controladores (Colapsable)
    - Separador
    - Área Inferior (Galería Izquierda + Workspace Derecha)
    """
    def __init__(self, chat_service, config_service, style_service, data_service=None):
        super().__init__(chat_service, config_service, style_service, data_service=data_service)
        
        # Opciones de Layout (Subclases pueden cambiar esto en su __init__)
        self.show_menu = False
        self.show_controllers = False
        self.show_gallery = False
        
        self.menu_items = []
        self.gallery_title = "LIBRERÍA"
        self.gallery_visible = True
        
        # Referencias a widgets comunes
        self.menu = None
        self.ctrl_panel = None
        self.gallery = None
        self.workspace = None
        
        # Contenedores internos
        self.sub_widget_area = None

    def get_widget(self, parent):
        """Implementa la construcción del layout estándar usando los flags configurados."""
        has_bg = self.style.get_background("center") is not None
        pad = 20 if has_bg else 0
        ghost_bg = self.style.get_color("bg_main")
        
        main_frame = tk.Frame(parent, bg=ghost_bg)
        
        # 0. Preparar Contenedores Inferiores PRIMERO para evitar race conditions con el menú
        self.sub_widget_area = tk.Frame(main_frame, bg=ghost_bg)
        
        self.sub_widget_area.columnconfigure(0, weight=0)
        self.sub_widget_area.columnconfigure(1, weight=1)
        self.sub_widget_area.rowconfigure(1, weight=1)

        # Galería
        if self.show_gallery:
            self._create_gallery_controls()
            self.gallery = GalleryWidget(self.sub_widget_area, title=self.gallery_title, style=self.style)
            if self.gallery_visible:
                self.gallery.grid(row=1, column=0, sticky="nsew", padx=(0, 10))

        # Workspace (DEBE existir antes de que el menú pueda disparar callbacks)
        self.workspace = tk.Frame(self.sub_widget_area, bg=ghost_bg)
        self.workspace.grid(row=1, column=1, sticky="nsew")

        # 1. Menú Superior (Ahora puede disparar callbacks con seguridad)
        if self.show_menu and self.menu_items:
            self.menu = HorizontalMenu(
                main_frame, 
                items=self.menu_items, 
                callback=self.on_menu_change,
                style=self.style
            )
            self.menu.pack(fill=tk.X, pady=(0, 10), side=tk.TOP)

        # 2. Panel de Controladores (Ahora incluye internamente las Acciones Superiores)
        if self.show_controllers:
            self.ctrl_panel = ControllerPanel(main_frame, style=self.style)
            self.ctrl_panel.pack(fill=tk.X, side=tk.TOP, padx=20, pady=(0, 10))
            
            # Hook para que la subclase dibuje en la columna derecha del panel colapsable
            self.render_top_actions(self.ctrl_panel.actions_container)
            
        # 3. Separador sutil
        if self.show_menu or self.show_controllers:
            tk.Frame(main_frame, bg="#333", height=1).pack(fill=tk.X, side=tk.TOP, padx=pad)

        # 4. Pack de Área de Contenido Principal (Ahora que está configurada)
        # Aplicamos el padding dinámico si hay imagen de fondo
        self.sub_widget_area.pack(fill=tk.BOTH, expand=True, padx=pad, pady=pad, side=tk.TOP)
        
        # Llamar al render específico de la subclase
        self.render_workspace(self.workspace)

        # Llamar a inicialización de controladores si existe
        if self.show_controllers:
            self.setup_controllers(self.ctrl_panel)

        return main_frame

    def _create_gallery_controls(self):
        """Crea el botón de colapso para la galería."""
        controls_header = tk.Frame(self.sub_widget_area, bg=self.style.get_color("bg_main"))
        controls_header.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 10))
        
        self.toggle_btn = tk.Label(controls_header, 
                                   text="◀ COLAPSAR" if self.gallery_visible else "▶ EXPANDIR", 
                                   bg=self.style.get_color("bg_header"), 
                                   fg=self.style.get_color("accent"),
                                   font=("Arial", 8, "bold"), 
                                   padx=10, pady=5, cursor="hand2")
        self.toggle_btn.pack(side=tk.LEFT)
        self.toggle_btn.bind("<Button-1>", lambda e: self.toggle_gallery())

    def toggle_gallery(self):
        """Lógica común para ocultar/mostrar la galería."""
        if not self.show_gallery: return
        
        self.gallery_visible = not self.gallery_visible
        if self.gallery_visible:
            self.gallery.grid(row=1, column=0, sticky="nsew", padx=(0, 10))
            self.sub_widget_area.columnconfigure(0, weight=0) # Mantener peso 0
            self.toggle_btn.config(text="◀ COLAPSAR")
        else:
            self.gallery.grid_forget()
            self.sub_widget_area.columnconfigure(0, weight=0)
            self.toggle_btn.config(text="▶ EXPANDIR")

    def refresh_workspace(self):
        """Limpia y vuelve a renderizar el workspace y las acciones superiores de forma segura."""
        # 1. Limpiar acciones superiores (si el panel de control existe)
        if hasattr(self, "ctrl_panel") and self.ctrl_panel and self.ctrl_panel.winfo_exists():
            if hasattr(self.ctrl_panel, "actions_container") and self.ctrl_panel.actions_container.winfo_exists():
                for widget in self.ctrl_panel.actions_container.winfo_children():
                    widget.destroy()
                self.render_top_actions(self.ctrl_panel.actions_container)

        # 2. Limpiar workspace principal
        if self.workspace and self.workspace.winfo_exists():
            for widget in self.workspace.winfo_children():
                widget.destroy()
            self.render_workspace(self.workspace)

    # --- MÉTODOS A SOBRESCRIBIR ---
    
    def render_workspace(self, parent):
        """Subclases dibujan aquí su contenido principal."""
        tk.Label(parent, text="Workspace Vacío", bg=self.style.get_color("bg_main")).pack()

    def setup_controllers(self, panel):
        """Subclases configuran aquí sus dropdowns del ControllerPanel."""
        pass

    def render_top_actions(self, parent):
        """Subclases dibujan aquí widgets adicionales para la parte superior derecha."""
        pass

    def on_menu_change(self, mode):
        """Subclases manejan aquí el cambio de modo del HorizontalMenu."""
        pass
    
    def on_deactivate(self):
        """
        Limpia las referencias a los widgets al desactivar el módulo.
        Esto evita que on_activate intente usar widgets destruidos de la sesión anterior.
        """
        self.menu = None
        self.ctrl_panel = None
        self.gallery = None
        self.workspace = None
        self.sub_widget_area = None
