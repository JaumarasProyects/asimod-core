import tkinter as tk
from tkinter import ttk
import calendar
from datetime import datetime

class CalendarWidget(tk.Frame):
    """
    Componente de calendario reutilizable y estilizado.
    """
    def __init__(self, parent, bg="#2b2b2b", accent="#0078d4"):
        super().__init__(parent, bg=bg)
        self.bg = bg
        self.accent = accent
        self.now = datetime.now()
        self.current_year = self.now.year
        self.current_month = self.now.month
        
        self.setup_ui()
        self.show_month(self.current_year, self.current_month)

    def setup_ui(self):
        # Header (Mes y Año con flechas)
        header = tk.Frame(self, bg=self.bg)
        header.pack(fill=tk.X, pady=10)
        
        btn_prev = tk.Button(header, text="<", command=self.prev_month, 
                             bg=self.bg, fg="white", bd=0, font=("Arial", 12, "bold"))
        btn_prev.pack(side=tk.LEFT, padx=10)
        
        self.lbl_month = tk.Label(header, text="", bg=self.bg, fg="white", 
                                  font=("Arial", 14, "bold"), width=15)
        self.lbl_month.pack(side=tk.LEFT, expand=True)
        
        btn_next = tk.Button(header, text=">", command=self.next_month, 
                             bg=self.bg, fg="white", bd=0, font=("Arial", 12, "bold"))
        btn_next.pack(side=tk.RIGHT, padx=10)
        
        # Grid del calendario
        self.days_container = tk.Frame(self, bg=self.bg)
        self.days_container.pack(fill=tk.BOTH, expand=True, padx=10)

    def show_month(self, year, month):
        # Limpiar días anteriores
        for widget in self.days_container.winfo_children():
            widget.destroy()
            
        month_names = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", 
                       "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
        self.lbl_month.config(text=f"{month_names[month-1]} {year}")
        
        # Cabecera de días (L M X J V S D)
        days_header = ["L", "M", "X", "J", "V", "S", "D"]
        for i, day in enumerate(days_header):
            color = "#888" if i < 5 else "#ff4d4d"
            lbl = tk.Label(self.days_container, text=day, bg=self.bg, fg=color, font=("Arial", 10, "bold"))
            lbl.grid(row=0, column=i, pady=5, sticky="ew")
            
        # Obtener días del mes
        cal = calendar.monthcalendar(year, month)
        
        for r, week in enumerate(cal):
            for c, day in enumerate(week):
                if day == 0:
                    continue
                
                is_today = (day == self.now.day and month == self.now.month and year == self.now.year)
                
                bg_color = self.accent if is_today else "#3c3c3c"
                fg_color = "white"
                
                btn = tk.Label(self.days_container, text=str(day), bg=bg_color, fg=fg_color,
                               width=4, height=2, font=("Arial", 10))
                btn.grid(row=r+1, column=c, padx=2, pady=2, sticky="nsew")

        # Configurar pesos de las columnas para que sean iguales
        for i in range(7):
            self.days_container.columnconfigure(i, weight=1)

    def prev_month(self):
        self.current_month -= 1
        if self.current_month < 1:
            self.current_month = 12
            self.current_year -= 1
        self.show_month(self.current_year, self.current_month)

    def next_month(self):
        self.current_month += 1
        if self.current_month > 12:
            self.current_month = 1
            self.current_year += 1
        self.show_month(self.current_year, self.current_month)
