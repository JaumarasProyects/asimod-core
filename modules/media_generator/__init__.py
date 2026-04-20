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
        
        # Estado de Generación Compuesto (Escritorio)
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
        
        # Estados específicos por pestaña (Persistencia real)
        self.audio_state = {"type": "Voces", "provider": "ASIMOD - Edge"}
        self.video_state = {"type": "Simple", "subtype": "Img+Audio2Video", "workflow": "DefaultImg+Autio2Video.json"}
        self.image_state = {"engine": "ComfyUI", "type": "Simple", "subtype": "text2img", "workflow": "DefaultText2Img.json", "count": "1"}
        
        # --- SEMILLADO DE DEFAULTS MAESTROS ("Piezas Base" solicitadas por Usuario) ---
        m_defaults = self.config_service.get("comfyui_defaults", {})
        dirty = False
        
        # [MIGRACIÓN] Si detectamos estructura antigua (keys como 'workflow', 'subtype'), limpiar para normalizar
        if "workflow" in m_defaults.get("Imagen", {}) or "workflow" in m_defaults.get("Video", {}):
            print("[MediaGenerator] Migrando configuración de defaults a estructura granular...")
            m_defaults = {
                "Imagen": {"text2img": "DefaultText2Img.json", "img2img": "DefaultImg2Img.json"},
                "Video": {"Img2Video": "DefaultImg2Video.json", "Img+Audio2Video": "DefaultImg+Autio2Video.json"},
                "Audio": {"voices": "ASIMOD - Edge.json", "music": "Defaulttext2Music.json", "sounds": ""},
                "3D": {"img_to_3d": "DefaultImg2_3D.json"}
            }
            dirty = True
        
        # Asegurar que todas las piezas base existan
        expected = {
            "Imagen": {"text2img": "DefaultText2Img.json", "img2img": "DefaultImg2Img.json"},
            "Video": {"Img2Video": "DefaultImg2Video.json", "Img+Audio2Video": "DefaultImg+Autio2Video.json"},
            "Audio": {"voices": "ASIMOD - Edge.json", "music": "Defaulttext2Music.json", "sounds": ""},
            "3D": {"img_to_3d": "DefaultImg2_3D.json"}
        }
        
        for cat, subs in expected.items():
            if cat not in m_defaults:
                m_defaults[cat] = {}
                dirty = True
            for sub, wf in subs.items():
                if sub not in m_defaults[cat]:
                    m_defaults[cat][sub] = wf
                    dirty = True
            
        if dirty:
            self.config_service.set("comfyui_defaults", m_defaults)
            
        if dirty:
            self.config_service.set("comfyui_defaults", m_defaults)
        
        # Limpiar restos del sistema anterior si existen (vía set a None o simplemente ignorar)
        if self.config_service.get("media_master_defaults"):
            self.config_service.set("media_master_defaults", None)
        
        self.web_data = {}
        self.state_3d = {"type": "Texto a 3D"}

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
        # 0. Saneamiento: Volver a modo Simple por defecto al cambiar de pestaña
        self.compound_state["type"] = "Simple"
        
        self.current_mode = mode
        print(f"[MediaGenerator] Cambiando a modo: {mode}")

        # 1. Actualizar solo la lógica de controladores (SIN redibujar todo el widget)
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
        
        # 1. Selector de Tipo (Simple / Compuesto) - prioridad máxima arriba
        self.ctrl_panel.add_dropdown("Tipo de Generación", "gen_type", 
                                    ["Simple", "Compuesto"], 
                                    default=self.compound_state["type"],
                                    callback=self._on_compound_type_change)

        # 2. Proveedor LLM (Solo si es Texto o Compuesto)
        if mode == "Texto" or self.compound_state["type"] == "Compuesto":
            providers = self.chat_service.get_providers_list()
            current_p = self.chat_service.current_adapter.name if self.chat_service.current_adapter else "Ollama"
            self.ctrl_panel.add_dropdown("Proveedor LLM", "provider", 
                                        providers, 
                                        default=current_p,
                                        callback=self._on_provider_change)
            self._fetch_llm_models()

        # 3. Delegación a paneles específicos (Siempre necesarios para saber CÓMO generar)
        # IMPORTANTE: Los sub-paneles YA NO LIMPIAN el panel, solo añaden sus controles.
        try:
            if mode == "Audio":
                self._rebuild_audio_panel(skip_clear=True)
            elif mode == "Video":
                self._rebuild_video_panel(skip_clear=True)
            elif mode == "3D":
                self._rebuild_3d_panel(skip_clear=True)
            elif mode == "Imagen":
                self._rebuild_image_panel(skip_clear=True)
            elif mode == "Texto":
                # En Texto Compuesto, el sub-panel se gestiona en _setup_compound_controllers
                pass
        except Exception as e:
            print(f"[MediaGenerator] ERROR regenerando panel {mode}: {e}")
            self.ctrl_panel.add_label(f"⚠️ Error cargando herramientas de {mode}", color="#ff5555")

        # 4. Controles adicionales de COMPUESTO (Upgrade path / G2-G4)
        if self.compound_state["type"] == "Compuesto":
            self._setup_compound_controllers(mode, skip_clear=True)
            self._add_reference_management_controls()

        # 5. El botón de generación ya está en el área de prompt (blue button)
        pass

        # 5. El botón de generación ya está en el área de prompt (blue button), no añadimos otro aquí
        pass

    def _on_compound_type_change(self, val):
        """Callback cuando cambia el tipo de generación (Simple/Compuesto)."""
        self.compound_state["type"] = val
        self._update_controllers_logic(self.current_mode)

    def _set_master_default(self, category):
        """Fija el workflow actual para el CATEGORIA y SUBTIPO específico."""
        current_subtype = ""
        wf_key = "workflow"
        
        if category == "Audio":
            wf_key = "audio_workflow"
            current_subtype = self.audio_state.get("type", "voices").lower() # voices, music, sounds
        elif category == "Video":
            current_subtype = self.video_state.get("subtype", "")
        elif category == "Imagen":
            current_subtype = self.image_state.get("subtype", "")
            
        selected_wf = self.ctrl_panel.get_value(wf_key)
        if not selected_wf:
            self.chat_service.notify_system_msg(f"ASIMOD: No hay workflow para fijar en {category}.", "#ff4444")
            return
            
        # Actualizar estructura COMPATIBLE con el panel de Configuración (Multi-Subtipo)
        m_defaults = self.config_service.get("comfyui_defaults", {})
        if category not in m_defaults: m_defaults[category] = {}
        
        # Guardamos el workflow directamente mapeado al subtipo
        m_defaults[category][current_subtype] = selected_wf
        
        # Sincronizar también el proveedor de voz si es Audio
        if category == "Audio":
            self.config_service.set("voice_provider", self.ctrl_panel.get_value("audio_provider"))

        self.config_service.set("comfyui_defaults", m_defaults)
        self.chat_service.notify_system_msg(f"ASIMOD: {selected_wf} fijado como Default para {category}/{current_subtype}.", "#4EC9B0")
        self._update_controllers_logic(self.current_mode)

    def _resolve_master_workflow(self, category, subtype=None, recipe_wf=None):
        """Resuelve el workflow usando la clave unificada con soporte de subtipo."""
        m_defaults = self.config_service.get("comfyui_defaults", {})
        cat_config = m_defaults.get(category, {})
        
        # 1. Intentar por subtipo exacto (ej: 'faces', 'voices')
        if subtype and subtype in cat_config:
            return cat_config[subtype]
            
        # 2. Intentar por clave genérica 'workflow' en esa categoría
        if "workflow" in cat_config:
            return cat_config["workflow"]
            
        # 3. Fallback final a la receta
        return recipe_wf

    def _setup_compound_controllers(self, mode, skip_clear=False):
        """Configura los controles específicos de composición."""
        if not self.ctrl_panel: return
        
        # --- SE HA ELIMINADO EL CLEAR INTERNO ---
        
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

            if self.compound_state["subtype"] in ["Productos", "Ingredientes"]:
                # La gestión de referencias ahora es universal, no hace falta añadirla aquí
                pass
        
        else:
            # Upgrade Grades (G2, G3, G4)
            # Para Audio (G3): buscamos origen G2
            # Para Video (G4): buscamos origen G3
            # Para Imagen (G2): buscamos origen G1
            target_grade = {"Imagen": 1, "Audio": 2, "Video": 3, "3D": 1}.get(mode, 1)
            
            # 1. Selector de Categoría (Prioritario)
            cats = self.CONFIG_COMPUESTA.get("Ingredientes", []) + self.CONFIG_COMPUESTA.get("Productos", [])
            self.ctrl_panel.add_dropdown("Categoría", "gen_category", cats,
                                        default=self.compound_state["category"],
                                        callback=self._on_category_change)
            
            # 2. Cargar lista de documentos compatibles (Escaneo Sincrónico para máxima estabilidad en Desktop)
            try:
                comp_root = os.path.join(self.output_root, "texto", "compuesto")
                docs = []
                sel_cat = self.compound_state.get("category", "Personaje") # Asegurar definición
                
                if os.path.exists(comp_root):
                    for root, dirs, files in os.walk(comp_root):
                        for filename in files:
                            if filename.endswith(".json"):
                                path = os.path.join(root, filename)
                                try:
                                    with open(path, "r", encoding="utf-8") as f:
                                        data = json.load(f)
                                        if data.get("grado_desarrollo") == int(target_grade) and data.get("categoria") == sel_cat:
                                            rel_path = os.path.relpath(path, comp_root).replace("\\", "/")
                                            docs.append({
                                                "name": data.get("titulo", filename),
                                                "path": f"texto/compuesto/{rel_path}"
                                            })
                                except: continue
                
                doc_names = [d["name"] for d in docs] if docs else []
                
                if not doc_names:
                    self.ctrl_panel.add_label(f"⚠️ Sin {sel_cat} G{target_grade} disponibles.", color="#ffaa00")
                else:
                    # Guardar mapeo para resolución rápida
                    self.current_source_docs = docs
                    
                    # Forzar selección inicial en el estado si está vacío
                    if not self.compound_state.get("source_doc") and docs:
                        self.compound_state["source_doc"] = docs[0]["path"]

                    self.ctrl_panel.add_dropdown(f"Seleccionar {sel_cat} (G{target_grade})", "source_doc", 
                                                doc_names, 
                                                default=doc_names[0],
                                                callback=lambda v: self._on_source_doc_change(v, docs))
                    
                    # La gestión de referencias ahora es universal
                    
                # El botón se añade ahora centralizado en _update_controllers_logic
                pass
            except Exception as e:
                print(f"[MediaGenerator] Error cargando documentos de origen: {e}")
                self.ctrl_panel.add_label("⚠️ Error detectando documentos origen.", color="#ff4444")

    def _add_reference_management_controls(self):
        """Añade los controles de gestión de referencias de forma uniforme."""
        # Limpiar posibles duplicados si el panel reutiliza el contenedor
        target = self.ctrl_panel.grid_container # Usamos el grid_container principal
        
        self.ctrl_panel.add_button("📎 Gestionar Referencias", self._open_reference_manager)
        
        # NUEVO: Botón de generación completa para personajes
        if self.compound_state.get("category") == "Personaje":
            self.ctrl_panel.add_button("🚀 Personaje Completo (Auto)", self.handle_auto_full_character_generation)
        
        ref_count = len(self.compound_state.get("references", []))
        label_color = "#4EC9B0" if ref_count > 0 else "#888"
        self.ctrl_panel.add_label(f"📦 {ref_count} referencias activas.", color=label_color)

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
        
        # Modal y centrado
        top.transient(self.workspace)
        top.grab_set()
        top.focus_set()
        
        # Centrar
        top.update_idletasks()
        w = top.winfo_width()
        h = top.winfo_height()
        extra_w = (top.winfo_screenwidth() - w) // 2
        extra_h = (top.winfo_screenheight() - h) // 2
        top.geometry(f"+{extra_w}+{extra_h}")
        
        # 1. Cabecera y Filtros
        tk.Label(top, text="GESTOR DE REFERENCIAS", bg=self.style.get_color("bg_main"),
                 fg=self.style.get_color("accent"), font=("Arial", 11, "bold")).pack(pady=10)
        
        filter_frame = tk.Frame(top, bg=self.style.get_color("bg_main"))
        filter_frame.pack(fill=tk.X, padx=10, pady=5)
        
        categories = ["TODOS", "Personaje", "Escenario", "Prop", "Sinopsis", "Productos", "Finales"]
        
        # Iniciar con el filtro de la categoría actual para que apunte a donde debe
        initial_filter = self.compound_state["category"] if self.compound_state["category"] in categories else "TODOS"
        self._ref_filter = tk.StringVar(value=initial_filter)
        
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

        # Cargar datos de forma segura
        all_pieces = []
        import asyncio
        import traceback
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            pieces_resp = loop.run_until_complete(self.list_all_compound_pieces())
            loop.close()
            res = pieces_resp.get("result", {})
            all_pieces = res.get("ingredients", []) + res.get("products", []) + res.get("finals", [])
        except Exception as e:
            print(f"[MediaGenerator][UI] Error cargando piezas para referencias: {e}")
            traceback.print_exc()
        
        # Estado persistente durante la vida de la ventana
        current_selection = set(self.compound_state["references"])
        checkbox_vars = {} # Map path -> BooleanVar

        def on_publish(path):
            """Publica el personaje y refresca."""
            msg_id = tk.messagebox.askyesno("Publicar", f"¿Deseas publicar este personaje en el Hub de ASIMOD?\n\nPath: {path}")
            if msg_id:
                async def run_publish():
                    res = await self.publish_to_hub(path)
                    color = "green" if res["status"] == "success" else "red"
                    tk.messagebox.showinfo("Resultado", res["message"])
                
                # Ejecutar en hilo para no bloquear UI
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(run_publish())
                loop.close()

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
                lbl = tk.Label(row, text=lbl_text, bg=self.style.get_color("bg_dark"),
                         fg="white", font=("Arial", 9))
                lbl.pack(side=tk.LEFT, padx=5)

                # Grado y Publicar
                grade = p.get("grade", 1)
                tk.Label(row, text=f"• G{grade}", bg=self.style.get_color("bg_dark"),
                         fg="#888", font=("Arial", 8)).pack(side=tk.LEFT, padx=5)

                if p["category"] == "Personaje" and grade >= 2:
                    btn_pub = tk.Button(row, text="🚀 PUBLICAR", bg="#2D5A27", fg="white", 
                                       font=("Arial", 7, "bold"), bd=0, padx=5, pady=2,
                                       command=lambda pt=path: on_publish(pt))
                    btn_pub.pack(side=tk.RIGHT, padx=5)

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
        
        # SANEAMIENTO: Si ya existe el widget y es válido, lo reutilizamos
        if getattr(self, "_main_widget", None) and self._main_widget.winfo_exists():
            # Pero nos aseguramos de que el panel de control se actualice
            if hasattr(self, "ctrl_panel"):
                self._update_controllers_logic(self.current_mode)
            return self._main_widget
            
        # Limpieza profunda del padre para evitar duplicados
        for child in parent.winfo_children():
            child.destroy()
            
        main_frame = tk.Frame(parent, bg=self.style.get_color("bg_main"))
        self._main_widget = main_frame
        
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
        # SANEAMIENTO PROFUNDO: Limpiar el contenedor de acciones antes de dibujar
        for child in parent.winfo_children():
            child.destroy()
            
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
            
            # Normalizar resultado si es una lista (ComfyUI devuelve listas)
            if isinstance(result, list) and result:
                result = result[0]

            # Si el resultado es una ruta de archivo, lo convertimos a URL estática
            if isinstance(result, str) and os.path.exists(result):
                # IMPORTANTE: Movemos el archivo de forma síncrona para que la URL sea válida ya mismo
                # SEGURIDAD: No mover si ya está en una carpeta de compuesta/ingrediente
                if "texto/compuesto" in result.replace("\\", "/"):
                    final_path = result
                else:
                    filename = os.path.basename(result)
                    target_dir = os.path.join(self.output_root, mode.lower())
                    os.makedirs(target_dir, exist_ok=True)
                    
                    final_path = os.path.join(target_dir, filename)
                    if os.path.abspath(result) != os.path.abspath(final_path):
                        shutil.move(result, final_path)
                
                # Obtener ruta relativa para la URL de la API
                rel_url_path = os.path.relpath(final_path, self.output_root).replace("\\", "/")
                filename = os.path.basename(final_path)
                
                # Actualizar la UI local si existe
                if hasattr(self, "workspace") and self.workspace:
                    self.workspace.after(0, lambda: self._show_result(final_path))

                return {
                    "status": "success", 
                    "type": "file", 
                    "url": f"/v1/modules/{self.id}/output/{rel_url_path}",
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

    async def list_compound_docs(self, grade=None, category=None):
        """Lista documentos compuestos filtrados por grado y categoría, buscando en subcarpetas."""
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
                            # Filtrar por Grado
                            if grade is not None and data.get("grado_desarrollo") != int(grade):
                                continue
                            
                            # Filtrar por Categoría
                            if category is not None and data.get("categoria") != category:
                                continue

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

    def handle_auto_full_character_generation(self):
        """Dispara el proceso completo secuencial de creación de personaje."""
        prompt = self.prompt_text.get("1.0", tk.END).strip()
        if not prompt or "Escribe aquí" in prompt:
            self._cache_result_and_show("Por favor, introduce un prompt descriptivo para el personaje.", "Texto")
            return
            
        def run_sequence():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                # 1. Fase G1: Perfil de Personaje (Texto)
                self.chat_service.notify_system_msg("🚀 Iniciando Fase 1/4: Generando Perfil (G1)...", color="#40E0D0")
                g1_params = {
                    "workflow": "character_instruction.json",
                    "compound": {
                        "type": "Compuesto",
                        "subtype": "Personaje",
                        "category": "Personaje"
                    }
                }
                # Enriquecer el prompt para el modelo local con estructura JSON sugerida
                enriched_prompt = f"Crea un personaje detallado en formato JSON basado en esta idea: {prompt}. "
                enriched_prompt += "Estructura obligatoria: {\"titulo\": \"...\", \"nombre\": \"...\", \"edad\": ..., \"apariencia\": \"...\", \"historia\": \"...\", \"personalidad\": \"...\"}. "
                enriched_prompt += "No escribas nada fuera del JSON."
                
                res1 = loop.run_until_complete(self._perform_generation(enriched_prompt, "Texto", web_params=g1_params))
                
                # Manejar retorno (puede ser dict exitoso o la ruta directamente)
                if isinstance(res1, dict) and res1.get("status") == "success":
                    g1_path = res1.get("json_path")
                elif isinstance(res1, str) and os.path.exists(res1):
                    g1_path = res1
                else:
                    raise Exception(f"No se pudo generar G1. El modelo devolvió: {str(res1)[:200]}...")
                
                # 2. Fase G2: Imagen (G2)
                self.chat_service.notify_system_msg("🎨 Fase 2/4: Generando Imagen Principal (G2)...", color="#40E0D0")
                g2_params = {
                    "source_doc": g1_path,
                    "compound": {
                        "type": "Compuesto",
                        "subtype": "Personaje",
                        "category": "Personaje"
                    }
                }
                res2 = loop.run_until_complete(self._perform_generation(prompt, "Imagen", web_params=g2_params))
                if isinstance(res2, dict) and res2.get("status") == "success":
                    g2_path = res2.get("json_path")
                elif isinstance(res2, list) and res2 and os.path.exists(res2[0]):
                    g2_path = res2[0]
                elif isinstance(res2, str) and os.path.exists(res2):
                    g2_path = res2
                else:
                    raise Exception(f"Fallo en G2: {str(res2)[:200]}...")

                # 3. Fase G3: Audio/Ficha (G3)
                self.chat_service.notify_system_msg("🎙️ Fase 3/4: Generando Voz y Ficha Técnica (G3)...", color="#40E0D0")
                g3_params = {
                    "source_doc": g2_path,
                    "compound": {
                        "type": "Compuesto",
                        "subtype": "Personaje",
                        "category": "Personaje"
                    }
                }
                res3 = loop.run_until_complete(self._perform_generation(prompt, "Audio", web_params=g3_params))
                if isinstance(res3, dict) and res3.get("status") == "success":
                    g3_path = res3.get("json_path")
                elif isinstance(res3, list) and res3 and os.path.exists(res3[0]):
                    g3_path = res3[0]
                elif isinstance(res3, str) and os.path.exists(res3):
                    g3_path = res3
                else:
                    raise Exception(f"Fallo en G3: {str(res3)[:200]}...")

                # 4. Fase G4: Vídeo (G4)
                self.chat_service.notify_system_msg("🎬 Fase 4/4: Generando Vídeos de Animación (G4)...", color="#40E0D0")
                g4_params = {
                    "source_doc": g3_path,
                    "compound": {
                        "type": "Compuesto",
                        "subtype": "Personaje",
                        "category": "Personaje"
                    }
                }
                res4 = loop.run_until_complete(self._perform_generation(prompt, "Video", web_params=g4_params))
                if isinstance(res4, dict) and res4.get("status") == "success":
                    g4_path = res4.get("json_path")
                    final_res = res4
                elif isinstance(res4, list) and res4 and os.path.exists(res4[0]):
                    g4_path = res4[0]
                    final_res = {"status": "success", "json_path": g4_path}
                elif isinstance(res4, str) and os.path.exists(res4):
                    g4_path = res4
                    final_res = {"status": "success", "json_path": g4_path}
                else:
                    raise Exception(f"Fallo en G4: {str(res4)[:200]}...")

                # 5. Publicación Automática (Ya se hace dentro de _perform_generation para G4 final, pero aseguramos)
                self.chat_service.notify_system_msg("✅ ¡PERSONAJE COMPLETO GENERADO CON ÉXITO!", color="#00ff00", beep=True)
                self._cache_result_and_show(final_res, "Video")

            except Exception as e:
                import traceback
                traceback.print_exc()
                self._cache_result_and_show(f"Error en flujo automático: {str(e)}", "Texto")
                self.chat_service.notify_system_msg(f"❌ Error en generación automática: {str(e)}", color="#ff4444")
            finally:
                loop.close()
            
        import threading
        threading.Thread(target=run_sequence, daemon=True).start()

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
        
        # Detectar modo compuesto: leer directamente del estado interno
        # Soportar variaciones de nombre (Compuesto/Compuesta) y ser flexible si se elige una receta
        current_type = self.compound_state.get("type", "Simple")
        current_wf = self._get_val("workflow", web_params) or ""
        
        is_recipe = "instruction.json" in current_wf.lower() or "recipe" in current_wf.lower()
        desktop_is_compound = (not web_params) and (current_type in ["Compuesto", "Compuesta"] or is_recipe)

        if web_params:
            comp_state = web_params.get("compound", {})
            # Forzar modo compuesto si hay receta o si se indica explícitamente
            if comp_state.get("type") in ["Compuesto", "Compuesta"] or is_recipe:
                is_compound = True
                comp_params = web_params
        elif desktop_is_compound:
            is_compound = True

        if is_compound:
            # --- RESOLUCIÓN DINÁMICA DE SOURCE DOC ---
            s_doc = None
            if web_params:
                s_doc = web_params.get("source_doc")
                comp_params = web_params
            else:
                s_doc = self.compound_state.get("source_doc")
                if not s_doc:
                    # Si no está en el estado, intentar recuperarlo del dropdown y mapearlo
                    ui_name = self._get_val("source_doc")
                    if ui_name and hasattr(self, "current_source_docs"):
                        for d in self.current_source_docs:
                            if d["name"] == ui_name:
                                s_doc = d["path"]
                                break
                
                comp_params = {
                    "compound": self.compound_state,
                    "source_doc": s_doc,
                    "workflow": current_wf
                }

            # Inyectar neg_prompt si existe
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
                    
                    current_wf = self._get_val("workflow", web_params)
                    
                    if w_type == "Compuesto":
                        # RECETA: Buscar en la carpeta 'processes'
                        full_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "processes", current_wf))
                    else:
                        # WORKFLOW SIMPLE: Buscar en la carpeta correspondiente
                        w_folder = "compuesta" if w_type.lower() == "compuesto" else w_type.lower()
                        full_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "workflows", w_folder))
                        if w_subtype:
                            full_path = os.path.join(full_path, w_subtype.lower())
                        full_path = os.path.join(full_path, current_wf)
                    
                    print(f"[MediaGenerator] Workflow/Receta: {full_path}")
                    if os.path.exists(full_path):
                        try:
                            with open(full_path, "r", encoding="utf-8") as f:
                                workflow_data = json.load(f)
                            
                            # --- FAILSAFE: Si el JSON tiene 'grades', es una RECETA, no un workflow ---
                            if isinstance(workflow_data, dict) and "grades" in workflow_data:
                                print(f"[MediaGenerator] Receta detectada por contenido. Forzando modo Compuesto.")
                                is_compound = True
                                if not comp_params:
                                    comp_params = {
                                        "compound": self.compound_state,
                                        "source_doc": self.compound_state.get("source_doc"),
                                        "workflow": current_wf
                                    }
                                return await self._generate_compound(prompt, mode, comp_params)
                                
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
            img_dims = None

            if v_subtype == "Img+Audio2Video":
                img = self._get_val("input_image", web_params)
                if img and img != "Ninguno": 
                    if not os.path.isabs(img): img = os.path.join(self.output_root, img)
                    if os.path.exists(img): 
                        input_files.append(img)
                        try:
                            with Image.open(img) as im:
                                img_dims = im.size
                            print(f"[MediaGenerator] Resolución detectada de imagen de entrada: {img_dims[0]}x{img_dims[1]}")
                        except: pass
                
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
            
            # Resolución de Video (Priorizar dimensiones de imagen si existe para evitar distorsión)
            if img_dims:
                w, h = img_dims
            else:
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
        subtype = comp_state.get("subtype") or web_params.get("subtype")
        category = comp_state.get("category") or web_params.get("category")
        source_path = web_params.get("source_doc")
        
        # 2. Cargar o Inicializar Datos
        piece_data = comp_state.get("compound", {})
        
        # NUEVO: Recuperación de metadatos existentes para evitar pérdida de assets (G2, G3)
        piece_id = piece_data.get("id")
        if piece_id:
            existing_data = self._load_existing_piece_metadata(piece_id, category)
            if existing_data:
                print(f"[Compound] Recuperados metadatos existentes para {piece_id}. Fusionando...")
                # Fusionar multimedia con cuidado
                ex_multimedia = existing_data.get("multimedia", {})
                curr_multimedia = piece_data.get("multimedia", {})
                for k, v in ex_multimedia.items():
                    if k not in curr_multimedia or not curr_multimedia[k]:
                        curr_multimedia[k] = v
                for k, v in existing_data.items():
                    if k not in piece_data or not piece_data[k]:
                        piece_data[k] = v
                piece_data["multimedia"] = curr_multimedia

        # Determinar el grado objetivo basado en el panel (modo)
        grade_map = {"Texto": 1, "Imagen": 2, "Audio": 3, "Video": 4}
        target_grade = grade_map.get(mode, 1)
        
        print(f"[MediaGenerator][Compound] Generando {category} G{target_grade}. Origen: {source_path}")

        # 1. Cargar Receta (Instrucciones)
        recipe = self._load_recipe(category)
        
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
                # Limpiar y parsear JSON
                clean_resp = self._clean_json_markdown(str(resp))
                llm_json = json.loads(clean_resp)
                piece_data.update(llm_json)
                # Preservar campos de tipo aunque el LLM los sobreescriba
                piece_data.update(tipo_field)
            except:
                # Si falla el JSON, intentar mappear campos básicos desde el texto bruto
                raw_text = str(resp)
                piece_data["descripcion_generada"] = raw_text
                # Heurística mínima para que G2 no falle (Nombre e Historia)
                if "titulo" not in piece_data or piece_data["titulo"].startswith("Nueva"):
                    lines = [l.strip() for l in raw_text.split("\n") if l.strip()]
                    if lines: piece_data["titulo"] = lines[0][:50]
                
                if "historia" not in piece_data:
                    piece_data["historia"] = raw_text[:500]
                if "personalidad" not in piece_data:
                    piece_data["personalidad"] = "Personalidad definida por su trasfondo."

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
                # --- GENERACIÓN MULTI-FASE BASADA EN RECETA (+ Master Defaults) ---
                # [ACTUALIZADO] Ahora buscamos en imagen/compuesta o imagen/simple según receta
                wf_folder = img_recipe.get("workflow_folder", "workflows/imagen/compuesta/personaje/imagen")
                steps = img_recipe.get("steps", [])
                
                if not steps:
                    # Fallback si no hay pasos definidos, usar el default antiguo o el maestro
                    master_wf = self._resolve_master_workflow("Imagen", recipe_wf=img_recipe.get("default_workflow", "DefaultImg2Img.json"))
                    steps = [{"name": "Fase 1", "workflow": master_wf, "output_key": "imagen_principal"}]

                step_results = {}
                for step in steps:
                    s_name = step.get("name")
                    # RESOLUCIÓN MAESTRA: Si el paso es el principal o indica default, usar el maestro
                    raw_wf = step.get("workflow")
                    s_file = self._resolve_master_workflow("Imagen", recipe_wf=raw_wf)
                    # Soporte para carpeta de workflow por paso (flexibilidad total)
                    s_folder = step.get("workflow_folder", wf_folder)
                    s_out_key = step.get("output_key", "imagen_aux")
                    s_input_from = step.get("input_from")
                    
                    wf_path = os.path.normpath(os.path.join(os.path.dirname(__file__), s_folder, s_file))
                    print(f"[Compound][G2] Ejecutando Paso '{s_name}': {wf_path}")
                    
                    if not os.path.exists(wf_path):
                        raise Exception(f"No se encuentra el workflow necesario en: {wf_path}")
                        
                    with open(wf_path, "r", encoding="utf-8") as f:
                        wf_json = json.load(f)
                    
                    # Preparar inputs y prompt
                    base_p = piece_data.get("descripcion_generada", piece_data.get("descripcion_detallada", prompt))
                    override_p = step.get("prompt_override")
                    p_text = f"{base_p}. {override_p}" if override_p else base_p
                    
                    inputs = []
                    if s_input_from and s_input_from in step_results:
                        inputs.append(step_results[s_input_from])
                    
                    print(f"[Compound][G2] Generando {s_name} (Resolución fija: 512x512)...")
                    res = await adapter.generate_image(p_text, workflow_json=wf_json, input_images=inputs, width=512, height=512)
                    
                    if isinstance(res, str) and os.path.exists(res):
                        # Registrar resultado en multimedia
                        if "multimedia" not in piece_data: piece_data["multimedia"] = {}
                        if "imagenes" not in piece_data["multimedia"]: piece_data["multimedia"]["imagenes"] = []
                        
                        fname = os.path.basename(res)
                        piece_data["multimedia"]["imagenes"].append(fname)
                        piece_data["multimedia"][s_out_key] = fname
                        step_results[s_name] = res # Guardar para siguientes pasos
                        print(f"[Compound][G2] Paso '{s_name}' completado: {fname}")
                    elif isinstance(res, list):
                        # Caso de múltiples salidas
                        flist = [os.path.basename(r) for r in res]
                        if "multimedia" not in piece_data: piece_data["multimedia"] = {}
                        piece_data["multimedia"].setdefault("imagenes", []).extend(flist)
                        piece_data["multimedia"][s_out_key] = flist
                        step_results[s_name] = res[0] # Usar la primera como referencia si hace falta
                        print(f"[Compound][G2] Paso '{s_name}' completado (Múltiples): {len(flist)} archivos.")

            if "multimedia" in piece_data and piece_data["multimedia"].get("imagenes"):
                piece_data["grado_desarrollo"] = 2
            else:
                print("[Warning] No se generaron imágenes en G2. El grado se mantiene en 1.")

        elif target_grade == 3:
            # Grado 3: Generación de Audio (Voz de presentación)
            print("[Compound] Escalando a Grado 3: Generando voz del personaje...")
            
            # 1. Determinar Datos del Personaje (NUEVO: Mejora de detección)
            personality = piece_data.get("personality", piece_data.get("descripcion_generada", piece_data.get("descripcion", "")))
            name = piece_data.get("titulo", "Este personaje")
            
            gender = piece_data.get("gender")
            if not gender:
                gender = self._detect_gender(name, personality)
                piece_data["gender"] = gender
                print(f"[Compound][G3] Género detectado automáticamente: {gender}")

            voice_id = piece_data.get("voice_id")
            
            # 2. Generar Frase de Presentación via LLM (ASIMOD Core)
            llm_prompt = f"Genera una frase de presentación MUY CORTA (máximo 15 palabras) para el personaje '{name}' basándote en su personalidad: {personality}. Escribe SOLO la frase, sin comillas."
            res = await self.chat_service.generate_chat([{"role": "user", "content": llm_prompt}], system_prompt="Eres un guionista experto en diálogos cortos y carismáticos.")
            presentation_phrase = str(res).strip()
            piece_data["presentation_phrase"] = presentation_phrase
            print(f"[Compound] Frase G3: {presentation_phrase}")

            # 3. Generar Audio TTS (NUEVO: Selección aleatoria por género)
            if not voice_id:
                from core.factories.voice_factory import VoiceFactory
                import random
                adapter = VoiceFactory.get_adapter("Edge TTS")
                if adapter:
                    all_voices = adapter.list_voices()
                    search_term = "Masculina" if gender == "male" else "Femenina"
                    matching = [v["id"] for v in all_voices if search_term in v["name"]]
                    if matching:
                        voice_id = random.choice(matching)
                        print(f"[Compound][G3] Voz aleatoria seleccionada para {gender}: {voice_id}")
                
                if not voice_id:
                    # Fallback tradicional
                    voice_id = "es-ES-ElviraNeural" if gender == "female" else "es-ES-AlvaroNeural"
                
                piece_data["voice_id"] = voice_id

            multimedia = piece_data.setdefault("multimedia", {})
            audios = multimedia.setdefault("audios", [])

            # --- RESOLUCIÓN DE WORKFLOW (Diferenciar Virtual de ComfyUI) ---
            wf_choice = self._resolve_master_workflow("Audio", subtype="voices")
            
            if wf_choice == "ASIMOD - Edge.json":
                # MODO RÁPIDO (Virtual): Usar adaptador Edge directamente
                target_prov = "Edge TTS"
                print(f"[Compound][G3] Usando Workflow VIRTUAL: {wf_choice} (Generación Ultra-Rápida)")
            else:
                # MODO COMFYUI: Usar adaptador ComfyUI (Si existe el workflow real)
                target_prov = "ComfyUI"
                print(f"[Compound][G3] Usando Workflow COMFYUI: {wf_choice}")
            
            from core.factories.voice_factory import VoiceFactory
            voice_adapter = VoiceFactory.get_adapter(target_prov) 
            
            if voice_adapter:
                # Generar audio temporal
                temp_audio = os.path.join(self.output_root, "audio", f"temp_{piece_data['id']}.mp3")
                os.makedirs(os.path.dirname(temp_audio), exist_ok=True)
                
                # Si es ComfyUI, pasaríamos el workflow, pero el adaptador actual de ComfyUI 
                # suele esperar que el pipeline sea distinto. De momento, usamos el adapter de voz
                # que sabe lidiar con ComfyUI o Edge.
                success = await voice_adapter.generate(presentation_phrase, temp_audio, voice_id=voice_id)
                if success and os.path.exists(temp_audio):
                    final_name = f"{piece_data['id']}_g3_voice.mp3"
                    final_path = os.path.join(self.output_root, "audio", final_name)
                    shutil.move(temp_audio, final_path)
                    
                    if final_name not in audios: audios.append(final_name)
                    multimedia["audio_principal"] = final_name
                    print(f"[Compound] Audio G3 generado con éxito: {final_name}")
            
            # --- NUEVO: CALIBRACIÓN EMOCIONAL (Entrevista de Personalidad) ---
            print(f"[Compound][G3] Iniciando Calibración Emocional para: {name}...")
            calibration_results = []
            questions = [
                {"type": "joy", "q": "¿Qué es lo que más te apasiona o te hace sentir realmente feliz? Usa muchos emojis en tu respuesta."},
                {"type": "joy", "q": "¡Has ganado un premio importante! ¿Cómo lo celebrarías? Demuéstrame tu alegría."},
                {"type": "anger", "q": "Alguien acaba de insultar tu trabajo y dice que no vales nada. ¿Qué le responderías? No te cortes con los emojis si te molesta."},
                {"type": "anger", "q": "Parece que hoy todo te sale mal y la gente no deja de molestarte. ¿Qué tienes que decir al respecto?"}
            ]
            
            calib_system = (
                f"Actúa estrictamente como el personaje '{name}'.\n"
                f"Personalidad: {personality}\n"
                f"Género: {gender}\n"
                "REGLAS:\n"
                "1. Responde de forma natural según tu personalidad.\n"
                "2. Usa emojis de forma abundante para expresar tu estado emocional actual.\n"
                "3. Mantén tus respuestas cortas (2-3 frases)."
            )
            
            for item in questions:
                try:
                    print(f"[Calibration] Pregunta ({item['type']}): {item['q']}")
                    res = await self.chat_service.generate_chat(
                        [{"role": "user", "content": item['q']}], 
                        system_prompt=calib_system
                    )
                    ans = str(res).strip()
                    calibration_results.append({
                        "type": item['type'],
                        "question": item['q'],
                        "answer": ans
                    })
                except Exception as e:
                    print(f"[Calibration] Error en pregunta: {e}")
            
            piece_data["calibration"] = calibration_results
            print(f"[Compound][G3] Calibración completada con {len(calibration_results)} respuestas.")
            
            # LIMPIEZA DE HISTORIAL: Asegurar que el personaje empiece limpio para el usuario
            piece_data["history"] = []
            
            # Validar que se generó el audio antes de subir el grado
            if "multimedia" in piece_data and piece_data["multimedia"].get("audio_principal"):
                piece_data["grado_desarrollo"] = 3
            else:
                print("[Warning] No se generó el audio en G3. El grado se mantiene en 2.")

        elif target_grade == 4:
            # Grado 4: Vídeo (Animación Talking e Idle)
            print("[Compound] Escalando a Grado 4: Generando videos de speech e idle...")
            
            multimedia = piece_data.setdefault("multimedia", {})
            videos = multimedia.setdefault("videos", [])
            
            # 1. Preparar Inputs
            img_list = multimedia.get("imagenes", [])
            audio_list = multimedia.get("audios", [])
            
            if not img_list and category == "Personaje":
                # NUEVO: Intentar rescatar imagen del HUB si no hay en la pieza actual (Resiliencia)
                print(f"[Compound][G4] Imágenes ausentes. Intentando rescate desde el HUB...")
                recovered_img = self._attempt_hub_recovery(piece_data)
                if recovered_img:
                    img_list = [recovered_img]
                    multimedia["imagenes"] = img_list
                    multimedia["imagen_principal"] = recovered_img
            
            if not img_list or not audio_list:
                raise Exception("Faltan imágenes (G2) o audios (G3) para generar el vídeo. Verifica si ComfyUI está encendido.")
            
            img_path = os.path.join(self.output_root, "imagen", img_list[0])
            speech_audio_path = os.path.join(self.output_root, "audio", multimedia.get("audio_principal", audio_list[0]))
            
            # Detectar resolución de la imagen base (G2) para evitar distorsión en el video final
            v_width, v_height = 1024, 1024
            try:
                with Image.open(img_path) as im:
                    v_width, v_height = im.size
                print(f"[Compound][G4] Sincronizando resolución con imagen original: {v_width}x{v_height}")
            except Exception as e:
                print(f"[Compound][Warning] No se pudo leer dimensiones de la imagen: {e}")
            
            # 2. Preparar Workflow
            vid_recipe = recipe.get("grades", {}).get("4", {})
            wf_folder = vid_recipe.get("workflow_folder", "workflows/video/simple/Img+Audio2Video")
            raw_wf = vid_recipe.get("default_workflow", "DefaultImg+Audio2Video.json")
            wf_file = self._resolve_master_workflow("Video", recipe_wf=raw_wf)
            
            wf_path = os.path.normpath(os.path.join(os.path.dirname(__file__), wf_folder, wf_file))

            # Ruta para idle (Priorizar si ya existe en metadata, sino usar el default silencioso)
            idle_audio_name = multimedia.get("audio_idle") or "idle_silent.mp3"
            if idle_audio_name.startswith("http") or os.path.isabs(idle_audio_name):
                idle_audio_path = idle_audio_name
            elif os.path.exists(os.path.join(self.output_root, "audio", idle_audio_name)):
                idle_audio_path = os.path.join(self.output_root, "audio", idle_audio_name)
            else:
                idle_audio_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "resources", "idle_silent.mp3"))

            print(f"[Compound][G4] Usando audios respectivos: Speak={os.path.basename(speech_audio_path)}, Idle={os.path.basename(idle_audio_path)}")
            
            # 2. GENERACIÓN MULTI-EMOCIONAL (Loopear sobre los estados detectados)
            emotion_map = {
                "neutral": multimedia.get("imagen_principal"),
                "anger": multimedia.get("imagen_anger"),
                "joy": multimedia.get("imagen_joy")
            }
            
            adapter = self.image_service.get_adapter("ComfyUI")
            if not os.path.exists(wf_path):
                raise Exception(f"No se encuentra el workflow de animación en: {wf_path}")
            with open(wf_path, "r", encoding="utf-8") as f: wf = json.load(f)

            for emotion, img_name in emotion_map.items():
                if not img_name: continue
                
                # Normalizar img_name si es lista
                if isinstance(img_name, list) and img_name: img_name = img_name[0]
                
                img_p = os.path.join(self.output_root, "imagen", img_name)
                if not os.path.exists(img_p): continue
                
                print(f"[Compound][G4] Generando VÍDEO para estado: {emotion.upper()}...")
                
                # 2.1 VÍDEO HABLANDO (SPEAKING)
                emotion_suffix = ""
                if emotion == "joy": emotion_suffix = ", talking with a big happy smile, joyful expression, looking at camera"
                elif emotion == "anger": emotion_suffix = ", talking while angry, enraged expression, rage, intense look"
                elif emotion == "neutral": emotion_suffix = ", talking normally, neutral expression"
                
                v_prompt = f"{prompt}{emotion_suffix}"
                v_res = await adapter.generate_image(v_prompt, workflow_json=wf, input_images=[img_p, speech_audio_path], width=v_width, height=v_height)
                if isinstance(v_res, list) and v_res: v_res = v_res[0]

                if isinstance(v_res, str) and os.path.exists(v_res):
                    suffix = "" if emotion == "neutral" else f"_{emotion}"
                    target_name = f"{piece_data['id']}_g4_talking{suffix}.mp4"
                    target_path = os.path.join(self.output_root, "video", target_name)
                    shutil.copy(v_res, target_path)
                    
                    if target_name not in videos: videos.append(target_name)
                    # Guardar en multimedia con el nombre exacto que espera AvatarVisualizer
                    key = "video_talking" if emotion == "neutral" else f"video_talking_{emotion}"
                    multimedia[key] = target_name
                    
                    # Aplicar bucle (Silent para el de habla por petición previa)
                    try:
                        await self._apply_ping_pong_loop(target_path, include_audio=False)
                    except Exception as e:
                        print(f"[MediaGenerator][Warning] Error aplicando bucle a video talking: {e}")

                # 2.2 VÍDEO EN REPOSO (IDLE)
                if os.path.exists(idle_audio_path):
                    print(f"[Compound][G4] Generando VÍDEO IDLE para estado: {emotion.upper()}...")
                    char_desc = piece_data.get('apariencia', piece_data.get('descripcion', 'personaje'))
                    
                    # Enriquecer prompt de idle con la emoción actual
                    idle_emotion_suffix = ", neutral expression"
                    if emotion == "joy": idle_emotion_suffix = ", happy smiling expression, joyful"
                    elif emotion == "anger": idle_emotion_suffix = ", angry annoyed expression, rage"
                    
                    v_idle_prompt = f"{char_desc}, idle loop, breathing, blinking, maintaining character consistency{idle_emotion_suffix}"
                    v_idle = await adapter.generate_image(v_idle_prompt, workflow_json=wf, input_images=[img_p, idle_audio_path], width=v_width, height=v_height)
                    if isinstance(v_idle, list) and v_idle: v_idle = v_idle[0]
                    
                    if isinstance(v_idle, str) and os.path.exists(v_idle):
                        suffix = "" if emotion == "neutral" else f"_{emotion}"
                        idle_name = f"{piece_data['id']}_g4_idle{suffix}.mp4"
                        idle_path = os.path.join(self.output_root, "video", idle_name)
                        shutil.copy(v_idle, idle_path)
                        
                        if idle_name not in videos: videos.append(idle_name)
                        # Mapear correctamente para visualizadores
                        key = "video_idle" if emotion == "neutral" else f"video_idle_{emotion}"
                        multimedia[key] = idle_name
                        try:
                            await self._apply_ping_pong_loop(idle_path)
                        except Exception as e:
                            print(f"[MediaGenerator][Warning] Error aplicando bucle a video idle: {e}")

            # Validar que se generó al menos el video principal antes de subir el grado
            if "multimedia" in piece_data and piece_data["multimedia"].get("video_talking"):
                piece_data["grado_desarrollo"] = 4
            else:
                raise Exception("[Error] No se generó el video principal en G4.")

        # 4. Guardar Resultado Progresivo en subcarpeta central (SIEMPRE en texto/compuesto para trazabilidad)
        output_name = f"{piece_data['id']}.json"
        # Forzar el uso de la ruta central para el JSON de metadata
        central_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "output", "texto", "compuesto"))
        subfolder_name = self._get_compound_path(category).split(os.path.sep)[-1] # Sacar el nombre final (Personajes, Escenarios...)
        dest_path = os.path.join(central_root, subfolder_name, output_name)
        
        print(f"[MediaGenerator][Debug] Guardando metadata central en: {dest_path}")
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        with open(dest_path, "w", encoding="utf-8") as f:
            json.dump(piece_data, f, indent=4, ensure_ascii=False)
            
        # PUBLICACIÓN AUTOMÁTICA AL HUB
        if category == "Personaje":
            await self.publish_to_hub(dest_path)
            
        return {
            "status": "success", 
            "json_path": dest_path, 
            "piece_data": piece_data,
            "id": piece_data.get("id")
        }

    async def publish_to_hub(self, json_path):
        """Publica un ingrediente (actualmente Personaje) al repositorio global de ASIMOD."""
        try:
            # Resolver ruta si es relativa
            if not os.path.isabs(json_path):
                full_path = os.path.join(self.output_root, json_path)
                if os.path.exists(full_path):
                    json_path = full_path

            if not os.path.exists(json_path):
                return {"status": "error", "message": f"Archivo no encontrado: {json_path}"}
                
            with open(json_path, "r", encoding="utf-8") as f:
                piece_data = json.load(f)
                
            category = piece_data.get("categoria", piece_data.get("category"))
            if category != "Personaje":
                return {"status": "error", "message": "Solo se pueden publicar Personajes de momento."}
                
            char_name = piece_data.get("titulo", piece_data.get("id"))
            # Sanitizar nombre para carpeta (Windows no permite : / \ * ? " < > |)
            char_folder = char_name
            for char in '<>:"/\\|?*':
                char_folder = char_folder.replace(char, "_")
                
            reg_path = os.path.join("Resources", "Characters", char_folder)
            os.makedirs(reg_path, exist_ok=True)
            
            # Extraer personalidad
            personality = ""
            desc = piece_data.get("descripcion_generada", "")
            if "```json" in desc:
                try:
                    inner = json.loads(desc.split("```json")[1].split("```")[0])
                    pers_list = inner.get('personality_and_traits', {}).get('personality_traits', [])
                    personality = f"Arquetipo: {inner.get('archetype')}. Personalidad: {', '.join(pers_list)}"
                except: pass
            
            # Cargar datos existentes si es un 'Upgrade'
            existing_reg_data = {}
            reg_json_path = os.path.join(reg_path, "character.json")
            if os.path.exists(reg_json_path):
                try:
                    with open(reg_json_path, "r", encoding="utf-8") as f:
                        existing_reg_data = json.load(f)
                    print(f"[MediaGenerator] Detectado upgrade para '{char_name}'. Preservando ID: {existing_reg_data.get('id')}")
                except: pass

            # Datos para character.json (Fusión)
            reg_data = {
                "id": existing_reg_data.get("id", piece_data["id"]),
                "name": char_name,
                "personality": personality if personality else existing_reg_data.get("personality", ""),
                "gender": piece_data.get("gender", existing_reg_data.get("gender", "male")),
                "active_thread": existing_reg_data.get("active_thread", f"thread_{piece_data['id']}"),
                "avatar": {},
                "video": {"idle": "", "talking": ""},
                "voice_id": piece_data.get("voice_id") or existing_reg_data.get("voice_id"),
                "voice_provider": piece_data.get("voice_provider") or existing_reg_data.get("voice_provider", "Edge TTS")
            }
            
            # Copiar Assets (Detección Dinámica de Variantes)
            multimedia = piece_data.get("multimedia", {})
            output_img_dir = os.path.join(os.path.dirname(__file__), "output", "imagen")
            output_vid_dir = os.path.join(os.path.dirname(__file__), "output", "video")
            
            def ensure_str(val):
                if isinstance(val, list) and val: return val[0]
                return val

            # 1. IMÁGENES (Avatares) - Mapeo de estados emocionales a assets
            avatar_map = {
                "idle": multimedia.get("imagen_principal"),
                "talking": multimedia.get("imagen_principal"),
                "idle_anger": multimedia.get("imagen_anger"),
                "talking_anger": multimedia.get("imagen_anger"),
                "idle_joy": multimedia.get("imagen_joy"),
                "talking_joy": multimedia.get("imagen_joy")
            }
            
            for key, img_name in avatar_map.items():
                img_name = ensure_str(img_name)
                if img_name:
                    src = os.path.join(output_img_dir, img_name)
                    if os.path.exists(src):
                        dest_fname = f"{key}.png"
                        shutil.copy(src, os.path.join(reg_path, dest_fname))
                        reg_data["avatar"][key] = f"Resources/Characters/{char_folder}/{dest_fname}"

            # 2. VÍDEOS - Mapeo de estados emocionales a archivos de video
            video_map = {
                "idle": multimedia.get("video_idle"),
                "talking": multimedia.get("video_talking"),
                "talking_anger": multimedia.get("video_talking_anger"),
                "talking_joy": multimedia.get("video_talking_joy")
            }

            for key, vid_name in video_map.items():
                vid_name = ensure_str(vid_name)
                if vid_name:
                    src = os.path.join(output_vid_dir, vid_name)
                    if os.path.exists(src):
                        dest_fname = f"{key}.mp4"
                        shutil.copy(src, os.path.join(reg_path, dest_fname))
                        reg_data["video"][key] = f"Resources/Characters/{char_folder}/{dest_fname}"

            # Guardar JSON final en el Hub
            with open(os.path.join(reg_path, "character.json"), "w", encoding="utf-8") as f:
                json.dump(reg_data, f, indent=4, ensure_ascii=False)
                
            print(f"[MediaGenerator] Personaje '{char_name}' publicado en el Hub.")
            return {"status": "success", "message": f"Personaje '{char_name}' publicado con éxito en el Hub."}
            
        except Exception as e:
            msg = f"Error publicando: {str(e)}"
            print(f"[MediaGenerator] {msg}")
            return {"status": "error", "message": msg}

    def _detect_gender(self, name, personality):
        """Intento simple de detectar género por palabras clave en nombre y descripción."""
        p = (name + " " + personality).lower()
        masc = ["hombre", "pirata", "caballero", "niño", "anciano", "rey", "señor", "niño", "lobo", "corsario", "masculino"]
        fem = ["mujer", "femenina", "dama", "niña", "anciana", "reina", "señora", "doctora", "chica"]
        
        # Prioridad a palabras muy específicas
        if any(w in p for w in ["mujer", "niña", "doctora", "reina", "femenina", "chica"]): return "female"
        if any(w in p for w in ["hombre", "niño", "rey", "masculino", "caballero"]): return "male"
        
        # Conteo simple
        m_count = sum(1 for w in masc if w in p)
        f_count = sum(1 for w in fem if w in p)
        
        return "female" if f_count > m_count else "male"

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
        # --- NUEVO: Priorizar el selector de 'Workflow' (que ahora muestra recetas en modo Compuesto) ---
        # En la UI de escritorio, el valor del workflow se guarda en self.prompt_params
        selected_wf = self._get_val("workflow")
        if selected_wf and selected_wf.endswith(".json"):
            recipe_file = selected_wf
        else:
            mapping = {
                "Personaje": "character_instruction.json",
                "Escenario": "setting_instruction.json",
                "Prop": "prop_instruction.json",
                "Sinopsis": "synopsis_instruction.json",
                "Plano": "plano_instruction.json"
            }
            recipe_file = mapping.get(category, "character_instruction.json")
            
        path = os.path.abspath(os.path.join(os.path.dirname(__file__), "processes", recipe_file))
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
        """Limpia bloques de código markdown y extrae el primer objeto JSON válido."""
        if not text: return ""
        text = str(text).strip()
        
        # 1. Intentar extraer contenido entre bloques de código ```json ... ```
        import re
        code_blocks = re.findall(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
        if code_blocks:
            return code_blocks[0].strip()
        
        # 2. Intentar encontrar el primer '{' y el último '}'
        # Esto sirve para cuando el LLM habla antes o después del JSON
        start = text.find('{')
        end = text.rfind('}')
        if start != -1 and end != -1 and end > start:
            return text[start:end+1].strip()
            
        # 3. Limpieza básica por si lo anterior falla
        return text.replace("```json", "").replace("```", "").strip()

    def _rebuild_3d_panel(self, g_type=None, skip_clear=False):
        """Construye el panel de control para generación 3D."""
        if not self.ctrl_panel: return
        
        if not skip_clear:
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
                    # SEGURIDAD: Si ya está en la carpeta de compuestos, no mover
                    if "texto/compuesto" in item.replace("\\", "/"):
                        processed.append(item)
                        continue

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
            # SEGURIDAD: Si ya está en la carpeta de compuestos, no mover
            if "texto/compuesto" in content.replace("\\", "/"):
                final_file = content
            else:
                new_p = os.path.join(target_dir, os.path.basename(content))
                if os.path.abspath(content) != os.path.abspath(new_p):
                    try: shutil.move(content, new_p)
                    except: pass
                    content = new_p
                final_file = content
            
            self.media_display.load_media(final_file)
            
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
            
            # 4. Refrescar controladores si estamos en modo compuesto para actualizar listas de ingredientes
            if self.compound_state.get("type") == "Compuesto":
                print("[MediaGenerator] Refrescando listas de ingredientes...")
                if hasattr(self, "workspace") and self.workspace:
                    self.workspace.after(100, lambda: self._update_controllers_logic(self.current_mode))

    def _rebuild_audio_panel(self, a_type=None, a_prov=None, skip_clear=False):
        """Reconstruye el panel de controles para el modo Audio de forma atómica."""
        if not self.ctrl_panel: return
        
        # Sincronizar con el estado persistente
        current_type = a_type or self.audio_state.get("type", "Voces")
        current_prov = a_prov or self.audio_state.get("provider", "ASIMOD - Edge")
        
        # Actualizar memoria interna
        self.audio_state.update({"type": current_type, "provider": current_prov})

        # --- SE HA ELIMINADO EL CLEAR INTERNO ---
        
        # 1. Selector de TIPO (Prioridad 1)
        tipos = ["Voces", "Música", "Efectos"]
        self.ctrl_panel.add_dropdown("Tipo (Audio)", "audio_type", tipos, default=current_type,
                                    callback=lambda v: [self.audio_state.update({"type": v}), 
                                                        self._update_controllers_logic(self.current_mode)])
        
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
                                    callback=lambda v: [self.audio_state.update({"provider": v}), 
                                                        self._update_controllers_logic(self.current_mode)])
                                                        
        # Botón para fijar como Default si es ComfyUI y estamos en Simple
        if current_prov == "ComfyUI" and self.compound_state["type"] == "Simple":
            # Usar la nueva clave unificada 'comfyui_defaults'
            m_config = self.config_service.get("comfyui_defaults", {}).get("Audio", {})
            current_master = m_config.get("workflow")
            btn_text = "📌 Marcar como Default Audio"
            if current_master: btn_text += f" ({current_master})"
            self.ctrl_panel.add_button(btn_text, lambda: self._set_master_default("Audio"))
        
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
        self.image_state["engine"] = engine_name
        self._update_controllers_logic(self.current_mode)

    def _rebuild_image_panel(self, engine_name=None, w_type=None, w_subtype=None, img_count=None, w_flow=None, skip_clear=False):
        """Dibuja el panel de control de imagen de forma atómica y limpia usando estado persistente."""
        if not self.ctrl_panel: return

        # 1. Sincronizar memoria persistente
        if engine_name: self.image_state["engine"] = engine_name
        if w_subtype: self.image_state["subtype"] = w_subtype
        if img_count: self.image_state["count"] = img_count
        if w_flow: self.image_state["workflow"] = w_flow
        
        # Recuperar valores consolidados
        engine_name = self.image_state["engine"]
        w_type = self.compound_state["type"] # Siempre prima el tipo global
        w_subtype = self.image_state["subtype"]
        img_count = self.image_state["count"]
        w_flow = self.image_state["workflow"]

        # --- SE HA ELIMINADO EL CLEAR INTERNO ---

        # Botón para fijar como Default en modo Simple
        if self.compound_state["type"] == "Simple":
            # Usar la nueva clave unificada 'comfyui_defaults'
            m_config = self.config_service.get("comfyui_defaults", {}).get("Imagen", {})
            current_master = m_config.get("workflow")
            btn_text = f"📌 Fijar como Default Imagen"
            if current_master: btn_text += f" ({current_master})"
            self.ctrl_panel.add_button(btn_text, lambda: self._set_master_default("Imagen"))

        # 3. Reconstruir dropdown Motor (siempre presente)
        engines = self.image_service.get_engines_list()
        self.ctrl_panel.add_dropdown("Motor de Imagen", "engine", engines, 
                                    default=engine_name,
                                    callback=lambda v: [self.image_state.update({"engine": v}), 
                                                        self._update_controllers_logic(self.current_mode)])
        
        # Si acabamos de entrar o no hay valores, forzar los predefinidos solicitados
        is_first_build = not w_type and not w_subtype

        if engine_name == "DALL-E 3":
            self.ctrl_panel.add_dropdown("Resolución", "res", ["1024x1024", "1024x1792", "1792x1024"])
        
        elif engine_name == "ComfyUI":
            # Jerarquía de Workflows (Cargar para saber qué hay en disco)
            # [ACTUALIZADO] Ahora la base para imagen es workflows/imagen
            base_w = os.path.join(os.path.dirname(__file__), "workflows", "imagen")
            w_struct = self.image_service.scan_workflows(base_w)
            
            # Usar el tipo global del estado para filtrar workflows
            w_type = self.compound_state["type"]
            
            # Selector Subtipo
            if w_type == "Compuesto":
                # Lista fija solicitada por el usuario
                subtypes = ["Personaje", "Escenario", "Prop", "Sinopsis", "Plano", "Escena", "Secuencia", "Pelicula"]
            else:
                # Para Simple, usamos lo que haya en la carpeta 'simple' (text2img, img2img, etc)
                subtypes = w_struct.get("simple", [])
            
            if subtypes:
                if not w_subtype or w_subtype not in subtypes:
                    w_subtype = "Personaje" if w_type == "Compuesto" else (
                                "text2img" if "text2img" in [s.lower() for s in subtypes] else subtypes[0])
                
                self.ctrl_panel.add_dropdown("Subtipo", "subtype", subtypes, default=w_subtype,
                                            callback=lambda v: [self.image_state.update({"subtype": v}), 
                                                                self._update_controllers_logic(self.current_mode)])
            
            # Selector de archivo Workflow
            self._update_workflow_files(w_type, w_subtype, current_flow=w_flow)
            
            # --- SECCIÓN DE COMPUESTA (Origen, Referencias y Workflows) ---
            if w_type == "Compuesto":
                # Usar el configurador centralizado para evitar colisiones
                self._setup_compound_controllers("Imagen", skip_clear=True)

            # Control de Semilla
            current_seed = self.ctrl_panel.get_value("seed") or "-1"
            self.ctrl_panel.add_input("Semilla (-1 = Aleatorio)", "seed", default=current_seed)

            # Según el subtipo, mostramos resolución o cargadores de imágenes
            if w_subtype and w_subtype.lower() == "img2img":
                self.ctrl_panel.add_dropdown("Nº Imágenes", "img_count", ["1", "2", "3"], 
                                            default=img_count,
                                            callback=lambda v: [self.image_state.update({"count": v}), 
                                                                self._update_controllers_logic(self.current_mode)])
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
        # --- SOLUCIÓN DEFINITIVA: Si es Compuesto, mostrar RECETAS en el selector de Workflow ---
        if w_type == "Compuesto":
            base_w = os.path.abspath(os.path.join(os.path.dirname(__file__), "processes"))
            print(f"[MediaGenerator] Modo Compuesto: Listando Recetas en {base_w}")
        else:
            # [ACTUALIZADO] Ahora Imagen usa su propia subcarpeta 'imagen' para ser coherente con Video/Audio
            w_type_folder = "compuesta" if w_type.lower() == "compuesto" else w_type.lower()
            
            if self.current_mode == "Imagen":
                base_w = os.path.join(os.path.dirname(__file__), "workflows", "imagen", w_type_folder)
            else:
                base_w = os.path.join(os.path.dirname(__file__), "workflows", self.current_mode.lower(), w_type_folder)
                
            if w_subtype:
                base_w = os.path.join(base_w, w_subtype.lower())
        
        # [NUEVO] Si no hay archivos .json en la carpeta base pero hay una subcarpeta 'imagen', entrar en ella
        # (Solo aplica para el modo Simple)
        if w_type != "Compuesto" and os.path.exists(base_w):
            img_path = os.path.join(base_w, "imagen")
            if os.path.exists(img_path):
                # Verificar si hay JSONs en la carpeta base actual
                if not [f for f in os.listdir(base_w) if f.endswith(".json")]:
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
            self.ctrl_panel.add_dropdown("Workflow de Imagen", "workflow", files, default=default_val,
                                        callback=lambda v: [self.image_state.update({"workflow": v}), 
                                                            self._update_controllers_logic(self.current_mode)])
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

    def _rebuild_video_panel(self, v_type=None, v_subtype=None, skip_clear=False):
        """Reconstruye el panel de controles para el modo Video de forma atómica."""
        if not self.ctrl_panel: return
        
        # Sincronizar con el estado persistente
        parent_type = self.compound_state.get("type", "Simple")
        current_type = v_type or self.video_state.get("type", "Simple")
        raw_subtype = v_subtype or self.video_state.get("subtype", "Img2Video")
        current_subtype = raw_subtype if raw_subtype else "Img2Video"
        
        # Memorizar
        self.video_state.update({"type": current_type, "subtype": current_subtype})
        
        # --- SE HA ELIMINADO EL CLEAR INTERNO ---

        # 1. Motor (Solo ComfyUI de momento)
        self.ctrl_panel.add_dropdown("Motor de Video", "engine", ["ComfyUI"])
        
        # 2. Workflow de Video
        # En compuesto Video (G4), el workflow es casi siempre Img+Audio2Video
        sub_folder = current_subtype.replace(" ", "") if parent_type == "Simple" else "Img+Audio2Video"
        wf_folder = os.path.join(os.path.dirname(__file__), "workflows", "video", "simple", sub_folder)
        if not os.path.exists(wf_folder):
            wf_folder = os.path.join(os.path.dirname(__file__), "workflows", "video", "simple")
        
        wf_files = [f for f in os.listdir(wf_folder) if f.endswith(".json")] if os.path.exists(wf_folder) else []
        if wf_files:
            current_wf = self.video_state.get("workflow") or wf_files[0]
            if current_wf not in wf_files: current_wf = wf_files[0]
            
            self.ctrl_panel.add_dropdown("Workflow de Video", "workflow", wf_files, default=current_wf,
                                        callback=lambda v: [self.video_state.update({"workflow": v}),
                                                            self._update_controllers_logic(self.current_mode)])
            
            # Botón para fijar como Default en modo Simple
            if self.compound_state["type"] == "Simple":
                # Usar la nueva clave unificada 'comfyui_defaults'
                m_config = self.config_service.get("comfyui_defaults", {}).get("Video", {})
                current_master = m_config.get("workflow")
                btn_text = "📌 Marcar como Default Video"
                if current_master: btn_text += f" ({current_master})"
                self.ctrl_panel.add_button(btn_text, lambda: self._set_master_default("Video"))
        else:
            self.ctrl_panel.add_label("⚠️ Sin workflows de video detectados.", color="#ffaa00")

        # 3. Inputs dinámicos (Solo para Simple)
        if parent_type == "Simple":
            if "img" in current_subtype.lower():
                self.ctrl_panel.add_file_picker("Imagen de entrada", "input_image")
            
            if current_subtype == "Img+Audio2Video":
                counts = ["1", "2", "3"]
                current_count = self.video_state.get("audio_count", "1")
                self.ctrl_panel.add_dropdown("Nº de Audios", "v_audio_count", counts, default=current_count,
                                            callback=lambda v: [self.video_state.update({"audio_count": v}), 
                                                                self._update_controllers_logic(self.current_mode)])
                
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
        
        if parent_type == "Compuesto":
            # Asegurar que la categoría por defecto sea Personaje si estamos en Video
            if not self.compound_state.get("category"):
                self.compound_state["category"] = "Personaje"
            self._setup_compound_controllers("Video", skip_clear=True)
        else:
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
        
        tk.Label(header, text="CONFIGURACIÓN MAESTRA DE WORKFLOWS", bg=style.get_color("bg_main"), 
                 fg=style.get_color("accent"), font=("Arial", 10, "bold")).pack(side=tk.LEFT, padx=20)
        
        # Contenedor con Scroll para que quepan todos los tipos
        self.canvas = tk.Canvas(self, bg=style.get_color("bg_main"), highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.scroll_frame = tk.Frame(self.canvas, bg=style.get_color("bg_main"))
        
        self.scroll_frame.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.create_window((0, 0), window=self.scroll_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Mapeo de Dropdowns
        self.selectors = {} # {(cat, sub): combobox}
        
        self._build_interface()
        
        # Pie de página
        footer = tk.Frame(self, bg=style.get_color("bg_main"))
        footer.pack(fill=tk.X, pady=(10, 0))
        
        tk.Button(footer, text="Guardar como Predeterminados", bg=style.get_color("accent"), fg="white", 
                  bd=0, padx=20, pady=8, font=("Arial", 9, "bold"),
                  command=self._save).pack(side=tk.RIGHT)

    def _build_interface(self):
        # Definición de la jerarquía que queremos configurar
        structure = {
            "Imagen": ["text2img", "img2img"],
            "Video": ["Img2Video", "Img+Audio2Video"],
            "Audio": ["voices", "music", "sounds"],
            "3D": ["img_to_3d"]
        }
        
        base_path = os.path.join(os.path.dirname(__file__), "workflows")
        
        for cat, subtypes in structure.items():
            # Grupo por Categoría
            group = tk.LabelFrame(self.scroll_frame, text=cat.upper(), bg=self.style.get_color("bg_main"), 
                                  fg=self.style.get_color("accent"), font=("Arial", 9, "bold"), padx=15, pady=10)
            group.pack(fill=tk.X, padx=5, pady=10)
            
            cat_folder = cat.lower()
            cat_path = os.path.join(base_path, cat_folder)
            
            for sub in subtypes:
                row = tk.Frame(group, bg=self.style.get_color("bg_main"), pady=2)
                row.pack(fill=tk.X)
                
                # Nombre del Subtipo
                lbl = tk.Label(row, text=f"{sub}:", width=18, anchor="w", 
                               bg=self.style.get_color("bg_main"), fg="#bbb", font=("Arial", 8))
                lbl.pack(side=tk.LEFT)
                
                # Buscar archivos en disco para este subtipo
                # La estructura ahora es workflows/[cat]/[type]/[sub] pero para config lo simplificamos a workflows/[cat]/simple/[sub] o lo que corresponda
                # Usamos simple como carpeta base para los defaults maestros
                sub_path = os.path.join(cat_path, "simple", sub)
                if not os.path.exists(sub_path):
                    # Fallback si no hay carpeta 'simple' intermedia
                    sub_path = os.path.join(cat_path, sub)
                
                files = []
                if os.path.exists(sub_path):
                    files = [f for f in os.listdir(sub_path) if f.endswith(".json")]
                
                cb = ttk.Combobox(row, values=files, state="readonly", font=("Arial", 8), width=40)
                cb.pack(side=tk.LEFT, fill=tk.X, expand=True)
                
                # Cargar valor actual de la configuración
                current_val = self.defaults.get(cat, {}).get(sub, "")
                if current_val in files:
                    cb.set(current_val)
                elif files:
                    cb.set(files[0])
                
                self.selectors[(cat, sub)] = cb

        # Campo extra para la ruta de output (Root)
        out_frame = tk.LabelFrame(self.scroll_frame, text="SISTEMA", bg=self.style.get_color("bg_main"),
                                 fg="#888", font=("Arial", 9, "bold"), padx=15, pady=10)
        out_frame.pack(fill=tk.X, padx=5, pady=10)
        
        tk.Label(out_frame, text="Ruta de Salida (Output Root):", bg=self.style.get_color("bg_main"), 
                 fg="#bbb", font=("Arial", 8)).pack(anchor="w")
        self.ent_output = tk.Entry(out_frame, bg=self.style.get_color("bg_input"), fg="white", 
                                  bd=0, font=("Arial", 9), insertbackground="white")
        self.ent_output.pack(fill=tk.X, pady=5)
        self.ent_output.insert(0, self.config.get("media_output_root", "output"))

    def _save(self):
        # Recopilar todos los valores de los comboboxes
        new_defaults = {}
        for (cat, sub), cb in self.selectors.items():
            if cat not in new_defaults: new_defaults[cat] = {}
            new_defaults[cat][sub] = cb.get()
        
        # Guardar en Config
        self.config.set("comfyui_defaults", new_defaults)
        
        # Guardar Output Root
        self.config.set("media_output_root", self.ent_output.get())
        
        # Notificar
        from tkinter import messagebox
        messagebox.showinfo("Configuración", "Workflows predeterminados guardados con éxito.")
        if self.on_back: self.on_back()

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

    async def _apply_ping_pong_loop(self, video_path, include_audio=False):
        """Aplica un efecto 'Ping-Pong' al video para que el final coincida con el principio."""
        if not os.path.exists(video_path): return
        
        temp_out = video_path.replace(".mp4", "_loop_temp.mp4")
        # Comando FFmpeg: Revierte el video y lo concatena al original
        # Añadimos -r 30 para forzar frame rate constante (evita parpadeos y fallos de concat)
        cmd = [
            "ffmpeg", "-y", "-i", video_path,
            "-filter_complex", "[0:v]reverse[r];[0:v][r]concat=n=2:v=1[v]",
            "-map", "[v]",
        ]
        
        if include_audio:
            cmd.extend(["-map", "0:a?", "-c:a", "copy"])
        else:
            cmd.append("-an")
            
        cmd.extend([
            "-r", "30", # Frame-rate constante para perfecta sincronización
            "-c:v", "libx264", "-crf", "23", "-pix_fmt", "yuv420p",
            temp_out
        ])
        
        try:
            # Usar shell=True o asegurar que los argumentos son correctos para Windows
            proc = await asyncio.create_subprocess_exec(
                *cmd, 
                stdout=asyncio.subprocess.PIPE, 
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()
            
            if proc.returncode == 0 and os.path.exists(temp_out):
                # En Windows, a veces os.replace falla si el archivo está siendo usado. Intentamos con cuidado.
                try:
                    os.replace(temp_out, video_path)
                except:
                    import shutil
                    shutil.copy2(temp_out, video_path)
                    os.remove(temp_out)
            else:
                error_msg = stderr.decode(errors='replace') if stderr else "Error desconocido en FFmpeg"
                print(f"[MediaGenerator][FFmpeg] Error en ping-pong: {error_msg}")
                if os.path.exists(temp_out): os.remove(temp_out)
        except Exception as e:
            if os.path.exists(temp_out): os.remove(temp_out)
            print(f"[MediaGenerator] Excepción fatal en _apply_ping_pong_loop: {e}")
            raise e

    def _load_existing_piece_metadata(self, piece_id, category):
        """Carga el JSON de metadata desde la carpeta central de output."""
        try:
            central_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "output", "texto", "compuesto"))
            subfolder_name = self._get_compound_path(category).split(os.path.sep)[-1]
            json_path = os.path.join(central_root, subfolder_name, f"{piece_id}.json")
            
            if os.path.exists(json_path):
                with open(json_path, "r", encoding="utf-8") as f:
                    return json.load(f)
        except: pass
        return None

    def _attempt_hub_recovery(self, piece_data):
        """Intenta rescatar una imagen de un personaje ya existente en el repositorio global."""
        try:
            char_name = piece_data.get("titulo", piece_data.get("id"))
            char_folder = char_name
            for char in '<>:"/\\|?*':
                char_folder = char_folder.replace(char, "_")
            
            hub_path = os.path.join("Resources", "Characters", char_folder, "idle.png")
            if os.path.exists(hub_path):
                # Copiar de vuelta a output/imagen para que los adapters la encuentren
                target_name = f"recovered_{piece_data.get('id', 'temp')}.png"
                target_path = os.path.join(self.output_root, "imagen", target_name)
                import shutil
                shutil.copy(hub_path, target_path)
                print(f"[HubRecovery] Imagen rescatada con éxito para '{char_name}': {target_name}")
                return target_name
        except Exception as e:
            print(f"[HubRecovery][Error] Falló el rescate desde el HUB: {e}")
        return None
