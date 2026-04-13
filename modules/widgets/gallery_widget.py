import tkinter as tk
from tkinter import ttk
import os
from PIL import Image, ImageTk

class GalleryWidget(tk.Frame):
    """
    Widget de galería modular y reutilizable.
    Muestra una lista scrollable de elementos creados.
    """
    def __init__(self, parent, title="GALERÍA", style=None, bg_color=None, item_bg=None, on_back=None):
        self.style = style
        self.on_back = on_back
        
        if self.style:
            bg_color = self.style.get_color("bg_main")
            item_bg = self.style.get_color("bg_input")
            header_bg = self.style.get_color("bg_header")
        else:
            bg_color = bg_color or "#2b2b2b"
            item_bg = item_bg or "#333333"
            header_bg = "#1e1e1e"
            
        super().__init__(parent, bg=bg_color)
        self.bg_color = bg_color
        self.item_bg = item_bg
        self.header_bg = header_bg
        
        # 1. Cabecera de la Galería
        self.header = tk.Frame(self, bg=self.header_bg, padx=10, pady=5)
        self.header.pack(fill=tk.X)
        
        # Botón Atrás (Flecha)
        self.btn_back = tk.Button(self.header, text="◀", bg=self.header_bg, fg=self.style.get_color("accent") if self.style else "#4EC9B0",
                                  relief="flat", font=("Arial", 10, "bold"), cursor="hand2", command=self._trigger_back)
        self.btn_back.pack(side=tk.LEFT, padx=(0, 5))
        self.btn_back.pack_forget() # Oculto por defecto
        
        tk.Label(self.header, text=title, bg=self.header_bg, fg=self.style.get_color("text_dim") if self.style else "#888", 
                 font=("Arial", 8, "bold")).pack(side=tk.LEFT)
        
        # 2. Área Scrollable
        self.canvas = tk.Canvas(self, bg=bg_color, highlightthickness=0, width=220)
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        
        self.scrollable_frame = tk.Frame(self.canvas, bg=bg_color)
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        
        self.canvas_window = self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        
        # Ajustar ancho del frame interno al ancho del canvas
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Soporte para rueda del ratón
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)

        # Registro de elementos numerados
        self.item_callbacks = [] # Lista de funciones (índice 0 = nada, 1 = elem 1)

    def set_back_visibility(self, visible):
        """Muestra u oculta el botón de retroceso."""
        if visible:
            self.btn_back.pack(side=tk.LEFT, padx=(0, 5), before=self.header.winfo_children()[1] if len(self.header.winfo_children())>1 else None)
        else:
            self.btn_back.pack_forget()

    def _trigger_back(self):
        if self.on_back:
            self.on_back()

    def _on_canvas_configure(self, event):
        self.canvas.itemconfig(self.canvas_window, width=event.width)

    def _on_mousewheel(self, event):
        try:
            if self.canvas.winfo_exists():
                self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        except:
            pass

    def add_item(self, title, subtitle="", icon="📄", callback=None, is_folder=False, thumbnail_path=None):
        """Añade un elemento a la galería con soporte para miniaturas y validación de estado."""
        if not self.winfo_exists(): return
        if not self.scrollable_frame.winfo_exists(): return
        
        if is_folder:
            icon = "📂"
            
        item_frame = tk.Frame(self.scrollable_frame, bg=self.item_bg, padx=10, pady=8, cursor="hand2")
        item_frame.pack(fill=tk.X, padx=5, pady=2)
        
        # Icono o Miniatura
        added_thumb = False
        if thumbnail_path and os.path.exists(thumbnail_path):
            try:
                img = Image.open(thumbnail_path)
                img.thumbnail((32, 32), Image.Resampling.LANCZOS)
                photo = ImageTk.PhotoImage(img)
                thumb_lbl = tk.Label(item_frame, image=photo, bg=self.item_bg)
                thumb_lbl.image = photo # Referencia vital
                thumb_lbl.pack(side=tk.LEFT, padx=(0, 10))
                added_thumb = True
            except:
                pass

        if not added_thumb:
            color = (self.style.get_color("accent") if self.style else "#ffd700") if is_folder else (self.style.get_color("text_dim") if self.style else "#aaa")
            icon_lbl = tk.Label(item_frame, text=icon, bg=self.item_bg, fg=color, font=("Arial", 14 if not is_folder else 12))
            icon_lbl.pack(side=tk.LEFT, padx=(0, 10))
            
        # 3. Número de índice (si existe)
        index = len(self.item_callbacks) + 1
        self.item_callbacks.append(callback)
        
        num_bg = self.style.get_color("accent") if self.style else "#4EC9B0"
        num_lbl = tk.Label(item_frame, text=str(index), bg=num_bg, fg="white", 
                           font=("Arial", 7, "bold"), width=3, pady=2)
        num_lbl.pack(side=tk.LEFT, padx=(0, 10))
        
        # Textos
        txt_frame = tk.Frame(item_frame, bg=self.item_bg)
        txt_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        tk.Label(txt_frame, text=title, bg=self.item_bg, fg=self.style.get_color("text_main") if self.style else "#eee", 
                 font=("Arial", 9, "bold" if is_folder else "normal"), anchor="w").pack(fill=tk.X)
        
        if subtitle:
            tk.Label(txt_frame, text=subtitle, bg=self.item_bg, fg="#777", 
                     font=("Arial", 8), anchor="w").pack(fill=tk.X)
            
        # Comportamiento
        if callback:
            item_frame.bind("<Button-1>", lambda e: callback())
            for child in item_frame.winfo_children():
                child.bind("<Button-1>", lambda e: callback())
                if isinstance(child, tk.Frame):
                    for grandchild in child.winfo_children():
                        grandchild.bind("<Button-1>", lambda e: callback())

        # Efecto hover
        hover_bg = self.style.get_color("bg_dark") if self.style else "#3d3d3d"
        item_frame.bind("<Enter>", lambda e: self._on_item_hover(item_frame, hover_bg, True))
        item_frame.bind("<Leave>", lambda e: self._on_item_hover(item_frame, self.item_bg, False))

    def _on_item_hover(self, frame, color, entering):
        if not frame.winfo_exists(): return
        frame.config(bg=color)
        for child in frame.winfo_children():
            child.config(bg=color)
            if isinstance(child, tk.Frame):
                for grandchild in child.winfo_children():
                    grandchild.config(bg=color)

    def trigger_index(self, index):
        """Ejecuta el callback del elemento en el índice dado (1-based)."""
        idx = index - 1
        if 0 <= idx < len(self.item_callbacks):
            cb = self.item_callbacks[idx]
            if cb:
                cb()
                return True
        return False

    def clear(self):
        """Limpia todos los elementos de la galería de forma segura."""
        if not self.winfo_exists(): return
        if not self.scrollable_frame.winfo_exists(): return
        
        self.item_callbacks = []
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()
