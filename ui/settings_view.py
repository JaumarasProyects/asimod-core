import tkinter as tk
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

        # Contenedor con scroll si fuera necesario (aunque 6 campos caben bien)
        container = tk.Frame(self, bg="#2b2b2b")
        container.pack(padx=20, fill=tk.BOTH, expand=True)

        self._entries = {}

        # Definición de campos
        fields = [
            ("Ollama URL", "ollama_url", False),
            ("OpenAI Key", "openai_key", True),
            ("Anthropic Key", "anthropic_key", True),
            ("Gemini Key", "gemini_key", True),
            ("DeepSeek Key", "deepseek_key", True),
            ("Groq Key", "groq_key", True),
            ("Perplexity Key", "perplexity_key", True),
            ("Ruta Audios", "voice_save_path", False),
            ("Puerto API", "api_port", False)
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

        # Botón Guardar
        save_btn = tk.Button(self, text="Guardar Cambios", bg="#0078d4", fg="white", 
                             font=("Arial", 10, "bold"), relief="flat", width=20, command=self.save)
        save_btn.pack(pady=20, ipady=5)

    def _on_language_change(self, event):
        selected_name = self.lang_combo.get()
        languages = self.locale_service.list_available_languages()
        lang_code = next((code for code, name in languages.items() if name == selected_name), "es")
        self.locale_service.set_language(lang_code)
        
        default_voice = self.locale_service.get_default_voice()
        self.config.set("voice_id", default_voice["voice_id"])
        
        messagebox.showinfo("Idioma cambiado", f"Idioma cambiado a: {selected_name}\nLos cambios se aplicarán al recargar.")

    def save(self):
        for key, entry in self._entries.items():
            self.config.set(key, entry.get())
        
        messagebox.showinfo("Éxito", "Toda la configuración ha sido guardada.")
        self.back_callback()
