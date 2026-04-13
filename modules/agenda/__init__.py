import tkinter as tk
from datetime import datetime
from core.base_module import BaseModule
from widgets.weather_service import WeatherService
from widgets.calendar_widget import CalendarWidget
from widgets.event_list_widget import EventListWidget

class AgendaModule(BaseModule):
    """
    Módulo de Agenda avanzado para ASIMOD.
    Usa componentes reutilizables (Widgets) y servicios externos para el clima.
    """
    def __init__(self, chat_service, config_service, style_service, data_service=None):
        super().__init__(chat_service, config_service, style_service, data_service=data_service)
        self.name = "Agenda"
        self.id = "agenda"
        self.icon = "📅"
        self.weather_data = None

    def get_widget(self, parent):
        # Frame principal con fondo oscuro
        frame = tk.Frame(parent, bg=self.style.get_color("bg_dark"))
        
        # --- HEADER (Reloj, Fecha y Clima) ---
        header = tk.Frame(frame, bg=self.style.get_color("bg_header"), height=100)
        header.pack(fill=tk.X, side=tk.TOP, padx=20, pady=20)
        header.pack_propagate(False)

        # Info de Tiempo (Izquierda del header)
        time_frame = tk.Frame(header, bg=self.style.get_color("bg_header"))
        time_frame.pack(side=tk.LEFT, padx=20)
        
        self.lbl_time = tk.Label(time_frame, text="00:00", fg=self.style.get_color("text_main"), bg=self.style.get_color("bg_header"), 
                                 font=("Arial", 28, "bold"))
        self.lbl_time.pack(anchor="w")
        
        self.lbl_date = tk.Label(time_frame, text="---", fg=self.style.get_color("text_dim"), bg=self.style.get_color("bg_header"), 
                                 font=("Arial", 10))
        self.lbl_date.pack(anchor="w")

        # Info de Clima (Derecha del header)
        weather_frame = tk.Frame(header, bg=self.style.get_color("bg_header"))
        weather_frame.pack(side=tk.RIGHT, padx=20)

        self.lbl_temp = tk.Label(weather_frame, text="--°", fg=self.style.get_color("accent"), bg=self.style.get_color("bg_header"), 
                                 font=("Arial", 24, "bold"))
        self.lbl_temp.pack(side=tk.LEFT, padx=5)
        
        self.lbl_condition = tk.Label(weather_frame, text="Cargando clima...", fg=self.style.get_color("text_dim"), bg=self.style.get_color("bg_header"), 
                                      font=("Arial", 10))
        self.lbl_condition.pack(side=tk.LEFT, padx=5)

        # --- CUERPO (Dos columnas) ---
        body = tk.Frame(frame, bg=self.style.get_color("bg_dark"))
        body.pack(fill=tk.BOTH, expand=True, padx=20)

        # Columna Izquierda: Calendario (70%)
        left_col = tk.Frame(body, bg=self.style.get_color("bg_dark"))
        left_col.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
        
        self.calendar = CalendarWidget(left_col, bg=self.style.get_color("bg_main"))
        self.calendar.pack(fill=tk.BOTH, expand=True)

        # Columna Derecha: Lista de Eventos (30%)
        right_col = tk.Frame(body, bg=self.style.get_color("bg_dark"), width=250)
        right_col.pack(side=tk.RIGHT, fill=tk.Y)
        right_col.pack_propagate(False)
        
        self.event_list = EventListWidget(right_col, bg=self.style.get_color("bg_main"))
        self.event_list.pack(fill=tk.BOTH, expand=True)
        
        # Cargar datos iniciales
        self._update_time()
        self._update_weather()
        self._populate_demo_events()

        return frame

    def _update_time(self):
        """Actualiza el reloj y la fecha."""
        now = datetime.now()
        self.lbl_time.config(text=now.strftime("%H:%M"))
        
        days_es = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
        months_es = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
        
        date_str = f"{days_es[now.weekday()]}, {now.day} de {months_es[now.month-1]}"
        self.lbl_date.config(text=date_str)
        
        # Programar siguiente actualización en 1 minuto
        self.lbl_time.after(60000, self._update_time)

    def _update_weather(self):
        """Obtiene clima actual de forma asíncrona (thread simple)."""
        import threading
        
        def fetch():
            data = WeatherService.get_weather()
            if data:
                self.lbl_temp.after(0, lambda: self.lbl_temp.config(text=f"{data['temp']}°"))
                self.lbl_condition.after(0, lambda: self.lbl_condition.config(text=data['condition']))

        threading.Thread(target=fetch, daemon=True).start()

    def _populate_demo_events(self):
        """Añade eventos de prueba para demostrar el widget."""
        self.event_list.clear()
        self.event_list.add_event("09:00", "Reunión de Equipo", "Repaso de objetivos semanales.")
        self.event_list.add_event("14:30", "Comida con Cliente", "Restaurante La Pausa.")
        self.event_list.add_event("18:00", "Gimnasio", "Día de pierna.")

    def get_voice_commands(self):
        return {
            "agenda": "open_agenda",
            "calendario": "open_agenda",
            "eventos": "open_agenda"
        }

    def on_voice_command(self, action_slug, text):
        if action_slug == "open_agenda":
            # La activación del módulo ya sucede en el ModuleService,
            # pero aquí podemos ejecutar una respuesta vocal o animar algo.
            self.chat_service.voice_service.process_text("Abriendo tu agenda personal.")
