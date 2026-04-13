import tkinter as tk
from tkinter import scrolledtext, ttk
import os
import threading
import time
from PIL import Image, ImageTk
import pygame
import cv2

class MediaDisplayWidget(tk.Frame):
    """
    Widget modular capaz de mostrar Texto, Imagen, Audio y Video.
    Detecta automáticamente el tipo según la extensión o contenido.
    """
    def __init__(self, parent, style=None, bg_color=None):
        self.style = style
        bg_color = bg_color or (style.get_color("bg_dark") if style else "#1e1e1e")
        super().__init__(parent, bg=bg_color)
        self.bg_color = bg_color
        
        # Estado interno
        self.current_media_path = None
        self.current_type = None
        self.is_playing = False
        self.image_ref = None
        self.video_thread = None
        self.stop_video_flag = threading.Event()

        # Configurar Grid principal para el widget
        self.grid_rowconfigure(0, weight=1) # Contenido (expandible)
        self.grid_rowconfigure(1, weight=0) # Controles (fijo)
        self.grid_columnconfigure(0, weight=1)

        # Contenedores
        self.content_frame = tk.Frame(self, bg=bg_color, highlightthickness=1, highlightbackground="#333")
        self.content_frame.grid(row=0, column=0, sticky="nsew")
        
        # Forzar un tamaño mínimo para que el widget sea visible aunque esté vacío
        self.content_frame.config(height=350) 
        self.content_frame.grid_propagate(False) # Mantener el tamaño mínimo inicial

        self.controls_frame = tk.Frame(self, bg=(style.get_color("bg_header") if style else "#111"), pady=5)
        self.controls_frame.grid(row=1, column=0, sticky="ew")

        # Widgets de visualización (se crean bajo demanda)
        self.text_widget = None
        self.image_label = None
        self.audio_canvas = None
        self.video_canvas = None

        # Controles
        self.btn_play = tk.Button(self.controls_frame, text="▶", bg="#333", fg="white", bd=0, padx=15, command=self._toggle_playback)
        self.btn_play.pack(side=tk.LEFT, padx=5)

        self.lbl_info = tk.Label(self.controls_frame, text="Esperando generación...", bg=self.controls_frame["bg"], fg="#888", font=("Arial", 8))
        self.lbl_info.pack(side=tk.LEFT, padx=10)

        # Placeholder inicial
        self._show_placeholder()

        # Inicializar Pygame Mixer si no está
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init()
        except:
            pass

    def load_media(self, file_path):
        """Carga cualquier tipo de medio basándose en la extensión."""
        # El contenedor debe respetar el tamaño asignado por el padre
        # y no expandirse infinitamente con el contenido.
        pass
        
        if not file_path:
            self._show_placeholder()
            self.lbl_info.config(text="Procesando...")
            return

        # Soporte para lista de medios (Galería Multimedia)
        if isinstance(file_path, list):
            if len(file_path) == 1:
                self.load_media(file_path[0])
            else:
                self._display_multi_media(file_path)
            return

        if not os.path.exists(file_path):
            self._show_error(f"Archivo no encontrado: {file_path}")
            return

        self.stop_playback()
        self.current_media_path = file_path
        ext = os.path.splitext(file_path)[1].lower()

        if ext in [".txt", ".md", ".json", ".log"]:
            self._display_text(file_path)
        elif ext in [".png", ".jpg", ".jpeg", ".webp", ".gif"]:
            self._display_image(file_path)
        elif ext in [".mp3", ".wav", ".ogg"]:
            self._display_audio(file_path)
        elif ext in [".mp4", ".avi", ".mkv", ".mov"]:
            self._display_video(file_path)
        elif ext in [".obj", ".glb", ".ply", ".stl"]:
            self._display_3d(file_path)
        else:
            # Intentar ver si es texto aunque no tenga extensión conocida
            try:
                # Probar si es legible como texto básico
                with open(file_path, 'rb') as f:
                    chunk = f.read(1024)
                    # Si contiene muchos nulos, probablemente es binario
                    if b'\x00' in chunk:
                        raise ValueError("Probable archivo binario")
                
                self._display_text(file_path)
            except:
                self._show_error(f"Formato no soportado o archivo binario: {ext}")

    def stop_playback(self):
        """Detiene cualquier reproducción activa y limpia threads."""
        self.is_playing = False
        self.btn_play.config(text="▶")
        
        # Audio
        try:
            pygame.mixer.music.stop()
        except: pass
        
        # Video
        self.stop_video_flag.set()
        if self.video_thread and self.video_thread.is_alive():
            # El video_thread debería terminar pronto por la flag
            pass

    def _clear_content(self, target=None):
        target = target or self.content_frame
        for widget in target.winfo_children():
            widget.destroy()
        if target == self.content_frame:
            self.image_label = None
            self.audio_canvas = None
            self.video_canvas = None
            self.text_widget = None

    def _show_placeholder(self):
        """Muestra un estado inicial elegante."""
        self._clear_content(self.content_frame)
        self.controls_frame.grid_remove() # Ocultar controles si no hay nada
        
        placeholder = tk.Frame(self.content_frame, bg=self.bg_color)
        placeholder.pack(expand=True, fill=tk.BOTH)
        
        tk.Label(placeholder, text="✨", font=("Arial", 40), bg=self.bg_color, fg="#333").pack(expand=True, pady=(20,0))
        tk.Label(placeholder, text="El resultado aparecerá aquí", font=("Arial", 10, "italic"), bg=self.bg_color, fg="#555").pack(expand=True, pady=(0,20))

    # --- TEXTO ---
    def _display_text(self, path, target=None):
        self.current_type = "text"
        target = target or self.content_frame
        self._clear_content(target)
        self.controls_frame.grid_remove() # No controles para texto

        # No reciclar el widget si el master es diferente
        if not self.text_widget or self.text_widget.master != target:
            self.text_widget = scrolledtext.ScrolledText(target, bg=self.bg_color, fg="#ddd", bd=0, font=("Consolas", 10))
        
        self.text_widget.pack(fill=tk.BOTH, expand=True)
        try:
            # Intentar varias codificaciones comunes
            content = None
            for enc in ['utf-8', 'latin-1', 'utf-16']:
                try:
                    with open(path, 'r', encoding=enc) as f:
                        content = f.read()
                    break # Éxito
                except:
                    continue
            
            if content is None:
                raise Exception("No se pudo determinar la codificación del texto.")
                
            self.text_widget.delete("1.0", tk.END)
            self.text_widget.insert(tk.END, content)
        except Exception as e:
            self.text_widget.insert(tk.END, f"Error leyendo texto: {e}")

    # --- IMAGEN ---
    def _display_image(self, path, target=None):
        self.current_type = "image"
        target = target or self.content_frame
        self._clear_content(target)
        self.controls_frame.grid_remove()

        self.image_label = tk.Label(target, bg=self.bg_color)
        self.image_label.pack(fill=tk.BOTH, expand=True)
        
        try:
            img = Image.open(path)
            # Redimensionado inteligente
            self._update_image_display(img, target)
            # Guardamos la imagen original para redimensionados futuros
            self.image_label.bind("<Configure>", lambda e, i=img, t=target: self._on_resize_image(i, t))
        except Exception as e:
            self._show_error(f"Error cargando imagen: {e}", target)

    def _update_image_display(self, img, target):
        if not self.image_label or self.image_label.master != target: return
        
        # Forzar actualización de geometría del padre para tener dimensiones reales
        target.update_idletasks()
        
        w, h = target.winfo_width(), target.winfo_height()
        if w < 10: w, h = 600, 400
        
        iw, ih = img.size
        ratio = min(w/iw, h/ih)
        
        # Escalado siempre (tanto para reducir como para ampliar y llenar el espacio)
        img_res = img.resize((int(iw*ratio), int(ih*ratio)), Image.Resampling.LANCZOS)
            
        self.image_ref = ImageTk.PhotoImage(img_res)
        self.image_label.config(image=self.image_ref)

    def _on_resize_image(self, img, target):
        # Evitar loops infinitos de resize
        if hasattr(self, "_resize_job"): self.after_cancel(self._resize_job)
        self._resize_job = self.after(200, lambda: self._update_image_display(img, target))

    def _display_audio(self, path, target=None):
        self.current_type = "audio"
        target = target or self.content_frame
        self._clear_content(target)
        self.controls_frame.grid() # Asegurar que los controles son visibles
        self.btn_play.config(text="▶")
        self.lbl_info.config(text=f"Audio: {os.path.basename(path)}")

        # Visualizador simple (un icono grande o barra)
        container = tk.Frame(target, bg=self.bg_color)
        container.pack(fill=tk.BOTH, expand=True)
        tk.Label(container, text="🎵", font=("Arial", 60), bg=self.bg_color, fg="#555").pack(expand=True)
        target.update()

    def _toggle_playback(self):
        if self.current_type == "audio":
            self._toggle_audio()
        elif self.current_type == "video":
            self._toggle_video()

    def ensure_playing(self):
        """Inicia la reproducción si no está ya activo (útil para re-clicks)."""
        if not self.is_playing:
            if self.current_type == "audio":
                self._toggle_audio()
            elif self.current_type == "video":
                self._toggle_video()
        else:
            # Si ya está reproduciendo, podríamos reiniciar o simplemente no hacer nada.
            # Según la petición, "darle al play" suele significar asegurar que suena/se ve.
            pass

    def _toggle_audio(self):
        if self.is_playing:
            pygame.mixer.music.pause()
            self.btn_play.config(text="▶")
            self.is_playing = False
        else:
            if pygame.mixer.music.get_busy():
                pygame.mixer.music.unpause()
            else:
                pygame.mixer.music.load(self.current_media_path)
                pygame.mixer.music.play()
            self.btn_play.config(text="⏸")
            self.is_playing = True

    # --- VIDEO ---
    def _display_video(self, path, target=None):
        self.current_type = "video"
        target = target or self.content_frame
        self._clear_content(target)
        self.controls_frame.grid(row=1, column=0, sticky="ew")
        self.btn_play.config(text="▶")
        self.lbl_info.config(text=f"Video: {os.path.basename(path)}")
        
        self.video_canvas = tk.Label(target, bg="black")
        self.video_canvas.pack(fill=tk.BOTH, expand=True)
        
        # Mostrar primer frame como preview
        cap = cv2.VideoCapture(path)
        ret, frame = cap.read()
        if ret:
            self._update_video_frame(frame, target)
        cap.release()

    def _toggle_video(self):
        if self.is_playing:
            self.stop_playback()
        else:
            # Obtener el target actual del canvas si existe
            target = self.video_canvas.master if self.video_canvas else self.content_frame
            
            self.is_playing = True
            self.btn_play.config(text="⏹")
            self.stop_video_flag.clear()
            self.video_thread = threading.Thread(target=self._video_loop, args=(self.current_media_path, target), daemon=True)
            self.video_thread.start()

    def _video_loop(self, path, target):
        cap = cv2.VideoCapture(path)
        fps = cap.get(cv2.CAP_PROP_FPS) or 30
        
        while not self.stop_video_flag.is_set():
            ret, frame = cap.read()
            if not ret: break # Fin de video
            
            self._update_video_frame(frame, target)
            time.sleep(1/fps)
            
        cap.release()
        self.is_playing = False
        self.after(0, lambda: self.btn_play.config(text="▶"))

    def _update_video_frame(self, frame, target=None):
        target = target or (self.video_canvas.master if self.video_canvas else self.content_frame)
        if not self.video_canvas or self.video_canvas.master != target: return
        # Convertir BGR a RGB
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        img = Image.fromarray(frame)
        
        # Redimensionar al canvas
        target.update_idletasks()
        w, h = target.winfo_width(), target.winfo_height()
        if w < 10: w, h = 600, 400
        
        iw, ih = img.size
        ratio = min(w/iw, h/ih)
        img = img.resize((int(iw*ratio), int(ih*ratio)), Image.Resampling.LANCZOS)
        
        self.image_ref = ImageTk.PhotoImage(img)
        self.after(0, lambda: self.video_canvas.config(image=self.image_ref))

    # --- MULTI MEDIA (GALLERY) ---
    def _display_multi_media(self, paths):
        self.current_type = "multi_media"
        self._clear_content()
        self.controls_frame.grid_remove()

        # Contenedor principal para la galería
        self.gallery_container = tk.PanedWindow(self.content_frame, orient=tk.HORIZONTAL, bg=self.bg_color, bd=0, sashwidth=4)
        self.gallery_container.pack(fill=tk.BOTH, expand=True)

        # 1. Área Principal (Izquierda) - El visor dinámico
        self.main_view_frame = tk.Frame(self.gallery_container, bg=self.bg_color)
        self.gallery_container.add(self.main_view_frame, stretch="always")
        
        # 2. Galería (Derecha) - Thumbnails
        sidebar = tk.Frame(self.gallery_container, bg="#151515", width=160, highlightbackground="#333", highlightthickness=1)
        self.gallery_container.add(sidebar, width=160)

        # Título para la galería
        tk.Label(sidebar, text="CONTENIDO", bg="#151515", fg="#555", font=("Arial", 7, "bold"), pady=5).pack(fill=tk.X)

        canvas = tk.Canvas(sidebar, bg="#111", highlightthickness=0, width=150)
        scrollbar = ttk.Scrollbar(sidebar, orient="vertical", command=canvas.yview)
        self.thumbs_container = tk.Frame(canvas, bg="#111")

        def _on_frame_configure(event):
            canvas.configure(scrollregion=canvas.bbox("all"))
        self.thumbs_container.bind("<Configure>", _on_frame_configure)
        
        canvas.create_window((0, 0), window=self.thumbs_container, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.thumb_refs = []

        def select_media(p):
            self.current_media_path = p
            # Limpiar área principal interna
            for widget in self.main_view_frame.winfo_children():
                widget.destroy()
            
            # Determinar tipo y cargar directamente en el panel principal de la galería
            ext = os.path.splitext(p)[1].lower()
            if ext in [".png", ".jpg", ".jpeg", ".webp", ".gif"]:
                self._display_image(p, target=self.main_view_frame)
            elif ext in [".mp3", ".wav", ".ogg"]:
                self._display_audio(p, target=self.main_view_frame)
            elif ext in [".mp4", ".avi", ".mov"]:
                self._display_video(p, target=self.main_view_frame)
            elif ext in [".obj", ".glb", ".ply", ".stl"]:
                self._display_3d(p, target=self.main_view_frame)
            else:
                self._display_text(p, target=self.main_view_frame)
            
            self.main_view_frame.update()

        # Crear thumbnails inteligentemente
        for p in paths:
            if not os.path.exists(p): continue
            try:
                ext = os.path.splitext(p)[1].lower()
                photo = None
                
                if ext in [".png", ".jpg", ".jpeg", ".webp", ".gif"]:
                    img_t = Image.open(p)
                    img_t.thumbnail((120, 120), Image.Resampling.LANCZOS)
                    photo = ImageTk.PhotoImage(img_t)
                else:
                    # Usar iconos para otros tipos
                    icon = "🎵" if ext in [".mp3", ".wav", ".ogg"] else "🎬" if ext in [".mp4", ".mov"] else "🧊" if ext in [".obj", ".glb"] else "📄"
                    # Crear una imagen pequeña con el texto del icono
                    from PIL import ImageDraw, ImageFont
                    img_icon = Image.new('RGB', (100, 100), color='#222')
                    # Intentar dibujar el icono si PIL lo permite, o simplemente dejarlo así
                    photo = ImageTk.PhotoImage(img_icon)
                    # Para simplificar, usaremos un label con texto si photo falla, 
                    # pero aquí intentaremos crear un botón con texto nativo si no hay foto
                
                if photo:
                    self.thumb_refs.append(photo)
                    btn = tk.Button(self.thumbs_container, image=photo, bg="#222", bd=1, 
                                   relief=tk.FLAT, activebackground="#444", 
                                   command=lambda path=p: select_media(path))
                else:
                    btn = tk.Button(self.thumbs_container, text=os.path.basename(p)[:12], bg="#222", fg="white", 
                                   relief=tk.FLAT, command=lambda path=p: select_media(path))
                
                btn.pack(pady=10, padx=15)
                # Si es audio/video, añadir una etiqueta debajo
                if ext not in [".png", ".jpg", ".jpeg", ".webp", ".gif"]:
                    tk.Label(self.thumbs_container, text=ext.upper(), bg="#111", fg="#666", font=("Arial", 7)).pack()

            except:
                continue

        # Mostrar primer elemento
        if paths:
            self.after(200, lambda: select_media(paths[0]))

    # --- 3D ---
    def _display_3d_old(self, path, parent=None):
        self.current_type = "3d"
        target = parent or self.content_frame
        self._clear_content(target)
        self.controls_frame.grid_remove()
        
    # --- 3D INTERNO ---
    def _display_3d(self, path, parent=None):
        self.current_type = "3d"
        target = parent or self.content_frame
        self._clear_content(target)
        self.controls_frame.grid_remove()
        
        container = tk.Frame(target, bg=self.bg_color)
        container.pack(fill=tk.BOTH, expand=True)
        
        # Título y ayuda
        help_lbl = tk.Label(container, text="🧊 VISUALIZACIÓN 3D INTERNA (Click y arrastra para rotar | Scroll para Zoom)", 
                           bg=self.bg_color, fg="#555", font=("Arial", 8))
        help_lbl.pack(pady=5)

        # Integrar el motor de renderizado por software
        from modules.widgets.internal_3d_renderer import Internal3DRenderer
        
        self.renderer_3d = Internal3DRenderer(container, bg=self.bg_color, highlightthickness=0)
        self.renderer_3d.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Cargar el modelo en el motor
        self.renderer_3d.load_model(path)

        # Botones de acción inferior
        actions_area = tk.Frame(container, bg=self.bg_color)
        actions_area.pack(fill=tk.X, pady=10)

        def open_folder():
            import subprocess
            subprocess.Popen(['explorer', '/select,', os.path.abspath(path)])

        btn_folder = tk.Button(actions_area, text="📂 Abrir Carpeta", 
                              bg="#222", fg="#888", bd=0, padx=15, pady=5, 
                              font=("Arial", 8, "bold"), cursor="hand2", command=open_folder)
        btn_folder.pack(side=tk.RIGHT, padx=20)
        
        name_lbl = tk.Label(actions_area, text=f"Archivo: {os.path.basename(path)}", 
                           bg=self.bg_color, fg="#888", font=("Arial", 8))
        name_lbl.pack(side=tk.LEFT, padx=20)

    def _show_error(self, message, target=None):
        target = target or self.content_frame
        self._clear_content(target)
        lbl = tk.Label(target, text=message, bg=self.bg_color, fg="#ff4444", wraplength=400)
        lbl.pack(expand=True)
