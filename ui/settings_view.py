import tkinter as tk
import os
from tkinter import ttk, messagebox

class SettingsView(tk.Frame):
    """
    Panel de configuración embebido dentro del ChatWidget.
    """
    def __init__(self, parent, config_service, locale_service, back_callback):
        super().__init__(parent, bg="#2b2b2b")
        self.config = config_service
        self.locale_service = locale_service
        self.back_callback = back_callback
        self._opencode_running = False
        self._opencode_process = None
        self.init_ui()

    def init_ui(self):
        # Header con botón volver
        header = tk.Frame(self, bg="#2b2b2b")
        header.pack(fill=tk.X, pady=(10, 5))
        
        btn_back = tk.Button(header, text="← Volver al Chat", bg="#2b2b2b", fg="#0078d4",
                             relief="flat", cursor="hand2", command=self.back_callback)
        btn_back.pack(side=tk.LEFT, padx=10)

        title = tk.Label(self, text="⚙️ Configuración Global", 
                         bg="#2b2b2b", fg="white", font=("Arial", 12, "bold"))
        title.pack(pady=10)

        # Selector de idioma
        lang_frame = tk.Frame(self, bg="#2b2b2b")
        lang_frame.pack(fill=tk.X, padx=20, pady=(0, 10))
        
        tk.Label(lang_frame, text="Idioma:", bg="#2b2b2b", fg="#888", font=("Arial", 10)).pack(side=tk.LEFT)
        
        languages = self.locale_service.list_available_languages()
        self.lang_combo = ttk.Combobox(lang_frame, values=list(languages.values()), state="readonly", width=15)
        self.lang_combo.pack(side=tk.LEFT, padx=10)
        
        current_lang_code = self.locale_service.get_current_language()
        self.lang_combo.set(languages.get(current_lang_code, "Español"))
        self.lang_combo.bind("<<ComboboxSelected>>", self._on_language_change)

        # Visualizer Toggle
        viz_frame = tk.Frame(self, bg="#2b2b2b")
        viz_frame.pack(fill=tk.X, padx=20, pady=(0, 10))
        
        tk.Label(viz_frame, text="Visualizador:", bg="#2b2b2b", fg="#888", font=("Arial", 10)).pack(side=tk.LEFT)
        
        self._viz_enabled = tk.BooleanVar(value=self.config.get("visualizer_enabled", False))
        self.chk_visualizer = tk.Checkbutton(
            viz_frame, 
            text="Activar visualizador de audio",
            bg="#2b2b2b", 
            fg="white",
            selectcolor="#2b2b2b",
            activebackground="#2b2b2b",
            activeforeground="white",
            variable=self._viz_enabled,
            command=self._on_visualizer_toggle
        )
        self.chk_visualizer.pack(side=tk.LEFT, padx=10)

        # GGUF Models Path
        gguf_path_frame = tk.Frame(self, bg="#2b2b2b")
        gguf_path_frame.pack(fill=tk.X, padx=20, pady=(0, 10))
        
        tk.Label(gguf_path_frame, text="GGUF Path:", bg="#2b2b2b", fg="#888", font=("Arial", 10)).pack(side=tk.LEFT)
        
        self.gguf_path_entry = tk.Entry(gguf_path_frame, bg="#3c3c3c", fg="white", insertbackground="white", relief="flat", width=30)
        self.gguf_path_entry.pack(side=tk.LEFT, padx=10)
        self.gguf_path_entry.insert(0, self.config.get("gguf_models_dir", ""))
        
        btn_refresh_models = tk.Button(gguf_path_frame, text="↻", bg="#3c3c3c", fg="white", 
                                       relief="flat", width=3, command=self._refresh_gguf_models)
        btn_refresh_models.pack(side=tk.LEFT)

        # GGUF Model Selector
        gguf_model_frame = tk.Frame(self, bg="#2b2b2b")
        gguf_model_frame.pack(fill=tk.X, padx=20, pady=(0, 10))
        
        tk.Label(gguf_model_frame, text="Modelo GGUF:", bg="#2b2b2b", fg="#888", font=("Arial", 10)).pack(side=tk.LEFT)
        
        self.gguf_model_combo = ttk.Combobox(gguf_model_frame, state="readonly", width=30)
        self.gguf_model_combo.pack(side=tk.LEFT, padx=10)
        self._populate_gguf_models()

        # Contenedor con scroll si fuera necesario (aunque 6 campos caben bien)
        container = tk.Frame(self, bg="#2b2b2b")
        container.pack(padx=20, fill=tk.BOTH, expand=True)

        self._entries = {}

        # Definición de campos
        fields = [
            ("Ollama URL", "ollama_url", False),
            ("LLM Studio URL", "llmstudio_url", False),
            ("OpenCode URL", "opencode_url", False),
            ("OpenCode API Key", "opencode_api_key", True),
            ("OpenAI Key", "openai_key", True),
            ("Anthropic Key", "anthropic_key", True),
            ("Gemini Key", "gemini_key", True),
            ("DeepSeek Key", "deepseek_key", True),
            ("Groq Key", "groq_key", True),
            ("Perplexity Key", "perplexity_key", True),
            ("Ruta Audios", "voice_save_path", False),
            ("Puerto API", "api_port", False),
        ]

        for i, (label, key, is_secret) in enumerate(fields):
            lbl = tk.Label(container, text=f"{label}:", bg="#2b2b2b", fg="#888", font=("Arial", 9))
            lbl.grid(row=i, column=0, sticky="w", pady=8, padx=(0, 10))
            
            ent = tk.Entry(container, bg="#3c3c3c", fg="white", insertbackground="white", 
                           relief="flat", show="*" if is_secret else "")
            ent.grid(row=i, column=1, sticky="ew", pady=8)
            ent.insert(0, self.config.get(key, ""))
            self._entries[key] = ent

        container.columnconfigure(1, weight=1)

        # Voice Playback Mode
        playback_frame = tk.Frame(self, bg="#2b2b2b")
        playback_frame.pack(fill=tk.X, padx=20, pady=(10, 0))

        tk.Label(playback_frame, text="Reproducción de Audio:", bg="#2b2b2b", fg="#888", font=("Arial", 10)).pack(side=tk.LEFT)
        
        self.combo_playback_mode = ttk.Combobox(
            playback_frame, 
            values=["Interrumpir anterior", "Esperar fin reproducción"], 
            state="readonly", 
            width=25
        )
        self.combo_playback_mode.pack(side=tk.LEFT, padx=10)
        
        current_mode = self.config.get("voice_playback_mode", "interrupt")
        self.combo_playback_mode.set("Interrumpir anterior" if current_mode == "interrupt" else "Esperar fin reproducción")
        self.combo_playback_mode.bind("<<ComboboxSelected>>", self._on_playback_mode_change)

        # Botón Guardar
        save_btn = tk.Button(self, text="Guardar Cambios", bg="#0078d4", fg="white", 
                             font=("Arial", 10, "bold"), relief="flat", width=20, command=self.save)
        save_btn.pack(pady=20, ipady=5)

        # Botón OpenCode Server
        opencode_frame = tk.Frame(self, bg="#2b2b2b")
        opencode_frame.pack(fill=tk.X, padx=20, pady=(10, 0))

        self.btn_opencode = tk.Button(
            opencode_frame, 
            text="🔴 Iniciar OpenCode Server", 
            bg="#e74c3c", fg="white",
            font=("Arial", 10, "bold"), 
            relief="flat", 
            width=25, 
            command=self._toggle_opencode_server
        )
        self.btn_opencode.pack(side=tk.LEFT)

        self.lbl_opencode_status = tk.Label(
            opencode_frame, 
            text="Detenido", 
            bg="#2b2b2b", 
            fg="#888", 
            font=("Arial", 9)
        )
        self.lbl_opencode_status.pack(side=tk.LEFT, padx=10)

        self._check_opencode_status()

    def _on_language_change(self, event):
        selected_name = self.lang_combo.get()
        languages = self.locale_service.list_available_languages()
        lang_code = next((code for code, name in languages.items() if name == selected_name), "es")
        self.locale_service.set_language(lang_code)
        
        default_voice = self.locale_service.get_default_voice()
        self.config.set("voice_id", default_voice["voice_id"])
        
        messagebox.showinfo("Idioma cambiado", f"Idioma cambiado a: {selected_name}\nLos cambios se aplicarán al recargar.")

    def _on_playback_mode_change(self, event):
        selected = self.combo_playback_mode.get()
        mode = "interrupt" if selected == "Interrumpir anterior" else "wait"
        self.config.set("voice_playback_mode", mode)

    def _on_visualizer_toggle(self):
        enabled = self._viz_enabled.get()
        self.config.set("visualizer_enabled", enabled)
        messagebox.showinfo("Visualizador", "El visualizador se activará al reiniciar la aplicación.")

    def _populate_gguf_models(self):
        models_dir = self.gguf_path_entry.get().strip()
        if not models_dir:
            models_dir = os.path.join(os.path.expanduser("~"), "Desktop", "ModelosGGUF")
        
        extensions = ('.gguf', '.bin', '.safetensors')
        models = []
        
        if os.path.exists(models_dir):
            for f in os.listdir(models_dir):
                if f.lower().endswith(extensions):
                    models.append(f)
        
        self.gguf_model_combo['values'] = sorted(models) if models else [""]
        if models:
            current_model = self.config.get("last_model", "")
            if current_model in models:
                self.gguf_model_combo.set(current_model)
            else:
                self.gguf_model_combo.current(0)
        else:
            self.gguf_model_combo.set("")

    def _refresh_gguf_models(self):
        self._populate_gguf_models()
        messagebox.showinfo("Actualizado", "Lista de modelos GGUF actualizada.")

    def save(self):
        gguf_path = self.gguf_path_entry.get().strip()
        if gguf_path:
            self.config.set("gguf_models_dir", gguf_path)
        
        selected_model = self.gguf_model_combo.get()
        if selected_model:
            self.config.set("last_model", selected_model)
        
        for key, entry in self._entries.items():
            self.config.set(key, entry.get())
        
        messagebox.showinfo("Éxito", "Toda la configuración ha sido guardada.")
        self.back_callback()

    def _check_opencode_status(self):
        import requests
        try:
            url = self.config.get("opencode_url", "http://localhost:9090")
            resp = requests.get(f"{url}/health", timeout=2)
            if resp.status_code == 200:
                self.lbl_opencode_status.config(text="🟢 Activo", fg="#2ecc71")
                self.btn_opencode.config(text="⏹️ Detener OpenCode Server", bg="#95a5a6")
                self._opencode_running = True
                return
        except:
            pass
        self.lbl_opencode_status.config(text="🔴 Detenido", fg="#e74c3c")
        self.btn_opencode.config(text="🔴 Iniciar OpenCode Server", bg="#e74c3c")
        self._opencode_running = False

    def _toggle_opencode_server(self):
        if self._opencode_running:
            if hasattr(self, '_opencode_process') and self._opencode_process:
                self._opencode_process.terminate()
            self._check_opencode_status()
            messagebox.showinfo("OpenCode", "Servidor detenido.")
        else:
            import subprocess
            import threading
            def start_server():
                try:
                    self._opencode_process = subprocess.Popen(
                        ["opencode", "serve", "--port", "9090"],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE
                    )
                except Exception as e:
                    print(f"Error starting OpenCode: {e}")
            
            thread = threading.Thread(target=start_server, daemon=True)
            thread.start()
            
            import time
            for i in range(10):
                time.sleep(1)
                self._check_opencode_status()
                if self._opencode_running:
                    break
            
            if self._opencode_running:
                messagebox.showinfo("OpenCode", "Servidor iniciado correctamente!")
            else:
                messagebox.showwarning("OpenCode", "No se pudo iniciar. ¿Tienes opencode instalado?")
