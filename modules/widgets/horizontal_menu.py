import tkinter as tk

class HorizontalMenu(tk.Frame):
    """
    Menú horizontal reutilizable para módulos.
    Permite navegar entre diferentes sub-vistas.
    """
    def __init__(self, parent, items, callback, style=None, bg_color=None, active_color=None, text_color=None, active_text_color=None):
        self.style = style
        # Si hay estilo, ignoramos los colores manuales para usar los del tema
        if self.style:
            bg_color = self.style.get_color("bg_main")
            active_color = self.style.get_color("accent")
            text_color = self.style.get_color("text_dim")
            active_text_color = self.style.get_color("text_main")
        else:
            bg_color = bg_color or "#2b2b2b"
            active_color = active_color or "#0078d4"
            text_color = text_color or "#aaaaaa"
            active_text_color = active_text_color or "#ffffff"
            
        super().__init__(parent, bg=bg_color)
        self.items = items
        self.callback = callback
        self.bg_color = bg_color
        self.active_color = active_color
        self.text_color = text_color
        self.active_text_color = active_text_color
        
        self.buttons = {}
        self.active_item = None
        
        self.init_ui()

    def init_ui(self):
        # Contenedor central para los botones
        self.content_frame = tk.Frame(self, bg=self.bg_color)
        self.content_frame.pack(side=tk.LEFT, fill=tk.Y)

        for item in self.items:
            # Contenedor para el botón + indicador (opcional)
            btn_frame = tk.Frame(self.content_frame, bg=self.bg_color)
            btn_frame.pack(side=tk.LEFT, padx=10)

            btn = tk.Label(btn_frame, text=item.upper(), bg=self.bg_color, fg=self.text_color,
                           font=("Arial", 9, "bold"), cursor="hand2", padx=10, pady=10)
            btn.pack()
            
            # Línea indicadora inferior
            indicator = tk.Frame(btn_frame, bg=self.bg_color, height=2)
            indicator.pack(fill=tk.X, side=tk.BOTTOM)
            
            # Eventos
            btn.bind("<Button-1>", lambda e, it=item: self._on_item_click(it))
            btn.bind("<Enter>", lambda e, b=btn, i=indicator: self._on_hover(b, i, True))
            btn.bind("<Leave>", lambda e, b=btn, i=indicator, it=item: self._on_hover(b, i, False, it))
            
            self.buttons[item] = {"btn": btn, "indicator": indicator}

        # Seleccionar el primero por defecto
        if self.items:
            self._on_item_click(self.items[0])

    def _on_item_click(self, item):
        if self.active_item == item:
            return
            
        # Desactivar anterior
        if self.active_item:
            prev = self.buttons[self.active_item]
            prev["btn"].config(fg=self.text_color)
            prev["indicator"].config(bg=self.bg_color)
            
        # Activar nuevo
        self.active_item = item
        curr = self.buttons[item]
        curr["btn"].config(fg=self.active_text_color)
        curr["indicator"].config(bg=self.active_color)
        
        # Notificar
        if self.callback:
            self.callback(item)

    def _on_hover(self, btn, indicator, enter, item=None):
        if item and self.active_item == item:
            return
            
        if enter:
            btn.config(fg=self.active_text_color)
        else:
            btn.config(fg=self.text_color)

    def select(self, item):
        """Selecciona un ítem programáticamente."""
        if item in self.buttons:
            self._on_item_click(item)
