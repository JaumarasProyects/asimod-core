import tkinter as tk
from tkinter import ttk


class APIKeysView(tk.Frame):
    """
    Panel de configuración de API Keys separado de configuraciones de funcionamiento.
    """
    def __init__(self, parent, config_service, back_callback, style_service):
        self.style = style_service
        super().__init__(parent, bg=self.style.get_color("bg_main"))
        self.config = config_service
        self.back_callback = back_callback
        self.init_ui()

    def init_ui(self):
        header = tk.Frame(self, bg=self.style.get_color("bg_main"))
        header.pack(fill=tk.X, pady=(10, 5))
        
        btn_back = tk.Button(header, text="← Volver", bg=self.style.get_color("bg_main"), fg=self.style.get_color("accent"),
                             relief="flat", cursor="hand2", command=self.back_callback)
        btn_back.pack(side=tk.LEFT, padx=10)

        title = tk.Label(self, text="🔑 API Keys", 
                         bg=self.style.get_color("bg_main"), fg=self.style.get_color("text_main"), font=("Arial", 12, "bold"))
        title.pack(pady=10)

        info = tk.Label(self, text="Configura las claves API para los proveedores de IA",
                        bg=self.style.get_color("bg_main"), fg=self.style.get_color("text_dim"), font=("Arial", 9, "italic"))
        info.pack(pady=(0, 15))

        container = tk.Frame(self, bg=self.style.get_color("bg_main"))
        container.pack(padx=20, fill=tk.BOTH, expand=True)

        self._entries = {}

        fields = [
            ("OpenAI Key", "openai_key", True),
            ("Anthropic Key", "anthropic_key", True),
            ("Gemini Key", "gemini_key", True),
            ("DeepSeek Key", "deepseek_key", True),
            ("Groq Key", "groq_key", True),
            ("Perplexity Key", "perplexity_key", True),
            ("OpenCode API Key", "opencode_api_key", True),
            ("OpenCode URL", "opencode_url", False),
            ("Ollama URL", "ollama_url", False),
            ("LLM Studio URL", "llmstudio_url", False),
            ("WhatsApp Phone ID", "whatsapp_phone_id", False),
            ("WhatsApp Access Token", "whatsapp_access_token", True),
            ("WhatsApp Verify Token", "whatsapp_verify_token", False),
            ("Cloudflare Tunnel Token", "cloudflare_tunnel_token", True),
        ]

        for i, (label, key, is_secret) in enumerate(fields):
            lbl = tk.Label(container, text=f"{label}:", bg=self.style.get_color("bg_main"), fg=self.style.get_color("text_dim"), font=("Arial", 9))
            lbl.grid(row=i, column=0, sticky="w", pady=10, padx=(0, 15))
            
            ent = tk.Entry(container, bg=self.style.get_color("bg_input"), fg=self.style.get_color("text_main"), insertbackground=self.style.get_color("text_main"), 
                           relief="flat", show="*" if is_secret else "", width=40)
            ent.grid(row=i, column=1, sticky="ew", pady=10)
            ent.insert(0, self.config.get(key, ""))
            self._entries[key] = ent

        container.columnconfigure(1, weight=1)

        btn_frame = tk.Frame(self, bg=self.style.get_color("bg_main"))
        btn_frame.pack(fill=tk.X, padx=20, pady=20)

        btn_save = tk.Button(btn_frame, text="💾 Guardar Keys", bg=self.style.get_color("accent"), fg=self.style.get_color("btn_fg"),
                            relief="flat", padx=20, pady=5, command=self._save_keys)
        btn_save.pack(side=tk.LEFT)

        btn_show = tk.Button(btn_frame, text="👁️ Mostrar/Ocultar", bg=self.style.get_color("btn_bg"), fg=self.style.get_color("btn_fg"),
                             relief="flat", padx=15, pady=5, command=self._toggle_visibility)
        btn_show.pack(side=tk.LEFT, padx=10)

    def _save_keys(self):
        for key, entry in self._entries.items():
            value = entry.get()
            self.config.set(key, value)
        self.config.save()
        from tkinter import messagebox
        messagebox.showinfo("API Keys", "Claves guardadas correctamente.")

    def _toggle_visibility(self):
        current_show = self._entries["openai_key"].cget("show")
        new_show = "" if current_show == "*" else "*"
        for entry in self._entries.values():
            entry.config(show=new_show)
