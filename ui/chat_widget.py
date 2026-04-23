import tkinter as tk
import os
import random
import threading
import winsound
import asyncio
from tkinter import ttk, scrolledtext, filedialog, messagebox
from core.ports.chat_port import ChatPort
from ui.settings_view import SettingsView
from ui.api_keys_view import APIKeysView
from core.services.stt_service import STTService
from core.services.vision_service import VisionService
from core.services.visualizer_service import VisualizerService
from ui.background_frame import BackgroundFrame
from modules.widgets import ImageButton

class ChatWidget(tk.Frame):
    """
    Widget de Chat avanzado con controles de IA, Voz (TTS) y Reconocimiento (STT).
    """
    def __init__(self, parent, chat_engine, config_service=None, style_service=None, character_service=None, on_collapse_cmd=None):
        super().__init__(parent)
        self.chat_engine = chat_engine
        self.config_service = config_service
        self.style = style_service
        self.char_service = character_service # Guardar referencia (NUEVO)
        self.on_collapse_cmd = on_collapse_cmd
        self.pending_avatar = None # Para guardar avatar del hub (NUEVO)
        self.pending_video = None # Para guardar video del hub (NUEVO)
        super().__init__(parent, bg=self.style.get_color("bg_main"))
        self.chat_engine = chat_engine
        self.config = config_service
        self.vision_service = VisionService()
        self.current_images = []
        self.visualizer = None
        self.toolbar_visible = False
        self.hub_visible = False # Estado del panel de biblioteca
        self.is_sending = False # Estado de envío actual
        
        # Vincular STT Service del engine con la UI
        self.stt_service = self.chat_engine.stt_service
        self.chat_engine.on_stt_finished_cb = self._on_stt_finished
        self.stt_service.add_voice_command_callback(self._on_voice_command)
        
        # Suscribir a mensajes de sistema/locales (sin voz)
        if hasattr(self.chat_engine, "on_system_msg_cb"):
            self.chat_engine.on_system_msg_cb = self._on_system_msg_notified
        
        # Suscribir a cambios de personaje/identidad
        if hasattr(self.chat_engine, "on_chat_injected_cb"):
            self.chat_engine.on_chat_injected_cb = self._on_chat_injected
        if hasattr(self.chat_engine, "on_character_changed_cb"):
            self.chat_engine.on_character_changed_cb = self._on_character_changed
        
        # Contenedor principal para las vistas (Soporte para Imagen de Fondo)
        self.container = BackgroundFrame(self, self.style, "chat")
        self.container.pack(fill=tk.BOTH, expand=True)

        self._setup_visualizer()
        self.init_ui()
        self._load_initial_state()
        self._update_ui_texts()
        
        # Suscribirse a cambios de estilo en tiempo de ejecución
        if hasattr(self.style, "subscribe"):
            self.style.subscribe(self.on_style_changed)

    def on_style_changed(self):
        """Notificación de que el tema global ha cambiado."""
        print("[ChatWidget] Actualizando interfaz por cambio de tema...")
        self.apply_styles()

    def apply_styles(self):
        """Re-aplica todos los colores y fondos del tema actual."""
        ghost_bg = self.style.get_color("bg_main")
        accent = self.style.get_color("accent")
        text_main = self.style.get_color("text_main")
        text_dim = self.style.get_color("text_dim")
        
        # 1. Contenedor principal
        self.config(bg=ghost_bg)
        
        # 2. Frames que no son BackgroundFrame (estos se actualizan solos al estar suscritos)
        # Nota: los BackgroundFrame (top_bar, container, toolbar, hub_panel) 
        # se actualizan solos porque también se suscriben al StyleService.
        
        # 3. Etiquetas y Botones Estándar (Los que usan ghost_bg)
        for widget in self.winfo_children():
            self._recursive_style_update(widget, ghost_bg, text_main, accent)

    def _recursive_style_update(self, widget, bg, fg, accent):
        try:
            if isinstance(widget, (tk.Label, tk.Frame, tk.Canvas)) and not hasattr(widget, 'update_style'):
                # No tocar BackgroundFrames (tienen su propio update_style)
                widget.config(bg=bg)
                if isinstance(widget, tk.Label):
                    # Mantener acentos si ya los tenían (heurística)
                    current_fg = widget.cget("fg")
                    if current_fg.lower() in ["#ffffff", "#888888", "white", "gray"]:
                         widget.config(fg=fg)
            elif isinstance(widget, tk.Button):
                widget.config(bg="#333", fg="white") # Estilo botón oscuro estandar
        except:
            pass
            
        for child in widget.winfo_children():
            self._recursive_style_update(child, bg, fg, accent)
        
    def _setup_visualizer(self):
        """Configura el visualizador si está habilitado mediante carga dinámica"""
        if self.config.get("visualizer_enabled", False):
            v_service = VisualizerService(self.config)
            v_type = self.config.get("visualizer_type", "avatar") # Avatar por defecto
            v_height = 260 if v_type == "avatar" else 60
            # Aumentamos el ancho para que llene el hueco
            self.visualizer = v_service.get_instance(v_type, self, width=300, height=v_height)
            
            if self.visualizer and self.chat_engine.voice_service:
                self.chat_engine.voice_service.on_audio_start = self.visualizer.on_audio_start
                self.chat_engine.voice_service.on_audio_end = self.visualizer.on_audio_end
                
                self.visualizer.on_thread_change = self._on_memory_change_from_viz
                self.visualizer.on_new_thread = self._on_new_thread_from_viz
                self.visualizer.on_stats_change = self._on_stats_change_from_viz

    def _on_stats_change_from_viz(self, stats):
        """Notificación de cambio en las estadísticas emocionales desde el visualizador."""
        if self.chat_engine and self.chat_engine.memory:
            # Actualizar en la memoria de la sesión (Thread activo)
            # Esto asegura que los cambios persistan en el hilo actual pero no afecten
            # a la definición original del personaje en el JSON base.
            self.chat_engine.memory.update_profile({"stats": stats})

    def _on_memory_change_from_viz(self, thread_id):
        """Cambio de hilo solicitado desde el visualizador."""
        self.combo_memory.set(thread_id)
        self._on_memory_change(None)

    def _on_new_thread_from_viz(self, thread_id):
        """Creación de nuevo hilo solicitada desde el visualizador (sin wizard)."""
        current_data = self.chat_engine.memory.data.copy()
        
        # 1. Crear el hilo
        self.chat_engine.memory.create_new_thread(thread_id)
        
        # 2. Re-aplicar el perfil actual (para mantener la identidad)
        self.chat_engine.memory.update_profile(
            name=current_data.get("name"),
            personality=current_data.get("personality"),
            history=current_data.get("character_history"),
            voice_id=current_data.get("voice_id"),
            voice_provider=current_data.get("voice_provider"),
            avatar=current_data.get("avatar"),
            video=current_data.get("video")
        )
        
        # 3. Registrar este nuevo hilo en el JSON del personaje si existe
        char_id = current_data.get("id")
        if char_id:
            char_data = self.char_service.get_character(char_id)
            if char_data:
                threads = char_data.get("threads", [])
                if thread_id not in threads:
                    threads.append(thread_id)
                    char_data["threads"] = threads
                    char_data["active_thread"] = thread_id
                    self.char_service.save_character(char_data)
                    
                    # NUEVO: Inyectar también en la memoria activa actual para evitar latencia
                    self.chat_engine.memory.update_profile(
                        threads=threads,
                        char_id=char_id
                    )
        
        # 4. Cambiar al nuevo hilo en la UI
        self._on_memory_change_from_viz(thread_id)

    def t(self, key: str) -> str:
        return self.chat_engine.locale_service.t(key)

    def _update_ui_texts(self):
        self._lbl_memory = getattr(self, '_lbl_memory', None)
        self._lbl_profile_name = getattr(self, '_lbl_profile_name', None)
        self._lbl_profile_pers = getattr(self, '_lbl_profile_pers', None)
        self._lbl_profile_voice = getattr(self, '_lbl_profile_voice', None)
        self._lbl_llm_provider = getattr(self, '_lbl_llm_provider', None)
        self._lbl_llm_model = getattr(self, '_lbl_llm_model', None)
        self._lbl_voice = getattr(self, '_lbl_voice', None)
        self._lbl_voice_mode = getattr(self, '_lbl_voice_mode', None)
        self._lbl_stt = getattr(self, '_lbl_stt', None)
        self._lbl_stt_mode = getattr(self, '_lbl_stt_mode', None)
        # self._lbl_vision is no longer used

        self._btn_add_audio = getattr(self, '_btn_add_audio', None)
        self._btn_send = getattr(self, '_btn_send', None)
        self._btn_stop = getattr(self, '_btn_stop', None)
        self._lbl_new_char_title = getattr(self, '_lbl_new_char_title', None)
        self._lbl_new_name = getattr(self, '_lbl_new_name', None)
        self._lbl_new_pers = getattr(self, '_lbl_new_pers', None)
        self._lbl_new_hist = getattr(self, '_lbl_new_hist', None)
        self._lbl_new_motor = getattr(self, '_lbl_new_motor', None)
        self._lbl_new_voice = getattr(self, '_lbl_new_voice', None)
        self._btn_create_thread = getattr(self, '_btn_create_thread', None)
        self._btn_cancel = getattr(self, '_btn_cancel', None)
        
        texts = {
            self._lbl_memory: self.t("memory.title"),
            self._lbl_profile_name: self.t("memory.name"),
            self._lbl_profile_pers: self.t("memory.personality"),
            self._lbl_profile_voice: self.t("memory.voice"),
            self._lbl_llm_provider: self.t("memory.motor"),
            self._lbl_llm_model: self.t("settings.model"),
            self._lbl_voice: self.t("settings.tts_output"),
            self._lbl_voice_mode: self.t("settings.mode"),
            self._lbl_stt: self.t("settings.stt_input"),
            self._lbl_stt_mode: self.t("settings.mode"),
            # self._lbl_vision: self.t("chat.vision"), (Desactivado para ahorrar espacio)
            self._btn_add_audio: self.t("chat.audio"),
            # self._btn_send and self._btn_stop are hardcoded in init_ui for neon style consistency
            self._lbl_new_char_title: self.t("settings.new_character"),
            self._lbl_new_name: self.t("settings.character_name"),
            self._lbl_new_pers: self.t("settings.attitude"),
            self._lbl_new_hist: self.t("settings.background"),
            self._lbl_new_motor: self.t("settings.voice_provider"),
            self._lbl_new_voice: self.t("settings.voice"),
            self._btn_create_thread: self.t("settings.create_thread"),
            self._btn_cancel: self.t("settings.cancel"),
        }
        for widget, text in texts.items():
            if widget and text:
                widget.config(text=text)
        
        # Etiquetas especiales solo icono
        if getattr(self, "_lbl_stt_mode", None): self._lbl_stt_mode.config(text="🤖")

    def init_ui(self):
        # 1. VISTA DE CHAT - Estructura "Glass" sin capas opacas
        ghost_bg = self.style.get_color("bg_main") # Un color oscuro que simula cristal
        
        # Lista para gestionar la visibilidad de los componentes del chat
        self.chat_components = []
        
        # --- BARRA DE HERRAMIENTAS ---
        header_bg_key = "header" if self.style.get_background("header") else ("chat" if self.style.get_background("chat") else "center")
        has_bg = self.style.get_background(header_bg_key) is not None
        
        if has_bg:
            self.top_bar = BackgroundFrame(self.container, self.style, header_bg_key)
            self.top_bar.pack(fill=tk.X, padx=20, pady=(5, 0))
        else:
            self.top_bar = tk.Frame(self.container, bg=ghost_bg, pady=5)
            self.top_bar.pack(fill=tk.X, padx=20, pady=(5, 0))
            
        self.chat_components.append(self.top_bar)

        # --- PANEL DE BIBLIOTECA (Hub colapsable debajo del TopBar) ---
        if has_bg:
            self.hub_panel = BackgroundFrame(self.container, self.style, header_bg_key)
        else:
            self.hub_panel = tk.Frame(self.container, bg=ghost_bg, pady=5)
        self.chat_components.append(self.hub_panel)
        
        # Estructura interna del Hub (Scrollable)
        hub_header = tk.Frame(self.hub_panel, bg=ghost_bg)
        hub_header.pack(fill=tk.X, padx=10, pady=(5, 0))
        
        tk.Label(hub_header, text="BIBLIOTECA DE IDENTIDADES", bg=ghost_bg, fg=self.style.get_color("accent"), font=("Arial", 8, "bold")).pack(side=tk.LEFT)
        tk.Button(hub_header, text="🔄 Refrescar", bg="#333", fg="white", relief="flat", font=("Arial", 7), command=self._populate_hub_panel).pack(side=tk.RIGHT)

        hub_inner = tk.Frame(self.hub_panel, bg=ghost_bg)
        hub_inner.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        self.hub_canvas = tk.Canvas(hub_inner, bg=ghost_bg, highlightthickness=0, height=200)
        self.hub_scroll = ttk.Scrollbar(hub_inner, orient="vertical", command=self.hub_canvas.yview)
        self.hub_container = tk.Frame(self.hub_canvas, bg=ghost_bg)
        
        self.hub_window_id = self.hub_canvas.create_window((0, 0), window=self.hub_container, anchor="nw")
        self.hub_canvas.configure(yscrollcommand=self.hub_scroll.set)
        
        # Ajustar ancho automáticamente cuando el canvas cambie de tamaño
        self.hub_canvas.bind("<Configure>", self._on_hub_canvas_configure)
        
        self.hub_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.hub_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        self.hub_container.bind("<Configure>", lambda e: self.hub_canvas.configure(scrollregion=self.hub_canvas.bbox("all")))

        # Botones Fantasma (Outline)
        btn_style = {"bg": ghost_bg, "fg": self.style.get_color("text_dim"), "relief": "flat", "bd": 1, "activebackground": "#222"}

        # Toolbar colapsable (debajo de top_bar)
        if has_bg:
            self.toolbar = BackgroundFrame(self.container, self.style, header_bg_key)
        else:
            self.toolbar = tk.Frame(self.container, bg=ghost_bg, pady=5)
        # self.toolbar no se empaqueta inicialmente (está colapsado)
        self.chat_components.append(self.toolbar)

        has_btn_bg = self.style.get_background("button") is not None

        # 1. Botones de Navegación (TRIÁNGULOS)
        if has_btn_bg:
            self.btn_toggle_toolbar = ImageButton(self.top_bar, text="▼", font=("Arial", 9, "bold"),
                                                  style=self.style, callback=self._toggle_toolbar, pady=2, padx=4)
            self.btn_toggle_toolbar.set_active(True)
        else:
            self.btn_toggle_toolbar = tk.Button(self.top_bar, text="▼", font=("Arial", 9), cursor="hand2", 
                                                command=self._toggle_toolbar, **btn_style)
        self.btn_toggle_toolbar.config(fg=self.style.get_color("accent"))
        self.btn_toggle_toolbar.pack(side=tk.LEFT, padx=(0, 2))

        if self.on_collapse_cmd:
            if has_btn_bg:
                self.btn_collapse = ImageButton(self.top_bar, text="▶", font=("Arial", 9, "bold"),
                                                style=self.style, callback=self.on_collapse_cmd, pady=2, padx=4)
                self.btn_collapse.set_active(True)
            else:
                self.btn_collapse = tk.Button(self.top_bar, text="▶",
                                             cursor="hand2", command=self.on_collapse_cmd,
                                             font=("Arial", 9, "bold"), **btn_style)
            self.btn_collapse.config(fg=self.style.get_color("accent"))
            self.btn_collapse.pack(side=tk.LEFT, padx=(0, 2))

        # 2. BOTÓN BIBLIOTECA (EL TERCERO)
        if has_btn_bg:
            self.btn_top_hub = ImageButton(self.top_bar, text="📁 BIBLIOTECA", font=("Arial", 7, "bold"),
                                         style=self.style, callback=self._toggle_hub_panel, pady=2, padx=10)
        else:
            self.btn_top_hub = tk.Button(self.top_bar, text="📁 BIBLIOTECA", font=("Arial", 7, "bold"), 
                                        command=self._toggle_hub_panel, **btn_style)
            self.btn_top_hub.config(fg=self.style.get_color("accent"))
        self.btn_top_hub.pack(side=tk.LEFT, padx=10)

        # 3. BOTONES DE CONFIGURACIÓN (LUEGO DE BIBLIOTECA)
        if has_btn_bg:
            self.btn_settings = ImageButton(self.top_bar, text="⚙️", font=("Arial", 11),
                                            style=self.style, callback=self.show_settings, pady=2, padx=4)
            self.btn_settings.set_active(True)
        else:
            self.btn_settings = tk.Button(self.top_bar, text="⚙️",
                                          cursor="hand2", command=self.show_settings, **btn_style)
            self.btn_settings.config(fg=self.style.get_color("accent"), font=("Arial", 11))
        self.btn_settings.pack(side=tk.LEFT, padx=2)

        if has_btn_bg:
            self.btn_api_keys = ImageButton(self.top_bar, text="🔑", font=("Arial", 11),
                                            style=self.style, callback=self.show_api_keys, pady=2, padx=4)
            self.btn_api_keys.set_active(True)
        else:
            self.btn_api_keys = tk.Button(self.top_bar, text="🔑",
                                          cursor="hand2", command=self.show_api_keys, **btn_style)
            self.btn_api_keys.config(fg="#ffd700", font=("Arial", 11))
        self.btn_api_keys.pack(side=tk.LEFT, padx=2)

        # Visualizer (si está habilitado) - POSICIÓN: ARRIBA
        if self.visualizer:
            self.visualizer.create(self.container)
            if self.visualizer._frame:
                # Usamos padx=20 para alinear con el top_bar
                self.visualizer._frame.pack(fill=tk.X, padx=20)
                self.chat_components.append(self.visualizer._frame)
                
                # Cargar estado inicial ahora que el visualizador está creado (NUEVO)
                if self.chat_engine.memory.data:
                    self.visualizer.set_character(self.chat_engine.memory.data)

        # LÍNEA 0: Gestión de Memoria e Hilos (NUEVA)
        self.memory_bar = tk.Frame(self.toolbar, bg=self.style.get_color("bg_main"), pady=2)
        self.memory_bar.pack(fill=tk.X)

        self._lbl_memory = tk.Label(self.memory_bar, text="Memoria:", bg=self.style.get_color("bg_main"), fg=self.style.get_color("accent"), font=("Arial", 8, "bold"))
        self._lbl_memory.pack(side=tk.LEFT)
        self.combo_memory = ttk.Combobox(self.memory_bar, state="readonly", width=25)
        self.combo_memory.pack(side=tk.LEFT, padx=5)
        self.combo_memory.bind("<<ComboboxSelected>>", self._on_memory_change)
        
        self.btn_refresh_mem = tk.Button(self.memory_bar, text="🔄", bg="#333", fg="white", 
                                         relief="flat", font=("Arial", 7), command=self._refresh_memories)
        self.btn_refresh_mem.pack(side=tk.LEFT, padx=2)

        # LÍNEA DE PERFIL (Nombre y Personalidad rápida)
        self.profile_bar = tk.Frame(self.toolbar, bg=self.style.get_color("bg_main"), pady=2)
        self.profile_bar.pack(fill=tk.X)
        
        self._lbl_profile_name = tk.Label(self.profile_bar, text="Nombre:", bg=self.style.get_color("bg_main"), fg=self.style.get_color("text_dim"), font=("Arial", 8))
        self._lbl_profile_name.pack(side=tk.LEFT)
        self.ent_char_name = tk.Entry(self.profile_bar, bg=self.style.get_color("bg_input"), fg=self.style.get_color("text_main"), font=("Arial", 8), width=10, relief="flat")
        self.ent_char_name.pack(side=tk.LEFT, padx=5)
        
        self._lbl_profile_pers = tk.Label(self.profile_bar, text="Personalidad:", bg=self.style.get_color("bg_main"), fg=self.style.get_color("text_dim"), font=("Arial", 8))
        self._lbl_profile_pers.pack(side=tk.LEFT, padx=(5,0))
        self.ent_char_pers = tk.Entry(self.profile_bar, bg=self.style.get_color("bg_input"), fg=self.style.get_color("text_main"), font=("Arial", 8), width=20, relief="flat")
        self.ent_char_pers.pack(side=tk.LEFT, padx=5)

        self._lbl_profile_voice = tk.Label(self.profile_bar, text="Voz:", bg=self.style.get_color("bg_main"), fg=self.style.get_color("text_dim"), font=("Arial", 8))
        self._lbl_profile_voice.pack(side=tk.LEFT, padx=(5,0))
        self.combo_char_motor = ttk.Combobox(self.profile_bar, state="readonly", font=("Arial", 8), width=10)
        self.combo_char_motor.pack(side=tk.LEFT, padx=2)
        self.combo_char_motor.bind("<<ComboboxSelected>>", self._on_sidebar_motor_change)

        self.combo_char_voice = ttk.Combobox(self.profile_bar, state="readonly", font=("Arial", 8), width=15)
        self.combo_char_voice.pack(side=tk.LEFT, padx=2)

        self.btn_save_profile = tk.Button(self.profile_bar, text="💾", bg=self.style.get_color("accent"), fg=self.style.get_color("btn_fg"), 
                                           relief="flat", font=("Arial", 7), command=self._save_profile)
        self.btn_save_profile.pack(side=tk.LEFT, padx=2)

        # LÍNEA 2: Controles de IA (Motor y Modelo)
        self.llm_bar = tk.Frame(self.toolbar, bg=self.style.get_color("bg_main"), pady=2)
        self.llm_bar.pack(fill=tk.X)

        self._lbl_llm_provider = tk.Label(self.llm_bar, text="Motor AI:", bg=self.style.get_color("bg_main"), fg=self.style.get_color("text_dim"), font=("Arial", 8))
        self._lbl_llm_provider.pack(side=tk.LEFT)
        allowed_backends = self.chat_engine.get_providers_list()
        self.combo_provider = ttk.Combobox(self.llm_bar, values=allowed_backends, state="readonly", width=12)
        self.combo_provider.pack(side=tk.LEFT, padx=5)
        self.combo_provider.bind("<<ComboboxSelected>>", self._on_provider_change)

        self._lbl_llm_model = tk.Label(self.llm_bar, text="Modelo:", bg=self.style.get_color("bg_main"), fg=self.style.get_color("text_dim"), font=("Arial", 8))
        self._lbl_llm_model.pack(side=tk.LEFT, padx=(5, 0))
        self.combo_model = ttk.Combobox(self.llm_bar, state="readonly", width=15)
        self.combo_model.pack(side=tk.LEFT, padx=5)
        self.combo_model.bind("<<ComboboxSelected>>", self._on_model_change)

        # LÍNEA 2.5: Controles de Inferencia (Max Tokens + Temperature)
        self.inference_bar = tk.Frame(self.toolbar, bg=self.style.get_color("bg_main"), pady=2)
        self.inference_bar.pack(fill=tk.X)

        tk.Label(self.inference_bar, text="Max Tokens:", bg=self.style.get_color("bg_main"), fg=self.style.get_color("text_dim"), font=("Arial", 8)).pack(side=tk.LEFT)
        self.spin_max_tokens = tk.Spinbox(self.inference_bar, from_=64, to=4096, width=6, bg=self.style.get_color("bg_input"), fg=self.style.get_color("text_main"))
        self.spin_max_tokens.pack(side=tk.LEFT, padx=5)
        self.spin_max_tokens.delete(0, tk.END)
        self.spin_max_tokens.insert(0, self.config.get("max_tokens", 1024))
        self.spin_max_tokens.bind("<<Spinbox>>", self._on_inference_change)

        tk.Label(self.inference_bar, text="Temp:", bg=self.style.get_color("bg_main"), fg=self.style.get_color("text_dim"), font=("Arial", 8)).pack(side=tk.LEFT, padx=(10, 0))
        self.slider_temp = tk.Scale(self.inference_bar, from_=0.1, to=2.0, resolution=0.1, orient=tk.HORIZONTAL, 
                                    bg=self.style.get_color("bg_main"), fg=self.style.get_color("text_main"), length=100, showvalue=1)
        self.slider_temp.pack(side=tk.LEFT, padx=5)
        self.slider_temp.set(self.config.get("temperature", 0.7))
        self.slider_temp.bind("<ButtonRelease-1>", self._on_inference_change)

        # LÍNEA 3: Controles de Salida de Voz (TTS)
        self.voice_bar = tk.Frame(self.toolbar, bg=self.style.get_color("bg_main"), pady=2)
        self.voice_bar.pack(fill=tk.X)

        self._lbl_voice = tk.Label(self.voice_bar, text="TTS (Salida):", bg=self.style.get_color("bg_main"), fg=self.style.get_color("text_dim"), font=("Arial", 8))
        self._lbl_voice.pack(side=tk.LEFT)
        voice_providers = ["None", "Edge TTS", "Local TTS"]
        self.combo_voice = ttk.Combobox(self.voice_bar, values=voice_providers, state="readonly", width=10)
        self.combo_voice.pack(side=tk.LEFT, padx=5)
        self.combo_voice.bind("<<ComboboxSelected>>", self._on_voice_change)

        self._lbl_voice_mode = tk.Label(self.voice_bar, text="Modo:", bg=self.style.get_color("bg_main"), fg=self.style.get_color("text_dim"), font=("Arial", 8))
        self._lbl_voice_mode.pack(side=tk.LEFT, padx=(5, 0))
        voice_modes = ["autoplay", "path"]
        self.combo_voice_mode = ttk.Combobox(self.voice_bar, values=voice_modes, state="readonly", width=10)
        self.combo_voice_mode.pack(side=tk.LEFT, padx=5)
        self.combo_voice_mode.bind("<<ComboboxSelected>>", self._on_voice_mode_change)

        self.combo_voice_id = ttk.Combobox(self.voice_bar, state="readonly", width=25)
        self.combo_voice_id.pack(side=tk.LEFT, padx=5)
        self.combo_voice_id.bind("<<ComboboxSelected>>", self._on_voice_id_change)

        # LÍNEA 4: Controles de Entrada de Voz (STT)
        self.stt_bar = tk.Frame(self.toolbar, bg=self.style.get_color("bg_main"), pady=2)
        self.stt_bar.pack(fill=tk.X)

        self._lbl_stt = tk.Label(self.stt_bar, text="STT (Entrada):", bg=self.style.get_color("bg_main"), fg=self.style.get_color("text_dim"), font=("Arial", 8))
        self._lbl_stt.pack(side=tk.LEFT)
        stt_providers = ["None", "Standard (Google)"]
        self.combo_stt_provider = ttk.Combobox(self.stt_bar, values=stt_providers, state="readonly", width=20)
        self.combo_stt_provider.pack(side=tk.LEFT, padx=5)
        self.combo_stt_provider.bind("<<ComboboxSelected>>", self._on_stt_provider_change)

        # Modo STT (Movido al panel inferior)

        self._lbl_test_mode = tk.Label(self.stt_bar, text="Test:", bg=self.style.get_color("bg_main"), fg=self.style.get_color("text_dim"), font=("Arial", 8))
        self._lbl_test_mode.pack(side=tk.LEFT, padx=(10, 0))
        self.var_test_mode = tk.BooleanVar(value=False)
        self.chk_test_mode = tk.Checkbutton(self.stt_bar, variable=self.var_test_mode, bg=self.style.get_color("bg_main"), 
                                             selectcolor=self.style.get_color("bg_input"), activebackground=self.style.get_color("bg_main"),
                                             fg=self.style.get_color("text_dim"), font=("Arial", 8), highlightthickness=0)
        self.chk_test_mode.pack(side=tk.LEFT, padx=2)

        # ELIMINADO: El separador ahora está integrado dentro del visualizador como una sola línea interna
        # para ahorrar el máximo espacio posible.

        # --- ÁREA DE ENTRADA (FOOTER - SIEMPRE ABAJO) ---
        has_footer_bg = self.style.get_background("button") is not None
        if has_footer_bg:
            self.input_area = BackgroundFrame(self.container, self.style, "button")
        else:
            self.input_area = tk.Frame(self.container, bg=self.style.get_color("bg_main"))
            
        self.input_area.pack(side=tk.BOTTOM, padx=20, pady=15, fill=tk.X)
        self.chat_components.append(self.input_area)

        # Línea de archivos seleccionados (También abajo)
        self.lbl_files = tk.Label(self.container, text="", bg=self.style.get_color("bg_main"), fg="#4EC9B0", font=("Arial", 8, "italic"))
        self.lbl_files.pack(fill=tk.X, padx=10, side=tk.BOTTOM)
        self.chat_components.append(self.lbl_files)

        # --- CONTENEDOR CENTRAL (Para Chat o Wizard) ---
        self.middle_container = tk.Frame(self.container, bg=self.style.get_color("bg_main"))
        self.middle_container.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 5)) # Sin margen superior para pegarse al separador
        self.chat_components.append(self.middle_container)

        # --- WIZAD DE NUEVO HILO (Hijo de middle_container) ---
        self.new_thread_frame = tk.Frame(self.middle_container, bg=self.style.get_color("bg_main"), padx=20, pady=10)
        
        self._lbl_new_char_title = tk.Label(self.new_thread_frame, text="✨ NUEVO MODELO DE PERSONAJE", bg=self.style.get_color("bg_main"), fg=self.style.get_color("accent"), font=("Arial", 10, "bold"))
        self._lbl_new_char_title.pack(pady=(0, 5))
        
        # Botón para abrir librería (NUEVO)
        self._btn_open_hub = tk.Button(self.new_thread_frame, text="📁 Explorar Biblioteca ASIMOD", bg="#333", fg="white", 
                                      relief="flat", font=("Arial", 8, "bold"), command=self._toggle_hub_panel)
        self._btn_open_hub.pack(fill=tk.X, pady=(0, 10))
        
        # Campo Nombre
        self._lbl_new_name = tk.Label(self.new_thread_frame, text="Nombre del Personaje:", bg=self.style.get_color("bg_main"), fg=self.style.get_color("text_dim"), font=("Arial", 8))
        self._lbl_new_name.pack(anchor="w")
        self.ent_new_name = tk.Entry(self.new_thread_frame, bg=self.style.get_color("bg_input"), fg=self.style.get_color("text_main"), relief="flat", font=("Arial", 10))
        self.ent_new_name.pack(fill=tk.X, pady=(2, 10))

        # Campo Actitud/Personalidad
        self._lbl_new_pers = tk.Label(self.new_thread_frame, text="Actitud / Personalidad:", bg=self.style.get_color("bg_main"), fg=self.style.get_color("text_dim"), font=("Arial", 8))
        self._lbl_new_pers.pack(anchor="w")
        self.ent_new_pers = tk.Entry(self.new_thread_frame, bg=self.style.get_color("bg_input"), fg=self.style.get_color("text_main"), relief="flat", font=("Arial", 10))
        self.ent_new_pers.pack(fill=tk.X, pady=(2, 10))

        # Campo Historia (Multi-línea)
        self._lbl_new_hist = tk.Label(self.new_thread_frame, text="Historia / Trasfondo:", bg=self.style.get_color("bg_main"), fg=self.style.get_color("text_dim"), font=("Arial", 8))
        self._lbl_new_hist.pack(anchor="w")
        self.txt_new_hist = scrolledtext.ScrolledText(self.new_thread_frame, bg=self.style.get_color("bg_input"), fg=self.style.get_color("text_main"), 
                                                      relief="flat", font=("Arial", 10), height=5)
        self.txt_new_hist.pack(fill=tk.X, pady=(2, 10))

        # Línea de Motor y Voz (NUEVO)
        motor_voice_frame = tk.Frame(self.new_thread_frame, bg=self.style.get_color("bg_main"))
        motor_voice_frame.pack(fill=tk.X, pady=(2, 10))

        mv_left = tk.Frame(motor_voice_frame, bg=self.style.get_color("bg_main"))
        mv_left.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self._lbl_new_motor = tk.Label(mv_left, text="Motor de Voz:", bg=self.style.get_color("bg_main"), fg=self.style.get_color("text_dim"), font=("Arial", 8))
        self._lbl_new_motor.pack(anchor="w")
        
        mv_right = tk.Frame(motor_voice_frame, bg=self.style.get_color("bg_main"))
        mv_right.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self._lbl_new_voice = tk.Label(mv_right, text="Voz:", bg=self.style.get_color("bg_main"), fg=self.style.get_color("text_dim"), font=("Arial", 8))
        self._lbl_new_voice.pack(anchor="w")

        # Botones de Acción
        btn_box = tk.Frame(self.new_thread_frame, bg=self.style.get_color("bg_main"))
        btn_box.pack(fill=tk.X)
        
        self._btn_create_thread = tk.Button(btn_box, text="Crear e Iniciar Hilo", bg=self.style.get_color("accent"), fg=self.style.get_color("btn_fg"), relief="flat", 
                  command=self._confirm_new_thread, padx=10)
        self._btn_create_thread.pack(side=tk.LEFT)
        self._btn_cancel = tk.Button(btn_box, text="Cancelar", bg="#555", fg="white", relief="flat", 
                  command=self._cancel_new_thread, padx=10)
        self._btn_cancel.pack(side=tk.LEFT, padx=10)

        # --- ÁREA DE TEXTO (Hijo de middle_container) ---
        # Usamos bg_dark para el área de chat, que ahora es un marrón oscuro en el tema Neon
        self.chat_display = scrolledtext.ScrolledText(self.middle_container, state='disabled', 
                                                      bg=self.style.get_color("bg_dark"), fg=self.style.get_color("text_main"), 
                                                      font=("Consolas", 10), wrap=tk.WORD, bd=0, highlightthickness=0)
        self.chat_display.pack(padx=10, fill=tk.BOTH, expand=True)


        # --- ÁREA DE ENTRADA (ya creada arriba en footer) ---

        # FILA 1: Campo de texto (Ocupa todo el ancho)
        if has_footer_bg:
            # Envolvemos el entry en su propio BackgroundFrame para que tenga textura
            input_container = BackgroundFrame(self.input_area, self.style, "button")
            input_container.pack(fill=tk.X, ipady=2, pady=(0, 5))
            # Hacemos que el entry sea casi transparente sobre el fondo
            self.input_field = tk.Entry(input_container, bg="#0a0a0f", fg=self.style.get_color("text_main"), 
                                        insertbackground=self.style.get_color("text_main"), relief="flat", font=("Arial", 10), bd=0)
            self.input_field.pack(fill=tk.X, padx=10, pady=5)
        else:
            self.input_field = tk.Entry(self.input_area, bg=self.style.get_color("bg_input"), fg=self.style.get_color("text_main"), 
                                        insertbackground=self.style.get_color("text_main"), relief="flat", font=("Arial", 10))
            self.input_field.pack(fill=tk.X, ipady=5, pady=(0, 5))

        self.input_field.bind("<Return>", lambda e: self.handle_send())

        # FILA 2: Botones y Controles
        if has_footer_bg:
            btns_frame = BackgroundFrame(self.input_area, self.style, "button")
        else:
            btns_frame = tk.Frame(self.input_area, bg=self.style.get_color("bg_main"))
        btns_frame.pack(fill=tk.X)

        # Vision - Solo el combo (eliminado el label que parecía un infinito)
        self.combo_vision = ttk.Combobox(btns_frame, values=["None", "Cam", "Screen", "Imagen"], state="readonly", width=8)
        self.combo_vision.set("None")
        self.combo_vision.pack(side=tk.LEFT, padx=5)
        self.combo_vision.bind("<<ComboboxSelected>>", self._on_vision_change)
        
        # Audio
        self._btn_add_audio = ImageButton(btns_frame, "➕ Audio", self.style,
                                         self.handle_add_audio, pady=2, padx=10, width=10)
        self._btn_add_audio.set_active(True)
        self._btn_add_audio.pack(side=tk.LEFT, padx=5)

        # Stop (Lo ponemos a la izquierda, junto al audio, para que siempre esté a la vista)
        self._btn_stop = ImageButton(btns_frame, "Stop", self.style,
                                    self._stop_audio, pady=2, padx=10, width=8)
        self._btn_stop.config(fg="#ff6b6b") # Color coral para destacar
        self._btn_stop.pack(side=tk.LEFT, padx=5)

        # Enviar (Derecha del todo)
        self._btn_send = ImageButton(btns_frame, "Enviar", self.style,
                                    self.handle_send, pady=2, padx=10, width=10)
        self._btn_send.set_active(True)
        self._btn_send.pack(side=tk.RIGHT, padx=(2, 10))


        # STT Mode (A la izquierda del botón Enviar)
        stt_modes = ["OFF", "CHAT", "VOICE_COMMAND", "AGENT", "AGENT_AUDIO"]
        self.combo_stt_mode = ttk.Combobox(btns_frame, values=stt_modes, state="readonly", width=10)
        self.combo_stt_mode.pack(side=tk.RIGHT, padx=5)
        self.combo_stt_mode.bind("<<ComboboxSelected>>", self._on_stt_mode_change)

        self._lbl_stt_mode = tk.Label(btns_frame, text="🤖", bg=self.style.get_color("bg_main"), fg=self.style.get_color("text_dim"), font=("Arial", 10, "bold"))
        if has_footer_bg: self._lbl_stt_mode.config(bg="#0a0a0f")
        self._lbl_stt_mode.pack(side=tk.RIGHT, padx=(5, 0))



        # (Ya fueron inicializados y empaquetados arriba para asegurar visibilidad en el layout)

        # 2. VISTA DE CONFIGURACIÓN
        self.settings_frame = SettingsView(self.container, self.config, self.chat_engine.locale_service, self.show_chat, self.style)
        
        # 3. VISTA DE API KEYS
        self.api_keys_frame = APIKeysView(self.container, self.config, self.show_chat, self.style)

    def _load_initial_state(self):
        # Memoria (NUEVA)
        self._refresh_memories()
        active_thread = self.chat_engine.memory.active_thread
        self.last_valid_thread = active_thread # Guardar para cancelar
        self.combo_memory.set(active_thread)
        self._update_profile_ui()

        # SUPER-PERSISTENCIA (NUEVO): Siempre forzar a la Secretaria al arrancar la App
        # Esto evita que si el usuario cerró la app interrogando un sospechoso, este aparezca en la oficina.
        print("[ChatWidget] Iniciando App: Forzando identidad de Secretaria para Oficina Principal.")
        self._apply_character_by_id("Secretaria")
        
        # Guardar el último personaje preferido (por si se quiere restaurar manualmente), 
        # pero para el inicio de la app, la Secretaria es la reina.
        last_char_id = self.config.get("last_character")
        if last_char_id and last_char_id != "Secretaria":
             print(f"[ChatWidget] Identidad previa detectada ({last_char_id}), pero ignorada por inicio de App.")

        # AI
        last_provider = self.config.get("last_provider", "Ollama")
        self.combo_provider.set(last_provider)
        self._on_provider_change(None)

        # TTS
        self.combo_voice.set(self.config.get("voice_provider", "None"))
        self.combo_voice_mode.set(self.config.get("voice_mode", "autoplay"))
        self._on_voice_change(None)

        # STT
        self.combo_stt_provider.set(self.config.get("stt_provider", "None"))
        self.combo_stt_mode.set(self.config.get("stt_mode", "OFF"))
        self.stt_service.update_adapter()

    def _refresh_memories(self):
        threads = ["None", "New"] + self.chat_engine.memory.list_threads()
        self.combo_memory['values'] = threads

    def _on_memory_change(self, event):
        selection = self.combo_memory.get()
        if selection == "New":
            # Mostrar Wizard en lugar de crear directamente
            self._set_wizard_visibility(True)
            return
            
        self.last_valid_thread = selection
        self.chat_engine.memory.load_thread(selection)
        self.config.set("active_thread", selection)
        self._update_profile_ui()
        
        # Limpiar chat y cargar historial
        self.chat_display.config(state='normal')
        self.chat_display.delete('1.0', tk.END)
        self.chat_display.config(state='disabled')
        for msg in self.chat_engine.get_history():
            color = "#569cd6" if msg.sender == "Tú" else "#ce9178"
            self._append_message(msg.sender, msg.content, color)

    def _set_wizard_visibility(self, visible: bool):
        if visible:
            # Limpiar campos para nuevo hilo
            self.ent_new_name.delete(0, tk.END)
            self.ent_new_pers.delete(0, tk.END)
            self.txt_new_hist.delete("1.0", tk.END)
            
            # Motores
            motors = self.chat_engine.get_voice_providers_list()
            self.combo_new_motor['values'] = motors
            self.combo_new_motor.set(self.combo_voice.get()) # Por defecto el actual global
            self._on_wizard_motor_change(None) # Cargar voces para ese motor
            
            self.chat_display.pack_forget()
            self.new_thread_frame.pack(fill=tk.BOTH, expand=True)
            self.input_field.config(state="disabled")
        else:
            self.new_thread_frame.pack_forget()
            self.chat_display.pack(padx=10, fill=tk.BOTH, expand=True)
            self.input_field.config(state="normal")

    def _on_wizard_motor_change(self, event):
        motor = self.combo_new_motor.get()
        # En el wizard usamos un motor temporal para listar voces
        from core.factories.voice_factory import VoiceFactory
        adapter = VoiceFactory.get_adapter(motor)
        if adapter:
            voices = adapter.list_voices()
            self.combo_new_voice['values'] = ["None"] + [f"{v['id']} - {v['name']}" for v in voices]
            self.combo_new_voice.set("None")

    def _confirm_new_thread(self):
        name = self.ent_new_name.get()
        pers = self.ent_new_pers.get()
        hist = self.txt_new_hist.get("1.0", tk.END).strip()
        
        motor = self.combo_new_motor.get()
        voice_selection = self.combo_new_voice.get()
        voice_id = ""
        if voice_selection != "None":
            voice_id = voice_selection.split(" - ")[0]
        
        # 1. Crear el hilo físicamente
        new_id = self.chat_engine.memory.create_new_thread()
        
        # 2. Aplicar perfil (incluyendo motor y voz) con HERENCIA (NUEVO)
        # Si no hay visuales nuevos en el wizard, heredamos los de la sesión actual
        current_avatar = self.chat_engine.memory.data.get("avatar")
        current_video = self.chat_engine.memory.data.get("video")
        
        self.chat_engine.memory.update_profile(
            name=name if name else None,
            personality=pers if pers else None,
            history=hist if hist else None,
            voice_id=voice_id if voice_id else None,
            voice_provider=motor if motor != "None" else None,
            avatar=self.pending_avatar if self.pending_avatar else current_avatar,
            video=self.pending_video if self.pending_video else current_video,
            char_id=self.config.get("last_character") # Mantener anclaje al personaje
        )
        self.pending_avatar = None # Limpiar tras aplicar
        self.pending_video = None # Limpiar tras aplicar
        
        # 3. Finalizar selección
        self.last_valid_thread = new_id
        self._refresh_memories()
        self.combo_memory.set(new_id)
        self.config.set("active_thread", new_id)
        self._set_wizard_visibility(False)
        self._on_memory_change(None) # Recargar UI (historial vacío)

        # Notificar al visualizador (NUEVO)
        if self.visualizer:
            self.visualizer.set_character(self.chat_engine.memory.data)

    def _cancel_new_thread(self):
        self._set_wizard_visibility(False)
        self.combo_memory.set(self.last_valid_thread)

    def _on_sidebar_motor_change(self, event):
        motor = self.combo_char_motor.get()
        from core.factories.voice_factory import VoiceFactory
        adapter = VoiceFactory.get_adapter(motor)
        if adapter:
            voices = adapter.list_voices()
            self.combo_char_voice['values'] = ["None"] + [f"{v['id']} - {v['name']}" for v in voices]
            self.combo_char_voice.set("None")

    def _update_profile_ui(self):
        data = self.chat_engine.memory.data
        self.ent_char_name.delete(0, tk.END)
        self.ent_char_name.insert(0, data.get("name", ""))
        self.ent_char_pers.delete(0, tk.END)
        self.ent_char_pers.insert(0, data.get("personality", ""))
        
        # Motores
        motors = self.chat_engine.get_voice_providers_list()
        self.combo_char_motor['values'] = motors
        char_motor = data.get("voice_provider", "")
        if char_motor and char_motor in motors:
            self.combo_char_motor.set(char_motor)
        else:
            self.combo_char_motor.set("None")
            
        self._on_sidebar_motor_change(None) # Poblar voces para ese motor
        
        # Seleccionar voz
        v_list = self.combo_char_voice['values']
        char_voice = data.get("voice_id", "")
        found = False
        if char_voice:
            for v_str in v_list:
                if v_str.startswith(f"{char_voice} -"):
                    self.combo_char_voice.set(v_str)
                    found = True
                    break
        if not found:
            self.combo_char_voice.set("None")

        # Notificar al visualizador (NUEVO)
        if self.visualizer:
            self.visualizer.set_character(data)

    def _save_profile(self):
        name = self.ent_char_name.get()
        pers = self.ent_char_pers.get()
        motor = self.combo_char_motor.get()
        voice_selection = self.combo_char_voice.get()
        
        voice_id = ""
        if voice_selection != "None":
            voice_id = voice_selection.split(" - ")[0]
            
        self.chat_engine.memory.update_profile(
            name=name, 
            personality=pers, 
            voice_id=voice_id,
            voice_provider=motor if motor != "None" else None,
            avatar=self.chat_engine.memory.data.get("avatar"), # Mantener avatar actual
            video=self.chat_engine.memory.data.get("video") # Mantener video actual
        )
        self.status_label_simulated = "Perfil guardado"

    def _on_provider_change(self, event):
        provider = self.combo_provider.get()
        self.config.set("last_provider", provider)
        self.chat_engine.switch_provider(provider)
        
        # Cargar modelos de forma asíncrona desactivando el combo temporalmente
        self.combo_model.config(state="disabled")
        threading.Thread(target=self._async_load_models, daemon=True).start()

    def _async_load_models(self):
        try:
            # Ejecutamos la corrutina en un nuevo bucle de eventos en este hilo
            models = asyncio.run(self.chat_engine.get_available_models())
            # Usamos after para interactuar con la UI desde el hilo principal de forma segura
            self.after(0, lambda: self._update_models_combo(models))
        except Exception as e:
            print(f"[UI] Error loading models: {e}")
            # Intentar rehabilitar el combo incluso si falla (de forma segura)
            self.after(0, lambda: self.combo_model.config(state="readonly"))

    def _update_models_combo(self, models):
        self.combo_model.config(state="readonly")
        self.combo_model['values'] = models
        last_model = self.config.get("last_model", "")
        if models:
            if last_model in models: 
                self.combo_model.set(last_model)
            else:
                self.combo_model.current(0)
                self.config.set("last_model", self.combo_model.get())

    def _on_model_change(self, event):
        self.config.set("last_model", self.combo_model.get())

    def _on_inference_change(self, event):
        max_tokens = int(self.spin_max_tokens.get())
        temperature = float(self.slider_temp.get())
        self.config.set("max_tokens", max_tokens)
        self.config.set("temperature", temperature)

    def _on_voice_change(self, event):
        provider = self.combo_voice.get()
        self.config.set("voice_provider", provider)
        self.chat_engine.voice_service.update_provider()
        voices_data = self.chat_engine.voice_service.get_available_voices()
        self.voice_map = {v["name"]: v["id"] for v in voices_data}
        names = list(self.voice_map.keys())
        self.combo_voice_id['values'] = names
        last_voice_id = self.config.get("voice_id", "")
        found_name = next((name for name, vid in self.voice_map.items() if vid == last_voice_id), None)
        if found_name: self.combo_voice_id.set(found_name)
        elif names:
            self.combo_voice_id.current(0)
            self.config.set("voice_id", self.voice_map[names[0]])

    def _on_voice_mode_change(self, event):
        self.config.set("voice_mode", self.combo_voice_mode.get())

    def _on_voice_id_change(self, event):
        name = self.combo_voice_id.get()
        if name in self.voice_map:
            self.config.set("voice_id", self.voice_map[name])

    def _on_stt_provider_change(self, event):
        self.config.set("stt_provider", self.combo_stt_provider.get())
        self.stt_service.update_adapter()

    def _on_stt_mode_change(self, event):
        self.config.set("stt_mode", self.combo_stt_mode.get())
        self.stt_service.manage_microphone_thread()

    def _on_stt_finished(self, text):
        """Callback cuando el STT termina de transcribir."""
        if text:
            # Enviamos al chat en el hilo principal
            self.after(0, lambda: self._process_stt_input(text))

    def _on_chat_injected(self, text, sender, role="assistant"):
        """Muestra un mensaje inyectado (del juego) como una burbuja de chat real."""
        if not text: return
        # Mapear rol a color
        color = self.style.get_color("text_main") if role == "user" else self.style.get_color("accent")
        try:
            self.after(0, lambda: self._append_message(sender, text, color) if self.winfo_exists() else None)
        except Exception as e:
            print(f"[ChatWidget] Error routing injected message: {e}")

    def _on_system_msg_notified(self, text, color=None, beep=False):
        """Muestra un mensaje del sistema en el chat (sin voz)."""
        color = color or "#888"
        if beep:
            winsound.Beep(800, 80)
        try:
            self.after(0, lambda: self._append_message("ASIMOD", text, color) if self.winfo_exists() else None)
        except Exception as e:
            print(f"[ChatWidget] Error routing system message: {e}")

    def _on_voice_command(self, command_matched, text):
        """Callback cuando se reconoce un comando de voz."""
        if command_matched:
            winsound.Beep(800, 80)
            try:
                self.after(0, lambda: self._append_message("SYSTEM", f"Voice command recognized: {text} → {command_matched}", "#FF6B6B") if self.winfo_exists() else None)
            except: pass
        elif self.var_test_mode.get():
            text_lower = text.lower()
            if "comando" in text_lower or "prueba" in text_lower:
                winsound.Beep(800, 80)
                try:
                    self.after(0, lambda: self._append_message("TEST MODE", f"Command detected: {text}", "#4ECDC4") if self.winfo_exists() else None)
                except: pass
        
        if text:
            # Solo mostrar el texto reconocido en el input si NO está siendo capturado por un módulo
            if not getattr(self.chat_engine, "stt_captured_by_module", False):
                try:
                    self.after(0, lambda: self._display_recognized_text(text) if self.winfo_exists() else None)
                except: pass
            else:
                # Opcional: Podríamos limpiar el input si algo quedó allí
                try:
                    self.after(0, lambda: self.input_field.delete(0, tk.END) if self.winfo_exists() else None)
                except: pass

    def _display_recognized_text(self, text):
        """Muestra el texto reconocido en el input field."""
        self.input_field.delete(0, tk.END)
        self.input_field.insert(0, text)

    def _process_stt_input(self, text):
        self.input_field.delete(0, tk.END)
        self.input_field.insert(0, text)
        self.handle_send()

    def handle_add_audio(self):
        """Abre un diálogo para seleccionar un archivo de audio."""
        file_path = filedialog.askopenfilename(filetypes=[("Audio files", "*.mp3 *.wav")])
        if file_path:
            self.stt_service.process_file(file_path)

    def show_settings(self):
        for widget in self.chat_components:
            widget.pack_forget()
        self.api_keys_frame.pack_forget()
        self.settings_frame.pack(fill=tk.BOTH, expand=True)

    def show_api_keys(self):
        for widget in self.chat_components:
            widget.pack_forget()
        self.settings_frame.pack_forget()
        self.api_keys_frame.pack(fill=tk.BOTH, expand=True)

    def show_chat(self):
        self.settings_frame.pack_forget()
        self.api_keys_frame.pack_forget()
        
        # Repáquetar componentes en orden original para mantener el diseño
        self.top_bar.pack(fill=tk.X, padx=20, pady=(15, 5))
        if self.hub_visible:
            self.hub_panel.pack(fill=tk.X, padx=10)
        if self.toolbar_visible:
            self.toolbar.pack(fill=tk.X, padx=10)
        
        if self.visualizer and self.visualizer._frame:
            self.visualizer._frame.pack(fill=tk.X, padx=20)
        
        # Buscar el separador en la lista (es un elemento sin nombre directo pero está en chat_components)
        for comp in self.chat_components:
            if isinstance(comp, ttk.Separator):
                comp.pack(fill=tk.X, padx=20, pady=5)
                break
                
        self.input_area.pack(side=tk.BOTTOM, padx=20, pady=15, fill=tk.X)
        self.lbl_files.pack(fill=tk.X, padx=10, side=tk.BOTTOM)
        self.middle_container.pack(fill=tk.BOTH, expand=True, padx=20, pady=5)
        
        self._on_provider_change(None)
        self._on_voice_change(None)

    def _toggle_toolbar(self):
        """Colapsa o expande el toolbar"""
        if self.toolbar_visible:
            self.toolbar.pack_forget()
            self.btn_toggle_toolbar.config(text="▼")
        else:
            # Interlock: Cerrar Hub si está abierto
            if self.hub_visible: self._toggle_hub_panel()

            if self.visualizer and self.visualizer._frame:
                self.toolbar.pack(fill=tk.X, padx=10, before=self.visualizer._frame)
            elif hasattr(self, 'middle_container'):
                self.toolbar.pack(fill=tk.X, padx=10, before=self.middle_container)
            else:
                self.toolbar.pack(fill=tk.X, padx=10)
            self.btn_toggle_toolbar.config(text="▲")
        self.toolbar_visible = not self.toolbar_visible

    def _on_vision_change(self, event):
        mode = self.combo_vision.get()
        if mode == "None": return
        
        path = None
        if mode == "Cam":
            path = self.vision_service.capture_cam()
        elif mode == "Screen":
            path = self.vision_service.capture_screen()
        elif mode == "Imagen":
            path = self.vision_service.pick_image()
            
        if path:
            self.current_images.append(path)
            # Actualizar label con nombres de archivos
            names = [os.path.basename(p) for p in self.current_images]
            self.lbl_files.config(text=f"📷 Archivos listos: {', '.join(names)}")
        
        # Resetear combo a None para permitir re-selección
        self.combo_vision.set("None")

    def handle_send(self):
        """Dispara el proceso de envío de forma asíncrona para no bloquear la UI."""
        # Protección contra envíos concurrentes
        if self.is_sending or self.chat_engine.busy:
            print("[UI] Busy: Ignorando intento de envío concurrente.")
            return

        text = self.input_field.get()
        if not text and not self.current_images: return

        # Pausar STT inmediatamente para evitar capturas durante la generación
        if self.stt_service:
            self.stt_service.pause_capture()

        self.is_sending = True
        
        display_text = text if text else self.t("chat.vision") + " " + self.t("chat.audio")
        self._append_message(self.t("chat.you"), display_text, "#569cd6")
        self.input_field.delete(0, tk.END)
        
        # Feedback visual y bloqueo preventivo
        self._btn_send.config(state=tk.DISABLED, text=self.t("chat.sending"))
        self.update() 
        
        model = self.combo_model.get()
        images = list(self.current_images) # Copia de la lista actual
        
        # Limpiar lista de imágenes de la UI
        self.current_images = []
        self.lbl_files.config(text="")
        
        # Ejecutar en hilo secundario
        thread = threading.Thread(
            target=self._async_send_task, 
            args=(text, model, images),
            daemon=True
        )
        thread.start()

    def _async_send_task(self, text, model, images):
        """Tarea ejecutada en hilo de fondo."""
        try:
            # Ejecutamos la corrutina en un nuevo bucle de eventos en este hilo
            result = asyncio.run(self.chat_engine.send_message(text, model=model, images=images))
            
            # REFRESH INMEDIATO DE STATS (NUEVO: Para que los gauges reaccionen antes del TTS)
            if self.visualizer and self.chat_engine.memory.data:
                self.after(0, lambda: self.visualizer.set_character(self.chat_engine.memory.data))

            # Notificar al hilo principal para actualizar UI
            if self.winfo_exists():
                self.after(0, lambda: self._handle_response(result) if self.winfo_exists() else None)
        except Exception as e:
            import traceback
            traceback.print_exc()
            error_msg = {"response": f"Error crítico al enviar: {str(e)}", "status": "error"}
            self.after(0, self._handle_response, error_msg)

    def _handle_response(self, result):
        """Actualiza la interfaz con la respuesta (Corre en el hilo principal)."""
        self.is_sending = False
        self._btn_send.config(state=tk.NORMAL, text=self.t("chat.send_btn"))
        
        # Si no hay audio activado o planeado, reanudamos el STT manualmente
        # (Si hay audio, VoiceService lo reanudará cuando termine de sonar)
        if not self.chat_engine.voice_service.is_playing and \
           not self.chat_engine.voice_service.is_generating:
            if self.stt_service:
                self.stt_service.resume_capture(delay=0.1)
        
        # Mostramos la respuesta original (con emojis/asteriscos) en la UI
        if isinstance(result, dict) and "response" in result:
            self._append_message(self.t("chat.ai"), result["response"], "#ce9178")
            
            # Pasar emojis al visualizador (NUEVO)
            if self.visualizer and "emojis" in result:
                self.visualizer.set_emojis(result["emojis"])
        else:
            self._append_message(self.t("chat.system"), str(result), "red")

    def _on_early_emojis_detected(self, emojis):
        """Callback temprano de emojis para sincronizar el visualizador antes del TTS."""
        if self.visualizer and emojis:
            # Forzar actualización en el hilo principal
            self.after(0, lambda: self.visualizer.set_emojis(emojis))

    def _stop_audio(self):
        """Detiene la reproducción de audio actual."""
        self.chat_engine.voice_service.stop_audio()

    def _append_message(self, sender, text, color):
        self.chat_display.config(state='normal')
        self.chat_display.insert(tk.END, f"{sender}: ", ("sender",))
        self.chat_display.insert(tk.END, f"{text}\n\n")
        self.chat_display.tag_config("sender", foreground=color, font=("Consolas", 10, "bold"))
        self.chat_display.see(tk.END)
        self.chat_display.config(state='disabled')

    # --- CHARACTER HUB LOGIC (NUEVO) ---

    def _toggle_hub_panel(self):
        """Muestra u oculta el panel de biblioteca de personajes."""
        if self.hub_visible:
            self.hub_panel.pack_forget()
        else:
            # Interlock: Cerrar toolbar si está abierta
            if self.toolbar_visible: self._toggle_toolbar()

            self._populate_hub_panel()
            if self.visualizer and self.visualizer._frame:
                self.hub_panel.pack(fill=tk.X, padx=10, before=self.visualizer._frame)
            else:
                self.hub_panel.pack(fill=tk.X, padx=10, before=self.middle_container)
        
        self.hub_visible = not self.hub_visible

    def _populate_hub_panel(self):
        """Llena el panel horizontal con los personajes disponibles."""
        if not self.char_service: return
        
        for widget in self.hub_container.winfo_children():
            widget.destroy()
            
        characters = self.char_service.list_characters()
        if not characters:
            tk.Label(self.hub_container, text="Biblioteca Vacía", bg=self.hub_container["bg"], fg="#555").pack(padx=20)
            return

        # NUEVO: Ordenar alfabéticamente por nombre
        characters.sort(key=lambda x: x.get("name", "").lower())

        for char in characters:
            # Botón de personaje estilo tarjeta vertical
            btn = tk.Button(self.hub_container, text=f"👤 {char['name']}", 
                           bg="#2a2a35", fg="white", relief="flat", padx=10, pady=8,
                           font=("Arial", 9, "bold"), anchor="w",
                           command=lambda c=char: self._apply_registry_character(c))
            btn.pack(fill=tk.X, pady=2, padx=5)

        # Ajustar ancho del contenedor al canvas tras poblar (Ahora se maneja via evento o forzado)
        self.hub_canvas.update_idletasks()
        self._on_hub_canvas_configure(None)

    def _on_hub_canvas_configure(self, event):
        """Asegura que el contenedor interno ocupe todo el ancho del canvas."""
        canvas_width = self.hub_canvas.winfo_width()
        if canvas_width > 1:
            self.hub_canvas.itemconfig(self.hub_window_id, width=canvas_width)

    def _apply_character_by_id(self, char_id):
        """Busca un personaje en el registro por ID y lo aplica."""
        if not self.char_service: return
        characters = self.char_service.list_characters()
        found = next((c for c in characters if c.get("id") == char_id), None)
        if found:
            print(f"[ChatWidget] Aplicando restauración para personaje ID: {char_id}")
            self._apply_registry_character(found)

    def _apply_registry_character(self, char_data):
        """Aplica los datos de un personaje del registro con soporte para hilos persistentes."""
        # Si el hub está visible, lo cerramos tras seleccionar
        if self.hub_visible:
            self._toggle_hub_panel()

        name = char_data.get("name", "")
        personality = char_data.get("personality", "")
        avatar = char_data.get("avatar")
        video = char_data.get("video")
        gender = char_data.get("gender", "male").lower()
        voice_id = char_data.get("voice_id")
        char_thread_id = char_data.get("active_thread")

        # Lógica de voz por género si no hay voice_id definido (NUEVO: Selección aleatoria dinámica)
        if not voice_id:
            from core.factories.voice_factory import VoiceFactory
            adapter = VoiceFactory.get_adapter("Edge TTS")
            if adapter:
                all_voices = adapter.list_voices()
                # Filtrar según género (Mapeo: male -> Masculina, female -> Femenina)
                search_term = "Masculina" if gender == "male" else "Femenina" if gender == "female" else None
                
                matching_voices = []
                if search_term:
                    matching_voices = [v["id"] for v in all_voices if search_term in v["name"]]
                
                if matching_voices:
                    voice_id = random.choice(matching_voices)
                    print(f"[ChatWidget] Voz aleatoria seleccionada para género '{gender}': {voice_id}")
                else:
                    # Fallback si no hay coincidencias o es non-binary
                    voice_id = "es-MX-DaliaNeural" if gender == "non-binary" else "es-ES-AlvaroNeural"

        # 1. ACTUALIZACIÓN DE HILO PERSISTENTE (MODO IDENTIDAD)
        if char_thread_id and self.chat_engine:
            available_threads = self.chat_engine.memory.list_threads()
            
            if char_thread_id in available_threads:
                print(f"[ChatWidget] Cargando hilo persistente: {char_thread_id}")
                self.chat_engine.memory.load_thread(char_thread_id)
            else:
                print(f"[ChatWidget] Creando nuevo hilo persistente para {name}: {char_thread_id}")
                self.chat_engine.memory.create_new_thread(char_thread_id)
                # Inicializar el perfil en el nuevo hilo
                self.chat_engine.memory.update_profile(
                    name=name,
                    personality=personality,
                    avatar=avatar,
                    video=video,
                    voice_id=voice_id,
                    voice_provider="Edge TTS"
                )

            # Sincronizar UI de hilos
            self._refresh_memories()
            self.combo_memory.set(char_thread_id)
            self.config.set("active_thread", char_thread_id)
            self.config.set("last_character", char_data.get("id", "")) # ANCLAJE GLOBAL (NUEVO)
            
            # ACTUALIZAR PERFIL (Sincronización total de metadatos)
            self.chat_engine.memory.update_profile(
                name=name,
                personality=personality,
                avatar=avatar,
                video=video,
                voice_id=voice_id,
                threads=char_data.get("threads", []),
                stats=char_data.get("stats", {}),
                char_id=char_data.get("id")
            )
            
            # Cargar los datos del hilo recién seleccionado en los campos de la UI
            self._load_current_thread_data()
        
        else:
            # MODO DINÁMICO: Si el Wizard está abierto, preparar campos para nuevo hilo.
            # Si no, sobreescribir identidad del hilo actual.
            is_wizard = self.new_thread_frame.winfo_ismapped()
            
            if is_wizard:
                print(f"[ChatWidget] Aplicando '{name}' como plantilla para nuevo hilo.")
                self.ent_new_name.delete(0, tk.END)
                self.ent_new_name.insert(0, name)
                self.ent_new_pers.delete(0, tk.END)
                self.ent_new_pers.insert(0, personality)
                self.pending_avatar = avatar
                self.pending_video = video
            else:
                print(f"[ChatWidget] Intercambiando identidad actual por '{name}'.")
                self.config.set("last_character", char_data.get("id", "")) # ANCLAJE GLOBAL (NUEVO)
                self.chat_engine.memory.update_profile(
                    name=name,
                    personality=personality,
                    avatar=avatar,
                    video=video,
                    voice_id=voice_id,
                    voice_provider="Edge TTS",
                    char_id=char_data.get("id")
                )
                self._load_current_thread_data()

        # Refrescar Visualizador inmediatamente con los datos del personaje seleccionado
        if self.visualizer:
            if self.new_thread_frame.winfo_ismapped():
                # En modo Wizard mostramos char_data como preview
                self.visualizer.set_character(char_data)
            else:
                # En modo chat usamos los datos sincronizados en memoria
                self.visualizer.set_character(self.chat_engine.memory.data)

        print(f"[ChatWidget] Personaje '{name}' activado desde el Hub.")

    def _load_current_thread_data(self):
        """Carga los datos de la memoria activa en todos los controles de la UI."""
        # 4. Auto-sincronizar metadatos del registro (NUEVÍSIMO)
        # Esto rellena 'threads' y 'stats' desde el JSON maestro si falta en el hilo
        self._sync_metadata_from_registry()
        
        # Recargar data tras sync
        data = self.chat_engine.memory.data

        # 1. Campos de Perfil
        self.ent_char_name.delete(0, tk.END)
        self.ent_char_name.insert(0, data.get("name", ""))
        self.ent_char_pers.delete(0, tk.END)
        self.ent_char_pers.insert(0, data.get("personality", ""))
        
        # Sincronizar Visualizador
        if self.visualizer:
            # Asegurar que el ID del hilo actual esté en la data para el visualizador
            viz_data = data.copy()
            viz_data["active_thread"] = self.chat_engine.memory.active_thread
            self.visualizer.set_character(viz_data)
        
        # 2. Configuración de Voz
        voice_id = data.get("voice_id", "")
        provider = data.get("voice_provider", "Edge TTS")
        if not provider or provider == "None" or provider == "": 
            provider = "Edge TTS"
            
        self.combo_char_motor.set(provider)
        
        # Sincronizar combo de voz
        if hasattr(self, 'combo_char_voice') and self.combo_char_voice:
            values = self.combo_char_voice['values']
            for i in range(len(values)):
                if values[i].startswith(voice_id):
                    self.combo_char_voice.current(i)
                    break

    def _sync_metadata_from_registry(self):
        """Si el personaje tiene un ID que coincide con uno del registro, asegura que tiene threads/stats."""
        data = self.chat_engine.memory.data
        char_id = data.get("id")
        # Si no tiene ID directo, intentamos por nombre
        if not char_id: char_id = data.get("name")
        
        if not char_id or not self.char_service: return
        
        master_data = self.char_service.get_character(char_id)
        if master_data:
            print(f"[ChatWidget] Sincronizando metadatos para {char_id} desde el registro maestro.")
            # Mezclar threads
            master_threads = master_data.get("threads", [])
            current_threads = data.get("threads", [])
            
            # Unir sin duplicados
            new_threads = list(set(master_threads + current_threads))
            
            # Sincronizar stats si los del hilo están vacíos o queremos los maestros
            # (En el futuro esto podría ser bidireccional, por ahora priorizamos maestros al cargar)
            master_stats = master_data.get("stats", {})
            
            self.chat_engine.memory.update_profile(
                threads=new_threads,
                stats=master_stats,
                char_id=master_data.get("id")
            )
            return
            
        # Solo sincronizar si falta el video
        if not data.get("video") or not data.get("video").get("idle"):
            registry_char = self.char_service.get_character(name)
            if registry_char:
                print(f"[ChatWidget] Sincronizando metadatos faltantes para {name}...")
                self.chat_engine.memory.update_profile(
                    avatar=registry_char.get("avatar"),
                    video=registry_char.get("video")
                )
                # Refrescar visualizador con los nuevos datos
                if self.visualizer:
                    self.visualizer.set_character(self.chat_engine.memory.data)

    def _on_character_changed(self):
        """Notificación de que la identidad en memoria ha cambiado, refrescar visualizador y UI."""
        print("[ChatWidget] Recibida notificación de cambio de personaje. Refrescando interfaz completa...")
            
        def _update_ui():
            try:
                if not self.winfo_exists():
                    return
                # 1. Refrescar Visualizador
                if self.visualizer:
                    # Si el juego pidió un bloqueo externo, activarlo ANTES de set_character
                    # (set_character se ejecutará porque aún no está bloqueado)
                    lock_requested = getattr(self.chat_engine, '_avatar_lock_requested', False)
                    if lock_requested:
                        self.chat_engine._avatar_lock_requested = False
                    
                    self.visualizer.set_character(self.chat_engine.memory.data)
                    
                    # Ahora bloquear tras cargar el personaje externo
                    if lock_requested and hasattr(self.visualizer, 'lock_character'):
                        self.visualizer.lock_character(timeout_ms=15000)
                    
                # 2. Actualizar campos de perfil en la UI (Nombre, Personalidad, etc.)
                self._load_current_thread_data()
                
                # 3. Recargar Historial de Chat
                self.chat_display.config(state='normal')
                self.chat_display.delete('1.0', tk.END)
                self.chat_display.config(state='disabled')
                
                for msg in self.chat_engine.get_history():
                    sender_name = msg.sender
                    # Traducir 'Tú' si es necesario
                    if sender_name == "Tú": sender_name = self.t("chat.you")
                    
                    color = "#569cd6" if msg.sender == "Tú" else "#ce9178"
                    self._append_message(sender_name, msg.content, color)
                
                # 4. Asegurar que el scroll esté al final
                self.chat_display.see(tk.END)
            except Exception as e:
                print(f"[ChatWidget] Error inside async _update_ui for character swap: {e}")
                import traceback
                traceback.print_exc()
            
        try:
            self.after(0, _update_ui)
        except Exception as e:
            print(f"[ChatWidget] Error routing character changed: {e}")
