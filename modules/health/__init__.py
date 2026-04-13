import tkinter as tk
from tkinter import ttk
from datetime import datetime, timedelta
from core.standard_module import StandardModule

class HealthModule(StandardModule):
    """
    Módulo de Salud y Estadísticas de ASIMOD.
    Muestra gráficas de actividad, nutrición y sueño, además de métricas de proyectos.
    """
    def __init__(self, chat_service, config_service, style_service, data_service=None):
        super().__init__(chat_service, config_service, style_service, data_service=data_service)
        self.name = "Salud"
        self.id = "health"
        self.icon = "📈"
        self.has_web_ui = True
        
        # Configuración de Layout
        self.show_menu = True
        self.show_controllers = False
        self.show_gallery = False
        self.menu_items = ["Resumen", "Nutrición", "Lista Compra"]
        
        self.current_mode = "Resumen"

    async def handle_get_data(self):
        """Bridge para proveer datos a la interfaz Web."""
        return {
            "status": "success",
            "rings": {
                "sport": {"value": 45, "total": 60, "unit": "min", "label": "Deporte"},
                "sleep": {"value": 7.5, "total": 8, "unit": "h", "label": "Sueño"},
                "calories": {"value": 1850, "total": 2500, "unit": "kcal", "label": "Calorías"}
            },
            "stats": [40, 60, 30, 80, 50, 90, 70],
            "shopping_list": ["Leche de avena", "Pechuga de pavo", "Aguacates", "Nueces", "Té verde"]
        }

    def render_workspace(self, parent):
        if self.current_mode == "Resumen":
            self._render_summary(parent)
        elif self.current_mode == "Lista Compra":
            self._render_shopping_list(parent)
        else:
            tk.Label(parent, text=f"Panel de {self.current_mode} en desarrollo...", 
                     bg=self.style.get_color("bg_main"), fg="#888").pack(pady=50)

    def _render_summary(self, parent):
        top_frame = tk.Frame(parent, bg=self.style.get_color("bg_main"))
        top_frame.pack(fill=tk.X, pady=20)

        # Simulación de anillos de actividad
        self._draw_ring(top_frame, "Deporte", 45, 60, self.style.get_color("success")).pack(side=tk.LEFT, padx=20)
        self._draw_ring(top_frame, "Sueño", 7.5, 8, self.style.get_color("accent")).pack(side=tk.LEFT, padx=20)
        self._draw_ring(top_frame, "Calorías", 1850, 2500, self.style.get_color("warning")).pack(side=tk.LEFT, padx=20)

        # Gráfica semanal (Canvas)
        chart_frame = tk.Frame(parent, bg=self.style.get_color("bg_dark"), padx=20, pady=20)
        chart_frame.pack(fill=tk.BOTH, expand=True, pady=20)
        
        tk.Label(chart_frame, text="ACTIVIDAD SEMANAL", font=("Arial", 10, "bold"), 
                 bg=self.style.get_color("bg_dark"), fg=self.style.get_color("text_dim")).pack(anchor="w")
        
        canvas = tk.Canvas(chart_frame, bg=self.style.get_color("bg_dark"), highlightthickness=0, height=200)
        canvas.pack(fill=tk.BOTH, expand=True, pady=10)
        
        self._draw_bar_chart(canvas)

    def _draw_ring(self, parent, title, value, total, color):
        frame = tk.Frame(parent, bg=self.style.get_color("bg_main"))
        canvas = tk.Canvas(frame, width=100, height=100, bg=self.style.get_color("bg_main"), highlightthickness=0)
        canvas.pack()
        
        # Círculo fondo
        canvas.create_oval(10, 10, 90, 90, outline="#333", width=8)
        # Arco progreso
        extent = -(value / total) * 359.9
        canvas.create_arc(10, 10, 90, 90, start=90, extent=extent, outline=color, width=8, style="arc")
        # Texto central
        canvas.create_text(50, 50, text=str(value), fill="white", font=("Arial", 14, "bold"))
        
        tk.Label(frame, text=title, fg=self.style.get_color("text_dim"), bg=self.style.get_color("bg_main"), font=("Arial", 8)).pack()
        return frame

    def _draw_bar_chart(self, canvas):
        data = [40, 60, 30, 80, 50, 90, 70]
        days = ["L", "M", "X", "J", "V", "S", "D"]
        
        canvas.update()
        w = canvas.winfo_width()
        h = 180
        
        bar_w = 40
        gap = (w - (len(data) * bar_w)) / (len(data) + 1)
        
        for i, val in enumerate(data):
            x0 = gap + i * (bar_w + gap)
            y0 = h - (val * 1.5)
            x1 = x0 + bar_w
            y1 = h
            
            canvas.create_rectangle(x0, y0, x1, y1, fill=self.style.get_color("accent"), outline="")
            canvas.create_text((x0+x1)/2, h + 15, text=days[i], fill="#888", font=("Arial", 8))

    def _render_shopping_list(self, parent):
        tk.Label(parent, text="Lista de la Compra Inteligente", fg=self.style.get_color("text_main"), 
                 bg=self.style.get_color("bg_main"), font=("Arial", 14, "bold")).pack(anchor="w", pady=(0, 20))
        
        items_frame = tk.Frame(parent, bg=self.style.get_color("bg_input"), padx=20, pady=20)
        items_frame.pack(fill=tk.BOTH, expand=True)
        
        sample_items = ["Leche de avena", "Pechuga de pavo", "Aguacates", "Nueces", "Té verde"]
        for item in sample_items:
            row = tk.Frame(items_frame, bg=self.style.get_color("bg_input"), pady=5)
            row.pack(fill=tk.X)
            tk.Label(row, text="☐", fg=self.style.get_color("accent"), bg=self.style.get_color("bg_input"), font=("Arial", 12)).pack(side=tk.LEFT, padx=(0, 10))
            tk.Label(row, text=item, fg="white", bg=self.style.get_color("bg_input"), font=("Arial", 10)).pack(side=tk.LEFT)

    def on_menu_change(self, mode):
        self.current_mode = mode
        self.refresh_workspace()

def get_module_class():
    return HealthModule
