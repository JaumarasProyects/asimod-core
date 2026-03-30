import tkinter as tk
from tkinter import ttk, messagebox

class SettingsView(tk.Frame):
    """
    Panel de configuración embebido dentro del ChatWidget.
    """
    def __init__(self, parent, config_service, back_callback):
        super().__init__(parent, bg="#2b2b2b")
        self.config = config_service
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

        # Contenedor con scroll si fuera necesario (aunque 6 campos caben bien)
        container = tk.Frame(self, bg="#2b2b2b")
        container.pack(padx=20, fill=tk.BOTH, expand=True)

        self._entries = {}

        # Definición de campos
        fields = [
            ("Ollama URL", "ollama_url", False),
            ("OpenAI Key", "openai_key", True),
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

    def save(self):
        for key, entry in self._entries.items():
            self.config.set(key, entry.get())
        
        messagebox.showinfo("Éxito", "Toda la configuración ha sido guardada.")
        self.back_callback()
