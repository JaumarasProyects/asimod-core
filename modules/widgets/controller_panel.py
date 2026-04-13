import tkinter as tk
from tkinter import ttk
import os

class ControllerPanel(tk.Frame):
    """
    Panel de controladores reutilizable y colapsable para módulos.
    """
    def __init__(self, parent, title="CONTROLES", style=None, bg_color=None, header_bg=None):
        self.style = style
        if self.style:
            bg_color = self.style.get_color("bg_main")
            header_bg = self.style.get_color("bg_header")
        else:
            bg_color = bg_color or "#242424"
            header_bg = header_bg or "#1e1e1e"
            
        super().__init__(parent, bg=bg_color)
        self.bg_color = bg_color
        self.header_bg = header_bg
        self.is_minimized = False
        
        # 1. Cabecera (Título + Botón Toggle)
        self.header = tk.Frame(self, bg=header_bg, padx=10, pady=5)
        self.header.pack(fill=tk.X)
        self.header.bind("<Button-1>", lambda e: self.toggle()) # Clic en cabecera colapsa

        self.title_label = tk.Label(self.header, text=title, bg=header_bg, fg="#888", 
                                    font=("Arial", 8, "bold"))
        self.title_label.pack(side=tk.LEFT)

        self.toggle_btn = tk.Label(self.header, text="▼", bg=header_bg, fg="#888", 
                                   font=("Arial", 10), cursor="hand2")
        self.toggle_btn.pack(side=tk.RIGHT)
        self.toggle_btn.bind("<Button-1>", lambda e: self.toggle())

        # 2. Área de Contenido
        self.content = tk.Frame(self, bg=bg_color, padx=15, pady=10)
        self.content.pack(fill=tk.X)
        self.content.columnconfigure(0, weight=1)
        self.content.columnconfigure(1, weight=1)

        # Contenedor interno para los controles (para grid limpio)
        self.grid_container = tk.Frame(self.content, bg=bg_color)
        self.grid_container.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        
        # Nueva columna para acciones externas (Prompt, botones, etc.)
        self.actions_container = tk.Frame(self.content, bg=bg_color)
        self.actions_container.grid(row=0, column=1, sticky="nsew")
        
        self.controls = {}

    def toggle(self):
        """Alterna entre minimizado y expandido."""
        if self.is_minimized:
            self.content.pack(fill=tk.X, after=self.header)
            self.toggle_btn.config(text="▼")
        else:
            self.content.pack_forget()
            self.toggle_btn.config(text="◀")
        self.is_minimized = not self.is_minimized

    def add_dropdown(self, label_text, key, values, default=None, callback=None):
        """Añade un selector desplegable al panel."""
        row = len(self.grid_container.winfo_children()) // 2
        
        lbl = tk.Label(self.grid_container, text=f"{label_text}:", bg=self.bg_color, 
                       fg=self.style.get_color("text_dim") if self.style else "#aaa", font=("Arial", 9))
        lbl.grid(row=row, column=0, sticky="w", pady=5, padx=(0, 10))
        
        combo = ttk.Combobox(self.grid_container, values=values, state="readonly", width=25)
        combo.grid(row=row, column=1, sticky="ew", pady=5)
        
        if default and default in values:
            combo.set(default)
        elif values:
            combo.current(0)
            
        if callback:
            combo.bind("<<ComboboxSelected>>", lambda e: callback(combo.get()))
            
        self.controls[key] = combo
        return combo

    def add_input(self, label_text, key, default=None):
        """Añade un campo de entrada de texto al panel."""
        row = len(self.grid_container.winfo_children()) // 2
        
        lbl = tk.Label(self.grid_container, text=f"{label_text}:", bg=self.bg_color, 
                       fg=self.style.get_color("text_dim") if self.style else "#aaa", font=("Arial", 9))
        lbl.grid(row=row, column=0, sticky="w", pady=5, padx=(0, 10))
        
        entry = tk.Entry(self.grid_container, bg=self.style.get_color("bg_dark") if self.style else "#333", 
                         fg=self.style.get_color("text_main") if self.style else "#eee", 
                         insertbackground=self.style.get_color("text_main") if self.style else "#eee",
                         bd=0, font=("Arial", 9))
        entry.grid(row=row, column=1, sticky="ew", pady=5, ipady=3)
        
        if default:
            entry.insert(0, str(default))
            
        self.controls[key] = entry
        return entry

    def add_resolution_control(self, label_text, key, values, default=None):
        """Añade un selector de resolución progresivo con presets y modo Custom."""
        row = len(self.grid_container.winfo_children()) // 2
        
        lbl = tk.Label(self.grid_container, text=f"{label_text}:", bg=self.bg_color, 
                       fg=self.style.get_color("text_dim") if self.style else "#aaa", font=("Arial", 9))
        lbl.grid(row=row, column=0, sticky="w", pady=5, padx=(0, 10))
        
        # Contenedor para el combo y los inputs custom
        container = tk.Frame(self.grid_container, bg=self.bg_color)
        container.grid(row=row, column=1, sticky="w", pady=5)
        
        combo = ttk.Combobox(container, values=values, state="readonly", width=25)
        combo.pack(side=tk.LEFT)
        
        # Frame para custom inputs (inicialmente oculto)
        custom_frame = tk.Frame(container, bg=self.bg_color)
        
        tk.Label(custom_frame, text=" W:", bg=self.bg_color, fg="#888", font=("Arial", 8)).pack(side=tk.LEFT)
        entry_w = tk.Entry(custom_frame, width=5, bg="#333", fg="#eee", bd=0)
        entry_w.pack(side=tk.LEFT, padx=2)
        entry_w.insert(0, "1024")
        
        tk.Label(custom_frame, text=" H:", bg=self.bg_color, fg="#888", font=("Arial", 8)).pack(side=tk.LEFT)
        entry_h = tk.Entry(custom_frame, width=5, bg="#333", fg="#eee", bd=0)
        entry_h.pack(side=tk.LEFT, padx=2)
        entry_h.insert(0, "1024")

        def on_change(event=None):
            if combo.get() == "Personalizado":
                custom_frame.pack(side=tk.LEFT, padx=5)
            else:
                custom_frame.pack_forget()
        
        combo.bind("<<ComboboxSelected>>", on_change)
        
        if default and default in values:
            combo.set(default)
        elif values:
            combo.current(0)
        
        on_change() # Estado inicial
        
        self.controls[key] = combo
        self.controls[f"{key}_w"] = entry_w
        self.controls[f"{key}_h"] = entry_h
        return combo

    def add_file_picker(self, label_text, key, file_types=[("Imágenes", "*.png *.jpg *.jpeg *.webp")], default=None):
        """Añade un selector de archivos al panel."""
        from tkinter import filedialog
        row = len(self.grid_container.winfo_children()) // 2
        
        lbl = tk.Label(self.grid_container, text=f"{label_text}:", bg=self.bg_color, 
                       fg=self.style.get_color("text_dim") if self.style else "#aaa", font=("Arial", 9))
        lbl.grid(row=row, column=0, sticky="w", pady=5, padx=(0, 10))
        
        container = tk.Frame(self.grid_container, bg=self.bg_color)
        container.grid(row=row, column=1, sticky="w", pady=5)
        
        path_var = tk.StringVar(value=default or "Ninguno")
        
        lbl_path = tk.Label(container, text=os.path.basename(path_var.get()), bg=self.bg_color, fg="#888", font=("Arial", 8))
        lbl_path.pack(side=tk.LEFT, padx=10)

        def pick_file():
            path = filedialog.askopenfilename(filetypes=file_types)
            if path:
                path_var.set(path)
                lbl_path.config(text=os.path.basename(path))

        btn = tk.Button(container, text="📁 Seleccionar", bg="#444", fg="white", bd=0, padx=8, font=("Arial", 8),
                         command=pick_file)
        btn.pack(side=tk.LEFT)
        
        # Guardamos la variable de control para poder recuperar el path completo
        self.controls[key] = path_var
        return container

    def update_dropdown(self, key, values, select_first=True):
        """Actualiza dinámicamente las opciones de un dropdown existente."""
        if key in self.controls:
            combo = self.controls[key]
            combo['values'] = values
            if select_first and values:
                combo.current(0)
            elif not values:
                combo.set("")

    def clear(self):
        """Elimina todos los controles del panel de forma segura."""
        if not self.winfo_exists(): return
        if not self.grid_container.winfo_exists(): return
        
        for widget in self.grid_container.winfo_children():
            widget.destroy()
        self.controls = {}

    def add_button(self, label_text, callback, bg=None):
        """Añade un botón de acción al panel."""
        row = len(self.grid_container.winfo_children()) // 2
        
        btn = tk.Button(self.grid_container, text=label_text, 
                        bg=bg or (self.style.get_color("accent") if self.style else "#4CAF50"), 
                        fg="white", bd=0, padx=15, pady=5, font=("Arial", 9, "bold"),
                        cursor="hand2", command=callback)
        btn.grid(row=row, column=1, sticky="ew", pady=5)
        return btn

    def add_textarea(self, label_text, key, height=4, default=None):
        """Añade un área de texto multilínea al panel."""
        row = len(self.grid_container.winfo_children()) // 2
        
        lbl = tk.Label(self.grid_container, text=f"{label_text}:", bg=self.bg_color, 
                       fg=self.style.get_color("text_dim") if self.style else "#aaa", font=("Arial", 9))
        lbl.grid(row=row, column=0, sticky="nw", pady=5, padx=(0, 10))
        
        txt = tk.Text(self.grid_container, height=height, width=25,
                      bg=self.style.get_color("bg_dark") if self.style else "#333", 
                      fg=self.style.get_color("text_main") if self.style else "#eee",
                      font=("Arial", 9), bd=0, padx=5, pady=5,
                      insertbackground=self.style.get_color("text_main") if self.style else "#eee")
        txt.grid(row=row, column=1, sticky="ew", pady=5)
        
        if default:
            txt.insert("1.0", default)
            
        self.controls[key] = txt
        return txt

    def get_value(self, key, default=None):
        """Retorna el valor de un controlador por su clave."""
        if key in self.controls:
            ctrl = self.controls[key]
            if isinstance(ctrl, tk.Text):
                return ctrl.get("1.0", tk.END).strip()
            return ctrl.get()
        return default

    def add_label(self, text, color=None):
        """Añade una etiqueta de información o advertencia al panel."""
        row = len(self.grid_container.winfo_children()) // 2
        
        lbl = tk.Label(self.grid_container, text=text, bg=self.bg_color, 
                       fg=color or (self.style.get_color("text_dim") if self.style else "#aaa"), 
                       font=("Arial", 9, "italic"), wraplength=200, justify="left")
        lbl.grid(row=row, column=0, columnspan=2, sticky="w", pady=5)
        return lbl
