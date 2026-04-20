import tkinter as tk
import os
import json
import cv2
import numpy as np
from PIL import Image, ImageTk
from core.ports.visualizer_port import VisualizerPort

class AvatarVisualizer(VisualizerPort):
    """
    Visualizador de Avatar (Plugin Modular).
    Soporta imágenes estáticas y vídeos MP4 en bucle con recorte inteligente.
    """
    
    def __init__(self, parent: tk.Widget, width: int = 400, height: int = 230):
        super().__init__(parent, width, height)
        self.character_data = {}
        self.idle_image = None
        self.talking_image = None
        self.current_emotion = "neutral" # Estado emocional detectado (neutral, joy, anger)
        self.joy_emojis = ["😊", "❤️", "😍", "🥳", "💖", "🌟", "😄", "😸", "💖", "😂", "🤣", "🥰", "😻", "🤩"]
        self.anger_emojis = ["💢", "😠", "😡", "🤬", "👿", "🖕", "💀", "🤡", "🙄", "😤", "👿", "🖤", "👊", "🖕", "🐷"]
        self.sadness_emojis = ["😢", "😭", "😞", "💔", "😔", "😿", "💧", "☁️", "🥀", "🎼", "🏚️", "🖤", "🥀", "🌫️"]
        self.style_emojis = ["✨", "💅", "💋", "💃", "🍭", "🥂", "🎉", "🌈", "💄", "👠", "👒", "🔥", "🎀", "🎸", "🎤"] # Estilo/Diva (Neutros)
        self.current_photo = None
        
        # UI Items
        self.image_item = None
        self.text_item = None # Legado (canvas), ahora usamos header_label
        self.header_name_label = None # NUEVO: En el frame superior
        self.frame_item = None
        self.dot_item = None
        self.emoji_item = None # NUEVO
        self.stat_items = {} # NUEVO: items de las barras de stats {key: {arc: ID, text: ID}}
        self.fallback_icon = "👤"
        
        # Opciones de visibilidad (Configurables)
        self.show_threads = True
        self.show_stats = True
        self.stats_canvas = None # NUEVO: Canvas para los gauges en la cabecera
        
        # Callbacks para comunicación con ChatWidget
        self.on_thread_change = None
        self.on_new_thread = None
        self.on_stats_change = None # NUEVO: Para notificar cambios en el perfil (stats)
        
        # State
        self._cap = None
        self._video_running = False
        self._current_video_path = None
        self._after_id = None
        self._reloading = False
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
            self._init_thread_ui() # NUEVO: UI de hilos (fuera del canvas)
            
        self._refresh_assets()
        self._show_state("idle")

    def _init_ui_items(self):
        """Crea los elementos gráficos base en el canvas."""
        if not self._canvas: return
        self._canvas.delete("all")
        
        # 1. Nombre (ELIMINADO DEL CANVAS para moverlo a la cabecera)
        # self.text_item = ...
        
        # 2. Marco
        self.frame_item = self._canvas.create_rectangle(
            0, 0, 0, 0, fill="#222", outline="#4EC9B0", width=1, state="hidden"
        )
        
        # 3. Imagen (Anclada al norte con un pequeño margen para ver el borde cyan)
        self.image_item = self._canvas.create_image(
            self.width / 2, 6, image=None, anchor="n"
        )
        
        # 4. Dot
        self.dot_item = self._canvas.create_oval(
            0, 0, 0, 0, fill="#4EC9B0", outline="", state="hidden"
        )
        
        # 5. Emojis (TAMAÑO REDUCIDO Y PROFESIONAL)
        self.emoji_item = self._canvas.create_text(
            self.width / 2, self.height - 12, text="", fill="white", 
            font=("Segoe UI Emoji", 14), anchor="s", state="hidden"
        )
        
        # 6. Línea Separadora Interna (Para eliminar gaps externos)
        self.bottom_sep = self._canvas.create_line(
            0, self.height - 1, self.width, self.height - 1, fill="#444", width=1
        )
        
        # 6. Stats (ELIMINADO DE AQUÍ para evitar "ghost items" en el canvas principal)
        # Se inicializan solo en stats_canvas dentro de _init_thread_ui

    def _init_stat_gauges(self):
        """Pre-crea los placeholders para las barras de estado en el stats_canvas."""
        canvas = self.stats_canvas if self.stats_canvas else self._canvas
        if not canvas: return
        
        self.stat_items = {}
        keys = [("S", "stress", "#ff4b4b"), ("A", "anger", "#ffa500"), ("J", "joy", "#ffff00"), ("M", "fear", "#a020f0")]
        
        for i, (label, key, color) in enumerate(keys):
            bg = canvas.create_oval(0, 0, 0, 0, outline="#333", width=1, state="hidden")
            arc = canvas.create_arc(0, 0, 0, 0, outline=color, width=2, style=tk.ARC, start=90, extent=0, state="hidden")
            txt = canvas.create_text(0, 0, text=label, fill="white", font=("Arial", 6, "bold"), state="hidden")
            val_txt = canvas.create_text(0, 0, text="0%", fill="#888", font=("Arial", 5), state="hidden")
            
            self.stat_items[key] = {
                "label": label,
                "color": color,
                "bg_id": bg,
                "arc_id": arc,
                "txt_id": txt,
                "val_id": val_txt
            }

    def _init_thread_ui(self):
        """Crea el selector de hilos si está habilitado."""
        if not self.show_threads or not self._frame: return
        
        # Frame superior para hilos
        self.thread_frame = tk.Frame(self._frame, bg="#1a1a1a", pady=2)
        
        # Con el nuevo VisualizerPort, self._canvas es SIEMPRE un hermano
        if self._canvas and self._canvas != self._frame:
            self.thread_frame.pack(fill=tk.X, side=tk.TOP, before=self._canvas)
        else:
            self.thread_frame.pack(fill=tk.X, side=tk.TOP)
        
        # Nombre del personaje en la cabecera (reemplaza 'Hilos:')
        self.header_name_label = tk.Label(self.thread_frame, text="", bg="#1a1a1a", fg="#4EC9B0", font=("Arial", 9, "bold"))
        self.header_name_label.pack(side=tk.LEFT, padx=(5, 5))
        
        from tkinter import ttk
        self.combo_threads = ttk.Combobox(self.thread_frame, state="readonly", font=("Arial", 8), width=12) # Mas estrecho
        self.combo_threads.pack(side=tk.LEFT, padx=2)
        self.combo_threads.bind("<<ComboboxSelected>>", self._internal_thread_change)
        
        # FIX VISIBILIDAD (Windows): Forzar colores del listbox (desplegable)
        self.combo_threads.option_add('*TCombobox*Listbox.background', '#1a1a1a')
        self.combo_threads.option_add('*TCombobox*Listbox.foreground', 'white')
        
        # Boton Nuevo (Movido a la izquierda del canvas de stats)
        self.btn_new_thread = tk.Button(self.thread_frame, text="+", bg="#333", fg="white", 
                                        relief="flat", font=("Arial", 8, "bold"), command=self._internal_new_thread)
        self.btn_new_thread.pack(side=tk.LEFT, padx=5)

        # NUEVO: Canvas para stats (Ahora despues del boton +)
        if self.show_stats:
            # Mas ancho para asegurar que caben los 4 (180px)
            self.stats_canvas = tk.Canvas(self.thread_frame, width=180, height=24, bg="#1a1a1a", 
                                          highlightthickness=0, bd=0)
            self.stats_canvas.pack(side=tk.LEFT, padx=2, fill=tk.X, expand=True)
            self._init_stat_gauges() 

    def _internal_thread_change(self, event):
        if self.on_thread_change:
            self.on_thread_change(self.combo_threads.get())

    def _internal_new_thread(self):
        if self.on_new_thread:
            # Crear hilo basado en el nombre del personaje
            char_name = self.character_data.get("name", "Nuevo")
            import time
            new_id = f"{char_name}_{int(time.time())}"
            self.on_new_thread(new_id)

    def _detect_emotion(self, emoji_text):
        """Analiza el texto de emojis para determinar el aura emocional (Ponderado)."""
        if not emoji_text:
            return "neutral"
            
        # Usar listas dinámicas (posiblemente sobreescritas en set_character)
        anger_list = getattr(self, "active_anger_emojis", self.anger_emojis)
        joy_list = getattr(self, "active_joy_emojis", self.joy_emojis)
        sad_list = getattr(self, "active_sadness_emojis", self.sadness_emojis)
            
        anger_count = sum(2 for e in anger_list if e in emoji_text) # PESO DOBLE para hostilidad
        joy_count = sum(1 for e in joy_list if e in emoji_text)
        sad_count = sum(1.5 for e in sad_list if e in emoji_text) # Peso extra para tristeza
        
        # Ponderación triple
        counts = {"anger": anger_count, "joy": joy_count, "sad": sad_count}
        max_val = max(counts.values())
        
        if max_val < 1: # Umbral mínimo para evitar cambios por ruido
            return "neutral"
            
        # Determinar el ganador
        winning_emotions = [k for k, v in counts.items() if v == max_val]
        
        if len(winning_emotions) == 1:
            return winning_emotions[0]
            
        # Desempate prioritario: Joy > Sad > Anger
        if "joy" in winning_emotions: return "joy"
        if "sad" in winning_emotions: return "sad"
        return "anger"

    def set_character(self, character_data):
        """Actualiza los datos del personaje y detecta su emoción por emojis."""
        self.character_data = character_data
        
        # Guardar el nombre para posibles recargas de emergencia
        raw_name = character_data.get("name", "SISTEMA")
        if isinstance(raw_name, dict):
            self._character_name = str(raw_name.get("content", "SISTEMA"))
        else:
            self._character_name = str(raw_name)
            
        # --- CALIBRACIÓN EMOJI DINA ÁMICA (NUEVO) ---
        # Cargar overrides específicos del personaje si existen
        emoji_map = character_data.get("emoji_map", {})
        self.active_anger_emojis = self.anger_emojis.copy()
        self.active_joy_emojis = self.joy_emojis.copy()
        self.active_sadness_emojis = self.sadness_emojis.copy()
        
        if emoji_map:
            print(f"[AvatarVisualizer] Aplicando mapa de emojis personalizado para {self._character_name}")
            if "anger" in emoji_map: self.active_anger_emojis = emoji_map["anger"]
            if "joy" in emoji_map: self.active_joy_emojis = emoji_map["joy"]
            if "sadness" in emoji_map: self.active_sadness_emojis = emoji_map["sadness"]
        
        # Log para depuración de assets cargados
        video_keys = list(character_data.get("video", {}).keys())
        print(f"[AvatarVisualizer] set_character: {self._character_name}. Variantes de vídeo: {video_keys}")
        
        # 1. Detectar Emoción Inicial
        emoji_text = character_data.get("emoji", "")
        self.current_emotion = self._detect_emotion(emoji_text)
            
        if self.current_emotion != "neutral":
            print(f"[AvatarVisualizer] set_character: Emoción detected: {self.current_emotion}")

        # 2. Cargar assets
        avatar_cfg = character_data.get("avatar", {})
        self.character_data = character_data
        
        print(f"[AvatarVisualizer] set_character: {self.character_data.get('name', 'None')}")
        
        self._refresh_assets()
        
        # 1. Actualizar nombre en UI (AHORA EN CABECERA)
        if self.header_name_label:
            name_data = self.character_data.get("name", "SISTEMA")
            # Defensa contra datos corruptos (si name es un dict por error)
            if isinstance(name_data, dict):
                name = str(name_data.get("content", "SISTEMA")).upper()
            else:
                name = str(name_data).upper()
            self.header_name_label.config(text=name)
        
        # 2. Actualizar hilos si hay selector
        if hasattr(self, 'combo_threads'):
            threads = self.character_data.get("threads", [])
            # ASEGURAR QUE EL ACTUAL ESTÉ (Fix solicitado)
            active_id = self.character_data.get("active_thread")
            
            # TEST FORZADO: Asegurar que hay algo
            if not threads: 
                threads = ["Hilos Vacios", "Esperando Sincronizacion"]
            if active_id and active_id not in threads:
                threads.append(active_id)
            
            # Limpiar y repoblar para evitar residuos
            self.combo_threads['values'] = threads
            if threads:
                current = active_id if active_id in threads else threads[0]
                self.combo_threads.set(current)
                print(f"[AvatarVisualizer] Combo set to: {current} (Values: {threads})")
        
        # 3. Actualizar barra de estado (Gauges)
        if self.show_stats:
            self._update_stat_gauges()
            
        if not self.is_active:
            self._show_state("idle")

    def _update_stat_gauges(self):
        """Dibuja los indicadores circulares de estado en el stats_canvas (Cabecera)."""
        canvas = self.stats_canvas if self.stats_canvas else self._canvas
        if not canvas: return
        
        # DEBUG: Forzar valores de prueba si vienen vacíos
        stats = self.character_data.get("stats", {})
        if not stats or all(v == 0 for v in stats.values()):
            stats = {"stress": 80, "anger": 40, "joy": 90, "fear": 20}
        
        # Configuración de layout EXTREMADAMENTE compacta para la cabecera
        margin = 15 # Menos margen inicial
        count = len(self.stat_items)
        # Separación entre círculos ligeramente reducida para seguridad (30px)
        spacing = 30 
        y_pos = 12 # Centrado verticalmente en los 24px de alto del canvas
        size = 18  # Diámetro
        
        for i, (key, items) in enumerate(self.stat_items.items()):
            val = stats.get(key, 0)
            x_pos = margin + (i * spacing)
            
            # Coordenadas
            coords = (x_pos - size/2, y_pos - size/2, x_pos + size/2, y_pos + size/2)
            
            # Mostrar elementos en el canvas de la cabecera
            canvas.coords(items["bg_id"], *coords)
            canvas.itemconfig(items["bg_id"], state="normal")
            
            canvas.coords(items["arc_id"], *coords)
            extent = -(val / 100.0) * 359.9
            canvas.itemconfig(items["arc_id"], extent=extent, width=2, state="normal" if val > 0 else "hidden")
            
            canvas.coords(items["txt_id"], x_pos, y_pos - 2)
            canvas.itemconfig(items["txt_id"], state="normal")
            
            # Valor numérico (%) - Miniatura
            canvas.coords(items["val_id"], x_pos, y_pos + 6)
            canvas.itemconfig(items["val_id"], text=f"{int(val)}", state="normal") # Solo numero para ahorrar espacio

    # Duplicate set_character removed

    def start(self):
        if self.is_active: return
        self.is_active = True
        self._show_state("talking")
    
    def stop(self):
        self.is_active = False
        self._show_state("idle")

    def _apply_emotional_impact(self, emotion: str):
        """Calcula el impacto de una emoción detectada en las estadísticas del personaje."""
        if not self.character_data: return
        stats = self.character_data.get("stats", {})
        if not stats: 
            stats = {"stress": 50, "anger": 50, "joy": 50, "fear": 50}
            self.character_data["stats"] = stats

        # Matriz de Impacto Emocional (Ajustable)
        impacts = {
            "joy":    {"joy": 10, "stress": -5, "anger": -5, "fear": -5},
            "anger":  {"anger": 15, "stress": 10, "joy": -10, "fear": -2},
            "sad":    {"joy": -15, "stress": 2, "fear": 5, "anger": -2},
            "neutral": {"joy": -1, "stress": -1, "anger": -1, "fear": -1} # Decaimiento natural
        }

        impact = impacts.get(emotion, impacts["neutral"])
        
        # Aplicar Deltas y Clamping [0, 100]
        for key, delta in impact.items():
            if key in stats:
                new_val = stats[key] + delta
                stats[key] = max(0, min(100, new_val))
        
        print(f"[AvatarVisualizer] Impacto Emocional '{emotion}': Nuevos Stats -> {stats}")
        
        # 1. Actualizar Gauges UI
        self._update_stat_gauges()
        
        # 2. Notificar al sistema para persistencia si hay callback
        if self.on_stats_change:
            self.on_stats_change(stats)

    def set_emojis(self, emojis: list):
        """Muestra una lista de emojis y actualiza el aura emocional en tiempo real."""
        if not self._canvas or not self.emoji_item: return
        
        text = "".join(emojis)
        
        # Actualizar Aura en tiempo real basándose en los nuevos emojis
        new_emotion = self._detect_emotion(text)
        
        # PERSISTENCIA EMOCIONAL (NUEVO): Evita que vuelva al neutro a mitad de frase 
        # si una parte del discurso no tiene emojis, manteniendo la emoción "pegada" mientras habla.
        if new_emotion == "neutral" and self.is_active:
            new_emotion = self.current_emotion
            
        # APLICAR IMPACTO EMOCIONAL EN LOS STATS (Con cada ráfaga de emojis reales)
        if text:
            self._apply_emotional_impact(new_emotion)
        
        if new_emotion != self.current_emotion:
            self.current_emotion = new_emotion
            print(f"[AvatarVisualizer] Cambio de aura en tiempo real: {self.current_emotion}")
            
            # REFRESH DE VÍDEO REACTIVO
            self._show_state("talking" if self.is_active else "idle")
        
        if not text:
            self._canvas.itemconfig(self.emoji_item, state="hidden")
            return
            
        self._canvas.itemconfig(self.emoji_item, text=text, state="normal")
        # Auto-ocultar texto pero MANTENER el aura hasta el siguiente mensaje o cambio de estado
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
            
            display_size = int(target_size * 0.60)
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
        """Gestiona Vídeo vs Imagen con soporte para variantes emocionales modernas y fail-safes."""
        video_cfg = self.character_data.get("video", {})
        
        # 1. Determinar el sufijo de emoción para el asset
        emotion = getattr(self, "current_emotion", "neutral")
        suffix = "" if emotion == "neutral" else f"_{emotion}"
        
        # 2. Intentar obtener el asset específico del estado y emoción
        key = ("talking" if state == "talking" else "idle") + suffix
        video_path = video_cfg.get(key)
        print(f"[AvatarVisualizer] _show_state: {state} + {emotion} -> Key: {key}, Path: {video_path}")
        
        # 3. AUTO-RECARGA DE EMERGENCIA (Si el asset falta en memoria pero estamos en un personaje conocido)
        if not video_path and suffix and self._character_name:
            print(f"[AvatarVisualizer] Asset '{key}' no encontrado en memoria. Reintentando carga desde disco...")
            char_file = os.path.join("Resources", "Characters", self._character_name, "character.json")
            if os.path.exists(char_file):
                try:
                    with open(char_file, "r", encoding="utf-8") as f:
                        new_data = json.load(f)
                        self.character_data = new_data
                        video_cfg = new_data.get("video", {})
                        video_path = video_cfg.get(key)
                        if video_path:
                            print(f"[AvatarVisualizer] ¡Asset '{key}' recuperado exitosamente tras recarga de disco!")
                except: pass

        # 4. Fail-safe: si el asset específico de habla FALTA, usar el neutral o forzar idle
        if state == "talking" and not video_path:
            video_path = video_cfg.get("talking")
            if not video_path:
                print(f"[AvatarVisualizer] ERROR: No hay asset de habla para {emotion}. Permaneciendo en IDLE.")
                self._show_state("idle")
                return

        # 4. Fallback legado: buscar en diccionario 'avatar'
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
        """Posiciona y configura los elementos del canvas (AJUSTE FINO ARRIBA)."""
        if not self._canvas: return
        
        # Pequeño margen para que el borde Cyan sea visible
        top_y = 6 
        
        if photo:
            display_size = photo.width() if hasattr(photo, 'width') else 200
            px = 4
            
            # 1. Definir paleta emocional
            emotion_colors = {
                "neutral": "#4EC9B0", # Cyan estándar
                "anger": "#FF0000",   # Rojo intenso
                "joy": "#00A2FF",     # Azul Intenso (solicitado para distinguir de neutral)
                "sad": "#A200FF"      # Púrpura/Triste
            }
            current_color = emotion_colors.get(self.current_emotion, "#4EC9B0")
            
            # 2. Actualizar Marco (Siempre visible con el color del animo)
            self._canvas.coords(self.frame_item, 
                               (self.width - display_size)/2 - px, top_y - px,
                               (self.width + display_size)/2 + px, top_y + display_size + px)
            self._canvas.itemconfig(self.frame_item, outline=current_color, state="normal")
            
            # 3. Actualizar Imagen (FORZAR ANCHOR N Y COORDS ARRIBA)
            self._canvas.coords(self.image_item, self.width / 2, top_y)
            self._canvas.itemconfig(self.image_item, image=photo, state="normal", anchor="n")
            self._canvas.image = photo
            
            # 4. Actualizar Dot (Solo visible al hablar, con el color del animo)
            if state == "talking":
                self._canvas.coords(self.dot_item, 
                                   (self.width + display_size)/2 + 15, top_y + 15,
                                   (self.width + display_size)/2 + 25, top_y + 25)
                self._canvas.itemconfig(self.dot_item, fill=current_color, state="normal")
            else:
                self._canvas.itemconfig(self.dot_item, state="hidden")
            
            # REPOSICIONAR EMOJIS (Alineados a la línea inferior integrada)
            if self.emoji_item:
                emoji_y = 218
                self._canvas.coords(self.emoji_item, self.width / 2, emoji_y)
            
            # Actualizar Línea Separadora
            if hasattr(self, 'bottom_sep'):
                self._canvas.coords(self.bottom_sep, 0, 228, self.width, 228)
        else:
            self._canvas.itemconfig(self.image_item, state="hidden")
            self._canvas.itemconfig(self.frame_item, state="hidden")
            self._canvas.itemconfig(self.dot_item, state="hidden")

    # --- VIDEO ENGINE ---

    def _start_video(self, path):
        if self._current_video_path == path and self._video_running: return
        if self._reloading: return # Ya hay un cambio en curso
        
        self._reloading = True
        self._stop_video()
        
        # Pequeña pausa (10ms) para que FFmpeg/libavcodec libere recursos hilos internos
        self.parent.after(10, lambda: self._do_start_video(path))

    def _do_start_video(self, path):
        """Abre físicamente el VideoCapture tras la pausa de seguridad."""
        if not self._reloading: return # Cancelado mientras esperábamos
        
        self._cap = cv2.VideoCapture(path)
        if self._cap and self._cap.isOpened():
            self._current_video_path = path
            self._video_running = True
            self._reloading = False
            
            # Detectar FPS reales y aplicar un factor de suavizado para evitar aceleración (Cámara Lenta AI)
            fps = self._cap.get(cv2.CAP_PROP_FPS)
            if not fps or fps <= 0 or fps > 120:
                fps = 25
            
            # FACTOR DE SUAVIZADO: Los vídeos de IA a menudo se ven mejor a menos velocidad
            # Forzamos un delay un 50% superior al detectado para que los movimientos sean fluidos y no nerviosos
            base_delay = int(1000 / fps)
            self._video_delay = int(base_delay * 1.5) 
            
            # Garantizar márgenes realistas (Min 40ms = 25fps, Max 100ms = 10fps)
            self._video_delay = max(40, min(100, self._video_delay))
            
            print(f"[AvatarVisualizer] Iniciando vídeo: {os.path.basename(path)} (Detectado: {fps} FPS, Delay Suavizado: {self._video_delay}ms)")
            self._update_video_frame()
        else:
            print(f"[AvatarVisualizer] ERROR: No se pudo abrir el vídeo: {path}")
            self._reloading = False
            self._show_state("idle")

    def _stop_video(self):
        self._video_running = False
        if self._after_id: self.parent.after_cancel(self._after_id); self._after_id = None
        
        # NULIFICACIÓN ATÓMICA: Evita que el loop acceda mientras liberamos
        cap_to_release = self._cap
        self._cap = None 
        
        if cap_to_release:
            cap_to_release.release()
            
        self._current_video_path = None

    def _update_video_frame(self):
        if not self._video_running or not self._cap or not self._canvas or self._reloading: return

        # Guard adicional por si self._cap se nulificó entre líneas
        cap = self._cap
        if not cap: return
        
        ret, frame = cap.read()
        if not ret:
            self._cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ret, frame = self._cap.read()
            if not ret: return

        # 1. CROP & CONVERT
        # El video suele venir en BGR de OpenCV, pasamos a RGB para PIL
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, _ = frame.shape
        
        # Ajuste inteligente: si es vertical, recortamos a cuadrado, si no, centramos
        if h > w: sf = frame[0:w, 0:w]
        else: l = (w - h) // 2; sf = frame[0:h, l:l+h]

        # 2. REDIMENSIONADO PROFESIONAL
        # Usamos el tamaño de visualización calculado en el diseño compacto (aprox 60% del ancho)
        ts = self.width if self.width > 20 else 400
        ds = int(ts * 0.60)
        sf = cv2.resize(sf, (ds, ds), interpolation=cv2.INTER_AREA)

        # 3. RENDERIZACIÓN A CANVAS
        img = Image.fromarray(sf)
        photo = ImageTk.PhotoImage(image=img)
        
        # 4. BUCLE DE REFRESCO SINCRO CON FPS REALES (COMPENSADO)
        import time
        start_time = time.time()
        
        self._update_frame_elements(photo, "talking" if "talking" in self._current_video_path else "idle")
        
        # Calcular cuánto tiempo tomó procesar y restar del delay
        elapsed = int((time.time() - start_time) * 1000)
        delay = max(1, getattr(self, '_video_delay', 33) - elapsed)
        
        self._after_id = self.parent.after(delay, self._update_video_frame)

    def _on_resize(self, event):
        if event.width > 20 and (abs(event.width - self.width) > 10):
            self.width = event.width
            # Mantener una altura proporcional o fija según configuración
            # Si self.height era 350, intentamos mantenerlo o escalarlo ligeramente
            self.height = event.height if event.height > 20 else self.height
            
            # Reposicionar items en el canvas (PERFECCIÓN PIXELAR 230px)
            if self.image_item: 
                self._canvas.coords(self.image_item, self.width / 2, 6)
                self._canvas.itemconfig(self.image_item, anchor="n")
                
            if self.emoji_item: 
                self._canvas.coords(self.emoji_item, self.width / 2, self.height - 8)
                self._canvas.itemconfig(self.emoji_item, font=("Segoe UI Emoji", 14), anchor="s")

            if hasattr(self, 'bottom_sep'):
                self._canvas.coords(self.bottom_sep, 0, self.height - 1, self.width, self.height - 1)
            
            # Recuadro de borde (Cyan) - Altura perfecta (230px)
            if self.frame_item:
                self._canvas.coords(self.frame_item, 2, 2, self.width - 2, self.height - 2)
                self._canvas.itemconfig(self.frame_item, state="normal")
            
            # RE-POSICIONAR GAUGES (Cabecera no necesita coords fijas por resize de canvas grande)
            if self.show_stats:
                self._update_stat_gauges()
            
            # RE-POSICIONAR IMAGEN/VIDEO
            self._refresh_assets()
            self._show_state("talking" if self.is_active else "idle")

    def destroy(self):
        self._stop_video()
        self.idle_image = self.talking_image = self.current_photo = None
        super().destroy()
