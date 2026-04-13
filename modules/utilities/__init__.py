import tkinter as tk
from tkinter import ttk, messagebox
import math
from core.standard_module import StandardModule

class UtilitiesModule(StandardModule):
    """
    Módulo de Utilidades de ASIMOD.
    Contiene herramientas rápidas como Calculadora, Editor de Texto, etc.
    """
    def __init__(self, chat_service, config_service, style_service, data_service=None):
        super().__init__(chat_service, config_service, style_service, data_service=data_service)
        self.name = "Utilidades"
        self.id = "utilities"
        self.icon = "🔧"
        self.has_web_ui = True
        
        # Configuración de Layout
        self.show_menu = True
        self.show_controllers = False
        self.show_gallery = True
        self.gallery_title = "NOTAS"
        self.menu_items = ["Calculadora", "Editor", "Cámara"]
        
        self.current_mode = "Calculadora"

    async def handle_get_notes(self):
        """Bridge para obtener todas las notas."""
        return {"status": "success", "notes": self.data_service.get_all_notes()}

    async def handle_save_note(self, title: str, content: str, note_id: int = None):
        """Bridge para guardar una nota."""
        res = self.data_service.save_note(title, content, note_id)
        return {"status": "success", "note_id": res}

    def handle_get_gallery(self):
        """Lista las notas en la barra lateral web."""
        notes = self.data_service.get_all_notes()
        items = []
        for n in notes:
            items.append({
                "id": n['id'],
                "title": n['title'],
                "subtitle": n['updated_at'],
                "type": "item",
                "icon": "📝",
                "callback_action": "handle_select_note",
                "callback_params": {"note_id": n['id']}
            })
        return {"items": items}

    async def handle_select_note(self, note_id: int):
        """Selecciona una nota para editar."""
        # En la web, el cliente la pedirá de nuevo por ID o usará la caché
        return {"status": "success", "note_id": note_id}
        self.expression = ""

    def render_workspace(self, parent):
        if self.current_mode == "Calculadora":
            self._render_calculator(parent)
        elif self.current_mode == "Editor":
            self._render_text_editor(parent)
        else:
            tk.Label(parent, text=f"Herramienta {self.current_mode} en desarrollo...", 
                     bg=self.style.get_color("bg_main"), fg="#888").pack(pady=50)

    # --- CALCULADORA ---
    def _render_calculator(self, parent):
        container = tk.Frame(parent, bg=self.style.get_color("bg_main"))
        container.place(relx=0.5, rely=0.5, anchor="center")
        
        # Pantalla
        display_frame = tk.Frame(container, bg=self.style.get_color("bg_dark"), padx=20, pady=20)
        display_frame.pack(fill=tk.X, pady=(0, 20))
        
        self.lbl_display = tk.Label(display_frame, text="0", font=("Arial", 24, "bold"), 
                                    bg=self.style.get_color("bg_dark"), fg="white", anchor="e")
        self.lbl_display.pack(fill=tk.X)

        # Botones
        btn_grid = tk.Frame(container, bg=self.style.get_color("bg_main"))
        btn_grid.pack()

        buttons = [
            ('7', '8', '9', '/'),
            ('4', '5', '6', '*'),
            ('1', '2', '3', '-'),
            ('C', '0', '=', '+')
        ]

        for r, row in enumerate(buttons):
            for c, char in enumerate(row):
                self._create_calc_btn(btn_grid, char, r, c)

    def _create_calc_btn(self, parent, char, r, c):
        bg = "#333" if char.isdigit() else self.style.get_color("bg_header")
        if char == "=": bg = self.style.get_color("accent")
        
        btn = tk.Button(parent, text=char, width=5, height=2, font=("Arial", 12, "bold"),
                        bg=bg, fg="white", bd=0, cursor="hand2",
                        command=lambda: self._on_calc_click(char))
        btn.grid(row=r, column=c, padx=5, pady=5)

    def _on_calc_click(self, char):
        if char == "=":
            try:
                result = eval(self.expression)
                self.lbl_display.config(text=str(result))
                self.expression = str(result)
            except:
                self.lbl_display.config(text="Error")
                self.expression = ""
        elif char == "C":
            self.expression = ""
            self.lbl_display.config(text="0")
        else:
            self.expression += str(char)
            self.lbl_display.config(text=self.expression)

    # --- EDITOR DE TEXTO ---
    def _render_text_editor(self, parent):
        tk.Label(parent, text="Bloc de Notas Rápido", fg=self.style.get_color("text_dim"), bg=self.style.get_color("bg_main")).pack(anchor="w")
        
        text_area = tk.Text(parent, bg=self.style.get_color("bg_input"), fg="white", bd=0, padx=10, pady=10, font=("Consolas", 11))
        text_area.pack(fill=tk.BOTH, expand=True, pady=10)
        
        btn_save = tk.Button(parent, text="💾 Guardar en Notas", bg=self.style.get_color("accent"), fg="white", bd=0, padx=15, pady=8)
        btn_save.pack(side=tk.RIGHT)

    def on_menu_change(self, mode):
        self.current_mode = mode
        self.expression = ""
        self.refresh_workspace()

    def get_voice_commands(self):
        return {
            "calculadora": "show_calc",
            "editor": "show_editor",
            "limpiar": "clear_all"
        }

    def on_voice_command(self, action_slug, text):
        if action_slug == "show_calc": self.on_menu_change("Calculadora")
        elif action_slug == "show_editor": self.on_menu_change("Editor")
        elif action_slug == "clear_all": self.expression = ""; self.refresh_workspace()

def get_module_class():
    return UtilitiesModule
