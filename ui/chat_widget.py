import tkinter as tk
import os
import threading
import winsound
import asyncio
from tkinter import ttk, scrolledtext, filedialog
from core.ports.chat_port import ChatPort
from ui.settings_view import SettingsView
from ui.api_keys_view import APIKeysView
from core.services.stt_service import STTService
from core.services.vision_service import VisionService
from core.services.visualizer_service import VisualizerService

class ChatWidget(tk.Frame):
    """
    Widget de Chat avanzado con controles de IA, Voz (TTS) y Reconocimiento (STT).
    """
    def __init__(self, parent, chat_engine: ChatPort, config_service, style_service, on_collapse_cmd=None):
        self.style = style_service
        self.on_collapse_cmd = on_collapse_cmd
        super().__init__(parent, bg=self.style.get_color("bg_main"))
        self.chat_engine = chat_engine
        self.config = config_service
        self.vision_service = VisionService()
        self.current_images = []
        self._ui_labels = {}
        self.visualizer = None
        self.toolbar_visible = False
        self.is_sending = False # Estado de envío actual
        
        # Vincular STT Service del engine con la UI
        self.stt_service = self.chat_engine.stt_service
        self.chat_engine.on_stt_finished_cb = self._on_stt_finished
        self.stt_service.add_voice_command_callback(self._on_voice_command)
        
        # Suscribir a mensajes de sistema/locales (sin voz)
        if hasattr(self.chat_engine, "on_system_msg_cb"):
            self.chat_engine.on_system_msg_cb = self._on_system_msg_notified
        
        # Contenedor principal para las vistas
        self.container = tk.Frame(self, bg=self.style.get_color("bg_main"))
        self.container.pack(fill=tk.BOTH, expand=True)

        self._setup_visualizer()
        self.init_ui()
        self._load_initial_state()
        self._update_ui_texts()
        
    def _setup_visualizer(self):
        """Configura el visualizador si está habilitado mediante carga dinámica"""
        if self.config.get("visualizer_enabled", False):
            v_service = VisualizerService(self.config)
            v_type = self.config.get("visualizer_type", "waveform")
            self.visualizer = v_service.get_instance(v_type, self, width=600, height=60)
            
            if self.visualizer and self.chat_engine.voice_service:
                self.chat_engine.voice_service.on_audio_start = self.visualizer.on_audio_start
                self.chat_engine.voice_service.on_audio_end = self.visualizer.on_audio_end

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
        self._lbl_vision = getattr(self, '_lbl_vision', None)
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
            self._lbl_vision: self.t("chat.vision"),
            self._btn_add_audio: self.t("chat.audio"),
            self._btn_send: self.t("chat.send"),
            self._btn_stop: self.t("chat.stop"),
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

    def init_ui(self):
        # 1. VISTA DE CHAT
        self.chat_frame = tk.Frame(self.container, bg="#2b2b2b")
        self.chat_frame.pack(fill=tk.BOTH, expand=True)
        
        # --- BARRA DE HERRAMIENTAS (Cuádruple Línea) ---
        # Header superior (no se oculta)
        self.top_bar = tk.Frame(self.chat_frame, bg=self.style.get_color("bg_header"), pady=5)
        self.top_bar.pack(fill=tk.X, padx=10)

        # Toolbar colapsable (debajo de top_bar)
        self.toolbar = tk.Frame(self.chat_frame, bg=self.style.get_color("bg_main"), pady=5)
        # self.toolbar.pack(fill=tk.X, padx=10) # Comentado para que inicie minimizado
        self.btn_toggle_toolbar = tk.Button(self.top_bar, text="▶", bg=self.style.get_color("bg_header"), fg=self.style.get_color("text_dim"),
                                            relief="flat", cursor="hand2", command=self._toggle_toolbar,
                                            font=("Arial", 10))
        self.btn_toggle_toolbar.pack(side=tk.LEFT, padx=(0, 5))
        
        # Botón para colapsar chat entero (si se provee comando)
        if self.on_collapse_cmd:
            self.btn_collapse = tk.Button(self.top_bar, text="➡", bg=self.style.get_color("bg_header"), fg=self.style.get_color("accent"),
                                         relief="flat", cursor="hand2", command=self.on_collapse_cmd,
                                         font=("Arial", 10, "bold"))
            self.btn_collapse.pack(side=tk.LEFT, padx=(0, 5))

        tk.Label(self.top_bar, text="ASIMOD Core", bg=self.style.get_color("bg_header"), fg=self.style.get_color("accent"), font=("Arial", 10, "bold")).pack(side=tk.LEFT)
        api_port = self.config.get("api_port", 8000)
        tk.Label(self.top_bar, text=f"API: ON ({api_port})", bg=self.style.get_color("bg_header"), fg="#4EC9B0", font=("Arial", 8, "italic")).pack(side=tk.LEFT, padx=10)
        
        self.btn_api_keys = tk.Button(self.top_bar, text="🔑 Keys", bg=self.style.get_color("bg_header"), fg="#ffd700",
                                      relief="flat", cursor="hand2", command=self.show_api_keys)
        self.btn_api_keys.pack(side=tk.RIGHT, padx=5)
        
        self.btn_settings = tk.Button(self.top_bar, text="⚙️", bg=self.style.get_color("bg_header"), fg=self.style.get_color("accent"),
                                      relief="flat", cursor="hand2", command=self.show_settings)
        self.btn_settings.pack(side=tk.RIGHT)

        # Visualizer (si está habilitado)
        if self.visualizer:
            self.visualizer.create(self.chat_frame)

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
        
        self._lbl_profile_pers = tk.Label(self.profile_bar, text="Personalidad:", bg="#2b2b2b", fg="#888", font=("Arial", 8))
        self._lbl_profile_pers.pack(side=tk.LEFT, padx=(5,0))
        self.ent_char_pers = tk.Entry(self.profile_bar, bg="#333", fg="white", font=("Arial", 8), width=20, relief="flat")
        self.ent_char_pers.pack(side=tk.LEFT, padx=5)

        self._lbl_profile_voice = tk.Label(self.profile_bar, text="Voz:", bg="#2b2b2b", fg="#888", font=("Arial", 8))
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

        self._lbl_llm_model = tk.Label(self.llm_bar, text="Modelo:", bg="#2b2b2b", fg="#888", font=("Arial", 8))
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

        self._lbl_voice_mode = tk.Label(self.voice_bar, text="Modo:", bg="#2b2b2b", fg="#888", font=("Arial", 8))
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

        ttk.Separator(self.chat_frame, orient="horizontal").pack(fill=tk.X, padx=10, pady=5)

        # --- CONTENEDOR CENTRAL (Para Chat o Wizard) ---
        # Se empaqueta primero para que pueda encogerse
        self.middle_container = tk.Frame(self.chat_frame, bg=self.style.get_color("bg_main"))
        self.middle_container.pack(fill=tk.BOTH, expand=True)

        # --- ÁREA DE ENTRADA (FOOTER - SIEMPRE ABAJO) ---
        # Se empaqueta al final con side=BOTTOM para anclarse abajo
        self.input_area = tk.Frame(self.chat_frame, bg=self.style.get_color("bg_main"))
        self.input_area.pack(side=tk.BOTTOM, padx=10, pady=5, fill=tk.X)

        # --- WIZAD DE NUEVO HILO (Hijo de middle_container) ---
        self.new_thread_frame = tk.Frame(self.middle_container, bg="#333", padx=20, pady=10)
        
        self._lbl_new_char_title = tk.Label(self.new_thread_frame, text="✨ NUEVO MODELO DE PERSONAJE", bg="#333", fg="#0078d4", font=("Arial", 10, "bold"))
        self._lbl_new_char_title.pack(pady=(0, 10))
        
        # Campo Nombre
        self._lbl_new_name = tk.Label(self.new_thread_frame, text="Nombre del Personaje:", bg="#333", fg="#ccc", font=("Arial", 8))
        self._lbl_new_name.pack(anchor="w")
        self.ent_new_name = tk.Entry(self.new_thread_frame, bg="#1e1e1e", fg="white", relief="flat", font=("Arial", 10))
        self.ent_new_name.pack(fill=tk.X, pady=(2, 10))

        # Campo Actitud/Personalidad
        self._lbl_new_pers = tk.Label(self.new_thread_frame, text="Actitud / Personalidad:", bg="#333", fg="#ccc", font=("Arial", 8))
        self._lbl_new_pers.pack(anchor="w")
        self.ent_new_pers = tk.Entry(self.new_thread_frame, bg="#1e1e1e", fg="white", relief="flat", font=("Arial", 10))
        self.ent_new_pers.pack(fill=tk.X, pady=(2, 10))

        # Campo Historia (Multi-línea)
        self._lbl_new_hist = tk.Label(self.new_thread_frame, text="Historia / Trasfondo:", bg="#333", fg="#ccc", font=("Arial", 8))
        self._lbl_new_hist.pack(anchor="w")
        self.txt_new_hist = scrolledtext.ScrolledText(self.new_thread_frame, bg="#1e1e1e", fg="white", 
                                                      relief="flat", font=("Arial", 10), height=5)
        self.txt_new_hist.pack(fill=tk.X, pady=(2, 10))

        # Línea de Motor y Voz (NUEVO)
        motor_voice_frame = tk.Frame(self.new_thread_frame, bg="#333")
        motor_voice_frame.pack(fill=tk.X, pady=(2, 10))

        mv_left = tk.Frame(motor_voice_frame, bg="#333")
        mv_left.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self._lbl_new_motor = tk.Label(mv_left, text="Motor de Voz:", bg="#333", fg="#ccc", font=("Arial", 8))
        self._lbl_new_motor.pack(anchor="w")
        self.combo_new_motor = ttk.Combobox(mv_left, state="readonly", font=("Arial", 10))
        self.combo_new_motor.pack(fill=tk.X, padx=(0, 5))
        self.combo_new_motor.bind("<<ComboboxSelected>>", self._on_wizard_motor_change)

        mv_right = tk.Frame(motor_voice_frame, bg="#333")
        mv_right.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self._lbl_new_voice = tk.Label(mv_right, text="Voz:", bg="#333", fg="#ccc", font=("Arial", 8))
        self._lbl_new_voice.pack(anchor="w")
        self.combo_new_voice = ttk.Combobox(mv_right, state="readonly", font=("Arial", 10))
        self.combo_new_voice.pack(fill=tk.X)

        # Botones de Acción
        btn_box = tk.Frame(self.new_thread_frame, bg="#333")
        btn_box.pack(fill=tk.X)
        
        self._btn_create_thread = tk.Button(btn_box, text="Crear e Iniciar Hilo", bg="#0078d4", fg="white", relief="flat", 
                  command=self._confirm_new_thread, padx=10)
        self._btn_create_thread.pack(side=tk.LEFT)
        self._btn_cancel = tk.Button(btn_box, text="Cancelar", bg="#555", fg="white", relief="flat", 
                  command=self._cancel_new_thread, padx=10)
        self._btn_cancel.pack(side=tk.LEFT, padx=10)

        # --- ÁREA DE TEXTO (Hijo de middle_container) ---
        self.chat_display = scrolledtext.ScrolledText(self.middle_container, state='disabled', 
                                                      bg=self.style.get_color("bg_dark"), fg=self.style.get_color("text_main"), 
                                                      font=("Consolas", 10), wrap=tk.WORD)
        self.chat_display.pack(padx=10, fill=tk.BOTH, expand=True)

        # --- ÁREA DE ENTRADA (ya creada arriba en footer) ---

        # FILA 1: Campo de texto (Ocupa todo el ancho)
        self.input_field = tk.Entry(self.input_area, bg=self.style.get_color("bg_input"), fg=self.style.get_color("text_main"), 
                                    insertbackground=self.style.get_color("text_main"), relief="flat", font=("Arial", 10))
        self.input_field.pack(fill=tk.X, ipady=5, pady=(0, 5))
        self.input_field.bind("<Return>", lambda e: self.handle_send())

        # FILA 2: Botones y Controles
        btns_frame = tk.Frame(self.input_area, bg=self.style.get_color("bg_main"))
        btns_frame.pack(fill=tk.X)

        # Vision
        self._lbl_vision = tk.Label(btns_frame, text="👁️ Vision:", bg=self.style.get_color("bg_main"), fg=self.style.get_color("text_dim"), font=("Arial", 8))
        self._lbl_vision.pack(side=tk.LEFT)
        self.combo_vision = ttk.Combobox(btns_frame, values=["None", "Cam", "Screen", "Imagen"], state="readonly", width=8)
        self.combo_vision.set("None")
        self.combo_vision.pack(side=tk.LEFT, padx=5)
        self.combo_vision.bind("<<ComboboxSelected>>", self._on_vision_change)

        # Audio
        self._btn_add_audio = tk.Button(btns_frame, text="➕ Audio", bg=self.style.get_color("btn_bg"), fg=self.style.get_color("btn_fg"),
                                      relief="flat", command=self.handle_add_audio, cursor="hand2")
        self._btn_add_audio.pack(side=tk.LEFT, padx=5)

        # Enviar (Derecha)
        self._btn_send = tk.Button(btns_frame, text=self.t("chat.send_btn"), bg=self.style.get_color("accent"), fg=self.style.get_color("btn_fg"),
                                  relief="flat", command=self.handle_send, cursor="hand2", width=8)
        self._btn_send.pack(side=tk.RIGHT, padx=2)

        # Stop (Derecha)
        self._btn_stop = tk.Button(btns_frame, text="⏹ Stop", bg="#d43f3a", fg="white",
                                  relief="flat", command=self._stop_audio, cursor="hand2")
        self._btn_stop.pack(side=tk.RIGHT, padx=2)

        # STT Mode (Derecha)
        stt_modes = ["OFF", "CHAT", "VOICE_COMMAND", "AGENT", "AGENT_AUDIO"]
        self.combo_stt_mode = ttk.Combobox(btns_frame, values=stt_modes, state="readonly", width=12)
        self.combo_stt_mode.pack(side=tk.RIGHT, padx=5)
        self.combo_stt_mode.bind("<<ComboboxSelected>>", self._on_stt_mode_change)

        self._lbl_stt_mode = tk.Label(btns_frame, text="STT:", bg=self.style.get_color("bg_main"), fg=self.style.get_color("text_dim"), font=("Arial", 8))
        self._lbl_stt_mode.pack(side=tk.RIGHT, padx=(5, 0))

        # Línea de archivos seleccionados
        self.lbl_files = tk.Label(self.chat_frame, text="", bg=self.style.get_color("bg_main"), fg="#4EC9B0", font=("Arial", 8, "italic"))
        self.lbl_files.pack(fill=tk.X, padx=10)

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
        
        # 2. Aplicar perfil (incluyendo motor y voz)
        self.chat_engine.memory.update_profile(
            name=name if name else None,
            personality=pers if pers else None,
            history=hist if hist else None,
            voice_id=voice_id if voice_id else None,
            voice_provider=motor if motor != "None" else None
        )
        
        # 3. Finalizar selección
        self.last_valid_thread = new_id
        self._refresh_memories()
        self.combo_memory.set(new_id)
        self.config.set("active_thread", new_id)
        self._set_wizard_visibility(False)
        self._on_memory_change(None) # Recargar UI (historial vacío)

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
            voice_provider=motor if motor != "None" else None
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
            self.after(0, lambda: self._update_models_combo(models))
        except Exception as e:
            print(f"[UI] Error loading models: {e}")
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

    def _on_system_msg_notified(self, text, color=None):
        """Muestra un mensaje del sistema en el chat (sin voz)."""
        color = color or "#888"
        self.after(0, lambda: self._append_message("ASIMOD", text, color))

    def _on_voice_command(self, command_matched, text):
        """Callback cuando se reconoce un comando de voz."""
        if command_matched:
            winsound.Beep(800, 80)
            self.after(0, lambda: self._append_message("SYSTEM", f"Voice command recognized: {text} → {command_matched}", "#FF6B6B"))
        elif self.var_test_mode.get():
            text_lower = text.lower()
            if "comando" in text_lower or "prueba" in text_lower:
                winsound.Beep(800, 80)
                self.after(0, lambda: self._append_message("TEST MODE", f"Command detected: {text}", "#4ECDC4"))
        
        if text:
            # Solo mostrar el texto reconocido en el input si NO está siendo capturado por un módulo
            if not getattr(self.chat_engine, "stt_captured_by_module", False):
                self.after(0, lambda: self._display_recognized_text(text))
            else:
                # Opcional: Podríamos limpiar el input si algo quedó allí
                self.after(0, lambda: self.input_field.delete(0, tk.END))

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
        self.chat_frame.pack_forget()
        self.api_keys_frame.pack_forget()
        self.settings_frame.pack(fill=tk.BOTH, expand=True)

    def show_api_keys(self):
        self.chat_frame.pack_forget()
        self.settings_frame.pack_forget()
        self.api_keys_frame.pack(fill=tk.BOTH, expand=True)

    def show_chat(self):
        self.settings_frame.pack_forget()
        self.api_keys_frame.pack_forget()
        self.chat_frame.pack(fill=tk.BOTH, expand=True)
        if self.toolbar_visible:
            if self.visualizer and self.visualizer._frame:
                self.toolbar.pack(fill=tk.X, padx=10, before=self.visualizer._frame)
            elif hasattr(self, 'middle_container'):
                self.toolbar.pack(fill=tk.X, padx=10, before=self.middle_container)
            else:
                self.toolbar.pack(fill=tk.X, padx=10)
            self.btn_toggle_toolbar.config(text="▼")
        self._on_provider_change(None)
        self._on_voice_change(None)

    def _toggle_toolbar(self):
        """Colapsa o expande el toolbar"""
        if self.toolbar_visible:
            self.toolbar.pack_forget()
            self.btn_toggle_toolbar.config(text="▶")
        else:
            if self.visualizer and self.visualizer._frame:
                self.toolbar.pack(fill=tk.X, padx=10, before=self.visualizer._frame)
            elif hasattr(self, 'middle_container'):
                self.toolbar.pack(fill=tk.X, padx=10, before=self.middle_container)
            else:
                self.toolbar.pack(fill=tk.X, padx=10)
            self.btn_toggle_toolbar.config(text="▼")
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
            # Notificar al hilo principal para actualizar UI
            self.after(0, self._handle_response, result)
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
        else:
            self._append_message(self.t("chat.system"), str(result), "red")

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
