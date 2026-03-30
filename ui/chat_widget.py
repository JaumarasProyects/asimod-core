import tkinter as tk
from tkinter import ttk, scrolledtext, filedialog
from core.ports.chat_port import ChatPort
from ui.settings_view import SettingsView
from core.services.stt_service import STTService

class ChatWidget(tk.Frame):
    """
    Widget de Chat avanzado con controles de IA, Voz (TTS) y Reconocimiento (STT).
    """
    def __init__(self, parent, chat_engine: ChatPort, config_service):
        super().__init__(parent, bg="#2b2b2b")
        self.chat_engine = chat_engine
        self.config = config_service
        
        # Vincular STT Service del engine con la UI
        self.stt_service = self.chat_engine.stt_service
        self.chat_engine.on_stt_finished_cb = self._on_stt_finished
        
        # Contenedor principal para las vistas
        self.container = tk.Frame(self, bg="#2b2b2b")
        self.container.pack(fill=tk.BOTH, expand=True)

        self.init_ui()
        self._load_initial_state()

    def init_ui(self):
        # 1. VISTA DE CHAT
        self.chat_frame = tk.Frame(self.container, bg="#2b2b2b")
        self.chat_frame.pack(fill=tk.BOTH, expand=True)
        
        # --- BARRA DE HERRAMIENTAS (Cuádruple Línea) ---
        self.toolbar = tk.Frame(self.chat_frame, bg="#2b2b2b", pady=5)
        self.toolbar.pack(fill=tk.X, padx=10)

        # LÍNEA 1: Cabecera (Título + API + Configuración)
        self.header_bar = tk.Frame(self.toolbar, bg="#2b2b2b")
        self.header_bar.pack(fill=tk.X, pady=(0, 5))

        tk.Label(self.header_bar, text="ASIMOD Core", bg="#2b2b2b", fg="#0078d4", font=("Arial", 10, "bold")).pack(side=tk.LEFT)
        # Indicador de API
        api_port = self.config.get("api_port", 8000)
        tk.Label(self.header_bar, text=f"🌐 API: ON ({api_port})", bg="#2b2b2b", fg="#4EC9B0", font=("Arial", 8, "italic")).pack(side=tk.LEFT, padx=10)
        
        self.btn_settings = tk.Button(self.header_bar, text="⚙️", bg="#2b2b2b", fg="#0078d4",
                                      relief="flat", cursor="hand2", command=self.show_settings)
        self.btn_settings.pack(side=tk.RIGHT)

        # LÍNEA 2: Controles de IA (Motor y Modelo)
        self.llm_bar = tk.Frame(self.toolbar, bg="#2b2b2b", pady=2)
        self.llm_bar.pack(fill=tk.X)

        tk.Label(self.llm_bar, text="Motor AI:", bg="#2b2b2b", fg="#888", font=("Arial", 8)).pack(side=tk.LEFT)
        allowed_backends = self.chat_engine.get_providers_list()
        self.combo_provider = ttk.Combobox(self.llm_bar, values=allowed_backends, state="readonly", width=12)
        self.combo_provider.pack(side=tk.LEFT, padx=5)
        self.combo_provider.bind("<<ComboboxSelected>>", self._on_provider_change)

        tk.Label(self.llm_bar, text="Modelo:", bg="#2b2b2b", fg="#888", font=("Arial", 8)).pack(side=tk.LEFT, padx=(5, 0))
        self.combo_model = ttk.Combobox(self.llm_bar, state="readonly", width=15)
        self.combo_model.pack(side=tk.LEFT, padx=5)
        self.combo_model.bind("<<ComboboxSelected>>", self._on_model_change)

        # LÍNEA 3: Controles de Salida de Voz (TTS)
        self.voice_bar = tk.Frame(self.toolbar, bg="#2b2b2b", pady=2)
        self.voice_bar.pack(fill=tk.X)

        tk.Label(self.voice_bar, text="TTS (Salida):", bg="#2b2b2b", fg="#888", font=("Arial", 8)).pack(side=tk.LEFT)
        voice_providers = ["None", "Edge TTS", "Local TTS"]
        self.combo_voice = ttk.Combobox(self.voice_bar, values=voice_providers, state="readonly", width=10)
        self.combo_voice.pack(side=tk.LEFT, padx=5)
        self.combo_voice.bind("<<ComboboxSelected>>", self._on_voice_change)

        tk.Label(self.voice_bar, text="Modo:", bg="#2b2b2b", fg="#888", font=("Arial", 8)).pack(side=tk.LEFT, padx=(5, 0))
        voice_modes = ["autoplay", "path"]
        self.combo_voice_mode = ttk.Combobox(self.voice_bar, values=voice_modes, state="readonly", width=10)
        self.combo_voice_mode.pack(side=tk.LEFT, padx=5)
        self.combo_voice_mode.bind("<<ComboboxSelected>>", self._on_voice_mode_change)

        self.combo_voice_id = ttk.Combobox(self.voice_bar, state="readonly", width=25)
        self.combo_voice_id.pack(side=tk.LEFT, padx=5)
        self.combo_voice_id.bind("<<ComboboxSelected>>", self._on_voice_id_change)

        # LÍNEA 4: Controles de Entrada de Voz (STT)
        self.stt_bar = tk.Frame(self.toolbar, bg="#2b2b2b", pady=2)
        self.stt_bar.pack(fill=tk.X)

        tk.Label(self.stt_bar, text="STT (Entrada):", bg="#2b2b2b", fg="#888", font=("Arial", 8)).pack(side=tk.LEFT)
        stt_providers = ["None", "Standard (Google)"]
        self.combo_stt_provider = ttk.Combobox(self.stt_bar, values=stt_providers, state="readonly", width=20)
        self.combo_stt_provider.pack(side=tk.LEFT, padx=5)
        self.combo_stt_provider.bind("<<ComboboxSelected>>", self._on_stt_provider_change)

        tk.Label(self.stt_bar, text="Modo:", bg="#2b2b2b", fg="#888", font=("Arial", 8)).pack(side=tk.LEFT, padx=(5, 0))
        stt_modes = ["OFF", "micro", "archive"]
        self.combo_stt_mode = ttk.Combobox(self.stt_bar, values=stt_modes, state="readonly", width=10)
        self.combo_stt_mode.pack(side=tk.LEFT, padx=5)
        self.combo_stt_mode.bind("<<ComboboxSelected>>", self._on_stt_mode_change)

        ttk.Separator(self.chat_frame, orient="horizontal").pack(fill=tk.X, padx=10, pady=5)

        # --- ÁREA DE TEXTO ---
        self.chat_display = scrolledtext.ScrolledText(self.chat_frame, state='disabled', 
                                                      bg="#1e1e1e", fg="white", 
                                                      font=("Consolas", 10), wrap=tk.WORD)
        self.chat_display.pack(padx=10, pady=5, fill=tk.BOTH, expand=True)

        # --- BARRA DE ENTRADA ---
        input_frame = tk.Frame(self.chat_frame, bg="#2b2b2b")
        input_frame.pack(padx=10, pady=10, fill=tk.X)

        # Botón Add Audio
        self.btn_add_audio = tk.Button(input_frame, text="➕ Audio", bg="#444", fg="white",
                                      relief="flat", command=self.handle_add_audio, cursor="hand2")
        self.btn_add_audio.pack(side=tk.LEFT, padx=(0, 5))

        self.input_field = tk.Entry(input_frame, bg="#3c3c3c", fg="white", 
                                    insertbackground="white", relief="flat")
        self.input_field.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5), ipady=3)
        self.input_field.bind("<Return>", lambda e: self.handle_send())

        self.send_btn = tk.Button(input_frame, text="Enviar", bg="#0078d4", fg="white",
                                  relief="flat", command=self.handle_send, cursor="hand2")
        self.send_btn.pack(side=tk.RIGHT)

        # 2. VISTA DE CONFIGURACIÓN
        self.settings_frame = SettingsView(self.container, self.config, self.show_chat)

    def _load_initial_state(self):
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
        self.combo_stt_mode.set(self.config.get("stt_mode", "none"))
        self.stt_service.update_adapter()

    def _on_provider_change(self, event):
        provider = self.combo_provider.get()
        self.config.set("last_provider", provider)
        self.chat_engine.switch_provider(provider)
        models = self.chat_engine.get_available_models()
        self.combo_model['values'] = models
        last_model = self.config.get("last_model", "")
        if models:
            if last_model in models: self.combo_model.set(last_model)
            else:
                self.combo_model.current(0)
                self.config.set("last_model", self.combo_model.get())

    def _on_model_change(self, event):
        self.config.set("last_model", self.combo_model.get())

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
        self.settings_frame.pack(fill=tk.BOTH, expand=True)

    def show_chat(self):
        self.settings_frame.pack_forget()
        self.chat_frame.pack(fill=tk.BOTH, expand=True)
        self._on_provider_change(None)
        self._on_voice_change(None)

    def handle_send(self):
        text = self.input_field.get()
        if not text: return
        self._append_message("Tú", text, "#569cd6")
        self.input_field.delete(0, tk.END)
        self.update()
        model = self.combo_model.get()
        response = self.chat_engine.send_message(text, model=model)
        self._append_message("AI", response, "#ce9178")

    def _append_message(self, sender, text, color):
        self.chat_display.config(state='normal')
        self.chat_display.insert(tk.END, f"{sender}: ", ("sender",))
        self.chat_display.insert(tk.END, f"{text}\n\n")
        self.chat_display.tag_config("sender", foreground=color, font=("Consolas", 10, "bold"))
        self.chat_display.see(tk.END)
        self.chat_display.config(state='disabled')
