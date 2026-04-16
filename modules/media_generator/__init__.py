import tkinter as tk
from tkinter import ttk
import asyncio
import threading
import os
import json
import shutil
import datetime
import time
from PIL import Image, ImageTk
from core.standard_module import StandardModule
from core.services.image_service import ImageService
from modules.widgets import MediaDisplayWidget

class MediaGeneratorModule(StandardModule):
    def __init__(self, chat_service, config_service, style_service, data_service=None):
        super().__init__(chat_service, config_service, style_service, data_service=data_service)
        self.name = "Media"
        self.id = "media_generator"
        self.icon = "🎨"
        
        # Servidor de imágenes
        self.image_service = ImageService(config_service)
        self.comfy_status = "Desconocido"
        self.current_image_ref = None # Referencia para evitar el garbage collector de Tkinter
        
        # Configuración de Plantilla Estándar
        self.show_menu = True
        self.show_controllers = True
        self.show_gallery = True
        self.menu_items = ["Texto", "Imagen", "Video", "Audio", "3D"]
        self.current_mode = "Texto"
        
        # Ruta de Output en el Módulo (Forzamos la local para evitar confusiones con la raíz)
        self.output_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "output"))
        self.gallery_path = self.output_root 
        
        # Estado de comandos de voz
        self.awaiting_instruction = False
        self.awaiting_gallery_num = False
        self.awaiting_type_selection = False
        self.last_gallery_wait_id = None  # ID para cancelar el temporizador de espera
        
        # Estado de modelos LLM para letras
        self.llm_models = []
        
        # Estado de Generación Compuesta (Escritorio)
        self.compound_state = {
            "type": "Simple",
            "subtype": "Ingredientes",
            "category": "Personaje",
            "target_product": "Plano",
            "references": [],
            "source_doc": None,
            "tipo_pieza": None,
            "tipo_accion": None  # Solo para Plano de tipo Accion
        }
        self.doc_map = {} # Mapeo de Título -> Path para Documento Origen
        self.ingredient_panel_visible = False
        
        self.CONFIG_COMPUESTA = {
            'Ingredientes': ['Personaje', 'Escenario', 'Prop', 'Sinopsis'],
            'Productos':    ['Plano', 'Escena', 'Secuencia'],
            'Finales':      ['Pelicula', 'Documental', 'Explicativo', 'Noticias', 'Musical', 'Archviz', 'Publicidad']
        }

    def _on_provider_change(self, provider_name):
        """Cambia el proveedor LLM global y refresca la lista de modelos."""
        print(f"[MediaGenerator] Cambiando proveedor LLM a: {provider_name}")
        self.chat_service.switch_provider(provider_name)
        self.config_service.set("last_provider", provider_name)
        
        # Limpiar modelos actuales y disparar carga en segundo plano
        self.llm_models = []
        self._fetch_llm_models()
        
        # Refrescar UI inmediatamente para mostrar estado 'Cargando...'
        if hasattr(self, 'workspace') and self.workspace:
            self.workspace.after(0, self._rebuild_audio_panel)

    def _fetch_llm_models(self):
        """Carga los modelos LLM disponibles en segundo plano."""
        def run():
            try:
                # Usar asyncio para obtener modelos del adaptador activo
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                models = loop.run_until_complete(self.chat_service.get_available_models())
                loop.close()
                
                self.llm_models = models
                print(f"[MediaGenerator] {len(models)} modelos LLM cargados para letras.")
                
                # Si el panel de audio está cargado, actualizar dropdown
                if self.current_mode == "Audio":
                    self.workspace.after(0, self._rebuild_audio_panel)
            except Exception as e:
                print(f"[MediaGenerator] Error cargando modelos LLM: {e}")

        threading.Thread(target=run, daemon=True).start()

    def setup_controllers(self, panel):
        """Configura los desplegables iniciales."""
        self._update_controllers_logic(self.current_mode)

    def on_menu_change(self, mode):
        """Callback cuando se cambia de pestaña en el menú superior."""
        if self.current_mode == mode:
            return
            
        self.current_mode = mode
        print(f"[MediaGenerator] Cambiando a modo: {mode}")

        # 1. Actualizar controladores
        self._update_controllers_logic(mode)
        
        # 2. Refrescar el área de trabajo
        self.refresh_workspace()
        
        # 3. Sincronizar comandos de voz
        if hasattr(self.chat_service, "module_service"):
            self.chat_service.module_service.resync_module_commands()

    def _update_controllers_logic(self, mode):
        """Lógica interna para actualizar el ControllerPanel."""
        if not self.ctrl_panel:
            return
            
        self.ctrl_panel.clear()
        
        # 1. Proveedor LLM (Fijo arriba si es Texto o Compuesto)
        if mode == "Texto" or self.compound_state["type"] == "Compuesto":
            providers = self.chat_service.get_providers_list()
            current_p = self.chat_service.current_adapter.name if self.chat_service.current_adapter else "Ollama"
            self.ctrl_panel.add_dropdown("Proveedor LLM", "provider", 
                                        providers, 
                                        default=current_p,
                                        callback=self._on_provider_change)
            self._fetch_llm_models()

        # 2. Selector de Tipo (Simple / Compuesto) - Siempre disponible
        self.ctrl_panel.add_dropdown("Tipo de Generación", "gen_type", 
                                    ["Simple", "Compuesto"], 
                                    default=self.compound_state["type"],
                                    callback=self._on_compound_type_change)
        
        if self.compound_state["type"] == "Compuesto":
            self._setup_compound_controllers(mode)
            return

        # 3. Controladores originales si es Simple
        if mode == "Texto":
            # (Ya añadido arriba como fijo)
            pass
                
        elif mode == "Imagen":
            engines = self.image_service.get_engines_list()
            default_engine = "ComfyUI" if "ComfyUI" in engines else (engines[0] if engines else "DALL-E 3")
            self.ctrl_panel.set_value("engine", default_engine)
            self._on_image_engine_change(default_engine)
        elif mode == "Audio":
            self._rebuild_audio_panel()
        elif mode == "Video":
            self._rebuild_video_panel()
        elif mode == "3D":
            self._rebuild_3d_panel()
        else:
            self.ctrl_panel.add_dropdown("Proveedor", "gen_provider", ["Default Engine"])

    def _on_compound_type_change(self, val):
        """Callback cuando cambia el tipo de generación (Simple/Compuesto)."""
        self.compound_state["type"] = val
        self._update_controllers_logic(self.current_mode)

    def _setup_compound_controllers(self, mode):
        """Configura los controles específicos de composición."""
        if mode == "Texto":
            # G1: Creación de piezas
            subtypes = list(self.CONFIG_COMPUESTA.keys())
            self.ctrl_panel.add_dropdown("Subtipo", "gen_subtype", subtypes, 
                                        default=self.compound_state["subtype"],
                                        callback=self._on_subtype_change)
            
            cats = self.CONFIG_COMPUESTA.get(self.compound_state["subtype"], [])
            self.ctrl_panel.add_dropdown("Categoría", "gen_category", cats,
                                        default=self.compound_state["category"],
                                        callback=self._on_category_change)
            
            if self.compound_state["category"] == "Sinopsis":
                products = self.CONFIG_COMPUESTA.get("Productos", [])
                self.ctrl_panel.add_dropdown("Destino Sinopsis", "target_product", products,
                                            default=self.compound_state["target_product"],
                                            callback=lambda v: self.compound_state.update({"target_product": v}))

            # --- NUEVO: Tipo de Plano / Tipo de Escena + Workflow de Instrucciones ---
            if self.compound_state["subtype"] == "Productos":
                cat = self.compound_state["category"]
                if cat == "Plano":
                    tipos = ["Transicion", "Recurso", "Accion", "Dialogo"]
                    self.ctrl_panel.add_dropdown(
                        "Tipo de Plano", "tipo_pieza", tipos,
                        default=self.compound_state.get("tipo_pieza") or tipos[0],
                        callback=lambda v: self.compound_state.update({"tipo_pieza": v}) or self._update_controllers_logic(self.current_mode)
                    )
                    if not self.compound_state.get("tipo_pieza"):
                        self.compound_state["tipo_pieza"] = tipos[0]

                    # Subtipo de Acción (solo si el tipo es Accion)
                    if self.compound_state.get("tipo_pieza") == "Accion":
                        self.ctrl_panel.add_dropdown(
                            "Tipo de Acción", "tipo_accion",
                            ["Accion Lenta", "Accion Rapida"],
                            default=self.compound_state.get("tipo_accion") or "Accion Lenta",
                            callback=lambda v: self.compound_state.update({"tipo_accion": v})
                        )
                        if not self.compound_state.get("tipo_accion"):
                            self.compound_state["tipo_accion"] = "Accion Lenta"

                    # Workflow de instrucciones: auto-seleccionar el del tipo activo
                    wf_folder = os.path.join(os.path.dirname(__file__), "workflows", "compuesta", "plano", "texto")
                    tipo_actual = self.compound_state.get("tipo_pieza", "").lower()
                    wf_auto = f"plano_{tipo_actual}.json"
                    wf_auto_path = os.path.join(wf_folder, wf_auto)
                    wf_files = [f for f in os.listdir(wf_folder) if f.endswith(".json")] if os.path.exists(wf_folder) else []
                    default_wf = wf_auto if wf_auto in wf_files else (wf_files[0] if wf_files else None)
                    if wf_files:
                        self.ctrl_panel.add_dropdown("Instrucciones", "compound_workflow", wf_files,
                                                    default=default_wf)
                    else:
                        self.ctrl_panel.add_label("⚠️ Sin workflows en compuesta/plano/texto", color="#ffaa00")

                elif cat == "Escena":
                    tipos = ["Transicion", "Recurso", "Accion", "Dialogo", "Mixta"]
                    self.ctrl_panel.add_dropdown(
                        "Tipo de Escena", "tipo_pieza", tipos,
                        default=self.compound_state.get("tipo_pieza") or tipos[0],
                        callback=lambda v: self.compound_state.update({"tipo_pieza": v})
                    )
                    if not self.compound_state.get("tipo_pieza"):
                        self.compound_state["tipo_pieza"] = tipos[0]
                    # Workflow de instrucciones para Escena
                    wf_folder = os.path.join(os.path.dirname(__file__), "workflows", "compuesta", "escena", "texto")
                    wf_files = [f for f in os.listdir(wf_folder) if f.endswith(".json")] if os.path.exists(wf_folder) else []
                    if wf_files:
                        self.ctrl_panel.add_dropdown("Instrucciones", "compound_workflow", wf_files,
                                                    default=wf_files[0])
                    else:
                        self.ctrl_panel.add_label("⚠️ Sin workflows en compuesta/escena/texto", color="#ffaa00")

            if self.compound_state["subtype"] == "Productos" or self.compound_state["category"] == "Sinopsis":
                self.ctrl_panel.add_button("📎 Gestionar Referencias", self._open_reference_manager)
                ref_count = len(self.compound_state["references"])
                self.ctrl_panel.add_label(f"📦 {ref_count} referencias activas.", color="#4EC9B0")
        
        else:
            # Upgrade Grades (G2, G3, G4)
            target_grade = {"Imagen": 1, "Audio": 2, "Video": 3, "3D": 1}.get(mode, 1)
            # Cargar lista de documentos compatibles
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            docs_resp = loop.run_until_complete(self.list_compound_docs(grade=target_grade))
            loop.close()
            
            docs = docs_resp.get("result", [])
            doc_names = [d["name"] for d in docs] if docs else ["Sin documentos compatibles"]
            
            self.ctrl_panel.add_dropdown(f"Documento Origen (G{target_grade})", "source_doc", 
                                        doc_names, 
                                        callback=lambda v: self._on_source_doc_change(v, docs))

    def _on_subtype_change(self, val):
        self.compound_state["subtype"] = val
        self.compound_state["category"] = self.CONFIG_COMPUESTA[val][0]
        self._update_controllers_logic(self.current_mode)

    def _on_category_change(self, val):
        self.compound_state["category"] = val
        self.compound_state["tipo_pieza"] = None  # Resetear tipo al cambiar categoría
        self._update_controllers_logic(self.current_mode)

    def _on_source_doc_change(self, name, docs):
        for d in docs:
            if d["name"] == name:
                self.compound_state["source_doc"] = d["path"]
                break

    def _open_reference_manager(self):
        """Ventana emergente mejorada con categorías y checkboxes."""
        import tkinter as tk
        from tkinter import ttk
        top = tk.Toplevel(self.workspace)
        top.title("Gestionar Referencias")
        top.geometry("500x600")
        top.configure(bg=self.style.get_color("bg_main"))
        
        # 1. Cabecera y Filtros
        tk.Label(top, text="GESTOR DE REFERENCIAS", bg=self.style.get_color("bg_main"),
                 fg=self.style.get_color("accent"), font=("Arial", 11, "bold")).pack(pady=10)
        
        filter_frame = tk.Frame(top, bg=self.style.get_color("bg_main"))
        filter_frame.pack(fill=tk.X, padx=10, pady=5)
        
        categories = ["TODOS", "Personaje", "Escenario", "Prop", "Sinopsis", "Productos", "Finales"]
        self._ref_filter = tk.StringVar(value="TODOS")
        
        for cat in categories:
            btn = tk.Radiobutton(filter_frame, text=cat.upper(), variable=self._ref_filter, value=cat,
                                 indicatoron=0, bg=self.style.get_color("bg_dark"), fg="white",
                                 selectcolor=self.style.get_color("accent"), bd=0, padx=5, pady=2,
                                 command=lambda: refresh_list())
            btn.pack(side=tk.LEFT, padx=2)

        # 2. Lista con Scroll
        container = tk.Frame(top, bg=self.style.get_color("bg_dark"))
        container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        canvas = tk.Canvas(container, bg=self.style.get_color("bg_dark"), highlightthickness=0)
        scrollbar = tk.Scrollbar(container, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg=self.style.get_color("bg_dark"))
        
        scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Cargar datos
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        pieces_resp = loop.run_until_complete(self.list_all_compound_pieces())
        loop.close()
        
        res = pieces_resp.get("result", {})
        all_pieces = res.get("ingredients", []) + res.get("products", []) + res.get("finals", [])
        
        # Estado persistente durante la vida de la ventana
        current_selection = set(self.compound_state["references"])
        checkbox_vars = {} # Map path -> BooleanVar

        def on_toggle(path, var):
            if var.get():
                current_selection.add(path)
            else:
                if path in current_selection:
                    current_selection.discard(path)

        def refresh_list():
            for widget in scrollable_frame.winfo_children():
                widget.destroy()
            
            f = self._ref_filter.get()
            ingredients_cats = ["Personaje", "Escenario", "Prop", "Sinopsis"]
            products_cats = ["Plano", "Escena", "Secuencia"]
            finals_cats = ["Pelicula", "Documental", "Explicativo", "Noticias", "Musical", "Archviz", "Publicidad"]
            for p in all_pieces:
                # Filtrar
                if f != "TODOS":
                    if f == "Productos" and p["category"] not in products_cats: continue
                    if f == "Finales" and p["category"] not in finals_cats: continue
                    if f not in ("Productos", "Finales") and p["category"] != f: continue
                
                path = p["path"]
                if path not in checkbox_vars:
                    checkbox_vars[path] = tk.BooleanVar(value=path in current_selection)

                # Fila personalizada
                row = tk.Frame(scrollable_frame, bg=self.style.get_color("bg_dark"), pady=2)
                row.pack(fill=tk.X, expand=True)
                
                var = checkbox_vars[path]
                cb = tk.Checkbutton(row, variable=var, 
                                    bg=self.style.get_color("bg_dark"), 
                                    activebackground=self.style.get_color("bg_dark"),
                                    selectcolor="#333", # Color más claro para el fondo del check
                                    fg="white", 
                                    command=lambda p=path, v=var: on_toggle(p, v))
                cb.pack(side=tk.LEFT)
                
                icon = {
                    "Personaje": "👤", "Escenario": "🌄", "Prop": "⛺", "Sinopsis": "📖",
                    "Plano": "🎬", "Escena": "🎞️", "Secuencia": "📽️",
                    "Pelicula": "🏆", "Documental": "📰", "Explicativo": "📚",
                    "Noticias": "📡", "Musical": "🎵", "Archviz": "🏢", "Publicidad": "🛍️"
                }.get(p["category"], "📄")
                lbl_text = f"{icon} {p['name']}"
                tk.Label(row, text=lbl_text, bg=self.style.get_color("bg_dark"),
                         fg="white", font=("Arial", 9)).pack(side=tk.LEFT, padx=5)

        refresh_list()

        def on_save():
            self.compound_state["references"] = list(current_selection)
            top.destroy()
            self._update_controllers_logic(self.current_mode)
            
        tk.Button(top, text="GUARDAR SELECCIÓN", bg=self.style.get_color("accent"), fg="white",
                  bd=0, padx=20, pady=10, font=("Arial", 10, "bold"), command=on_save).pack(pady=10)

    def get_widget(self, parent):
        """Sobrescribe el layout estándar para poner resultados ARRIBA y controles ABAJO."""
        from modules.widgets import HorizontalMenu, ControllerPanel, GalleryWidget
        
        main_frame = tk.Frame(parent, bg=self.style.get_color("bg_main"))
        
        # 1. Menú Superior (Siempre arriba)
        if self.show_menu and self.menu_items:
            self.menu = HorizontalMenu(
                main_frame, 
                items=self.menu_items, 
                callback=self.on_menu_change,
                style=self.style
            )
            self.menu.pack(fill=tk.X, pady=(0, 2), side=tk.TOP)

        # 2. Área de Resultados (CENTRO) - Expandible
        self.sub_widget_area = tk.Frame(main_frame, bg=self.style.get_color("bg_main"))
        self.sub_widget_area.columnconfigure(0, weight=0)
        self.sub_widget_area.columnconfigure(1, weight=1)
        self.sub_widget_area.rowconfigure(1, weight=1)

        # Galería con soporte de navegación
        if self.show_gallery:
            self._create_gallery_controls()
            self.gallery = GalleryWidget(self.sub_widget_area, title=self.gallery_title, 
                                         style=self.style, on_back=self._on_gallery_back)
            if self.gallery_visible:
                self.gallery.grid(row=1, column=0, sticky="nsew", padx=(0, 10))

        # Workspace
        self.workspace = tk.Frame(self.sub_widget_area, bg=self.style.get_color("bg_main"))
        self.workspace.grid(row=1, column=1, sticky="nsew")

        # 3. Separador sutil (Abajo de resultados)
        self.separator = tk.Frame(main_frame, bg="#333", height=1)

        # 4. Render inicial del workspace (DEBE ser antes de setup_controllers)
        self.render_workspace(self.workspace)

        # 5. Panel de Controladores (ABAJO)
        if self.show_controllers:
            self.ctrl_panel = ControllerPanel(main_frame, style=self.style)
            self.ctrl_panel.pack(fill=tk.X, side=tk.BOTTOM, padx=20, pady=(10, 20))
            
            # Dibujar prompt y botones dentro del panel (abajo)
            self.render_top_actions(self.ctrl_panel.actions_container)
            self.setup_controllers(self.ctrl_panel)

        # Empaquetamos el área de contenido (Resultados)
        self.separator.pack(fill=tk.X, side=tk.BOTTOM)
        self.sub_widget_area.pack(fill=tk.BOTH, expand=True, padx=20, pady=(10, 0), side=tk.TOP)

        return main_frame

    def _on_gallery_back(self):
        """Sube un nivel en la galería."""
        if self.gallery_path != self.output_root:
            self.gallery_path = os.path.dirname(self.gallery_path)
            self._refresh_gallery_from_disk()

    def render_top_actions(self, parent):
        """Dibuja el área de prompt y botones en el panel inferior."""
        frame = tk.Frame(parent, bg=self.style.get_color("bg_main"))
        frame.pack(fill=tk.BOTH, expand=True)

        # Caja de Prompt Positivo
        tk.Label(frame, text="Prompt Positivo:", fg=self.style.get_color("text_dim"), bg=self.style.get_color("bg_main"), 
                 font=("Arial", 9)).pack(anchor="w")
        
        self.prompt_text = tk.Text(frame, bg=self.style.get_color("bg_dark"), fg=self.style.get_color("text_main"), bd=0, 
                                   font=("Arial", 10), height=3, width=35, padx=10, pady=10,
                                   insertbackground=self.style.get_color("text_main"))
        self.prompt_text.pack(fill=tk.NONE, side=tk.TOP, anchor="e", pady=(5, 5))
        
        # Caja de Prompt Negativo (NUEVO)
        tk.Label(frame, text="Prompt Negativo:", fg=self.style.get_color("text_dim"), bg=self.style.get_color("bg_main"), 
                 font=("Arial", 8)).pack(anchor="e")
        
        self.neg_prompt_text = tk.Text(frame, bg=self.style.get_color("bg_dark"), fg=self.style.get_color("text_main"), bd=0, 
                                      font=("Arial", 9), height=2, width=35, padx=8, pady=8,
                                      insertbackground=self.style.get_color("text_main"))
        self.neg_prompt_text.pack(fill=tk.NONE, side=tk.TOP, anchor="e", pady=(0, 10))

        # Placeholders
        p_pos = f"Escribe aquí lo que quieres generar..."
        p_neg = "low quality, blurry, static, text, watermark, deformed, bad proportions"
        
        self.prompt_text.insert("1.0", p_pos)
        self.prompt_text.config(fg="#888")
        self.neg_prompt_text.insert("1.0", p_neg)
        self.neg_prompt_text.config(fg=self.style.get_color("text_main")) # Ya no es placeholder, es default

        def on_focus_in(e, widget, ph):
            if widget.get("1.0", tk.END).strip() == ph:
                widget.delete("1.0", tk.END)
                widget.config(fg=self.style.get_color("text_main"))

        def on_focus_out(e, widget, ph):
            if not widget.get("1.0", tk.END).strip():
                widget.insert("1.0", ph)
                widget.config(fg="#888")

        self.prompt_text.bind("<FocusIn>", lambda e: on_focus_in(e, self.prompt_text, p_pos))
        self.prompt_text.bind("<FocusOut>", lambda e: on_focus_out(e, self.prompt_text, p_pos))
        # El prompt negativo ahora tiene un valor real por defecto, no necesita placeholder reactivo



        # Botonera
        actions_frame = tk.Frame(frame, bg=self.style.get_color("bg_main"))
        actions_frame.pack(fill=tk.X)

        btn_generate = tk.Button(actions_frame, text=f"✨ Generar", 
                                bg=self.style.get_color("accent"), fg=self.style.get_color("btn_fg"), bd=0, padx=20, pady=8,
                                font=("Arial", 10, "bold"), cursor="hand2", command=self.handle_generate)
        btn_generate.pack(side=tk.RIGHT, padx=(0, 10))

        btn_clear = tk.Button(actions_frame, text="🗑️ Limpiar", 
                             bg=self.style.get_color("btn_bg"), fg=self.style.get_color("text_dim"), bd=0, padx=15, pady=8,
                             font=("Arial", 9), cursor="hand2", command=self._clear_all)
        btn_clear.pack(side=tk.RIGHT, padx=5)

        # Botón para mostrar ingredientes (NUEVO)
        self.btn_ing = tk.Button(actions_frame, text="📦", 
                                 bg=self.style.get_color("btn_bg"), fg=self.style.get_color("text_dim"), bd=0, padx=10, pady=8,
                                 font=("Arial", 10), cursor="hand2", command=self._toggle_ingredient_panel)
        self.btn_ing.pack(side=tk.RIGHT, padx=5)

        # Panel de Ingredientes (NUEVO, oculto por defecto)
        # Lo ponemos dentro de un frame que flote a la derecha
        self.ingredient_panel = tk.LabelFrame(parent, text=" REFERENCIAS / INGREDIENTES ", 
                                              bg=self.style.get_color("bg_main"), fg=self.style.get_color("accent"),
                                              font=("Arial", 8, "bold"), padx=10, pady=10)
        # No hacemos pack aún

    def _toggle_ingredient_panel(self):
        """Muestra u oculta el panel de selección de ingredientes."""
        if not hasattr(self, "ingredient_panel"): return
        
        if self.ingredient_panel_visible:
            self.ingredient_panel.pack_forget()
            self.btn_ing.config(bg=self.style.get_color("btn_bg"), fg=self.style.get_color("text_dim"))
        else:
            # Empaquetar a la derecha
            self.ingredient_panel.pack(side=tk.RIGHT, fill=tk.Y, padx=(10, 0))
            self.btn_ing.config(bg=self.style.get_color("accent"), fg=self.style.get_color("btn_fg"))
        
        self.ingredient_panel_visible = not self.ingredient_panel_visible

    def render_workspace(self, parent):
        """Dibuja el visor de resultados (ocupando la parte superior)."""
        # Widget Modular de Visualización
        self.media_display = MediaDisplayWidget(parent, style=self.style)
        self.media_display.pack(fill=tk.BOTH, expand=True)

        # Llenar Galería dinámicamente desde disco
        self._refresh_gallery_from_disk()

    async def handle_generate_from_web(self, prompt: str, mode: str, params: dict = None):
        """Hook específico para peticiones desde el Dashboard Web (Awaitable)."""
        print(f"[MediaGenerator][Web] Generando {mode} para web: {prompt}")
        
        # Sincronizar parámetros si vienen (de forma segura con el hilo principal)
        if params and self.ctrl_panel:
            def sync_ui():
                for k, v in params.items():
                    # Resolución de rutas relativas de la galería web
                    if isinstance(v, str) and not os.path.isabs(v) and ("input_" in k or k == "input_image"):
                        abs_v = os.path.join(self.output_root, v)
                        if os.path.exists(abs_v):
                            v = abs_v
                    self.ctrl_panel.set_value(k, v)
            if hasattr(self, "workspace") and self.workspace:
                self.workspace.after(0, sync_ui)

        # Ejecutar la lógica de generación y esperar el resultado
        try:
            # Ahora inyectamos los parámetros directamente para no depender del hilo de la UI
            result = await self._perform_generation(prompt, mode, web_params=params)
            print(f"[MediaGenerator][Web] Resultado obtenido: {result}")
            
            # Si el resultado es una ruta de archivo, lo convertimos a URL estática
            if isinstance(result, str) and os.path.exists(result):
                # IMPORTANTE: Movemos el archivo de forma síncrona para que la URL sea válida ya mismo
                filename = os.path.basename(result)
                target_dir = os.path.join(self.output_root, mode.lower())
                os.makedirs(target_dir, exist_ok=True)
                
                final_path = os.path.join(target_dir, filename)
                if os.path.abspath(result) != os.path.abspath(final_path):
                    shutil.move(result, final_path)
                
                # Actualizar la UI local si existe
                if hasattr(self, "workspace") and self.workspace:
                    self.workspace.after(0, lambda: self._show_result(final_path))

                return {
                    "status": "success", 
                    "type": "file", 
                    "url": f"/v1/modules/{self.id}/output/{mode.lower()}/{filename}",
                    "filename": filename
                }
            else:
                # Es un resultado de texto
                if hasattr(self, "workspace") and self.workspace:
                    self.workspace.after(0, lambda: self._show_result(result))
                return {"status": "success", "type": "text", "content": result}
                
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def _get_compound_path(self, category):
        """Devuelve la subcarpeta correspondiente a una categoría."""
        cat_norm = str(category).capitalize() if category else ""
        
        # Ingredientes
        ingredient_map = {
            "Personaje": "Personajes",
            "Escenario": "Escenarios",
            "Prop": "Props",
            "Sinopsis": "Sinopsis"
        }
        # Productos intermedios
        product_map = {
            "Plano": "Planos",
            "Escena": "Escenas",
            "Secuencia": "Secuencias"
        }
        # Entregables finales
        final_map = {
            "Pelicula": "Peliculas",
            "Documental": "Documentales",
            "Explicativo": "Explicativos",
            "Noticias": "Noticias",
            "Musical": "Musicales",
            "Archviz": "Archviz",
            "Publicidad": "Publicidad"
        }
        
        base = os.path.join(self.output_root, "texto", "compuesto")
        if cat_norm in ingredient_map:
            return os.path.join(base, ingredient_map[cat_norm])
        elif cat_norm in product_map:
            return os.path.join(base, "Productos", product_map[cat_norm])
        elif cat_norm in final_map:
            return os.path.join(base, "Finales", final_map[cat_norm])
        else:
            return os.path.join(base, "Otros")

    async def list_compound_docs(self, grade=None):
        """Lista documentos compuestos filtrados por grado, buscando en subcarpetas."""
        comp_root = os.path.join(self.output_root, "texto", "compuesto")
        if not os.path.exists(comp_root): return {"status": "success", "result": []}
        
        docs = []
        for root, dirs, files in os.walk(comp_root):
            for filename in files:
                if filename.endswith(".json"):
                    path = os.path.join(root, filename)
                    try:
                        with open(path, "r", encoding="utf-8") as f:
                            data = json.load(f)
                            if grade is None or data.get("grado_desarrollo") == int(grade):
                                # Ruta relativa al root de compuesto para consistencia
                                rel_path = os.path.relpath(path, comp_root).replace("\\", "/")
                                docs.append({
                                    "name": data.get("titulo", filename),
                                    "path": f"texto/compuesto/{rel_path}",
                                    "grade": data.get("grado_desarrollo", 1),
                                    "category": data.get("categoria")
                                })
                    except: continue
        return {"status": "success", "result": docs}

    async def list_all_compound_pieces(self):
        """Lista todas las piezas para referencias, organizadas recursivamente por tipo."""
        comp_root = os.path.join(self.output_root, "texto", "compuesto")
        result = {"ingredients": [], "products": [], "finals": []}
        if not os.path.exists(comp_root): return {"status": "success", "result": result}

        ingredients_types = {"Personaje", "Escenario", "Prop", "Sinopsis"}
        products_types    = {"Plano", "Escena", "Secuencia"}
        finals_types      = {"Pelicula", "Documental", "Explicativo", "Noticias", "Musical", "Archviz", "Publicidad"}

        for root, dirs, files in os.walk(comp_root):
            for filename in files:
                if filename.endswith(".json"):
                    path = os.path.join(root, filename)
                    try:
                        with open(path, "r", encoding="utf-8") as f:
                            data = json.load(f)
                            rel_path = os.path.relpath(path, comp_root).replace("\\", "/")
                            piece = {
                                "name": data.get("titulo", filename),
                                "path": f"texto/compuesto/{rel_path}",
                                "category": data.get("categoria", ""),
                                "grade": data.get("grado_desarrollo", 1)
                            }
                            cat = piece["category"]
                            if cat in ingredients_types:
                                result["ingredients"].append(piece)
                            elif cat in products_types:
                                result["products"].append(piece)
                            elif cat in finals_types:
                                result["finals"].append(piece)
                            else:
                                result["products"].append(piece)  # Fallback
                    except: continue
        return {"status": "success", "result": result}

    def handle_generate_manual(self, prompt):
        """Versión de compatibilidad para disparar hilos desde la UI desktop."""
        def run():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                res = loop.run_until_complete(self._perform_generation(prompt, self.current_mode))
                self._cache_result_and_show(res, self.current_mode)
            except Exception as e:
                import traceback
                traceback.print_exc()
                self._cache_result_and_show(f"Error en la generación: {str(e)}", self.current_mode)
            finally:
                loop.close()
            
        threading.Thread(target=run, daemon=True).start()

    def handle_get_gallery(self, path=""):
        """Retorna la lista de archivos de la galería local expuestos vía API."""
        print(f"[MediaGenerator][Web] Galería solicitada para path: '{path}'")
        from pathlib import Path
        output_root = Path(self.output_root).resolve()
        
        # Resolver el path solicitado (ej: 'imagen')
        target_dir = output_root / path.strip("/\\")
        
        # Búsqueda insensible a mayúsculas si no existe la carpeta exacta
        if not target_dir.exists():
            clean_path = path.strip("/\\").lower()
            for entry in output_root.iterdir():
                if entry.is_dir() and entry.name.lower() == clean_path:
                    target_dir = entry
                    break
        
        # Resolver ruta final absoluta
        target_dir = target_dir.resolve()
        
        # Seguridad: No permitir salir de output_root
        if not str(target_dir).startswith(str(output_root)):
            target_dir = output_root
            
        if not target_dir.exists():
            target_dir = output_root # Fallback a raíz si no existe el path
            path = ""
            
        items = []
        # Añadir opción de subir nivel si no estamos en la raíz
        if path:
            p = Path(path)
            parent_path = str(p.parent) if p.parent != p else ""
            if parent_path == ".": parent_path = ""
            items.append({
                "name": ".. (Volver)",
                "type": "folder",
                "path": parent_path,
                "url": None
            })

        valid_exts = {'.png', '.jpg', '.jpeg', '.gif', '.webp', '.wav', '.mp3', '.ogg', '.mp4', '.avi', '.mov', '.txt', '.pdf', '.json', '.glb', '.obj'}
        
        try:
            # Listar subcarpetas primero, luego archivos
            entries = sorted(target_dir.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))
            
            for item in entries:
                rel_path = item.relative_to(output_root).as_posix()
                
                if item.is_dir():
                    items.append({
                        "name": item.name,
                        "type": "folder", # Usar 'folder' para compatibilidad con app.js
                        "path": rel_path,
                        "url": None
                    })
                elif item.suffix.lower() in valid_exts:
                    ext = item.suffix.lower()
                    # Mapear el tipo de archivo para el visor web
                    m_type = "image" if ext in ['.png', '.jpg', '.jpeg', '.gif', '.webp'] else \
                             "video" if ext in ['.mp4', '.avi', '.mov', '.webm'] else \
                             "audio" if ext in ['.wav', '.mp3', '.ogg', '.m4a'] else \
                             "3d" if ext in ['.glb', '.obj'] else "file"
                             
                    file_url = f"/v1/modules/{self.id}/output/{rel_path}"
                    items.append({
                        "name": item.name,
                        "type": m_type,
                        "path": rel_path,
                        "url": file_url,
                        "ext": ext[1:]
                    })
        except Exception as e:
            print(f"[MediaGenerator] Error listando galería: {e}")
            
        return {"items": items, "current_path": path}

    def _get_val(self, key, web_params=None, default=None):
        """Ayudante para obtener parámetros de forma segura (Thread-safe) priorizando la web."""
        # 1. Prioridad: Parámetros directos de la petición Web
        if web_params:
            if key in web_params: return web_params[key]
            # También buscar en el sub-diccionario 'params' si existe
            inner = web_params.get("params", {})
            if isinstance(inner, dict) and key in inner: return inner[key]

        # 2. Casos especiales de widgets fijos en Desktop
        if not web_params:
            if key == "neg_prompt" and hasattr(self, "neg_prompt_text"):
                return self.neg_prompt_text.get("1.0", tk.END).strip()

        # 3. Ultimo recurso: Leer del panel local (Tkinter)
        if self.ctrl_panel:
            return self.ctrl_panel.get_value(key, default)
            
        return default

    async def _perform_generation(self, prompt, mode, web_params=None):
        """Lógica centralizada y awaitable de generación."""
        print(f"[MediaGenerator] Generando {mode}... (Web Injected: {web_params is not None})")
        
        # --- LÓGICA DE GENERACIÓN COMPUESTA ---
        is_compound = False
        comp_params = None
        
        # Leer Prompt Negativo del widget si no viene de la web
        neg_prompt = None
        if not web_params and hasattr(self, "neg_prompt_text"):
            neg_prompt = self.neg_prompt_text.get("1.0", tk.END).strip()
            # Si es el placeholder, ignorar
            if "Lo que NO quieres" in neg_prompt: neg_prompt = ""
        
        # Detectar modo compuesto: leer directamente del estado interno (ya actualizado por callbacks)
        desktop_is_compound = (not web_params) and self.compound_state.get("type") == "Compuesto"

        if web_params:
            comp_state = web_params.get("compound", {})
            if comp_state.get("type") == "Compuesto":
                is_compound = True
                comp_params = web_params
        elif desktop_is_compound:
            is_compound = True
            comp_params = {
                "compound": self.compound_state,
                "source_doc": self.compound_state.get("source_doc")
            }

        if is_compound:
            # Inyectar neg_prompt en comp_params
            if neg_prompt:
                if "params" not in comp_params: comp_params["params"] = {}
                comp_params["params"]["neg_prompt"] = neg_prompt
            return await self._generate_compound(prompt, mode, comp_params)

        if mode == "Imagen":
            engine_name = self._get_val("engine", web_params, default="DALL-E 3")
            adapter = self.image_service.get_adapter(engine_name)
            if not adapter: raise Exception(f"Adaptador {engine_name} no encontrado")
            
            res = self._get_val("res", web_params, default="1024x1024")
            preset = self._get_val("resolution", web_params)
            w, h = 1024, 1024
            
            if preset == "Personalizado":
                w = self._get_val("resolution_w", web_params)
                h = self._get_val("resolution_h", web_params)
            elif preset:
                import re
                match = re.search(r"\((\d+)x(\d+)\)", str(preset))
                if match: w, h = match.groups()

            # Cargar workflow si es ComfyUI
            workflow_data = None
            if engine_name == "ComfyUI":
                w_file = self._get_val("workflow", web_params)
                if w_file:
                    w_type = self._get_val("type", web_params, default="Simple")
                    w_subtype = self._get_val("subtype", web_params)
                    
                    base_w = os.path.join(os.path.dirname(__file__), "workflows", w_type.lower())
                    if not os.path.exists(base_w):
                        base_w = os.path.join(os.path.dirname(__file__), "workflows", w_type.capitalize())
                    
                    if w_subtype:
                        base_w = os.path.join(base_w, w_subtype.lower())
                    
                    full_path = os.path.join(base_w, w_file)
                    print(f"[MediaGenerator] Workflow: {full_path}")
                    if os.path.exists(full_path):
                        try:
                            with open(full_path, "r", encoding="utf-8") as f:
                                workflow_data = json.load(f)
                        except Exception as e:
                            print(f"[MediaGenerator] Error workflow JSON: {e}")
                    else:
                        print(f"[MediaGenerator] ERROR: Workflow NO encontrado en {full_path}")

            # Imagen(es) de entrada
            input_images = []
            img_count = self._get_val("img_count", web_params) or "1"
            try:
                for i in range(1, int(img_count) + 1):
                    p_val = self._get_val(f"input_image_{i}", web_params)
                    if not p_val: p_val = self._get_val("input_image", web_params) if i==1 else None
                    
                    if p_val and p_val != "Ninguno":
                        # Resolver ruta si es relativa (importante para web)
                        if not os.path.isabs(p_val):
                            p_val = os.path.join(self.output_root, p_val)
                        if os.path.exists(p_val):
                            input_images.append(p_val)
            except: pass

            neg_prompt = self._get_val("neg_prompt", web_params, default="")
            
            # Recuperar y procesar Semilla (Seed)
            seed_val = self._get_val("seed", web_params, default="-1")
            try:
                seed = int(seed_val)
                if seed == -1:
                    import random
                    seed = random.randint(1, 1125899906842624) # Rango estándar de ComfyUI
            except:
                import random
                seed = random.randint(1, 1125899906842624)

            return await adapter.generate_image(prompt, resolution=res, workflow_json=workflow_data, width=w, height=h, input_images=input_images, negative_prompt=neg_prompt, seed=seed)
        
        elif mode == "Audio":
            tipo = self._get_val("audio_type", web_params)
            prov = self._get_val("audio_provider", web_params)
            
            if prov == "ComfyUI":
                w_file = self._get_val("audio_workflow", web_params)
                folder_map = {"Voces": "voices", "Música": "music", "Efectos": "sounds"}
                sub = folder_map.get(tipo, "voices")
                
                full_path = os.path.join(os.path.dirname(__file__), "workflows", "Audio", sub, w_file)
                workflow_data = None
                if os.path.exists(full_path):
                    try:
                        with open(full_path, "r", encoding="utf-8") as f:
                            workflow_data = json.load(f)
                    except: pass
                
                adapter = self.image_service.get_adapter("ComfyUI")
                extra_params = {}
                if tipo == "Música":
                    dur = self._get_val("audio_duration", web_params)
                    extra_params["bpm"] = self._get_val("audio_bpm", web_params)
                    extra_params["keyscale"] = self._get_val("audio_key", web_params)
                    extra_params["duration"] = dur
                    extra_params["seconds"] = dur
                    extra_params["lyrics"] = self._get_val("audio_lyrics", web_params)
                
                return await adapter.generate_image(prompt, workflow_json=workflow_data, **extra_params)
                
            elif "ASIMOD" in prov:
                voice_id = self._get_val("audio_voice", web_params)
                prov_key = "Edge TTS" if "Edge" in prov else "Local TTS"
                return await self.chat_service.voice_service.generate_audio_only(prompt, voice_id=voice_id, voice_provider=prov_key)

        elif mode == "3D":
             g_type = self._get_val("3d_type", web_params)
             prov = self._get_val("3d_provider", web_params)
             
             if prov == "ComfyUI":
                 w_file = self._get_val("3d_workflow", web_params)
                 folder_map = {"Texto a 3D": "text_to_3d", "Imagen a 3D": "img_to_3d"}
                 sub = folder_map.get(g_type, "text_to_3d")
                 full_path = os.path.join(os.path.dirname(__file__), "workflows", "3d", sub, w_file)
                 workflow_data = None
                 if os.path.exists(full_path):
                     try:
                         with open(full_path, "r", encoding="utf-8") as f:
                             workflow_data = json.load(f)
                     except: pass
                 
                 adapter = self.image_service.get_adapter("ComfyUI")
                 input_images = []
                 if g_type == "Imagen a 3D":
                     img_path = self._get_val("3d_input_image", web_params)
                     if img_path and img_path != "Ninguno":
                         if not os.path.isabs(img_path): img_path = os.path.join(self.output_root, img_path)
                         if os.path.exists(img_path): input_images.append(img_path)
                 
                 return await adapter.generate_image(prompt, workflow_json=workflow_data, input_images=input_images)
             else:
                 return f"Error: Proveedor {prov} no disponible manualmente."

        elif mode == "Video":
            v_type = self._get_val("video_type", web_params, default="Simple")
            v_subtype = self._get_val("video_subtype", web_params, default="text2video")
            w_file = self._get_val("video_workflow", web_params)
            
            if not w_file:
                return "Error: No se ha seleccionado ningún workflow de video."
            
            base_w = os.path.join(os.path.dirname(__file__), "workflows", "video", v_type.lower())
            if v_subtype:
                base_w = os.path.join(base_w, v_subtype.lower())
            
            full_path = os.path.join(base_w, w_file)
            workflow_data = None
            if os.path.exists(full_path):
                try:
                    with open(full_path, "r", encoding="utf-8") as f:
                        workflow_data = json.load(f)
                except Exception as e:
                    print(f"[MediaGenerator] Error cargando workflow de video: {e}")
            else:
                return f"Error: No se encuentra el archivo de workflow de video: {w_file}"
            
            # Recoger inputs dinámicos
            input_files = []
            if v_subtype == "Img+Audio2Video":
                img = self._get_val("input_image", web_params)
                if img and img != "Ninguno": 
                    if not os.path.isabs(img): img = os.path.join(self.output_root, img)
                    if os.path.exists(img): input_files.append(img)
                
                count_val = self._get_val("v_audio_count", web_params) or "1"
                try: count = int(count_val)
                except: count = 1

                for i in range(1, count + 1):
                    a_path = self._get_val(f"input_audio_{i}", web_params)
                    if a_path and a_path != "Ninguno":
                        if not os.path.isabs(a_path): a_path = os.path.join(self.output_root, a_path)
                        if os.path.exists(a_path): input_files.append(a_path)
                
                # Inyección quirúrgica en el workflow para audios extra
                if workflow_data and count > 1:
                    multitalk_node = workflow_data.get("18")
                    if multitalk_node and "19" in workflow_data:
                        for i in range(2, count + 1):
                            new_id = str(100 + i)
                            new_node = json.loads(json.dumps(workflow_data["19"]))
                            workflow_data[new_id] = new_node
                            multitalk_node["inputs"][f"audio_{i}"] = [new_id, 0]
            else:
                for k in ["input_image", "input_audio", "input_video"]:
                    val = self._get_val(k, web_params)
                    if val and val != "Ninguno":
                        if not os.path.isabs(val): val = os.path.join(self.output_root, val)
                        if os.path.exists(val): input_files.append(val)
            
            # Resolución de Video
            preset = self._get_val("video_resolution", web_params, default="Apaisada SD (640x480)")
            w, h = 640, 640 
            if preset == "Personalizado":
                w = self._get_val("video_resolution_w", web_params, default=640)
                h = self._get_val("video_resolution_h", web_params, default=640)
            elif preset:
                import re
                match = re.search(r"\((\d+)x(\d+)\)", str(preset))
                if match: w, h = match.groups()
            
            dur = self._get_val("video_duration", web_params, default=5)
            neg_prompt = self._get_val("neg_prompt", web_params, default="")
            
            print(f"[MediaGenerator] Generando video ({w}x{h}, {dur}s) con ComfyUI. Inputs: {len(input_files)}")
            adapter = self.image_service.get_adapter("ComfyUI")
            return await adapter.generate_image(prompt, 
                                                workflow_json=workflow_data, 
                                                input_images=input_files, 
                                                negative_prompt=neg_prompt,
                                                width=w, height=h, 
                                                duration=dur)
        
        elif mode == "3D":
             g_type = self._get_val("3d_type", web_params, default="Texto a 3D")
             g_provider = self._get_val("3d_provider", web_params, default="ComfyUI")
             w_file = self._get_val("3d_workflow", web_params)
             
             if not w_file:
                 return "Error: No se ha seleccionado ningún workflow 3D."
             
             folder_map = {"Texto a 3D": "text_to_3d", "Imagen a 3D": "img_to_3d"}
             sub = folder_map.get(g_type, "text_to_3d")
             
             full_path = os.path.join(os.path.dirname(__file__), "workflows", "3d", sub, w_file)
             workflow_data = None
             if os.path.exists(full_path):
                 try:
                     with open(full_path, "r", encoding="utf-8") as f:
                         workflow_data = json.load(f)
                 except Exception as e:
                     print(f"[MediaGenerator] Error cargando workflow 3D: {e}")
             else:
                 return f"Error: No se encuentra el archivo de workflow: {w_file}"
             
             input_files = []
             img_input = self._get_val("3d_input_image", web_params)
             if img_input and img_input != "Ninguno":
                 if not os.path.isabs(img_input): img_input = os.path.join(self.output_root, img_input)
                 if os.path.exists(img_input): input_files.append(img_input)
             
             print(f"[MediaGenerator] Generando 3D ({g_type}) con {g_provider}. Inputs: {len(input_files)}")
             
             if g_provider == "ComfyUI":
                 adapter = self.image_service.get_adapter("ComfyUI")
                 return await adapter.generate_image(prompt, workflow_json=workflow_data, input_images=input_files)
             else:
                 return f"Error: Proveedor {g_provider} no soportado para 3D todavía."
        
        else:
            # Texto (Fallback por defecto)
            # Intentar obtener valores del panel de texto si están disponibles
            provider = self.ctrl_panel.get_value("provider") if (hasattr(self, 'ctrl_panel') and self.ctrl_panel) else None
            model = self.ctrl_panel.get_value("model") if (hasattr(self, 'ctrl_panel') and self.ctrl_panel) else None
            
            # Sincronizar proveedor si se especifica y es distinto al actual
            if provider and (not self.chat_service.current_adapter or self.chat_service.current_adapter.name != provider):
                self.chat_service.switch_provider(provider)
            
            adapter = self.chat_service.current_adapter
            if not adapter:
                raise Exception("No hay un motor de LLM configurado en el núcleo.")
            
            # --- AISLAMIENTO ESTRATÉGICO ---
            print(f"[MediaGenerator] Ejecutando generación pura aislada con {adapter.name}")
            
            generator_system = (
                "Eres un motor de generación de contenido profesional de alta precisión. "
                "Tu única tarea es producir el contenido solicitado por el usuario. "
                "REGLAS CRÍTICAS:\n"
                "1. NO incluyas saludos, introducciones ni despedidas.\n"
                "2. NO actúes como un asistente personal ni uses tu nombre.\n"
                "3. Responde ÚNICAMENTE con el contenido solicitado.\n"
                "4. SI ES UNA CANCIÓN/LETRA: NO incluyas indicadores como [VERSO], [CORO], [INTRO], [OUTRO], ni títulos como '--- LETRAS ---'.\n"
                "5. SI ES UNA CANCIÓN/LETRA: NO incluyas descripciones entre paréntesis como (Piano suave) o (Fade out).\n"
                "6. Mantén el formato solicitado de forma estricta."
            )
            
            history = [{"role": "user", "content": prompt}]
            max_t = self.chat_service.config.get("max_tokens", 1024)
            temp = self.chat_service.config.get("temperature", 0.7)
            target_model = model or self.chat_service.config.get("last_model")

            result = await adapter.generate_chat(
                history=history, 
                system_prompt=generator_system, 
                model=target_model, 
                images=None, 
                max_tokens=max_t, 
                temperature=temp
            )
            
            # Limpieza post-proceso para letras
            text_result = str(result).strip()
            import re
            # Eliminar títulos tipo --- LETRAS ---
            text_result = re.sub(r'^--- .* ---$', '', text_result, flags=re.MULTILINE)
            # Eliminar indicadores tipo [VERSO 1], [CORO], etc.
            text_result = re.sub(r'\[.*?\]', '', text_result)
            # Eliminar indicaciones entre paréntesis tipo (Acordes suaves), (FADE OUT)
            text_result = re.sub(r'\(.*?\)', '', text_result)
            # Eliminar múltiples saltos de línea y espacios sobrantes
            text_result = "\n".join([line.strip() for line in text_result.split("\n") if line.strip()])
            
            return text_result
        
        return None

    async def _generate_compound(self, prompt, mode, web_params):
        """Maneja el pipeline de 4 grados para piezas compuestas."""
        comp_state = web_params.get("compound", {})
        subtype = comp_state.get("subtype")
        category = comp_state.get("category")
        source_path = web_params.get("source_doc")
        
        # Determinar el grado objetivo basado en el panel (modo)
        grade_map = {"Texto": 1, "Imagen": 2, "Audio": 3, "Video": 4}
        target_grade = grade_map.get(mode, 1)
        
        print(f"[MediaGenerator][Compound] Generando {category} G{target_grade}. Origen: {source_path}")

        # 1. Cargar Receta (Instrucciones)
        recipe = self._load_recipe(category)
        
        # 2. Cargar o Inicializar Datos
        piece_data = {}
        if target_grade == 1:
            # Creación inicial
            piece_id = f"{category.lower()}_{int(time.time())}"
            piece_data = {
                "id": piece_id,
                "titulo": prompt.split("\n")[0][:50] if prompt else f"Nueva {category}",
                "categoria": category,
                "subtipo": subtype,
                "grado_desarrollo": 1,
                "prompt_original": prompt,
                "referencias": comp_state.get("references", []),
                "metadata": {}
            }
        else:
            # Upgrade de grado
            if not source_path: raise Exception("Se requiere un documento origen para subir de grado.")
            abs_source = os.path.join(self.output_root, source_path)
            with open(abs_source, "r", encoding="utf-8") as f:
                piece_data = json.load(f)
            
            if piece_data["grado_desarrollo"] >= target_grade:
                print(f"[Warning] La pieza ya está en grado {piece_data['grado_desarrollo']}")

        # 3. Lógica específica por Grado
        if target_grade == 1:
            # Grado 1: Texto base via LLM
            tipo_pieza = comp_state.get("tipo_pieza")
            target_info = ""
            tipo_field = {}

            if category == "Sinopsis":
                target_p = web_params.get("compound", {}).get("target_product", "Plano")
                target_info = f" destinada a un {target_p}"

            elif category == "Plano":
                if tipo_pieza:
                    tipo_field = {"tipo_plano": tipo_pieza}
                    target_info = f" de tipo '{tipo_pieza}'"

            elif category == "Escena":
                # Calcular tipo automáticamente desde las referencias de planos
                refs = comp_state.get("references", [])
                tipos_encontrados = set()
                for ref_path in refs:
                    try:
                        abs_ref = os.path.join(self.output_root, ref_path)
                        if not os.path.isabs(ref_path):
                            comp_root = os.path.join(self.output_root, "texto", "compuesto")
                            abs_ref = os.path.join(comp_root, ref_path.replace("texto/compuesto/", ""))
                        with open(abs_ref, "r", encoding="utf-8") as f:
                            ref_data = json.load(f)
                        if ref_data.get("categoria") == "Plano" and ref_data.get("tipo_plano"):
                            tipos_encontrados.add(ref_data["tipo_plano"])
                    except Exception as e:
                        print(f"[Compound] No se pudo leer referencia {ref_path}: {e}")

                if tipos_encontrados:
                    tipo_calculado = list(tipos_encontrados)[0] if len(tipos_encontrados) == 1 else "Mixta"
                else:
                    tipo_calculado = tipo_pieza or "Mixta"

                tipo_field = {"tipo_escena": tipo_calculado}
                target_info = f" de tipo '{tipo_calculado}'"
                print(f"[Compound] Tipo de escena calculado: {tipo_calculado} (planos ref: {tipos_encontrados})")

            # Añadir campos de tipo al piece_data
            piece_data.update(tipo_field)

            # --- Cargar system_prompt del workflow (auto-mapeado por tipo) ---
            workflow_system_p = None
            tipo_pieza_lower = (tipo_pieza or "").lower()
            # Auto-mapear: primero intentar el archivo del tipo, luego el seleccionado manualmente
            wf_file = None
            if category in ("Plano", "Escena") and tipo_pieza_lower:
                cat_lower = category.lower()
                auto_wf = f"{cat_lower}_{tipo_pieza_lower}.json"
                auto_wf_path = os.path.join(os.path.dirname(__file__), "workflows", "compuesta", cat_lower, "texto", auto_wf)
                if os.path.exists(auto_wf_path):
                    wf_file = auto_wf
                else:
                    # Fallback al seleccionado manualmente en el panel
                    wf_file = self._get_val("compound_workflow", web_params)

            if wf_file and category in ("Plano", "Escena"):
                cat_lower = category.lower()
                wf_path = os.path.join(os.path.dirname(__file__), "workflows", "compuesta", cat_lower, "texto", wf_file)
                if os.path.exists(wf_path):
                    try:
                        with open(wf_path, "r", encoding="utf-8") as f:
                            wf_data = json.load(f)
                        raw_sys = wf_data.get("system_prompt", "")
                        # Sustituir variables de tipo
                        tipo_val = list(tipo_field.values())[0] if tipo_field else ""
                        tipo_accion_val = comp_state.get("tipo_accion") or self._get_val("tipo_accion", web_params) or "Accion Lenta"
                        workflow_system_p = (raw_sys
                            .replace("{tipo_plano}", tipo_val)
                            .replace("{tipo_escena}", tipo_val)
                            .replace("{tipo_accion}", tipo_accion_val)
                        )
                        # Inyectar tipo_accion al piece_data si es un plano de accion
                        if category == "Plano" and tipo_pieza == "Accion":
                            piece_data["tipo_accion"] = tipo_accion_val
                        print(f"[Compound] Usando workflow auto: {wf_file}")
                    except Exception as e:
                        print(f"[Compound] Error cargando workflow: {e}")

            if workflow_system_p:
                system_p = workflow_system_p
                if piece_data.get("referencias"):
                    system_p += f"\nIngredientes asociados: {self._load_references_content(piece_data['referencias'])}"
            else:
                system_p = f"Eres un experto en pre-producción cinematográfica. Crea un JSON descriptivo para un {category}{target_info} basándote en: {prompt}."
                if piece_data["referencias"]:
                    system_p += f"\nIngredientes asociados: {self._load_references_content(piece_data['referencias'])}"
                if tipo_field:
                    system_p += f"\nEl resultado DEBE reflejar el tipo '{list(tipo_field.values())[0]}' en su contenido narrativo y técnico."

            # Usar chat_service para generar el texto base
            resp = await self.chat_service.generate_chat([{"role":"user", "content":prompt}], system_prompt=system_p)
            try:
                llm_json = json.loads(str(resp))
                piece_data.update(llm_json)
                # Preservar campos de tipo aunque el LLM los sobreescriba
                piece_data.update(tipo_field)
            except:
                piece_data["descripcion_generada"] = str(resp)

            piece_data["grado_desarrollo"] = 1

            # --- AUTO-INGREDIENTES PARA PLANO ---
            if category == "Plano":
                await self._auto_create_plano_ingredients(piece_data, comp_state, prompt)

        elif target_grade == 2:
            # Grado 2: Imagen + Enriquecimiento Narrativo + Audio Plan
            print("[Compound] Escalando a Grado 2: Imagen y Guion...")
            
            # A. Enriquecimiento Narrativo y Plan de Audio via LLM
            enrich_prompt = f"Desarrolla el guion técnico y planifica el audio para este {category} G1."
            refs_content = self._load_references_content(piece_data.get("referencias", []))
            system_p = f"Datos base: {json.dumps(piece_data)}\nIngredientes referenciados: {refs_content}\n"
            system_p += "Genera un JSON con campos 'guion_detallado' (acciones y diálogos) y 'audio_plan' (voces, música, FX)."
            
            resp = await self.chat_service.generate_chat([{"role":"user", "content":enrich_prompt}], system_prompt=system_p)
            try:
                enrich_data = json.loads(self._clean_json_markdown(str(resp)))
                piece_data.update(enrich_data)
            except:
                piece_data["error_enriquecimiento"] = str(resp)

            # B. Generación de Imagen (via ComfyUI)
            img_recipe = recipe.get("grades", {}).get("2", {})
            if img_recipe.get("workflow_folder"):
                adapter = self.image_service.get_adapter("ComfyUI")
                
                # --- FASE 1: IMAGEN PRINCIPAL ---
                main_wf_path = os.path.join(os.path.dirname(__file__), img_recipe["workflow_folder"], img_recipe["default_workflow"])
                with open(main_wf_path, "r", encoding="utf-8") as f:
                    main_wf = json.load(f)
                
                # Usar descripción generada como prompt (Confirmado por usuario)
                p_text = piece_data.get("descripcion_generada", piece_data.get("descripcion_detallada", prompt))
                print(f"[Compound] Generando Imagen Principal para {category}...")
                main_img_res = await adapter.generate_image(p_text, workflow_json=main_wf)
                
                if isinstance(main_img_res, str) and os.path.exists(main_img_res):
                    if "multimedia" not in piece_data: piece_data["multimedia"] = {}
                    piece_data["multimedia"]["imagen_principal"] = os.path.basename(main_img_res)
                    # También lo guardamos en la lista general para compatibilidad con la galería
                    if "imagenes" not in piece_data["multimedia"]: piece_data["multimedia"]["imagenes"] = []
                    piece_data["multimedia"]["imagenes"].append(os.path.basename(main_img_res))
                    
                    # --- FASE 2: MULTIPLANO (Solo Personajes) ---
                    if category == "Personaje":
                        print("[Compound] Iniciando Fase 2 (Multiplano) para Personaje...")
                        multi_wf_path = os.path.join(os.path.dirname(__file__), img_recipe["workflow_folder"], "multi_view.json")
                        
                        if os.path.exists(multi_wf_path):
                            with open(multi_wf_path, "r", encoding="utf-8") as f:
                                multi_wf = json.load(f)
                            
                            # Pasamos la imagen principal como input para mayor consistencia
                            # El adaptador de ComfyUI se encargará de inyectarla en el nodo LoadImage
                            multi_res = await adapter.generate_image(p_text, workflow_json=multi_wf, input_images=[main_img_res])
                            
                            # Procesar resultados (pueden ser uno o varios archivos)
                            multi_list = []
                            if isinstance(multi_res, str):
                                multi_list.append(os.path.basename(multi_res))
                                piece_data["multimedia"]["imagenes"].append(os.path.basename(multi_res))
                            elif isinstance(multi_res, list):
                                for r in multi_res:
                                    multi_list.append(os.path.basename(r))
                                    piece_data["multimedia"]["imagenes"].append(os.path.basename(r))
                            
                            piece_data["multimedia"]["hoja_diseno"] = multi_list

                    # --- EXPORTACIÓN AL REPOSITORIO GLOBAL (NUEVO) ---
                    if category == "Personaje":
                        try:
                            import shutil
                            char_name = piece_data.get("titulo", piece_data.get("id"))
                            reg_path = os.path.join("Resources", "Characters", char_name)
                            if not os.path.exists(reg_path):
                                os.makedirs(reg_path, exist_ok=True)
                            
                            # Extraer descripción si existe el JSON interno
                            personality = ""
                            if "descripcion_generada" in piece_data:
                                desc = piece_data["descripcion_generada"]
                                if "```json" in desc:
                                    try:
                                        inner = json.loads(desc.split("```json")[1].split("```")[0])
                                        personality = f"Arquetipo: {inner.get('archetype')}. Personalidad: {', '.join(inner.get('personality_and_traits', {}).get('personality_traits', []))}"
                                    except: pass
                            
                            # Generar JSON simplificado para el Core
                            reg_data = {
                                "id": piece_data["id"],
                                "name": char_name,
                                "personality": personality,
                                "avatar": piece_data.get("avatar", {}),
                                "voice_id": piece_data.get("voice_config", {}).get("voice_id"),
                                "voice_provider": piece_data.get("voice_config", {}).get("voice_provider")
                            }
                            
                            # Copiar Assets a la carpeta del personaje
                            multimedia = piece_data.get("multimedia", {})
                            output_img_dir = os.path.join(os.path.dirname(__file__), "output", "imagen")
                            
                            for key in ["imagen_principal"]:
                                img_name = multimedia.get(key)
                                if img_name:
                                    src = os.path.join(output_img_dir, img_name)
                                    if os.path.exists(src):
                                        shutil.copy(src, os.path.join(reg_path, "idle.png"))
                                        reg_data["avatar"]["idle"] = f"Resources/Characters/{char_name}/idle.png"
                                        reg_data["avatar"]["talking"] = f"Resources/Characters/{char_name}/idle.png"

                            # Guardar JSON en el Hub
                            with open(os.path.join(reg_path, "character.json"), "w", encoding="utf-8") as f:
                                json.dump(reg_data, f, indent=4, ensure_ascii=False)
                                
                            print(f"[CharacterHub] Personaje '{char_name}' exportado con éxito.")
                        except Exception as e:
                            print(f"[CharacterHub] Error exportando: {e}")

            piece_data["grado_desarrollo"] = 2

        elif target_grade == 3:
            # Grado 3: Generación de Audio (Voces, Música, FX)
            print("[Compound] Escalando a Grado 3: Generando activos de audio...")
            audio_plan = piece_data.get("audio_plan", {})
            if not audio_plan:
                print("[Warning] No hay plan de audio en la pieza. Intentando generar uno básico.")
                # Lógica de fallback para generar plan de audio si falta
            
            multimedia = piece_data.setdefault("multimedia", {})
            audios = multimedia.setdefault("audios", [])
            
            # 1. Generar Voces (TTS o ComfyUI)
            # 2. Generar Música
            # 3. Generar Efectos
            # Por ahora, implementamos una llamada genérica al adaptador de audio
            # Basándonos en la receta de audio
            audio_recipe = recipe.get("grades", {}).get("3", {})
            if audio_recipe.get("workflow_folder"):
                 adapter = self.image_service.get_adapter("ComfyUI")
                 # Aquí la lógica sería iterar sobre el plan de audio y disparar generaciones
                 # Simplificamos a una generación de música ambiente por ahora
                 wf_path = os.path.join(os.path.dirname(__file__), audio_recipe["workflow_folder"], audio_recipe["default_workflow"])
                 if os.path.exists(wf_path):
                     with open(wf_path, "r", encoding="utf-8") as f: wf = json.load(f)
                     prompt_audio = f"Atmósfera sonora para {piece_data.get('titulo')}: {prompt}"
                     audio_res = await adapter.generate_image(prompt_audio, workflow_json=wf)
                     if isinstance(audio_res, str) and os.path.exists(audio_res):
                         audios.append(os.path.basename(audio_res))

            piece_data["grado_desarrollo"] = 3

        elif target_grade == 4:
            # Grado 4: Video (Composición final)
            print("[Compound] Escalando a Grado 4: Renderizando video final...")
            
            multimedia = piece_data.setdefault("multimedia", {})
            videos = multimedia.setdefault("videos", [])
            
            video_recipe = recipe.get("grades", {}).get("4", {})
            if video_recipe.get("workflow_folder"):
                 adapter = self.image_service.get_adapter("ComfyUI")
                 wf_path = os.path.join(os.path.dirname(__file__), video_recipe["workflow_folder"], video_recipe["default_workflow"])
                 if os.path.exists(wf_path):
                     with open(wf_path, "r", encoding="utf-8") as f: wf = json.load(f)
                     
                     # Recoger inputs de los grados anteriores
                     input_files = []
                     # Imagen del G2
                     if multimedia.get("imagenes"):
                         input_files.append(os.path.join(self.output_root, "imagen", multimedia["imagenes"][0]))
                     # Audio del G3
                     if multimedia.get("audios"):
                         input_files.append(os.path.join(self.output_root, "audio", multimedia["audios"][0]))
                     
                     video_res = await adapter.generate_image(prompt, workflow_json=wf, input_images=input_files)
                     if isinstance(video_res, str) and os.path.exists(video_res):
                         videos.append(os.path.basename(video_res))

            piece_data["grado_desarrollo"] = 4

        # 4. Guardar Resultado Progresivo en subcarpeta
        output_name = f"{piece_data['id']}.json"
        subfolder = self._get_compound_path(category)
        dest_path = os.path.join(subfolder, output_name)
        
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        with open(dest_path, "w", encoding="utf-8") as f:
            json.dump(piece_data, f, indent=4, ensure_ascii=False)
            
        return dest_path

    async def _auto_create_plano_ingredients(self, piece_data, comp_state, original_prompt):
        """
        Para un Plano de Grado 1:
        - Crea automáticamente una Sinopsis de tipo Plano si no hay ninguna ya referenciada.
        - Analiza el contenido generado y crea los Personajes necesarios que no estén en las referencias.
        - Actualiza piece_data["referencias"] con todos los ingredientes (existentes + nuevos).
        """
        print("[Compound][Plano] Iniciando auto-creación de ingredientes...")

        tipo_plano = piece_data.get("tipo_plano", "")
        existing_refs = list(piece_data.get("referencias", []))
        new_refs = list(existing_refs)

        # Cargar datos de las referencias existentes
        existing_data = []
        comp_root = os.path.join(self.output_root, "texto", "compuesto")

        def _load_ref(ref_path):
            abs_ref = os.path.join(self.output_root, ref_path)
            if not os.path.exists(abs_ref):
                abs_ref = os.path.join(comp_root, ref_path.replace("texto/compuesto/", ""))
            with open(abs_ref, "r", encoding="utf-8") as f:
                return json.load(f)

        for ref_path in existing_refs:
            try:
                existing_data.append(_load_ref(ref_path))
            except Exception as e:
                print(f"[Compound][Plano] No se pudo leer ref {ref_path}: {e}")

        desc_plano = piece_data.get("descripcion_visual",
                     piece_data.get("descripcion_generada",
                     piece_data.get("descripcion", original_prompt)))

        # Helper para guardar un ingrediente y añadirlo a new_refs
        def _save_ingredient(data, categoria):
            folder = self._get_compound_path(categoria)
            os.makedirs(folder, exist_ok=True)
            path = os.path.join(folder, f"{data['id']}.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
            rel = os.path.relpath(path, self.output_root).replace("\\", "/")
            new_refs.append(rel)
            existing_data.append(data)
            print(f"[Compound][Plano] Ingrediente '{data['titulo']}' ({categoria}) creado.")
            return rel

        # ====================================================================
        # PASO 1: SINOPSIS DEL PLANO (siempre obligatoria)
        # ====================================================================
        has_sinopsis = any(d.get("categoria") == "Sinopsis" for d in existing_data)
        if not has_sinopsis:
            print("[Compound][Plano] Creando Sinopsis automática...")
            sin_system = (
                f"Eres un experto en guion. Crea una sinopsis concisa (máximo 3 párrafos) "
                f"para un plano de tipo '{tipo_plano}'. "
                f"Describe qué ocurre visualmente, quiénes aparecen y qué aporta narrativamente. "
                f"Responde SOLO con el texto, sin JSON ni cabeceras."
            )
            try:
                sin_resp = await self.chat_service.generate_chat(
                    [{"role": "user", "content": f"Plano:\n{desc_plano}"}],
                    system_prompt=sin_system
                )
                sin_id = f"sinopsis_plano_{int(time.time())}"
                _save_ingredient({
                    "id": sin_id,
                    "titulo": f"Sinopsis: {piece_data.get('titulo', 'Plano')}",
                    "categoria": "Sinopsis",
                    "target_product": "Plano",
                    "tipo_plano_asociado": tipo_plano,
                    "grado_desarrollo": 1,
                    "descripcion_generada": str(sin_resp),
                    "referencias": [],
                    "metadata": {"auto_generado": True}
                }, "Sinopsis")
            except Exception as e:
                print(f"[Compound][Plano] Error creando sinopsis: {e}")

        # ====================================================================
        # PASO 2: ESCENARIO / LOCALIZACIÓN (siempre obligatorio)
        # ====================================================================
        has_escenario = any(d.get("categoria") == "Escenario" for d in existing_data)
        if not has_escenario:
            print("[Compound][Plano] Creando Escenario automático...")
            esc_system = (
                "Eres un experto en dirección de arte y pre-producción. "
                "Basándote en la siguiente descripción de un plano, genera un JSON descriptivo del escenario/localización. "
                "El JSON debe tener: titulo, descripcion_fisica (aspecto visual, materiales, dimensiones), "
                "descripcion_ambiental (luz, atmósfera, hora del día), notas_de_produccion. "
                "Responde SOLO con el JSON válido."
            )
            try:
                esc_resp = await self.chat_service.generate_chat(
                    [{"role": "user", "content": f"Descripción del plano:\n{desc_plano}"}],
                    system_prompt=esc_system
                )
                esc_id = f"escenario_auto_{int(time.time())}"
                try:
                    esc_llm = json.loads(self._clean_json_markdown(str(esc_resp)))
                except:
                    esc_llm = {"descripcion_generada": str(esc_resp)}
                esc_data = {
                    "id": esc_id, "titulo": esc_llm.pop("titulo", f"Escenario de {piece_data.get('titulo','Plano')}"),
                    "categoria": "Escenario", "grado_desarrollo": 1,
                    "referencias": [], "metadata": {"auto_generado": True},
                    **esc_llm
                }
                esc_data["id"] = esc_id
                esc_data["categoria"] = "Escenario"
                _save_ingredient(esc_data, "Escenario")
            except Exception as e:
                print(f"[Compound][Plano] Error creando escenario: {e}")

        # ====================================================================
        # PASO 3: PERSONAJES (según tipo de plano)
        # ====================================================================
        existing_chars = [d.get("titulo", "") for d in existing_data if d.get("categoria") == "Personaje"]

        # Helper para crear un personaje por nombre
        async def _create_personaje(char_name):
            already = any(char_name.lower() in ec.lower() or ec.lower() in char_name.lower()
                          for ec in existing_chars)
            if already:
                print(f"[Compound][Plano] Personaje '{char_name}' ya existe, saltando.")
                return
            char_system = (
                f"Eres un experto en pre-producción. Crea un JSON descriptivo para el personaje '{char_name}' "
                f"que aparece en el siguiente plano: {desc_plano}. "
                f"El JSON debe tener: titulo, descripcion_fisica, descripcion_psicologica, rol_en_escena. "
                f"Responde SOLO con el JSON válido."
            )
            try:
                cresp = await self.chat_service.generate_chat(
                    [{"role": "user", "content": f"Crea el perfil del personaje: {char_name}"}],
                    system_prompt=char_system
                )
                char_id = f"personaje_{char_name.lower().replace(' ', '_')}_{int(time.time())}"
                try:
                    char_llm = json.loads(self._clean_json_markdown(str(cresp)))
                except:
                    char_llm = {"descripcion_generada": str(cresp)}
                char_data = {
                    "id": char_id, "titulo": char_name, "categoria": "Personaje",
                    "grado_desarrollo": 1, "referencias": [],
                    "metadata": {"auto_generado": True}, **char_llm
                }
                char_data["id"] = char_id
                char_data["titulo"] = char_name
                char_data["categoria"] = "Personaje"
                _save_ingredient(char_data, "Personaje")
                existing_chars.append(char_name)
            except Exception as e:
                print(f"[Compound][Plano] Error creando personaje '{char_name}': {e}")

        if tipo_plano == "Dialogo":
            # DIÁLOGO: necesita EXACTAMENTE 2 personajes mínimo
            # Primero intentar leer personajes del campo dialogo generado
            dialogo_list = piece_data.get("dialogo", [])
            chars_en_dialogo = list({d.get("personaje") for d in dialogo_list if d.get("personaje")})
            chars_en_escena = piece_data.get("personajes_en_escena", [])
            todos = list(dict.fromkeys(chars_en_dialogo + chars_en_escena))  # Preservar orden, sin duplicados

            if len(todos) < 2:
                # Si el LLM no generó suficientes personajes, pedirlos al LLM
                char_detect_s = (
                    "Dado el siguiente plano de diálogo, devuelve ÚNICAMENTE un JSON con exactamente 2 personajes: "
                    "{\"personajes\": [\"NombrePersonaje1\", \"NombrePersonaje2\"]}. "
                    "Inventa nombres apropiados si no están definidos en el texto."
                )
                try:
                    cresp = await self.chat_service.generate_chat(
                        [{"role": "user", "content": f"Plano:\n{desc_plano}"}],
                        system_prompt=char_detect_s
                    )
                    cj = json.loads(self._clean_json_markdown(str(cresp)))
                    todos = cj.get("personajes", todos)
                except Exception as e:
                    print(f"[Compound][Plano][Dialogo] No se pudo detectar personajes: {e}")
                    if not todos:
                        todos = ["Personaje A", "Personaje B"]

            print(f"[Compound][Plano][Dialogo] Asegurando 2 personajes: {todos}")
            for char_name in todos[:4]:  # Máximo 4 personajes en diálogo
                await _create_personaje(char_name)

        else:
            # OTROS TIPOS: detectar personajes del contenido generado
            chars_en_escena = piece_data.get("personajes_en_escena", [])
            if chars_en_escena:
                print(f"[Compound][Plano] Personajes en escena (del JSON generado): {chars_en_escena}")
                for char_name in chars_en_escena:
                    await _create_personaje(char_name)
            else:
                # Preguntar al LLM si hay personajes
                char_detect_s = (
                    "Analiza la siguiente descripción de un plano y devuelve ÚNICAMENTE "
                    "un JSON: {\"personajes\": [\"Nombre1\"]}. "
                    "Si no hay personajes devolves: {\"personajes\": []}. "
                    "Solo personajes con presencia física en el plano."
                )
                try:
                    cresp = await self.chat_service.generate_chat(
                        [{"role": "user", "content": f"Plano:\n{desc_plano}"}],
                        system_prompt=char_detect_s
                    )
                    cj = json.loads(self._clean_json_markdown(str(cresp)))
                    for char_name in cj.get("personajes", []):
                        await _create_personaje(char_name)
                except Exception as e:
                    print(f"[Compound][Plano] No se pudo detectar personajes: {e}")

        # ====================================================================
        # PASO 4: Actualizar piece_data con todas las referencias finales
        # ====================================================================
        piece_data["referencias"] = new_refs
        print(f"[Compound][Plano] Total referencias finales: {len(new_refs)}")


    def _load_recipe(self, category):
        """Carga el JSON de instrucciones para una categoría."""
        mapping = {
            "Personaje": "character_instruction.json",
            "Escenario": "setting_instruction.json",
            "Prop": "prop_instruction.json",
            "Sinopsis": "synopsis_instruction.json",
            "Plano": "plano_instruction.json"
        }
        recipe_file = mapping.get(category, "character_instruction.json")
        path = os.path.join(os.path.dirname(__file__), "processes", recipe_file)
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    def _load_references_content(self, references):
        """Carga el contenido de los JSONs referenciados para inyectar en el prompt."""
        contents = []
        for ref in references:
            abs_path = os.path.join(self.output_root, ref)
            if os.path.exists(abs_path):
                try:
                    with open(abs_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        contents.append(f"[{data.get('categoria', 'Pieza')}]: {data.get('titulo')} - {str(data)[:200]}...")
                except: continue
        return "\n".join(contents)

    def _clean_json_markdown(self, text):
        """Limpia bloques de código markdown de una respuesta LLM."""
        return text.replace("```json", "").replace("```", "").strip()

    def _rebuild_3d_panel(self, g_type=None):
        """Construye el panel de control para generación 3D."""
        if not self.ctrl_panel: return
        self.ctrl_panel.clear()

        # 1. Tipo de generación 3D
        options = ["Texto a 3D", "Imagen a 3D"]
        current_g = g_type or self.ctrl_panel.get_value("3d_type", options[0])
        self.ctrl_panel.add_dropdown("Tipo", "3d_type", options, default=current_g,
                                    callback=lambda v: self._rebuild_3d_panel(g_type=v))

        # 2. Proveedor
        providers = ["ComfyUI", "API (Próximamente)"]
        current_p = self.ctrl_panel.get_value("3d_provider", providers[0])
        self.ctrl_panel.add_dropdown("Proveedor", "3d_provider", providers, default=current_p)

        # 3. Workflows (si es ComfyUI)
        if current_p == "ComfyUI":
            folder_map = {"Texto a 3D": "text_to_3d", "Imagen a 3D": "img_to_3d"}
            sub = folder_map.get(current_g, "text_to_3d")
            base_w = os.path.join(os.path.dirname(__file__), "workflows", "3d", sub)
            
            w_files = []
            if os.path.exists(base_w):
                w_files = [f for f in os.listdir(base_w) if f.endswith(".json")]
            
            if not w_files:
                self.ctrl_panel.add_label(f"⚠️ No hay workflows en {sub}", color="#ffaa00")
            else:
                defaults = self.config_service.get("comfyui_defaults", {}).get("3D", {})
                user_default = defaults.get("workflow") if defaults.get("type") == sub else None
                
                default_val = user_default if user_default in w_files else w_files[0]
                self.ctrl_panel.add_dropdown("Workflow", "3d_workflow", w_files, default=default_val)
            
            # Controles de lanzamiento
            self._add_comfy_launch_controls()

        # 4. Inputs específicos para Img-to-3D
        if current_g == "Imagen a 3D":
            self.ctrl_panel.add_file_picker("Imagen de Referencia", "3d_input_image")

    def handle_generate(self):
        prompt = self.prompt_text.get("1.0", tk.END).strip()
        if not prompt: return
        self.handle_generate_manual(prompt)

    def _show_type_dropdown(self):
        """Intenta desplegar visualmente el combo de tipo actual."""
        if not self.ctrl_panel: return
        
        key_map = {
            "Audio": "audio_type",
            "Video": "video_type",
            "3D": "3d_type",
            "Imagen": "type"
        }
        
        target_key = key_map.get(self.current_mode)
        if target_key and target_key in self.ctrl_panel.controls:
            combo = self.ctrl_panel.controls[target_key]
            if isinstance(combo, ttk.Combobox):
                combo.focus_set()
                # Truco para desplegar: generar evento de flecha abajo
                combo.event_generate('<Down>')

    def _perform_type_selection(self, text):
        """Captura el texto y busca una coincidencia en los tipos del modo actual."""
        self.awaiting_type_selection = False
        self.chat_service.stt_captured_by_module = False
        
        if not text or not self.ctrl_panel: return
        
        key_map = {
            "Audio": "audio_type",
            "Video": "video_type",
            "3D": "3d_type",
            "Imagen": "type"
        }
        
        target_key = key_map.get(self.current_mode)
        if not target_key or target_key not in self.ctrl_panel.controls:
            self.chat_service.notify_system_msg(f"ASIMOD: El modo {self.current_mode} no tiene tipos seleccionables.", "#ff4444")
            return

        combo = self.ctrl_panel.controls[target_key]
        if not isinstance(combo, ttk.Combobox): return
        
        options = combo['values']
        text_clean = text.lower().strip()
        
        match = None
        # Búsqueda exacta primero
        for opt in options:
            if opt.lower() == text_clean:
                match = opt
                break
        
        # Búsqueda parcial si no hubo exacta
        if not match:
            for opt in options:
                if text_clean in opt.lower() or opt.lower() in text_clean:
                    match = opt
                    break
        
        if match:
            self.ctrl_panel.set_value(target_key, match)
            # Disparar manualmente el evento de selección para ejecutar callbacks
            combo.event_generate("<<ComboboxSelected>>")
            self.chat_service.notify_system_msg(f"ASIMOD: Tipo seleccionado: {match}", "#4EC9B0")
        else:
            self.chat_service.notify_system_msg(f"ASIMOD: No reconozco el tipo '{text}'. Inténtalo de nuevo.", "#ffaa00")

    def _cache_result_and_show(self, content, mode):
        """Muestra el resultado y lo organiza en disco. Retorna la ruta final."""
        if not content: return None
        
        # Wrapper para llamar a _show_result en el hilo de la UI
        if hasattr(self, "workspace") and self.workspace:
            self.workspace.after(0, lambda: self._show_result(content))
        
        return content

    def _show_result(self, content):
        """Muestra el resultado y lo organiza jerárquicamente en disco."""
        if not content:
            self.media_display.load_media(None)
            return

        # Manejo de errores directos (para mostrar en pantalla en vez de popups)
        if isinstance(content, str) and (content.startswith("Error") or content.startswith("Exception")):
            self.media_display._show_error(content)
            return

        # 1. Determinar categorías y subcategorías para la organización
        mode = self.current_mode.lower()
        sub_type = ""
        
        if mode == "imagen":
            sub_type = self.ctrl_panel.get_value("type") or "Simple"
        elif mode == "video":
            sub_type = self.ctrl_panel.get_value("video_subtype") or "text2video"
        elif mode == "audio":
            raw_type = self.ctrl_panel.get_value("audio_type") or "Voces"
            folder_map = {"Voces": "Voices", "Música": "Music", "Efectos": "Efects"}
            sub_type = folder_map.get(raw_type, "Voices")
        elif mode == "3d":
            raw_type = self.ctrl_panel.get_value("3d_type") or "Texto a 3D"
            folder_map = {"Texto a 3D": "text_to_3d", "Imagen a 3D": "img_to_3d"}
            sub_type = folder_map.get(raw_type, "text_to_3d")
        
        target_dir = os.path.join(self.output_root, mode)
        if sub_type: target_dir = os.path.join(target_dir, sub_type)
        os.makedirs(target_dir, exist_ok=True)

        # 2. Procesar el contenido (lista o ruta única)
        final_file = None
        if isinstance(content, list) and content:
            processed = []
            for item in content:
                if isinstance(item, str) and os.path.exists(item):
                    new_p = os.path.join(target_dir, os.path.basename(item))
                    if os.path.abspath(item) != os.path.abspath(new_p):
                        try: shutil.move(item, new_p)
                        except: pass
                        item = new_p
                    processed.append(item)
            if processed:
                self.media_display.load_media(processed)
                final_file = processed[0]
        
        elif isinstance(content, str) and os.path.exists(content):
            new_p = os.path.join(target_dir, os.path.basename(content))
            if os.path.abspath(content) != os.path.abspath(new_p):
                try: shutil.move(content, new_p)
                except: pass
                content = new_p
            self.media_display.load_media(content)
            final_file = content
            
        elif isinstance(content, str):
            # Es texto (Prompt o resultado literario)
            filename = f"texto_{int(time.time())}.txt"
            target_path = os.path.join(self.output_root, "texto", filename)
            os.makedirs(os.path.dirname(target_path), exist_ok=True)
            try:
                with open(target_path, "w", encoding="utf-8") as f:
                    f.write(content)
                self.media_display.load_media(target_path)
                final_file = target_path
            except: pass

        # 3. Navegar la galería a la nueva carpeta y refrescar
        if final_file:
            self.gallery_path = os.path.dirname(final_file)
            self._refresh_gallery_from_disk()

    def _rebuild_audio_panel(self, a_type=None, a_prov=None):
        """Reconstruye el panel de controles para el modo Audio de forma atómica."""
        if not self.ctrl_panel: return
        
        # Capturar estado actual o usar defaults
        current_type = a_type or self.ctrl_panel.get_value("audio_type") or "Voces"
        current_prov = a_prov or self.ctrl_panel.get_value("audio_provider")
        
        self.ctrl_panel.clear()
        
        # 1. Selector de TIPO (Prioridad 1)
        tipos = ["Voces", "Música", "Efectos"]
        self.ctrl_panel.add_dropdown("Tipo (Audio)", "audio_type", tipos, default=current_type,
                                    callback=lambda v: self._rebuild_audio_panel(a_type=v, a_prov=None))
        
        # 2. Selector de PROVEEDOR (Dependiente de Tipo)
        providers_map = {
            "Voces": ["ASIMOD - Edge", "ASIMOD - Local", "ElevenLabs", "ComfyUI"],
            "Música": ["ComfyUI", "Suno"],
            "Efectos": ["ComfyUI", "ElevenLabs", "Suno"]
        }
        available_providers = providers_map.get(current_type, ["ComfyUI"])
        
        # Validar si el proveedor actual sirve para el nuevo tipo
        if not current_prov or current_prov not in available_providers:
            current_prov = available_providers[0]
            
        self.ctrl_panel.add_dropdown("Proveedor", "audio_provider", available_providers, default=current_prov,
                                    callback=lambda v: self._rebuild_audio_panel(a_type=current_type, a_prov=v))
        
        # 3. CONTROLES ESPECÍFICOS SEGÚN PROVEEDOR
        if current_prov == "ComfyUI":
            self._update_audio_workflow_files(current_type)
            
            # Si es música, externalizar parámetros extra
            if current_type == "Música":
                # Selección de Proveedor y Modelo LLM para letras
                available_providers = self.chat_service.get_providers_list()
                current_p = self.config_service.get("last_provider", "Ollama")
                self.ctrl_panel.add_dropdown("Proveedor LLM", "audio_llm_provider", 
                                            available_providers, default=current_p,
                                            callback=self._on_llm_provider_change)

                active_llm = self.config_service.get("last_model", "Default")
                self.ctrl_panel.add_dropdown("Modelo LLM", "audio_llm_model", 
                                            self.llm_models if self.llm_models else [active_llm], 
                                            default=active_llm,
                                            callback=lambda v: self.config_service.set("last_model", v))

                self.ctrl_panel.add_dropdown("BPM", "audio_bpm", ["90", "120", "128", "140", "150", "190"], default="190")
                self.ctrl_panel.add_dropdown("Escala", "audio_key", ["C major", "C minor", "D major", "D minor", "E major", "E minor", "F major", "F minor", "G major", "G minor", "A major", "A minor", "B major", "B minor"], default="E minor")
                self.ctrl_panel.add_dropdown("Duración (Seg)", "audio_duration", ["30", "60", "90", "120", "150", "180"], default="120")
                self.ctrl_panel.add_textarea("Letras (Lyrics)", "audio_lyrics", default="[Intro]...", height=6)
                self.ctrl_panel.add_button("✨ Generar Letras", self._handle_generate_lyrics)
            
            # Controles de lanzamiento
            self._add_comfy_launch_controls()
        
        elif "ASIMOD" in current_prov:
            from core.factories.voice_factory import VoiceFactory
            prov_key = "Edge TTS" if "Edge" in current_prov else "Local TTS"
            adapter = VoiceFactory.get_adapter(prov_key)
            voices = [v["name"] for v in adapter.list_voices()] if adapter else ["Default"]
            self.ctrl_panel.add_dropdown("Voz (Core)", "audio_voice", voices)
            
        elif current_prov == "ElevenLabs":
            self.ctrl_panel.add_dropdown("Voz ElevenLabs", "audio_voice_eleven", ["Cargando..."], default="Cargando...")
            # Aquí se dispararía la carga asíncrona de voces de ElevenLabs si hubiera adaptador
            
        elif current_prov == "Suno":
             self.ctrl_panel.add_dropdown("Estilo Suno", "audio_suno_style", ["Chiptune", "Synthwave", "Classic", "Vibrant"], default="Synthwave")

    def _handle_generate_lyrics(self):
        """Usa el LLM activo para componer letras basadas en el prompt actual."""
        prompt = self.prompt_text.get("1.0", tk.END).strip()
        
        # Validación más robusta: Ignorar si es el placeholder exacto o está vacío
        placeholder_prefix = "Escribe aquí lo que quieres generar"
        if not prompt or prompt.startswith(placeholder_prefix) and len(prompt) < len(placeholder_prefix) + 10:
            # Notificar error en el área de letras
            txt_ctrl = self.ctrl_panel.controls.get("audio_lyrics")
            if txt_ctrl:
                txt_ctrl.delete("1.0", tk.END)
                txt_ctrl.insert("1.0", "Error: Por favor, escribe el tema de la canción en el cuadro de texto de arriba.")
            return

        def run_ai():
            try:
                # 1. Estado de carga en el widget de texto
                txt_ctrl = self.ctrl_panel.controls.get("audio_lyrics")
                if txt_ctrl and txt_ctrl.winfo_exists():
                    self.workspace.after(0, lambda: txt_ctrl.delete("1.0", tk.END) if txt_ctrl.winfo_exists() else None)
                    self.workspace.after(0, lambda: txt_ctrl.insert("1.0", "✨ Componiendo letras... por favor espera...") if txt_ctrl.winfo_exists() else None)
                
                # 2. Configurar el LLM para composición (Ahora usando system_prompt override)
                sys_songwriter = (
                    "ACTÚA ÚNICAMENTE COMO UN COMPOSITOR DE CANCIONES PROFESIONAL.\n"
                    "REGLAS CRÍTICAS:\n"
                    "1. Devuelve ÚNICAMENTE la letra de la canción.\n"
                    "2. NO digas '¡Hola!', NO te presentes como Asimod, NO des explicaciones.\n"
                    "3. Usa etiquetas de estructura claras: [VERSO], [CORO], [PUENTE], [OUTRO].\n"
                    "4. Mantén un estilo rítmico, poético y coherente.\n"
                    "5. Si el tema es breve, expande la narrativa para crear una canción completa."
                )
                
                user_prompt = f"Dame la letra de una canción sobre: {prompt}"
                
                print(f"[MediaGenerator] Generando letras con LLM especializado para: {prompt[:50]}...")
                
                # Usar el modelo seleccionado en el panel
                selected_model = self.ctrl_panel.get_value("audio_llm_model") or self.config_service.get("last_model")

                # Asegurar que el adaptador actual es el que dice el panel (doble check)
                p_selected = self.ctrl_panel.get_value("audio_llm_provider")
                if p_selected and p_selected != self.chat_service.current_adapter.name:
                    print(f"[MediaGenerator] Sincronización forzada de proveedor: {p_selected}")
                    self.chat_service.switch_provider(p_selected)

                # Ejecutar llamada asíncrona usando el nuevo system_prompt override
                res = asyncio.run(self.chat_service.send_message(
                    user_prompt, 
                    model=selected_model, 
                    silent=True, 
                    system_prompt=sys_songwriter
                ))
                lyrics = res.get("response", "Error: No se pudo generar la letra.")
                
                # 3. Limpiar y actualizar UI (verificando que el control aún exista)
                def update_ui():
                    # A. Actualizar sidebar
                    curr_txt = self.ctrl_panel.controls.get("audio_lyrics")
                    if curr_txt and curr_txt.winfo_exists():
                        curr_txt.delete("1.0", tk.END)
                        curr_txt.insert("1.0", lyrics)
                    
                    # B. Inyectar en prompt principal (Área de trabajo)
                    if self.prompt_text and self.prompt_text.winfo_exists():
                        current_prompt = self.prompt_text.get("1.0", tk.END).strip()
                        # Si solo está el placeholder, reemplazar. Si no, añadir.
                        placeholder_prefix = "Escribe aquí"
                        if not current_prompt or current_prompt.startswith(placeholder_prefix):
                            self.prompt_text.delete("1.0", tk.END)
                            self.prompt_text.insert("1.0", f"Letras Generadas:\n\n{lyrics}")
                        else:
                            self.prompt_text.delete("1.0", tk.END)
                            self.prompt_text.insert("1.0", f"{current_prompt}\n\n--- LETRAS ---\n{lyrics}")
                        
                        self.prompt_text.config(fg=self.style.get_color("text_main"))

                self.workspace.after(0, update_ui)
            
            except Exception as e:
                import traceback
                traceback.print_exc()
                print(f"[MediaGenerator][Web] Error en generación: {e}")
                def show_error():
                    curr_txt = self.ctrl_panel.controls.get("audio_lyrics")
                    if curr_txt and curr_txt.winfo_exists():
                        curr_txt.insert(tk.END, f"\n\n[Error: {str(e)}]")
                self.workspace.after(0, show_error)

        threading.Thread(target=run_ai, daemon=True).start()

    def _update_audio_workflow_files(self, a_type):
        """Escanea la carpeta de workflows de audio según el tipo seleccionado."""
        folder_map = {"Voces": "voices", "Música": "music", "Efectos": "sounds"}
        sub = folder_map.get(a_type, "voices")
        
        base_w = os.path.join(os.path.dirname(__file__), "workflows", "Audio", sub)
        if not os.path.exists(base_w):
            os.makedirs(base_w, exist_ok=True)
            
        files = self.image_service.get_workflow_files(base_w)
        
        defaults = self.config_service.get("comfyui_defaults", {}).get("Audio", {})
        user_default = defaults.get("workflow") if defaults.get("type") == sub else None
        
        default_val = None
        if user_default and user_default in files:
            default_val = user_default
        elif files:
            # Buscar un default por nombre
            for f in files:
                if "default" in f.lower():
                    default_val = f
                    break
            if not default_val:
                default_val = files[0]
                
        self.ctrl_panel.add_dropdown("Workflow de Audio", "audio_workflow", files, default=default_val)

    def _refresh_gallery_from_disk(self):
        """Escanea la carpeta actual (self.gallery_path) y llena la galería."""
        if not self.gallery: return
        self.gallery.clear()
        
        if not os.path.exists(self.gallery_path):
            os.makedirs(self.gallery_path, exist_ok=True)

        # Botón atrás visible si no estamos en el root
        self.gallery.set_back_visibility(os.path.abspath(self.gallery_path) != os.path.abspath(self.output_root))

        # Listar contenido
        try:
            items = os.listdir(self.gallery_path)
        except: items = []

        # Dossier de carpetas primero
        dirs = [d for d in items if os.path.isdir(os.path.join(self.gallery_path, d))]
        files = [f for f in items if os.path.isfile(os.path.join(self.gallery_path, f))]

        for d in sorted(dirs):
            self.gallery.add_item(d, "Carpeta", is_folder=True, callback=lambda d=d: self._on_folder_click(d))

        # Archivos ordenados por fecha
        file_list = []
        for f in files:
            f_path = os.path.join(self.gallery_path, f)
            mtime = os.path.getmtime(f_path)
            ext = os.path.splitext(f)[1].lower()
            icon = "🖼️" if ext in [".png", ".jpg", ".webp"] else \
                   "🎥" if ext in [".mp4", ".gif", ".webm"] else \
                   "🎵" if ext in [".wav", ".mp3", ".ogg"] else \
                   "📄" if ext == ".txt" else "📦"
            file_list.append((f, icon, f_path, mtime))
        
        file_list.sort(key=lambda x: x[3], reverse=True)
        for f, icon, f_path, mtime in file_list:
            date_str = datetime.datetime.fromtimestamp(mtime).strftime("%d/%m %H:%M")
            thumb = f_path if icon == "🖼️" else None
            self.gallery.add_item(f, date_str, icon=icon, thumbnail_path=thumb, 
                                 callback=lambda p=f_path: self._handle_gallery_click(p))

    def _handle_gallery_click(self, file_path):
        """Maneja el clic en un archivo de la galería, activando play si ya está seleccionado."""
        if hasattr(self, "media_display") and self.media_display:
            if self.media_display.current_media_path == file_path:
                # Ya seleccionado -> Play automático si es audiovisual
                self.media_display.ensure_playing()
            else:
                # Cargar nuevo
                self.media_display.load_media(file_path)

    def _on_folder_click(self, folder_name):
        self.gallery_path = os.path.join(self.gallery_path, folder_name)
        self._refresh_gallery_from_disk()
        
        # Periodo de gracia: Mantener el modo escucha 5 segundos tras entrar en carpeta
        self.awaiting_gallery_num = True
        self.chat_service.notify_system_msg("ASIMOD: [Galería] Carpeta abierta. Dime un número...", "#4EC9B0")
        
        if self.last_gallery_wait_id:
            self.workspace.after_cancel(self.last_gallery_wait_id)
        self.last_gallery_wait_id = self.workspace.after(5000, self._stop_gallery_wait)

    def _stop_gallery_wait(self):
        """Cancela la espera activa de número si se agota el tiempo."""
        self.awaiting_gallery_num = False
        self.chat_service.stt_captured_by_module = False
        self.last_gallery_wait_id = None
        # Opcional: Podríamos mostrar un mensaje de "Espera finalizada", pero mejor ser silencioso

    def _clear_all(self):
        self.prompt_text.delete("1.0", tk.END)
        self.media_display.stop_playback()
        self.media_display._clear_content()

    def _on_image_engine_change(self, engine_name):
        """Callback simple para redirigir a la reconstrucción completa."""
        self._rebuild_image_panel(engine_name=engine_name)

    def _rebuild_image_panel(self, engine_name=None, w_type=None, w_subtype=None, img_count=None, w_flow=None):
        """
        Dibuja el panel de control de imagen de forma atómica y limpia.
        Relee los valores necesarios para no perder el estado al reconstruir.
        """
        if not self.ctrl_panel: return

        # 1. Recuperar valores actuales antes de limpiar (si existen)
        if not engine_name: 
            engine_name = self.ctrl_panel.get_value("engine") or "DALL-E 3"
        
        if not w_type: 
            w_type = self.ctrl_panel.get_value("type")
            
        if not w_subtype: 
            w_subtype = self.ctrl_panel.get_value("subtype")
            
        if not img_count: 
            img_count = self.ctrl_panel.get_value("img_count") or "1"
        
        # Validar numérico para evitar fallos en el bucle
        try:
            icount = int(img_count)
        except:
            icount = 1
            
        if not w_flow:
            w_flow = self.ctrl_panel.get_value("workflow")

        # 2. Limpiar panel por completo
        self.ctrl_panel.clear()

        # 3. Reconstruir dropdown Motor (siempre presente)
        engines = self.image_service.get_engines_list()
        self.ctrl_panel.add_dropdown("Motor de Imagen", "engine", engines, 
                                    default=engine_name,
                                    callback=lambda v: self._rebuild_image_panel(engine_name=v))
        
        # Si acabamos de entrar o no hay valores, forzar los predefinidos solicitados
        is_first_build = not w_type and not w_subtype

        if engine_name == "DALL-E 3":
            self.ctrl_panel.add_dropdown("Resolución", "res", ["1024x1024", "1024x1792", "1792x1024"])
        
        elif engine_name == "ComfyUI":
            # Jerarquía de Workflows (Cargar para saber qué hay en disco)
            base_w = os.path.join(os.path.dirname(__file__), "workflows")
            w_struct = self.image_service.scan_workflows(base_w)
            
            # Selector Tipo (Forzado a Simple / Compuesta según petición)
            types = ["Simple", "Compuesta"]
            if not w_type or w_type not in types:
                # Intentar recuperar del panel si existe, si no default
                w_type = self.ctrl_panel.get_value("type") or "Simple"
            
            self.ctrl_panel.add_dropdown("Tipo", "type", types, default=w_type,
                                        callback=lambda v: self._rebuild_image_panel(w_type=v, w_subtype=None))
            
            # Selector Subtipo
            if w_type == "Compuesta":
                # Lista fija solicitada por el usuario
                subtypes = ["Personaje", "Escenario", "Prop", "Sinopsis", "Plano", "Escena", "Secuencia", "Pelicula"]
            else:
                # Para Simple, usamos lo que haya en la carpeta 'simple' (text2img, img2img, etc)
                subtypes = w_struct.get("simple", [])
            
            if subtypes:
                if not w_subtype or w_subtype not in subtypes:
                    w_subtype = "Personaje" if w_type == "Compuesta" else (
                                "text2img" if "text2img" in [s.lower() for s in subtypes] else subtypes[0])
                
                self.ctrl_panel.add_dropdown("Subtipo", "subtype", subtypes, default=w_subtype,
                                            callback=lambda v: self._rebuild_image_panel(w_type=w_type, w_subtype=v, w_flow=None))
            
            # Selector de archivo Workflow
            self._update_workflow_files(w_type, w_subtype, current_flow=w_flow)
            
            # --- SECCIÓN DE COMPUESTA (Origen e Ingredientes) ---
            if w_type == "Compuesta":
                try:
                    # 1. Documento Origen
                    res_docs = asyncio.run(self.list_compound_docs())
                    all_docs = res_docs.get("result", [])
                    cat_docs = [d for d in all_docs if d.get("category") == w_subtype]
                    if cat_docs:
                        names = [d["name"] for d in cat_docs]
                        self.doc_map = {d["name"]: d["path"] for d in cat_docs}
                        self.ctrl_panel.add_dropdown("Documento Origen", "doc_origin", names)
                    else:
                        self.ctrl_panel.add_label(f"⚠️ No hay {w_subtype} G1 para desarrollar.", color="#ffaa00")
                except Exception as e:
                    print(f"[MediaGenerator] Error en origen: {e}")

            # Botón de ingredientes solo visible en Compuesta
            if hasattr(self, "btn_ing"):
                if w_type == "Compuesta":
                    self.btn_ing.pack(side=tk.RIGHT, padx=5)
                else:
                    self.btn_ing.pack_forget()
                    if self.ingredient_panel_visible: self._toggle_ingredient_panel()

            # 2. Selector de Referencias (En el panel de la derecha)
            if w_type == "Compuesta":
                try:
                    for child in self.ingredient_panel.winfo_children():
                        child.destroy()
                    
                    res_pieces = asyncio.run(self.list_all_compound_pieces())
                    ingredients = res_pieces.get("result", {}).get("ingredients", [])
                    if ingredients:
                        items = [(f"[{i['category']}] {i['name']}", i['path']) for i in ingredients]
                        # Inyectar checklist en el panel lateral derecho
                        self.ctrl_panel.add_check_list("🗳️", "references", items, parent=self.ingredient_panel)
                except Exception as e:
                    print(f"[MediaGenerator] Error en panel ingredientes: {e}")

            # Control de Semilla
            current_seed = self.ctrl_panel.get_value("seed") or "-1"
            self.ctrl_panel.add_input("Semilla (-1 = Aleatorio)", "seed", default=current_seed)

            # Según el subtipo, mostramos resolución o cargadores de imágenes
            if w_subtype and w_subtype.lower() == "img2img":
                self.ctrl_panel.add_dropdown("Nº Imágenes", "img_count", ["1", "2", "3"], 
                                            default=img_count,
                                            callback=lambda v: self._rebuild_image_panel(img_count=v))
                for i in range(1, int(img_count) + 1):
                    key = f"input_image_{i}"
                    container = self.ctrl_panel.add_file_picker(f"Imagen {i}", key)
                    tk.Button(container, text="🖼️ Usar Seleccionada", bg="#333", fg="#4EC9B0", 
                              bd=0, padx=8, font=("Arial", 8), cursor="hand2",
                              command=lambda k=key: self._use_selected_media_as_input(k)).pack(side=tk.LEFT, padx=5)
            else:
                res_options = [
                    "Cuadrada Pequeña (512x512)", "Cuadrada Grande (1024x1024)",
                    "Apaisada Pequeña (768x512)", "Apaisada Grande (1280x720)",
                    "Vertical Pequeña (512x768)", "Vertical Grande (720x1280)",
                    "Personalizado"
                ]
                self.ctrl_panel.add_resolution_control("Resolución", "resolution", res_options, 
                                                       default="Apaisada Pequeña (768x512)")
            
            # 5. Controles de lanzamiento
            self._add_comfy_launch_controls()

    def _update_image_controls(self, *args):
        # Este método era redundante, ahora todo lo hace _rebuild_image_panel
        pass

    def _add_comfy_launch_controls(self, parent=None):
        """Añade los controles especiales para ComfyUI."""
        # Si no se pasa parent, usamos el panel de controles (compatibilidad)
        target = parent if parent else (self.ctrl_panel.grid_container if self.ctrl_panel else None)
        if not target: return
        
        bg = target["bg"]
        
        btn_frame = tk.Frame(target, bg=bg)
        if parent:
            btn_frame.pack(side=tk.LEFT, padx=10)
        else:
            row = len(target.winfo_children()) // 2
            btn_frame.grid(row=row, column=0, columnspan=2, sticky="ew", pady=5)
        
        tk.Button(btn_frame, text="🚀 Lanzar ComfyUI", bg="#444", fg="white", bd=0, padx=10, 
                  command=self._launch_comfy).pack(side=tk.LEFT, padx=5)
        
        tk.Button(btn_frame, text="⚙️ Config", bg="#333", fg="#4EC9B0", bd=0, padx=8,
                  command=self._show_comfy_config, cursor="hand2").pack(side=tk.LEFT, padx=5)
        
        self.lbl_comfy_status = tk.Label(btn_frame, text=f"Estado: {self.comfy_status}", bg=bg, fg="#aaa")
        self.lbl_comfy_status.pack(side=tk.LEFT, padx=10)
        
        # Iniciar polling de estado
        self._poll_comfy_status()

    def _show_comfy_config(self):
        """Muestra el panel de configuración sustituyendo el prompt."""
        if not self.ctrl_panel: return
        
        container = self.ctrl_panel.actions_container
        for widget in container.winfo_children():
            widget.destroy()
            
        self.config_overlay = ComfyUIConfigView(
            container, 
            self.config_service, 
            self.style, 
            self.image_service,
            on_back=self._hide_comfy_config
        )
        self.config_overlay.pack(fill=tk.X)

    def _hide_comfy_config(self):
        """Vuelve al prompt normal y recarga la configuración."""
        # Recargar ruta de salida por si cambió
        default_out = os.path.abspath(os.path.join(os.path.dirname(__file__), "output"))
        self.output_root = self.config_service.get("comfyui_output_path", default_out)
        self.gallery_path = self.output_root # Volver a la raíz tras cambiar la configuración
        
        if hasattr(self, "ctrl_panel") and self.ctrl_panel:
            for widget in self.ctrl_panel.actions_container.winfo_children():
                widget.destroy()
            self.render_top_actions(self.ctrl_panel.actions_container)
        
        self._refresh_gallery_from_disk()

    def _poll_comfy_status(self):
        def check():
            adapter = self.image_service.get_adapter("ComfyUI")
            if adapter:
                try:
                    active = asyncio.run(adapter.check_status())
                    self.comfy_status = "Activo" if active else "Inactivo"
                    color = "#4EC9B0" if active else "#F44336"
                    
                    lbl = self.lbl_comfy_status
                    if lbl and lbl.winfo_exists():
                        lbl.after(0, lambda: lbl.config(text=f"Estado: {self.comfy_status}", fg=color) if lbl.winfo_exists() else None)
                except:
                    pass
        threading.Thread(target=check, daemon=True).start()

    def _launch_comfy(self):
        lnk_path = r"C:\Users\jauma\Desktop\COMFYUI (2).lnk"
        if os.path.exists(lnk_path):
            os.startfile(lnk_path)
            self.comfy_status = "Iniciando..."
            self.lbl_comfy_status.config(text=f"Estado: {self.comfy_status}", fg="#FFD700")
        else:
            self._show_result(f"Error: No se encontró el acceso directo en {lnk_path}")

    def _update_workflow_files(self, w_type, w_subtype, current_flow=None):
        base_w = os.path.join(os.path.dirname(__file__), "workflows", w_type.lower())
        if w_subtype:
            base_w = os.path.join(base_w, w_subtype.lower())
        
        # [NUEVO] Si no hay archivos .json en la carpeta base pero hay una subcarpeta 'imagen', entrar en ella
        # Esto permite que 'compuesta/personaje' encuentre los flujos en 'compuesta/personaje/imagen'
        if os.path.exists(base_w):
            direct_json = [f for f in os.listdir(base_w) if f.endswith(".json")]
            if not direct_json:
                img_path = os.path.join(base_w, "imagen")
                if os.path.exists(img_path):
                    base_w = img_path

        files = self.image_service.get_workflow_files(base_w)
        
        # Prioridad de selección:
        # 1. El flujo que ya estaba seleccionado (si sigue existiendo)
        # 2. El flujo default según el subtipo (ej: DefaultImg2Img.json)
        # 3. El primero de la lista
        
        defaults = self.config_service.get("comfyui_defaults", {}).get("Imagen", {})
        user_default = defaults.get("workflow") if defaults.get("type") == w_type and defaults.get("subtype") == w_subtype else None
        
        default_val = None
        if current_flow and current_flow in files:
            default_val = current_flow
        elif user_default and user_default in files:
            default_val = user_default
        else:
            is_img2img = w_subtype and w_subtype.lower() == "img2img"
            if is_img2img and "DefaultImg2Img.json" in files:
                default_val = "DefaultImg2Img.json"
            elif "DefaultText2Img.json" in files:
                default_val = "DefaultText2Img.json"
            elif files:
                default_val = files[0]

        if "workflow" not in self.ctrl_panel.controls:
            self.ctrl_panel.add_dropdown("Workflow", "workflow", files, default=default_val)
        else:
            self.ctrl_panel.update_dropdown("workflow", files)

    def _use_selected_media_as_input(self, target_key):
        """Toma la imagen actualmente visualizada en el workspace y la pone en el picker indicado."""
        if not hasattr(self, "media_display") or not self.media_display:
            return
            
        path = self.media_display.current_media_path
        if not path or not os.path.exists(path):
            self.chat_service.notify_system_msg("ASIMOD: No hay ninguna imagen seleccionada en la galería.", "#F44336")
            return
            
        # Verificar extensión de imagen
        ext = os.path.splitext(path)[1].lower()
        if ext not in [".png", ".jpg", ".jpeg", ".webp"]:
            self.chat_service.notify_system_msg("ASIMOD: El archivo seleccionado no es una imagen válida para generación.", "#F44336")
            return
            
        # Inyectar en el controlador
        self.ctrl_panel.set_value(target_key, path)
        self.chat_service.notify_system_msg(f"ASIMOD: Imagen cargada en {target_key}.", "#4EC9B0")

    def _update_models_dropdown(self, models):
        if self.ctrl_panel and self.ctrl_panel.winfo_exists():
            if "model" in self.ctrl_panel.controls:
                self.ctrl_panel.update_dropdown("model", models)
            else:
                self.ctrl_panel.add_dropdown("Modelo", "model", models)

    def _rebuild_video_panel(self, v_type=None, v_subtype=None):
        """Reconstruye el panel de controles para el modo Video de forma atómica."""
        if not self.ctrl_panel: return
        
        # Capturar estado actual
        current_type = v_type or self.ctrl_panel.get_value("video_type") or "Simple"
        current_subtype = v_subtype or self.ctrl_panel.get_value("video_subtype")
        
        self.ctrl_panel.clear()
        
        # 1. Motor (Solo ComfyUI de momento)
        self.ctrl_panel.add_dropdown("Motor de Video", "engine", ["ComfyUI"])
        
        # 2. Tipo
        tipos = ["Simple", "Compuesto"]
        self.ctrl_panel.add_dropdown("Tipo", "video_type", tipos, default=current_type,
                                    callback=lambda v: self._rebuild_video_panel(v_type=v, v_subtype=None))
        
        # 3. Subtipo (Solo para Simple)
        if current_type == "Simple":
            subtipos = ["text2video", "img2video", "Img+Audio2Video", "video2video"]
            if not current_subtype or current_subtype not in subtipos:
                current_subtype = "text2video"
            
            self.ctrl_panel.add_dropdown("Subtipo", "video_subtype", subtipos, default=current_subtype,
                                        callback=lambda v: self._rebuild_video_panel(v_type=current_type, v_subtype=v))
        
        # 4. Selector de Workflow
        self._update_video_workflow_files(current_type, current_subtype)
        
        # 5. Inputs dinámicos según subtipo
        if current_type == "Simple":
            if "img" in current_subtype.lower():
                self.ctrl_panel.add_file_picker("Imagen de entrada", "input_image")
            
            if current_subtype == "Img+Audio2Video":
                counts = ["1", "2", "3"]
                current_count = self.ctrl_panel.get_value("v_audio_count") or "1"
                self.ctrl_panel.add_dropdown("Nº de Audios", "v_audio_count", counts, default=current_count,
                                            callback=lambda v: self._rebuild_video_panel(v_subtype=current_subtype))
                
                for i in range(1, int(current_count) + 1):
                    self.ctrl_panel.add_file_picker(f"Audio {i}", f"input_audio_{i}", 
                                                    file_types=[("Audio", "*.mp3 *.wav *.ogg *.m4a")])
            elif "audio" in current_subtype.lower():
                self.ctrl_panel.add_file_picker("Audio de entrada", "input_audio", 
                                                file_types=[("Audio", "*.mp3 *.wav *.ogg")])
            
            if current_subtype == "video2video":
                self.ctrl_panel.add_file_picker("Video de entrada", "input_video",
                                                file_types=[("Video", "*.mp4 *.avi *.mov")])
        
        # 6. Resolución de Video (Presets)
        res_options = [
            "Cuadrada (640x640)", "Cuadrada HD (1024x1024)",
            "Apaisada SD (640x480)", "Apaisada HD (1280x720)",
            "Vertical SD (480x640)", "Vertical HD (720x1280)",
            "Personalizado"
        ]
        self.ctrl_panel.add_resolution_control("Resolución Video", "video_resolution", res_options, 
                                               default="Apaisada SD (640x480)")
        
        # 7. Duración y Prompt Negativo
        self.ctrl_panel.add_input("Duración (seg)", "video_duration", default="5")
        self.ctrl_panel.add_input("Prompt Negativo", "neg_prompt", 
                                 default="low quality, blurry, static, text, watermark, deformed, bad proportions")
        
        self._add_comfy_launch_controls()

    def _update_video_workflow_files(self, v_type, v_subtype):
        """Escanea la carpeta de workflows de video según el tipo y subtipo."""
        base_w = os.path.join(os.path.dirname(__file__), "workflows", "video", v_type.lower())
        if v_subtype:
            base_w = os.path.join(base_w, v_subtype.lower())
        
        if not os.path.exists(base_w):
            os.makedirs(base_w, exist_ok=True)
            
        files = self.image_service.get_workflow_files(base_w)
        
        defaults = self.config_service.get("comfyui_defaults", {}).get("Video", {})
        user_default = defaults.get("workflow") if defaults.get("type") == v_type and defaults.get("subtype") == v_subtype else None
        
        default_val = None
        if user_default and user_default in files:
            default_val = user_default
        elif files:
            # Fallback a buscar palabra "default"
            for f in files:
                if "default" in f.lower():
                    default_val = f
                    break
            if not default_val:
                default_val = files[0]
                
        self.ctrl_panel.add_dropdown("Workflow de Video", "video_workflow", files, default=default_val)

    def get_voice_commands(self):
        """Genera el diccionario de comandos basado en el modo actual."""
        commands = {
            "texto": "set_mode_texto",
            "imagen": "set_mode_imagen",
            "fotos": "set_mode_imagen",
            "video": "set_mode_video",
            "vídeo": "set_mode_video",
            "3d": "set_mode_3d",
            "tres d": "set_mode_3d",
            "3 d": "set_mode_3d",
            "audio": "set_mode_audio",
            "sonido": "set_mode_audio",
            "generar": "generate",
            "galería": "gallery_nav",
            "galeria": "gallery_nav",
            "instrucción": "instruction",
            "instruccion": "instruction",
            "tipo": "wait_for_type",
            "tipos": "wait_for_type"
        }
        
        # Variantes naturales
        commands["crear imagen"] = "set_mode_imagen"
        commands["hacer un video"] = "set_mode_video"
        commands["grabar video"] = "set_mode_video"
        commands["hacer un vídeo"] = "set_mode_video"
        commands["pon modo audio"] = "set_mode_audio"
        commands["crear 3d"] = "set_mode_3d"
        
        return commands

    def on_voice_command(self, action_slug, text):
        """Maneja la ejecución de los comandos de voz."""
        
        # 1. Tratar capturas activas (Modo espera)
        if not action_slug:
            if self.awaiting_instruction:
                self._capture_prompt(text)
                return
            if self.awaiting_gallery_num:
                self._perform_gallery_selection(text)
                return
            if self.awaiting_type_selection:
                self._perform_type_selection(text)
                return
            return

        # 2. Comandos directos o activadores
        print(f"[MediaGenerator] Comando ejecutado: {action_slug} (Text: {text})")
        
        if action_slug == "instruction":
            # Intentar ver si ya viene el prompt en la misma frase (ej: "instrucción pájaro azul")
            prompt_only = self._strip_trigger(text, ["instrucción", "instruccion"])
            
            # Si no hay trigger pero hay texto, y el comando es 'instruction', 
            # asumimos que es una inyección directa (ej: desde el Agente)
            final_prompt = prompt_only if prompt_only else (text if text and text.lower() not in ["instrucción", "instruccion"] else None)
            
            if final_prompt:
                self._capture_prompt(final_prompt)
            else:
                self.awaiting_instruction = True
                self.chat_service.stt_captured_by_module = True
                self.chat_service.notify_system_msg("ASIMOD: Esperando instrucción de prompt...", "#4EC9B0")
            return

            return
        
        if action_slug == "gallery_nav":
            # Intentar ver si ya hay un número en el comando "galería X"
            if not self._perform_gallery_selection(text, silent_if_fail=True):
                # Si no había número, entrar en modo espera
                self.awaiting_gallery_num = True
                self.chat_service.stt_captured_by_module = True
                self.chat_service.notify_system_msg("ASIMOD: [Galería] Dime un número o 'atrás'...", "#4EC9B0")
            return
        
        if action_slug == "wait_for_type":
            self.awaiting_type_selection = True
            self.chat_service.stt_captured_by_module = True
            
            # Feedback visual y sonoro
            self._show_type_dropdown()
            self.chat_service.notify_system_msg("ASIMOD: [Tipos] Dime la categoría a seleccionar...", "#4EC9B0")
            return

        if action_slug.startswith("set_mode_"):
            mode_map = {
                "set_mode_texto": "Texto",
                "set_mode_imagen": "Imagen",
                "set_mode_video": "Video",
                "set_mode_audio": "Audio",
                "set_mode_3d": "3D"
            }
            target = mode_map.get(action_slug)
            if target and self.workspace:
                # Thread Safety: Envolver cambio de modo en el hilo principal
                self.workspace.after(0, lambda: self._safe_mode_change(target))
            return

        if action_slug == "generate":
            # Si el comando trae texto (prompt directo desde el Agente)
            # Primero quitamos el trigger "generar" si existe al inicio
            prompt_clean = self._strip_trigger(text, ["generar", "generate", "crear", "imagen de", "foto de", "haz una imagen de"])
            
            if self.workspace:
                # Thread Safety: Inyectar y disparar en el hilo principal
                self.workspace.after(0, lambda: self._safe_generate_with_prompt(prompt_clean))
            return

    def _strip_trigger(self, text, triggers):
        """Elimina el trigger del inicio del texto para obtener solo el prompt."""
        text_clean = text.lower().strip()
        for t in triggers:
            if text_clean.startswith(t):
                # Cortamos el trigger del texto original (preservamos caso)
                return text[len(t):].strip()
        return text.strip() # Devolvemos todo el texto original limpio

    def _capture_prompt(self, text):
        """Captura el texto y lo inyecta en el prompt_text de forma segura."""
        self.awaiting_instruction = False
        self.chat_service.stt_captured_by_module = False
        
        if self.workspace:
            self.workspace.after(0, lambda: self._safe_inject_prompt(text))

    def _safe_inject_prompt(self, text):
        """Inyección de prompt segura para el hilo principal de Tkinter."""
        if not self.prompt_text: return
        self.prompt_text.delete("1.0", tk.END)
        self.prompt_text.insert("1.0", text)
        self.prompt_text.config(fg=self.style.get_color("text_main"))

    def _safe_mode_change(self, target):
        """Cambio de modo seguro para el hilo principal de Tkinter."""
        if self.menu: self.menu.select(target)
        else: self.on_menu_change(target)

    def _safe_generate_with_prompt(self, prompt_clean):
        """Inyección y generación segura para el hilo principal de Tkinter."""
        if not self.prompt_text: return
        # Si hay un prompt real (y no es solo la palabra 'generar')
        if prompt_clean:
            # Eliminar placeholder si existe
            placeholder = f"Escribe aquí lo que quieres generar para {self.current_mode}..."
            current = self.prompt_text.get("1.0", tk.END).strip()
            
            self.prompt_text.delete("1.0", tk.END)
            self.prompt_text.insert("1.0", prompt_clean)
            self.prompt_text.config(fg=self.style.get_color("text_main"))
        
        self.handle_generate()

    def _perform_gallery_selection(self, text, silent_if_fail=False):
        """Extrae el número o acción de navegación del texto y lo ejecuta en la galería."""
        self.awaiting_gallery_num = False
        self.chat_service.stt_captured_by_module = False
        text_clean = text.lower().strip()
        
        # 1. Comandos de navegación
        nav_keywords = ["atrás", "atras", "retroceder", "volver", "subir"]
        if any(k in text_clean for k in nav_keywords):
            self._on_gallery_back()
            return True

        # 2. Mapeo de números (Palabras a Int)
        num_map = {
            "uno": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5,
            "seis": 6, "siete": 7, "ocho": 8, "nueve": 9, "diez": 10,
            "once": 11, "doce": 12, "trece": 13, "catorce": 14, "quince": 15
        }
        
        # Extraer número digitado o palabra
        import re
        match = re.search(r'\d+', text_clean)
        num = None
        if match:
            num = int(match.group())
        else:
            for word, val in num_map.items():
                if word in text_clean:
                    num = val
                    break
        
        if num and self.gallery:
            success = self.gallery.trigger_index(num)
            if success:
                # Cancelar cualquier espera de carpeta pendiente si ya seleccionamos un ítem
                if self.last_gallery_wait_id:
                    self.workspace.after_cancel(self.last_gallery_wait_id)
                    self.last_gallery_wait_id = None
                
                if hasattr(self, "media_display") and self.media_display:
                    self.media_display.ensure_playing()
                self.chat_service.notify_system_msg(f"Abriendo elemento {num}...", "#4EC9B0")
                return True
            else:
                self.chat_service.notify_system_msg(f"Error: El número {num} no está en la lista.", "#FF6B6B")
                return True
        
        return False


class ComfyUIConfigView(tk.Frame):
    def __init__(self, parent, config, style, image_service, on_back=None):
        super().__init__(parent, bg=style.get_color("bg_main"), padx=20, pady=10)
        self.on_back = on_back
        self.config = config
        self.style = style
        self.image_service = image_service
        self.defaults = self.config.get("comfyui_defaults", {})
        
        # Header con botón volver
        header = tk.Frame(self, bg=style.get_color("bg_main"))
        header.pack(fill=tk.X, pady=(0, 10))
        
        tk.Button(header, text="← VOLVER", bg=style.get_color("bg_main"), fg=style.get_color("accent"),
                  relief="flat", font=("Arial", 8, "bold"), cursor="hand2", 
                  command=self.on_back).pack(side=tk.LEFT)
        
        tk.Label(header, text="CONFIGURACIÓN DE WORKFLOWS", bg=style.get_color("bg_main"), 
                 fg=style.get_color("accent"), font=("Arial", 9, "bold")).pack(side=tk.LEFT, padx=20)
        
        self.container = tk.Frame(self, bg=style.get_color("bg_main"))
        self.container.pack(fill=tk.BOTH, expand=True)
        
        # Layout en 2 columnas para que no ocupe tanto alto
        self.entries = {}
        self._build_interface()
        
        # Pie de página con botón de guardar
        footer = tk.Frame(self, bg=style.get_color("bg_main"))
        footer.pack(fill=tk.X, pady=(10, 0))
        
        tk.Button(footer, text="Guardar como Predeterminados", bg=style.get_color("accent"), fg="white", 
                  bd=0, padx=15, pady=5, font=("Arial", 8, "bold"),
                  command=self._save).pack(side=tk.RIGHT)

    def _build_interface(self):
        categories = ["Imagen", "Video", "3D", "Audio"]
        base_path = os.path.join(os.path.dirname(__file__), "workflows")
        
        # Usar grid dentro del container para 2x2
        for i, cat in enumerate(categories):
            r, c = i // 2, i % 2
            frame = tk.LabelFrame(self.container, text=cat, bg=self.style.get_color("bg_main"), 
                                  fg="#666", font=("Arial", 8, "bold"), padx=10, pady=5)
            frame.grid(row=r, column=c, sticky="nsew", padx=5, pady=2)
            
            # Recuperar valores actuales
            current = self.defaults.get(cat, {})
            c_type = current.get("type", "Simple")
            c_subtype = current.get("subtype", "")
            c_flow = current.get("workflow", "")
            
            cat_path = os.path.join(base_path, cat.lower()) if cat.lower() != "3d" else os.path.join(base_path, "3d")
            w_struct = self.image_service.scan_workflows(cat_path) if os.path.exists(cat_path) else {}
            
            # Controles compactos
            tk.Label(frame, text="Tipo / Subtipo:", bg=self.style.get_color("bg_main"), fg="#888", font=("Arial", 7)).pack(anchor="w")
            row1 = tk.Frame(frame, bg=self.style.get_color("bg_main"))
            row1.pack(fill=tk.X)
            
            type_list = list(w_struct.keys()) or ["Simple"]
            cb_type = ttk.Combobox(row1, values=type_list, width=10, state="readonly", font=("Arial", 8))
            cb_type.pack(side=tk.LEFT)
            cb_type.set(c_type if c_type in type_list else type_list[0])
            
            subtypes = w_struct.get(cb_type.get(), [])
            cb_sub = ttk.Combobox(row1, values=subtypes, width=10, state="readonly", font=("Arial", 8))
            cb_sub.pack(side=tk.LEFT, padx=5)
            cb_sub.set(c_subtype if c_subtype in subtypes else (subtypes[0] if subtypes else ""))
            
            tk.Label(frame, text="Archivo:", bg=self.style.get_color("bg_main"), fg="#888", font=("Arial", 7)).pack(anchor="w", pady=(5,0))
            
            files_path = os.path.join(cat_path, cb_type.get().lower())
            if cb_sub.get(): files_path = os.path.join(files_path, cb_sub.get().lower())
            files = self.image_service.get_workflow_files(files_path) if os.path.exists(files_path) else []
            
            cb_flow = ttk.Combobox(frame, values=files, width=25, state="readonly", font=("Arial", 8))
            cb_flow.pack(fill=tk.X)
            cb_flow.set(c_flow if c_flow in files else (files[0] if files else ""))
            
            self.entries[cat] = {
                "type": cb_type, "subtype": cb_sub, "workflow": cb_flow, "cat_path": cat_path
            }
            
            cb_sub.bind("<<ComboboxSelected>>", lambda e, c=cat: self._update_row(c))

        # Ruta de Output Configurable
        tk.Frame(self.container, bg="#333", height=1).grid(row=2, column=0, columnspan=2, sticky="ew", pady=10)
        
        row3 = tk.Frame(self.container, bg=self.style.get_color("bg_main"))
        row3.grid(row=3, column=0, columnspan=2, sticky="ew", padx=10)
        
        tk.Label(row3, text="Ruta de Salida (Output Root):", bg=self.style.get_color("bg_main"),
                 fg="#888", font=("Arial", 8, "bold")).pack(side=tk.LEFT)
        self.ent_path = tk.Entry(row3, bg=self.style.get_color("bg_input"), fg="white", bd=0, font=("Arial", 9))
        self.ent_path.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=10)
        self.ent_path.insert(0, self.config.get("comfyui_output_path", os.path.abspath(os.path.join(os.path.dirname(__file__), "output"))))
        
        self.container.columnconfigure(0, weight=1)
        self.container.columnconfigure(1, weight=1)

    def _update_row(self, cat):
        row = self.entries[cat]
        t = row["type"].get()
        s = row["subtype"].get()
        
        # Actualizar subtipos si cambió el tipo
        w_struct = self.image_service.scan_workflows(row["cat_path"])
        new_subtypes = w_struct.get(t, [])
        row["subtype"]['values'] = new_subtypes
        if s not in new_subtypes:
            row["subtype"].set(new_subtypes[0] if new_subtypes else "")
        
        s = row["subtype"].get()
        
        # Actualizar archivos
        files_path = os.path.join(row["cat_path"], t.lower())
        if s: files_path = os.path.join(files_path, s.lower())
        
        new_files = self.image_service.get_workflow_files(files_path) if os.path.exists(files_path) else []
        row["workflow"]['values'] = new_files
        if row["workflow"].get() not in new_files:
            row["workflow"].set(new_files[0] if new_files else "")

    def _save(self):
        new_defaults = {}
        for cat, widgets in self.entries.items():
            new_defaults[cat] = {
                "type": widgets["type"].get(),
                "subtype": widgets["subtype"].get(),
                "workflow": widgets["workflow"].get()
            }
        
        self.config.set("comfyui_defaults", new_defaults)
        self.config.set("comfyui_output_path", self.ent_path.get())
        
        tk.messagebox.showinfo("Configuración", "Predefinidos de ComfyUI guardados correctamente.")
        if self.on_back: self.on_back()
