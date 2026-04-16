import tkinter as tk
from PIL import Image, ImageTk
import os

class BackgroundFrame(tk.Canvas):
    """
    Un contenedor que muestra una imagen de fondo estirada automáticamente.
    Hereda de Canvas para permitir transparencia de algunos elementos y
    mejor control de capas.
    """
    def __init__(self, parent, style_service, bg_key, **kwargs):
        self.style = style_service
        self.bg_key = bg_key
        
        # Color base por si la imagen falla o no existe
        bg_color = self.style.get_color("bg_main")
        
        # Heredar de Canvas pero configurarlo para que actúe como una caja (Frame)
        super().__init__(parent, bg=bg_color, highlightthickness=0, **kwargs)
        
        self.img_path = self.style.get_background(self.bg_key)
        self.photo = None
        self.pil_img = None
        
        if self.img_path:
            # Intentar normalizar ruta (por si viene con / o \)
            self.img_path = os.path.normpath(self.img_path)
            if os.path.exists(self.img_path):
                try:
                    self.pil_img = Image.open(self.img_path)
                    self.bind("<Configure>", self._resize_image)
                    # Forzar un dibujado inicial en cuanto el widget esté listo
                    self.after(100, lambda: self._resize_image(type('obj', (object,), {'width': self.winfo_width(), 'height': self.winfo_height()})))
                except Exception as e:
                    print(f"[BackgroundFrame] Error cargando imagen {self.img_path}: {e}")

    def _resize_image(self, event):
        w, h = event.width, event.height
        if w < 10 or h < 10: return
        
        if self.pil_img:
            try:
                # Estirar imagen al tamaño del contenedor (Stretch)
                resized = self.pil_img.resize((w, h), Image.Resampling.LANCZOS)
                self.photo = ImageTk.PhotoImage(resized)
                
                # Dibujar en el fondo
                self.delete("bg")
                self.create_image(0, 0, anchor="nw", image=self.photo, tags="bg")
                self.tag_lower("bg")
            except Exception as e:
                print(f"[BackgroundFrame] Error redimensionando: {e}")

    def update_style(self):
        """Actualiza la imagen si el estilo cambia."""
        new_path = self.style.get_background(self.bg_key)
        if new_path != self.img_path:
            self.img_path = new_path
            if self.img_path and os.path.exists(self.img_path):
                self.pil_img = Image.open(self.img_path)
                self._resize_image(type('obj', (object,), {'width': self.winfo_width(), 'height': self.winfo_height()}))
            else:
                self.pil_img = None
                self.delete("bg")
                self.config(bg=self.style.get_color("bg_main"))
