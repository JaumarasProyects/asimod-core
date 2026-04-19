import tkinter as tk
import os
import json
import cv2
from PIL import Image, ImageTk
from core.ports.visualizer_port import VisualizerPort

class AvatarVisualizer(VisualizerPort):
    """
    Visualizador de Avatar (Plugin Modular).
    Soporta imágenes estáticas y vídeos MP4 en bucle con recorte inteligente.
    """
    
    def __init__(self, parent: tk.Widget, width: int = 400, height: int = 400):
        super().__init__(parent, width, height)
        self.character_data = {}
        self.idle_image = None
        self.talking_image = None
        self.current_photo = None
        
        # UI Items
        self.image_item = None
        self.text_item = None
        self.frame_item = None
        self.dot_item = None
        self.emoji_item = None # NUEVO
        self.fallback_icon = "👤"
        
        # State
        self._cap = None
        self._video_running = False
        self._current_video_path = None
        self._after_id = None
        self._last_rendered_size = (0, 0)
        
    @property
    def name(self) -> str:
        return "Avatar"
    
    def _init_canvas(self):
        """Inicializa el canvas y los items base."""
        if self._canvas:
            self._canvas.bind("<Configure>", self._on_resize)
            # Crear items una sola vez
            self._init_ui_items()
            
        self._refresh_assets()
        self._show_state("idle")

    def _init_ui_items(self):
        """Crea los elementos gráficos base en el canvas."""
        if not self._canvas: return
        self._canvas.delete("all")
        
        # 1. Nombre
        self.text_item = self._canvas.create_text(
            self.width / 2, 20, text="", fill="#4EC9B0", font=("Arial", 10, "bold")
        )
        
        # 2. Marco
        self.frame_item = self._canvas.create_rectangle(
            0, 0, 0, 0, fill="#222", outline="#4EC9B0", width=1, state="hidden"
        )
        
        # 3. Imagen
        self.image_item = self._canvas.create_image(
            self.width / 2, self.height / 2, image=None, anchor="center"
        )
        
        # 4. Dot
        self.dot_item = self._canvas.create_oval(
            0, 0, 0, 0, fill="#4EC9B0", outline="", state="hidden"
        )
        
        # 5. Emojis (NUEVO)
        self.emoji_item = self._canvas.create_text(
            self.width / 2, self.height - 40, text="", fill="white", 
            font=("Segoe UI Emoji", 24), anchor="n", state="hidden"
        )

    def set_character(self, character_data: dict):
        """Recibe los datos del personaje y recarga los assets."""
        self.character_data = character_data
        self._refresh_assets()
        # Actualizar nombre en UI
        if self._canvas and self.text_item:
            name = self.character_data.get("name", "SISTEMA").upper()
            self._canvas.itemconfig(self.text_item, text=name)
            
        if not self.is_active:
            self._show_state("idle")

    def start(self):
        if self.is_active: return
        self.is_active = True
        self._show_state("talking")
    
    def stop(self):
        self.is_active = False
        self._show_state("idle")

    def set_emojis(self, emojis: list):
        """Muestra una lista de emojis en el lateral del avatar."""
        if not self._canvas or not self.emoji_item: return
        
        text = "".join(emojis)
        if not text:
            self._canvas.itemconfig(self.emoji_item, state="hidden")
            return
            
        self._canvas.itemconfig(self.emoji_item, text=text, state="normal")
        # Auto-ocultar después de 5 segundos
        self.parent.after(5000, lambda: self._canvas.itemconfig(self.emoji_item, state="hidden") if self._canvas else None)

    def _refresh_assets(self):
        """Carga imágenes estáticas soportando diccionario (moderno) o string (legado)."""
        self.idle_image = None
        self.talking_image = None
        if not self.character_data: return

        avatar_cfg = self.character_data.get("avatar", {})
        
        # Soporte para avatar como string (directamente la ruta)
        if isinstance(avatar_cfg, str):
            idle_path = avatar_cfg
            talk_path = None
        else:
            idle_path = avatar_cfg.get("idle")
            talk_path = avatar_cfg.get("talking")
        
        if idle_path: 
            self.idle_image = self._load_and_resize(idle_path)
            
        if talk_path: 
            self.talking_image = self._load_and_resize(talk_path)
        
        # Fallback: si no hay imagen de hablar, usar la de reposo
        if not self.talking_image:
            self.talking_image = self.idle_image

    def _load_and_resize(self, path):
        try:
            full_path = self._resolve_path(path)
            if not full_path or not os.path.exists(full_path): return None

            img = Image.open(full_path)
            target_size = self.width if self.width > 20 else 400
            
            # Smart Crop
            w, h = img.size
            if h > w: img = img.crop((0, 0, w, w))
            else:
                left = (w - h) // 2
                img = img.crop((left, 0, left + h, h))
            
            display_size = int(target_size * 0.75)
            img = img.resize((display_size, display_size), Image.Resampling.LANCZOS)
            return ImageTk.PhotoImage(img)
        except Exception as e:
            print(f"[AvatarVisualizer] Error cargando imagen {path}: {e}")
            return None

    def _resolve_path(self, path):
        if not path: return None
        if os.path.isabs(path) and os.path.exists(path): return path
        
        # Normalización agresiva de separadores para Windows
        clean_path = path.replace("/", os.sep).replace("\\", os.sep).lstrip(os.sep)
        
        # Áreas de búsqueda: Raíz, CWD, Salida de Media Generator
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        search_roots = [
            base_dir,
            os.getcwd(),
            os.path.join(base_dir, "modules", "media_generator"),
            os.path.join(base_dir, "modules", "media_generator", "output"),
            os.path.join(base_dir, "modules", "media_generator", "output", "imagen"),
            os.path.join(base_dir, "modules", "media_generator", "output", "video")
        ]
        
        for r in search_roots:
            test_p = os.path.join(r, clean_path)
            if os.path.exists(test_p): return test_p
            
            # Re-intento: si la ruta ya incluía 'output/imagen/' y la estamos uniendo a una raíz que ya la tiene
            # simplemente intentamos con el basename
            basename = os.path.basename(clean_path)
            test_b = os.path.join(r, basename)
            if os.path.exists(test_b): return test_b
            
        print(f"[AvatarVisualizer] No se pudo resolver ruta: {path} (Buscado en {len(search_roots)} raíces)")
        return None

    def _show_state(self, state):
        """Gestiona Vídeo vs Imagen con soporte para esquemas modernos y legados."""
        # 1. Buscar en diccionario 'video' (moderno)
        video_cfg = self.character_data.get("video", {})
        video_path = video_cfg.get("talking" if state == "talking" else "idle")
        
        # 2. Fallback: buscar en diccionario 'avatar' (para los publicados anteriormente)
        if not video_path:
            avatar_cfg = self.character_data.get("avatar", {})
            if isinstance(avatar_cfg, dict):
                video_path = avatar_cfg.get("talking_video" if state == "talking" else "idle_video")
        
        full_video_path = self._resolve_path(video_path)

        if full_video_path and os.path.exists(full_video_path):
            self._start_video(full_video_path)
        else:
            self._stop_video()
            self._update_static_ui(state)

    def _update_static_ui(self, state):
        """Actualiza la imagen estática en los items existentes."""
        if not self._canvas or not self.image_item: return
        
        photo = self.talking_image if (state == "talking" and self.talking_image) else self.idle_image
        self._update_frame_elements(photo, state)

    def _update_frame_elements(self, photo, state):
        """Posiciona y configura los elementos del canvas."""
        if not self._canvas: return
        
        center_y = (self.height / 2) + 12
        
        if photo:
            display_size = photo.width() if hasattr(photo, 'width') else 200
            px = 6
            
            # Actualizar Marco
            self._canvas.coords(self.frame_item, 
                               (self.width - display_size)/2 - px, center_y - (display_size/2) - px,
                               (self.width + display_size)/2 + px, center_y + (display_size/2) + px)
            self._canvas.itemconfig(self.frame_item, state="normal")
            
            # Actualizar Imagen
            self._canvas.coords(self.image_item, self.width / 2, center_y)
            self._canvas.itemconfig(self.image_item, image=photo, state="normal")
            self._canvas.image = photo
            
            # Actualizar Dot
            if state == "talking":
                self._canvas.coords(self.dot_item, 
                                   (self.width + display_size)/2 + 15, center_y - 5,
                                   (self.width + display_size)/2 + 25, center_y + 5)
                self._canvas.itemconfig(self.dot_item, state="normal")
            else:
                self._canvas.itemconfig(self.dot_item, state="hidden")
            
            # Reposicionar emojis debajo del marco
            if self.emoji_item:
                emoji_y = center_y + (display_size / 2) + px + 10
                self._canvas.coords(self.emoji_item, self.width / 2, emoji_y)
        else:
            self._canvas.itemconfig(self.image_item, state="hidden")
            self._canvas.itemconfig(self.frame_item, state="hidden")
            self._canvas.itemconfig(self.dot_item, state="hidden")

    # --- VIDEO ENGINE ---

    def _start_video(self, path):
        if self._current_video_path == path and self._video_running: return
        self._stop_video()
        self._cap = cv2.VideoCapture(path)
        if self._cap.isOpened():
            self._current_video_path = path
            self._video_running = True
            self._update_video_frame()

    def _stop_video(self):
        self._video_running = False
        if self._after_id: self.parent.after_cancel(self._after_id); self._after_id = None
        if self._cap: self._cap.release(); self._cap = None
        self._current_video_path = None

    def _update_video_frame(self):
        if not self._video_running or not self._cap or not self._canvas: return

        ret, frame = self._cap.read()
        if not ret:
            self._cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ret, frame = self._cap.read()
            if not ret: return

        # 1. CROP & CONVERT
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, _ = frame.shape
        # Smart Crop (H > W => Vertical)
        if h > w: sf = frame[0:w, 0:w]
        else: l = (w - h) // 2; sf = frame[0:h, l:l+h]

        # 2. RESIZE
        ts = self.width if self.width > 20 else 400
        ds = int(ts * 0.75)
        sf = cv2.resize(sf, (ds, ds), interpolation=cv2.INTER_LINEAR)

        # 3. UPDATE TK
        self.current_photo = ImageTk.PhotoImage(image=Image.fromarray(sf))
        self._update_frame_elements(self.current_photo, "talking" if self.is_active else "idle")

        # Loop
        self._after_id = self.parent.after(33, self._update_video_frame)

    def _on_resize(self, event):
        if event.width > 20 and (abs(event.width - self.width) > 10):
            self.width = event.width
            self.height = int(event.width * 0.9)
            if self._frame: self._frame.config(height=self.height)
            if self._canvas: self._canvas.config(height=self.height)
            
            # Reposicionar nombre
            if self.text_item: self._canvas.coords(self.text_item, self.width / 2, 20)
            # Reposicionar emojis (NUEVO: Centrado horizontalmente)
            if self.emoji_item: self._canvas.coords(self.emoji_item, self.width / 2, self.height - 40)
            
            self._refresh_assets()
            self._show_state("talking" if self.is_active else "idle")

    def destroy(self):
        self._stop_video()
        self.idle_image = self.talking_image = self.current_photo = None
        super().destroy()
