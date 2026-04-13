import tkinter as tk
from tkinter import ttk

class EventListWidget(tk.Frame):
    """
    Componente de lista de eventos reutilizable con scroll.
    """
    def __init__(self, parent, bg="#2b2b2b"):
        super().__init__(parent, bg=bg)
        self.bg = bg
        self.setup_ui()

    def setup_ui(self):
        # Header de la lista
        header = tk.Label(self, text="Próximos Eventos", bg=self.bg, fg="#888", 
                          font=("Arial", 10, "bold"), anchor="w")
        header.pack(fill=tk.X, pady=(0, 10), padx=5)

        # Canvas con Scrollbar para la lista
        self.canvas = tk.Canvas(self, bg=self.bg, highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        
        self.scrollable_frame = tk.Frame(self.canvas, bg=self.bg)
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )

        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

    def add_event(self, time_str, title, description=""):
        """Añade un elemento a la lista."""
        item = tk.Frame(self.scrollable_frame, bg="#333", padx=10, pady=8)
        item.pack(fill=tk.X, pady=2, padx=5)
        
        time_lbl = tk.Label(item, text=time_str, bg="#333", fg="#0078d4", font=("Arial", 9, "bold"))
        time_lbl.pack(anchor="w")
        
        title_lbl = tk.Label(item, text=title, bg="#333", fg="white", font=("Arial", 10, "bold"))
        title_lbl.pack(anchor="w")
        
        if description:
            desc_lbl = tk.Label(item, text=description, bg="#333", fg="#888", font=("Arial", 9), wraplength=200, justify="left")
            desc_lbl.pack(anchor="w")

    def clear(self):
        """Limpia todos los eventos."""
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()
