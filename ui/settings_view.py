import tkinter as tk
import os
import subprocess
import threading
import time
from tkinter import ttk, messagebox
from core.services.visualizer_service import VisualizerService
from core.tunnels.run_tunnel import get_tunnel_command

class SettingsView(tk.Frame):
    """
    Panel de configuración embebido dentro del ChatWidget.
    """
    def __init__(self, parent, config_service, locale_service, back_callback, style_service):
        self.style = style_service
        super().__init__(parent, bg=self.style.get_color("bg_main"))
        self.config = config_service
        self.locale_service = locale_service
        self.back_callback = back_callback
        self._opencode_running = False
        self._opencode_process = None
        self._tunnel_process = None
        self._tunnel_temp_file = None
        self._tunnel_thread = None
        self._force_quick_tunnel = tk.BooleanVar(value=False)
        self.init_ui()

    def init_ui(self):
        # Header con botón volver
        header = tk.Frame(self, bg=self.style.get_color("bg_main"))
        header.pack(fill=tk.X, pady=(10, 5))
        
        btn_back = tk.Button(header, text="← Volver al Chat", bg=self.style.get_color("bg_main"), fg=self.style.get_color("accent"),
                             relief="flat", cursor="hand2", command=self.back_callback)
        btn_back.pack(side=tk.LEFT, padx=10)

        title = tk.Label(self, text="⚙️ Configuración Global", 
                         bg=self.style.get_color("bg_main"), fg=self.style.get_color("text_main"), font=("Arial", 12, "bold"))
        title.pack(pady=10)

        # Selector de idioma
        lang_frame = tk.Frame(self, bg=self.style.get_color("bg_main"))
        lang_frame.pack(fill=tk.X, padx=20, pady=(0, 10))
        
        tk.Label(lang_frame, text="Idioma:", bg=self.style.get_color("bg_main"), fg=self.style.get_color("text_dim"), font=("Arial", 10)).pack(side=tk.LEFT)
        
        languages = self.locale_service.list_available_languages()
        self.lang_combo = ttk.Combobox(lang_frame, values=list(languages.values()), state="readonly", width=15)
        self.lang_combo.pack(side=tk.LEFT, padx=10)
        
        current_lang_code = self.locale_service.get_current_language()
        self.lang_combo.set(languages.get(current_lang_code, "Español"))
        self.lang_combo.bind("<<ComboboxSelected>>", self._on_language_change)

        # --- TEMA VISUAL (NUEVO) ---
        theme_frame = tk.Frame(self, bg=self.style.get_color("bg_main"))
        theme_frame.pack(fill=tk.X, padx=20, pady=(0, 10))
        
        tk.Label(theme_frame, text="Tema Visual:", bg=self.style.get_color("bg_main"), fg=self.style.get_color("text_dim"), font=("Arial", 10)).pack(side=tk.LEFT)
        
        themes = self.style.get_available_styles_names()
        self.theme_combo = ttk.Combobox(theme_frame, values=list(themes.values()), state="readonly", width=15)
        self.theme_combo.pack(side=tk.LEFT, padx=10)
        
        current_style_id = self.config.get("current_style", "dark_carbon")
        self.theme_combo.set(themes.get(current_style_id, "Dark Carbon"))
        self.theme_combo.bind("<<ComboboxSelected>>", self._on_theme_change)

        # Modules Path
        mod_path_frame = tk.Frame(self, bg=self.style.get_color("bg_main"))
        mod_path_frame.pack(fill=tk.X, padx=20, pady=(0, 10))
        
        tk.Label(mod_path_frame, text="Ruta de Módulos:", bg=self.style.get_color("bg_main"), fg=self.style.get_color("text_dim"), font=("Arial", 10)).pack(side=tk.LEFT)
        self.mod_path_entry = tk.Entry(mod_path_frame, bg=self.style.get_color("bg_input"), fg=self.style.get_color("text_main"), font=("Arial", 10), width=30, relief="flat")
        self.mod_path_entry.pack(side=tk.LEFT, padx=10)
        self.mod_path_entry.insert(0, self.config.get("modules_path", "modules"))
        
        tk.Button(mod_path_frame, text="Guardar Ruta", command=self._on_save_mod_path, 
                  bg="#444", fg="white", relief="flat", font=("Arial", 8)).pack(side=tk.LEFT)

        # Visualizer Toggle
        viz_frame = tk.Frame(self, bg=self.style.get_color("bg_main"))
        viz_frame.pack(fill=tk.X, padx=20, pady=(0, 10))
        
        tk.Label(viz_frame, text="Visualizador:", bg=self.style.get_color("bg_main"), fg=self.style.get_color("text_dim"), font=("Arial", 10)).pack(side=tk.LEFT)
        
        self._viz_enabled = tk.BooleanVar(value=self.config.get("visualizer_enabled", False))
        self.chk_visualizer = tk.Checkbutton(
            viz_frame, 
            text="Activar visualizador de audio",
            bg=self.style.get_color("bg_main"), 
            fg=self.style.get_color("text_main"),
            selectcolor=self.style.get_color("bg_main"),
            activebackground=self.style.get_color("bg_main"),
            activeforeground=self.style.get_color("text_main"),
            variable=self._viz_enabled,
            command=self._on_visualizer_toggle
        )
        self.chk_visualizer.pack(side=tk.LEFT, padx=10)
        
        # Tipo de Visualizador (Dropdown modular)
        v_type_frame = tk.Frame(self, bg=self.style.get_color("bg_main"))
        v_type_frame.pack(fill=tk.X, padx=20, pady=(0, 10))
        tk.Label(v_type_frame, text="Tipo de Visualizador:", bg=self.style.get_color("bg_main"), fg=self.style.get_color("text_dim"), font=("Arial", 10)).pack(side=tk.LEFT)
        
        v_service = VisualizerService(self.config)
        visualizers = v_service.get_visualizer_list()
        
        self.v_type_combo = ttk.Combobox(v_type_frame, values=visualizers, state="readonly", width=15)
        self.v_type_combo.pack(side=tk.LEFT, padx=10)
        
        current_v = self.config.get("visualizer_type", "waveform")
        if current_v in visualizers:
            self.v_type_combo.set(current_v)
        elif visualizers:
            self.v_type_combo.current(0)
            
        self.v_type_combo.bind("<<ComboboxSelected>>", self._on_v_type_change)
        
        # Modular System Toggle
        mod_frame = tk.Frame(self, bg=self.style.get_color("bg_main"))
        mod_frame.pack(fill=tk.X, padx=20, pady=(0, 10))
        
        tk.Label(mod_frame, text="Sistema Modular:", bg=self.style.get_color("bg_main"), fg=self.style.get_color("text_dim"), font=("Arial", 10)).pack(side=tk.LEFT)
        
        self._modules_enabled = tk.BooleanVar(value=self.config.get("modules_enabled", True))
        self.chk_modules = tk.Checkbutton(
            mod_frame, 
            text="Cargar barra de módulos y área de apps",
            bg=self.style.get_color("bg_main"), 
            fg=self.style.get_color("text_main"),
            selectcolor=self.style.get_color("bg_input"),
            activebackground=self.style.get_color("bg_main"),
            activeforeground=self.style.get_color("text_main"),
            variable=self._modules_enabled,
            command=self._on_modules_toggle
        )
        self.chk_modules.pack(side=tk.LEFT, padx=10)

        # GGUF Models Path
        gguf_path_frame = tk.Frame(self, bg=self.style.get_color("bg_main"))
        gguf_path_frame.pack(fill=tk.X, padx=20, pady=(0, 10))
        
        tk.Label(gguf_path_frame, text="GGUF Path:", bg=self.style.get_color("bg_main"), fg=self.style.get_color("text_dim"), font=("Arial", 10)).pack(side=tk.LEFT)
        
        self.gguf_path_entry = tk.Entry(gguf_path_frame, bg=self.style.get_color("bg_input"), fg=self.style.get_color("text_main"), insertbackground=self.style.get_color("text_main"), relief="flat", width=30)
        self.gguf_path_entry.pack(side=tk.LEFT, padx=10)
        self.gguf_path_entry.insert(0, self.config.get("gguf_models_dir", ""))
        
        btn_refresh_models = tk.Button(gguf_path_frame, text="↻", bg=self.style.get_color("bg_input"), fg=self.style.get_color("text_main"), 
                                       relief="flat", width=3, command=self._refresh_gguf_models)
        btn_refresh_models.pack(side=tk.LEFT)

        # GGUF Model Selector
        gguf_model_frame = tk.Frame(self, bg=self.style.get_color("bg_main"))
        gguf_model_frame.pack(fill=tk.X, padx=20, pady=(0, 10))
        
        tk.Label(gguf_model_frame, text="Modelo GGUF:", bg=self.style.get_color("bg_main"), fg=self.style.get_color("text_dim"), font=("Arial", 10)).pack(side=tk.LEFT)
        
        self.gguf_model_combo = ttk.Combobox(gguf_model_frame, state="readonly", width=30)
        self.gguf_model_combo.pack(side=tk.LEFT, padx=10)
        self._populate_gguf_models()

        # --- SECCIÓN TÚNEL CLOUDFLARE ---
        tunnel_frame = tk.Frame(self, bg=self.style.get_color("bg_main"))
        tunnel_frame.pack(fill=tk.X, padx=20, pady=(10, 5))

        # Fila 1: Título, Indicador, Estado, Botón
        row1 = tk.Frame(tunnel_frame, bg=self.style.get_color("bg_main"))
        row1.pack(fill=tk.X)

        tk.Label(row1, text="🌐 Túnel Cloudflare:", bg=self.style.get_color("bg_main"), fg=self.style.get_color("text_dim"), font=("Arial", 10)).pack(side=tk.LEFT)
        self.tunnel_canvas = tk.Canvas(row1, width=15, height=15, bg=self.style.get_color("bg_main"), highlightthickness=0)
        self.tunnel_canvas.pack(side=tk.LEFT, padx=10)
        self.tunnel_indicator = self.tunnel_canvas.create_oval(2, 2, 13, 13, fill="#555", outline="")
        self.lbl_tunnel_status = tk.Label(row1, text="Detenido", bg=self.style.get_color("bg_main"), fg="#aaa", font=("Arial", 9))
        self.lbl_tunnel_status.pack(side=tk.LEFT, padx=5)
        self.btn_toggle_tunnel = tk.Button(row1, text="Lanzar Túnel", command=self._toggle_tunnel,
                                          bg=self.style.get_color("bg_input"), fg=self.style.get_color("text_main"), relief="flat", padx=10, font=("Arial", 8, "bold"))
        self.btn_toggle_tunnel.pack(side=tk.RIGHT)

        # Fila 2: Checkbox y URL (si existe)
        row2 = tk.Frame(tunnel_frame, bg=self.style.get_color("bg_main"))
        row2.pack(fill=tk.X, pady=(5, 0))

        self.chk_quick_tunnel = tk.Checkbutton(
            row2, text="Usar Túnel Rápido (Temporal)", variable=self._force_quick_tunnel,
            bg=self.style.get_color("bg_main"), fg=self.style.get_color("accent"), selectcolor=self.style.get_color("bg_input"), activebackground=self.style.get_color("bg_main"), 
            font=("Arial", 8, "bold"), cursor="hand2"
        )
        self.chk_quick_tunnel.pack(side=tk.LEFT)

        # Fila 3: URL Grande y Botón Copiar (oculta por defecto)
        self.row_url = tk.Frame(tunnel_frame, bg=self.style.get_color("bg_main"))
        # No la empaquetamos aún, se mostrará al detectar URL
        
        self.lbl_tunnel_url = tk.Label(self.row_url, text="", bg=self.style.get_color("bg_main"), fg=self.style.get_color("accent"), 
                                       font=("Arial", 10, "bold"), cursor="hand2")
        self.lbl_tunnel_url.pack(side=tk.LEFT, padx=(0, 10))
        self.lbl_tunnel_url.bind("<Button-1>", lambda e: self._copy_tunnel_url())

        self.btn_copy_url = tk.Button(self.row_url, text="📋 Copiar", command=self._copy_tunnel_url,
                                     bg=self.style.get_color("btn_bg"), fg=self.style.get_color("btn_fg"), relief="flat", padx=8, font=("Arial", 8))
        self.btn_copy_url.pack(side=tk.LEFT)

        # --- SEPARADOR ---
        tk.Frame(self, bg="#333", height=1).pack(fill=tk.X, padx=20, pady=5)

        # Contenedor con scroll si fuera necesario (aunque 6 campos caben bien)
        container = tk.Frame(self, bg=self.style.get_color("bg_main"))
        container.pack(padx=20, fill=tk.BOTH, expand=True)

        self._entries = {}

        # Definición de campos (solo configuraciones de funcionamiento)
        fields = [
            ("Ollama URL", "ollama_url", False),
            ("LLM Studio URL", "llmstudio_url", False),
            ("OpenCode URL", "opencode_url", False),
            ("Ruta Audios", "voice_save_path", False),
            ("Puerto API", "api_port", False),
        ]

        for i, (label, key, is_secret) in enumerate(fields):
            lbl = tk.Label(container, text=f"{label}:", bg=self.style.get_color("bg_main"), fg=self.style.get_color("text_dim"), font=("Arial", 9))
            lbl.grid(row=i, column=0, sticky="w", pady=8, padx=(0, 10))
            
            ent = tk.Entry(container, bg=self.style.get_color("bg_input"), fg=self.style.get_color("text_main"), insertbackground=self.style.get_color("text_main"), 
                           relief="flat", show="*" if is_secret else "")
            ent.grid(row=i, column=1, sticky="ew", pady=8)
            ent.insert(0, self.config.get(key, ""))
            self._entries[key] = ent

        container.columnconfigure(1, weight=1)

        # Voice Playback Mode
        playback_frame = tk.Frame(self, bg=self.style.get_color("bg_main"))
        playback_frame.pack(fill=tk.X, padx=20, pady=(10, 0))

        tk.Label(playback_frame, text="Reproducción de Audio:", bg=self.style.get_color("bg_main"), fg=self.style.get_color("text_dim"), font=("Arial", 10)).pack(side=tk.LEFT)
        
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

        # Destreaming Control
        destream_frame = tk.Frame(self, bg=self.style.get_color("bg_main"))
        destream_frame.pack(fill=tk.X, padx=20, pady=(10, 0))

        tk.Label(destream_frame, text="Destreaming:", bg=self.style.get_color("bg_main"), fg=self.style.get_color("text_dim"), font=("Arial", 10)).pack(side=tk.LEFT)
        
        self._destream_enabled = tk.BooleanVar(value=self.config.get("destreaming_enabled", False))
        self.chk_destream = tk.Checkbutton(
            destream_frame, 
            text="Activar",
            bg=self.style.get_color("bg_main"), 
            fg=self.style.get_color("text_main"),
            selectcolor=self.style.get_color("bg_input"),
            activebackground=self.style.get_color("bg_main"),
            activeforeground=self.style.get_color("text_main"),
            variable=self._destream_enabled,
            command=self._on_destreaming_toggle
        )
        self.chk_destream.pack(side=tk.LEFT, padx=10)

        tk.Label(destream_frame, text="TamañoChunk:", bg=self.style.get_color("bg_main"), fg=self.style.get_color("text_dim"), font=("Arial", 10)).pack(side=tk.LEFT, padx=(20, 5))
        
        self._chunk_size_var = tk.StringVar(value=str(self.config.get("destreaming_chunk_size", 500)))
        self.chunk_size_entry = tk.Entry(destream_frame, bg=self.style.get_color("bg_input"), fg=self.style.get_color("text_main"), insertbackground=self.style.get_color("text_main"), 
                                         relief="flat", width=8, textvariable=self._chunk_size_var)
        self.chunk_size_entry.pack(side=tk.LEFT, padx=5)
        
        # Audio Agent Control (NUEVO)
        agent_audio_frame = tk.Frame(self, bg=self.style.get_color("bg_main"))
        agent_audio_frame.pack(fill=tk.X, padx=20, pady=(10, 0))

        tk.Label(agent_audio_frame, text="Audio del Agente (Voz):", bg=self.style.get_color("bg_main"), fg=self.style.get_color("text_dim"), font=("Arial", 10)).pack(side=tk.LEFT)
        
        self._audio_agent_enabled = tk.BooleanVar(value=self.config.get("audio_agent", True))
        self.chk_audio_agent = tk.Checkbutton(
            agent_audio_frame, 
            text="Activar voz en modo Agente",
            bg=self.style.get_color("bg_main"), 
            fg=self.style.get_color("text_main"),
            selectcolor=self.style.get_color("bg_input"),
            activebackground=self.style.get_color("bg_main"),
            activeforeground=self.style.get_color("text_main"),
            variable=self._audio_agent_enabled,
            command=self._on_audio_agent_toggle
        )
        self.chk_audio_agent.pack(side=tk.LEFT, padx=10)

        # Botón Guardar
        save_btn = tk.Button(self, text="Guardar Cambios", bg=self.style.get_color("accent"), fg=self.style.get_color("btn_fg"), 
                             font=("Arial", 10, "bold"), relief="flat", width=20, command=self.save)
        save_btn.pack(pady=20, ipady=5)

        # Botón OpenCode Server
        opencode_frame = tk.Frame(self, bg=self.style.get_color("bg_main"))
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
            bg=self.style.get_color("bg_main"), 
            fg=self.style.get_color("text_dim"), 
            font=("Arial", 9)
        )
        self.lbl_opencode_status.pack(side=tk.LEFT, padx=10)

        self._check_opencode_status()

    def _on_language_change(self, event):
        selected_name = self.lang_combo.get()
        languages = self.locale_service.list_available_languages()
        
        # Encontrar el código por el nombre
        lang_code = next((code for code, name in languages.items() if name == selected_name), "es")
        
        self.config.set("language", lang_code)
        messagebox.showinfo("Idioma cambiado", f"Idioma cambiado a: {selected_name}\nLos cambios se aplicarán al recargar.")

    def _on_theme_change(self, event):
        selected_name = self.theme_combo.get()
        themes = self.style.get_available_styles_names()
        # Encontrar ID por nombre
        style_id = next((sid for sid, name in themes.items() if name == selected_name), "dark_carbon")
        
        if self.style.apply_style(style_id):
            messagebox.showinfo("Tema cambiado", f"Tema '{selected_name}' seleccionado.\nReinicia ASIMOD para aplicar el estilo a toda la interfaz.")
            # Aplicar inmediatamente al fondo de este panel (feedback visual parcial)
            new_bg = self.style.get_color("bg_main")
            self.configure(bg=new_bg)
            for widget in self.winfo_children():
                try:
                    widget.configure(bg=new_bg)
                except:
                    pass

    def _on_playback_mode_change(self, event):
        selected = self.combo_playback_mode.get()
        mode = "interrupt" if selected == "Interrumpir anterior" else "wait"
        self.config.set("voice_playback_mode", mode)

    def _on_destreaming_toggle(self):
        enabled = self._destream_enabled.get()
        self.config.set("destreaming_enabled", enabled)
        
        try:
            chunk_size = int(self._chunk_size_var.get())
            if chunk_size > 0:
                self.config.set("destreaming_chunk_size", chunk_size)
        except ValueError:
            pass
        
        messagebox.showinfo("Destreaming", f"Destreaming {'activado' if enabled else 'desactivado'}")

    def _on_audio_agent_toggle(self):
        enabled = self._audio_agent_enabled.get()
        self.config.set("audio_agent", enabled)
        messagebox.showinfo("Audio Agente", f"Voz del agente {'activada' if enabled else 'desactivada'}")

    def _on_visualizer_toggle(self):
        enabled = self._viz_enabled.get()
        self.config.set("visualizer_enabled", enabled)
        messagebox.showinfo("Visualizador", f"Visualizador {'activado' if enabled else 'desactivado'}. Reinicia para aplicar.")

    def _on_v_type_change(self, event=None):
        new_v = self.v_type_combo.get()
        self.config.set("visualizer_type", new_v)
        messagebox.showinfo("Visualizador", f"Cambiado a visualizador: {new_v}. Reinicia para aplicar.")

    def _on_modules_toggle(self):
        enabled = self._modules_enabled.get()
        self.config.set("modules_enabled", enabled)
        messagebox.showinfo("Sistema Modular", f"El sistema modular se {'activará' if enabled else 'desactivará'} al reiniciar la aplicación.")

    def _on_save_mod_path(self):
        path = self.mod_path_entry.get().strip()
        if path:
            self.config.set("modules_path", path)
            messagebox.showinfo("Módulos", "Ruta de módulos actualizada. Reinicia la aplicación para refrescar.")

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

    def _toggle_tunnel(self):
        """Inicia o detiene el túnel de Cloudflare."""
        if self._tunnel_process is None:
            # LANZAR
            self.lbl_tunnel_status.config(text="Iniciando...", fg="#ffcc00")
            self.tunnel_canvas.itemconfig(self.tunnel_indicator, fill="#ffcc00")
            
            try:
                # Si forzamos túnel rápido, enviamos un dict vacío para que run_tunnel use el fallback
                tunnel_settings = {} if self._force_quick_tunnel.get() else self.config.settings
                cmd, temp_file = get_tunnel_command(tunnel_settings)
                self._tunnel_temp_file = temp_file
                
                # Lanzar proceso en segundo plano con el CWD correcto
                self._tunnel_process = subprocess.Popen(
                    cmd, 
                    stdout=subprocess.PIPE, 
                    stderr=subprocess.STDOUT, 
                    text=True,
                    cwd=os.path.abspath(os.path.join(os.path.dirname(__file__), "..")), # Root del proyecto (ui es hijo de root)
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
                )
                
                # Iniciar hilo de monitoreo
                self._tunnel_thread = threading.Thread(target=self._monitor_tunnel, daemon=True)
                self._tunnel_thread.start()
                
                self.btn_toggle_tunnel.config(text="Detener Túnel", bg="#e94560")
                messagebox.showinfo("Túnel", "Iniciando túnel de Cloudflare. Consulta el log si es un túnel rápido para ver la URL.")
            except Exception as e:
                self._kill_tunnel()
                messagebox.showerror("Error", f"No se pudo iniciar el túnel: {e}")
        else:
            # DETENER
            self._kill_tunnel()
            messagebox.showinfo("Túnel", "Túnel cerrado correctamente.")

    def _monitor_tunnel(self):
        """Hilo que vigila si el proceso del túnel sigue vivo y busca la URL."""
        import re
        url_pattern = re.compile(r'https://[a-z0-9-]+\.trycloudflare\.com')
        
        if not self._force_quick_tunnel.get():
            fixed_host = self.config.get("cloudflare_hostname", "")
            if fixed_host and self.winfo_exists():
                self.after(0, lambda h=fixed_host: self._show_tunnel_url(f"https://{h}") if self.winfo_exists() else None)

        try:
            while self._tunnel_process and self._tunnel_process.poll() is None:
                line = self._tunnel_process.stdout.readline()
                if line:
                    print(f"[Tunnel Output] {line.strip()}")
                    # Buscar URL en el log si es túnel rápido
                    if self._force_quick_tunnel.get():
                        match = url_pattern.search(line)
                        if match:
                            found_url = match.group(0)
                            if self.winfo_exists():
                                self.after(0, lambda u=found_url: self._show_tunnel_url(u) if self.winfo_exists() else None)
                
                try:
                    if self.winfo_exists():
                        self.after(0, lambda: self.tunnel_canvas.itemconfig(self.tunnel_indicator, fill="#00ff00") if self.winfo_exists() else None)
                        self.after(0, lambda: self.lbl_tunnel_status.config(text="Activo", fg="#00ff00") if self.winfo_exists() else None)
                except:
                    pass
                
                if not line:
                    time.sleep(0.5)
        except Exception as e:
            print(f"Error monitoreando túnel: {e}")
        
        try:
            if self.winfo_exists():
                self.after(0, lambda: self._on_tunnel_died() if self.winfo_exists() else None)
        except:
            pass

    def _on_tunnel_died(self):
        """Callback cuando el proceso termina."""
        self._kill_tunnel()
        self.tunnel_canvas.itemconfig(self.tunnel_indicator, fill="#ff4444")
        self.lbl_tunnel_status.config(text="Cerrado/Error", fg="#ff4444")
        self.btn_toggle_tunnel.config(text="Lanzar Túnel", bg="#3c3c3c")

    def _kill_tunnel(self):
        """Limpia el proceso y archivos del túnel."""
        if self._tunnel_process:
            try:
                self._tunnel_process.terminate()
                self._tunnel_process.wait(timeout=2)
            except:
                try: self._tunnel_process.kill()
                except: pass
            self._tunnel_process = None
        
        if self._tunnel_temp_file and os.path.exists(self._tunnel_temp_file):
            try: os.remove(self._tunnel_temp_file)
            except: pass
            self._tunnel_temp_file = None
        
        try:
            if self.winfo_exists():
                self.lbl_tunnel_status.config(text="Detenido", fg="#aaa")
                self.tunnel_canvas.itemconfig(self.tunnel_indicator, fill="#555")
                self.btn_toggle_tunnel.config(text="Lanzar Túnel", bg="#3c3c3c")
                self.lbl_tunnel_url.config(text="")
                self.row_url.pack_forget()
        except:
            pass

    def _show_tunnel_url(self, url):
        """Muestra la fila de la URL con el texto indicado."""
        self.lbl_tunnel_url.config(text=url)
        self.row_url.pack(fill=tk.X, pady=(5, 0))

    def _copy_tunnel_url(self):
        """Copia la URL al portapapeles."""
        url = self.lbl_tunnel_url.cget("text")
        if url:
            self.clipboard_clear()
            self.clipboard_append(url)
            self.update() # Requerido por algunos sistemas para que el portapapeles persista
            messagebox.showinfo("Copiado", "URL copiada al portapapeles.")

    def __del__(self):
        """Asegurar que el túnel muere al destruir el widget."""
        self._kill_tunnel()

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
