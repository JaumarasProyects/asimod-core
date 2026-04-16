import tkinter as tk
from PIL import Image, ImageTk
import os

class ImageButton(tk.Label):
    """
    Botón personalizado que usa una imagen de fondo de StyleService.
    Soporta escalado automático y superposición de texto.
    """
    def __init__(self, parent, text, style, callback, **kwargs):
        self.style = style
        self.callback = callback
        self.original_text = text
        
        # Obtener configuración del tema
        self.bg_img_path = self.style.get_background("button")
        self.accent_color = self.style.get_color("accent")
        self.text_main = self.style.get_color("text_main")
        self.text_dim = self.style.get_color("text_dim")
        
        # Colores de fallback si no hay imagen
        bg_color = kwargs.pop("bg", self.style.get_color("btn_bg"))
        fg_color = kwargs.pop("fg", self.text_main)
        
        # Extraer pady y width para calcular dimensiones fijas
        self.requested_pady = kwargs.pop("pady", 10)
        self.requested_width = kwargs.pop("width", None)
        
        super().__init__(parent, text=text, bg=bg_color, fg=fg_color, cursor="hand2", compound="center", **kwargs)
        
        # Crear un placeholder de 1x1 para poder fijar el tamaño en píxeles desde el inicio
        self.placeholder = tk.PhotoImage(width=1, height=1)
        
        # Calcular altura fija: aproximación (tamaño fuente + 2 * pady)
        try:
            font_size = kwargs.get("font", ("Arial", 10))[1]
            if not isinstance(font_size, int): font_size = 10
        except:
            font_size = 10
            
        self.fixed_height = font_size + (2 * self.requested_pady) + 10 # Margen extra
        
        # Configuración inicial de tamaño
        config_args = {"image": self.placeholder, "height": self.fixed_height, "pady": 0}
        if self.requested_width:
            config_args["width"] = self.requested_width

            
        self.config(**config_args)

        
        self.photo = None
        self.pil_img = None
        
        self.is_active = False
        self.last_size = (0, 0)
        self._resizing = False
        self._after_id = None
        
        if self.bg_img_path and os.path.exists(self.bg_img_path):
            try:
                self.pil_img = Image.open(self.bg_img_path)
                # No especificamos bordes para que la imagen se vea limpia e ignoramos pady interno
                self.config(bd=0) 
                self.bind("<Configure>", self._on_configure)
            except Exception as e:
                print(f"[ImageButton] Error cargando {self.bg_img_path}: {e}")
        
        self.bind("<Button-1>", lambda e: self.callback())
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<Map>", lambda e: self.after(100, self._resize_image)) # Forzar dibujo inicial

    def _on_configure(self, event):
        """Manejador de evento Configure con debouncing."""
        if self._after_id:
            self.after_cancel(self._after_id)
        self._after_id = self.after(50, self._resize_image)

    def _resize_image(self, event=None):
        if self._resizing: return
        
        w = self.winfo_width()
        h = self.winfo_height()
        
        if w < 10 or h < 10: return
        
        # Evitar bucles infinitos: Solo redimensionar si el cambio es significativo (> 3px)
        old_w, old_h = self.last_size
        if abs(w - old_w) <= 3 and abs(h - old_h) <= 3:
            return
            
        self.last_size = (w, h)
        self._resizing = True
        
        if self.pil_img:
            try:
                # Redimensionar imagen para que coincida exactamente con el tamaño actual del Label
                resized = self.pil_img.resize((w, h), Image.Resampling.LANCZOS)
                self.photo = ImageTk.PhotoImage(resized)
                self.config(image=self.photo)
            except Exception as e:
                print(f"[ImageButton] Error redimensionando: {e}")
            finally:
                # Liberar el protector de reentrada tras un breve lapso para que el diseño se asiente
                self.after(100, self._reset_resizing)

    def _reset_resizing(self):
        self._resizing = False

    def _on_enter(self, event):
        self.config(fg=self.accent_color)
        if not self.pil_img:
            # Si no hay imagen, usamos color de fondo como fallback
            self.config(bg=self.style.get_color("accent_hover"))

    def _on_leave(self, event):
        if self.is_active: return
        self.config(fg=self.text_main)
        if not self.pil_img:
            self.config(bg=self.style.get_color("btn_bg"))

    def set_active(self, active):
        """Mantiene el estado visual activo."""
        self.is_active = active
        if active:
            self.config(fg=self.accent_color)
        else:
            self.config(fg=self.text_main)
