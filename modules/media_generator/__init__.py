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
        self.name = "Media Generator"
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
        
        # Ruta de Output Configurable
        default_out = os.path.abspath(os.path.join(os.path.dirname(__file__), "output"))
        self.output_root = self.config_service.get("comfyui_output_path", default_out)
        self.gallery_path = self.output_root # Ruta actual en la galería
        
        # Asegurar carpetas base
        for sub in ["texto", "imagen", "audio", "video", "3d"]:
            os.makedirs(os.path.join(self.output_root, sub), exist_ok=True)
            
        # Estado de modelos LLM para letras
        self.llm_models = []
        self._fetch_llm_models()

    def _on_llm_provider_change(self, provider_name):
        """Cambia el proveedor LLM global y refresca la lista de modelos."""
        print(f"[MediaGenerator] Cambiando proveedor LLM a: {provider_name}")
        self.chat_service.switch_provider(provider_name)
        self.config_service.set("last_provider", provider_name)
        
        # Limpiar modelos actuales y disparar carga en segundo plano
        self.llm_models = []
        self._fetch_llm_models()
        
        # Refrescar UI inmediatamente para mostrar estado 'Cargando...'
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

    def _update_controllers_logic(self, mode):
        """Lógica interna para actualizar el ControllerPanel."""
        if not self.ctrl_panel:
            return
            
        self.ctrl_panel.clear()
        
        if mode == "Texto":
            providers = self.chat_service.get_providers_list()
            self.ctrl_panel.add_dropdown("Proveedor LLM", "provider", 
                                        providers, 
                                        callback=self._on_provider_change)
            if providers:
                self._on_provider_change(providers[0])
            else:
                self.ctrl_panel.add_dropdown("Modelo", "model", ["Cargando..."])
                
        elif mode == "Imagen":
            engines = self.image_service.get_engines_list()
            self.ctrl_panel.add_dropdown("Motor de Imagen", "engine", 
                                        engines, 
                                        callback=self._on_image_engine_change)
            
            # Sub-Selectores para ComfyUI o DALL-E
            self._on_image_engine_change(engines[0] if engines else "DALL-E 3")
        elif mode == "Audio":
            self._rebuild_audio_panel()
        elif mode == "Video":
            self._rebuild_video_panel()
        elif mode == "3D":
            self._rebuild_3d_panel()
        else:
            self.ctrl_panel.add_dropdown("Proveedor", "gen_provider", ["Default Engine"])

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

        # 4. Panel de Controladores (ABAJO - Reservar primero)
        if self.show_controllers:
            self.ctrl_panel = ControllerPanel(main_frame, style=self.style)
            self.ctrl_panel.pack(fill=tk.X, side=tk.BOTTOM, padx=20, pady=(10, 20))
            
            # Dibujar prompt y botones dentro del panel (abajo)
            self.render_top_actions(self.ctrl_panel.actions_container)
            self.setup_controllers(self.ctrl_panel)

        # Una vez reservado el footer, empaquetamos el área de resultados para que llene el RESTO
        self.separator.pack(fill=tk.X, side=tk.BOTTOM)
        self.sub_widget_area.pack(fill=tk.BOTH, expand=True, padx=20, pady=(10, 0), side=tk.TOP)

        # Render inicial del workspace
        self.render_workspace(self.workspace)
        return main_frame

        # Render inicial del workspace
        self.render_workspace(self.workspace)
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

        # Caja de Prompt
        tk.Label(frame, text="Prompt / Instrucciones:", fg=self.style.get_color("text_dim"), bg=self.style.get_color("bg_main"), 
                 font=("Arial", 9)).pack(anchor="w")
        
        self.prompt_text = tk.Text(frame, bg=self.style.get_color("bg_dark"), fg=self.style.get_color("text_main"), bd=0, 
                                   font=("Arial", 10), height=3, padx=10, pady=10,
                                   insertbackground=self.style.get_color("text_main"))
        self.prompt_text.pack(fill=tk.X, pady=(5, 10))
        
        placeholder = f"Escribe aquí lo que quieres generar para {self.current_mode}..."
        self.prompt_text.insert("1.0", placeholder)
        self.prompt_text.config(fg="#888")

        def on_focus_in(event):
            if self.prompt_text.get("1.0", tk.END).strip() == placeholder:
                self.prompt_text.delete("1.0", tk.END)
                self.prompt_text.config(fg=self.style.get_color("text_main"))

        def on_focus_out(event):
            if not self.prompt_text.get("1.0", tk.END).strip():
                self.prompt_text.insert("1.0", placeholder)
                self.prompt_text.config(fg="#888")

        self.prompt_text.bind("<FocusIn>", on_focus_in)
        self.prompt_text.bind("<FocusOut>", on_focus_out)

        # Botonera
        actions_frame = tk.Frame(frame, bg=self.style.get_color("bg_main"))
        actions_frame.pack(fill=tk.X)

        btn_generate = tk.Button(actions_frame, text=f"✨ Generar", 
                                bg=self.style.get_color("accent"), fg=self.style.get_color("btn_fg"), bd=0, padx=20, pady=8,
                                font=("Arial", 10, "bold"), cursor="hand2", command=self.handle_generate)
        btn_generate.pack(side=tk.LEFT, padx=(0, 10))

        btn_clear = tk.Button(actions_frame, text="🗑️ Limpiar", 
                             bg=self.style.get_color("btn_bg"), fg=self.style.get_color("text_dim"), bd=0, padx=15, pady=8,
                             font=("Arial", 9), cursor="hand2", command=self._clear_all)
        btn_clear.pack(side=tk.LEFT)

        btn_clear.pack(side=tk.LEFT)

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
        
        # Sincronizar parámetros si vienen
        if params and self.ctrl_panel:
            for k, v in params.items():
                self.ctrl_panel.set_value(k, v)

        # Ejecutar la lógica de generación y esperar el resultado
        try:
            result = await self._perform_generation(prompt, mode)
            
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
                    "url": f"/output/{mode.lower()}/{filename}",
                    "filename": filename
                }
            else:
                # Es un resultado de texto
                if hasattr(self, "workspace") and self.workspace:
                    self.workspace.after(0, lambda: self._show_result(result))
                return {"status": "success", "type": "text", "content": result}
                
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def handle_generate_manual(self, prompt):
        """Versión de compatibilidad para disparar hilos desde la UI desktop."""
        def run():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            res = loop.run_until_complete(self._perform_generation(prompt, self.current_mode))
            self._cache_result_and_show(res, self.current_mode)
            loop.close()
            
        threading.Thread(target=run, daemon=True).start()

    async def _perform_generation(self, prompt, mode):
        """Lógica centralizada y awaitable de generación."""
        if mode == "Imagen":
            # Usar valores del panel si existen, si no, usar parámetros por defecto o de la web
            engine_name = self.ctrl_panel.get_value("engine") if (hasattr(self, 'ctrl_panel') and self.ctrl_panel) else "DALL-E 3"
            adapter = self.image_service.get_adapter(engine_name)
            if not adapter: raise Exception(f"Adaptador {engine_name} no encontrado")
            
            res = self.ctrl_panel.get_value("res") if (hasattr(self, 'ctrl_panel') and self.ctrl_panel) else "1024x1024"
            
            # Obtener ancho y alto del nuevo control de resolución
            preset = self.ctrl_panel.get_value("resolution")
            w, h = 1024, 1024 # Default
            
            if preset == "Personalizado":
                w = self.ctrl_panel.get_value("resolution_w")
                h = self.ctrl_panel.get_value("resolution_h")
            elif preset:
                # Extraer de strings como "Cuadrada Grande (1024x1024)"
                import re
                match = re.search(r"\((\d+)x(\d+)\)", preset)
                if match:
                    w, h = match.groups()

            # Cargar workflow si es ComfyUI
            workflow_data = None
            if engine_name == "ComfyUI" and self.ctrl_panel:
                w_file = self.ctrl_panel.get_value("workflow")
                if w_file:
                    # Re-calcular ruta del archivo
                    w_type = self.ctrl_panel.get_value("type")
                    w_subtype = self.ctrl_panel.get_value("subtype")
                    
                    base_w = os.path.join(os.path.dirname(__file__), "workflows", w_type.lower())
                    if w_subtype:
                        base_w = os.path.join(base_w, w_subtype.lower())
                    
                    full_path = os.path.join(base_w, w_file)
                    if os.path.exists(full_path):
                        try:
                            with open(full_path, "r", encoding="utf-8") as f:
                                workflow_data = json.load(f)
                        except Exception as e:
                            print(f"[MediaGenerator] Error cargando workflow JSON: {e}")

            # Imagen(es) de entrada para Img2Img
            input_images = []
            img_count = self.ctrl_panel.get_value("img_count") or "1"
            try:
                for i in range(1, int(img_count) + 1):
                    path = self.ctrl_panel.get_value(f"input_image_{i}")
                    if path and path != "Ninguno":
                        input_images.append(path)
            except: pass

            neg_prompt = self.ctrl_panel.get_value("neg_prompt") if (hasattr(self, 'ctrl_panel') and self.ctrl_panel) else ""
            return await adapter.generate_image(prompt, resolution=res, workflow_json=workflow_data, width=w, height=h, input_images=input_images, negative_prompt=neg_prompt)
        
        elif mode == "Audio":
            tipo = self.ctrl_panel.get_value("audio_type")
            prov = self.ctrl_panel.get_value("audio_provider")
            
            if prov == "ComfyUI":
                w_file = self.ctrl_panel.get_value("audio_workflow")
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
                
                # Capturar parámetros extra para música
                extra_params = {}
                if tipo == "Música":
                    # Sincronizar duration y seconds
                    dur = self.ctrl_panel.get_value("audio_duration")
                    extra_params["bpm"] = self.ctrl_panel.get_value("audio_bpm")
                    extra_params["keyscale"] = self.ctrl_panel.get_value("audio_key")
                    extra_params["duration"] = dur
                    extra_params["seconds"] = dur # Algunos workflows usan 'seconds' en lugar de 'duration'
                    extra_params["lyrics"] = self.ctrl_panel.get_value("audio_lyrics")
                
                return await adapter.generate_image(prompt, workflow_json=workflow_data, **extra_params)
                
            elif "ASIMOD" in prov:
                # Usar VoiceService del núcleo
                voice_id = self.ctrl_panel.get_value("audio_voice")
                prov_key = "Edge TTS" if "Edge" in prov else "Local TTS"
                
                print(f"[MediaGenerator] Generando voz core con {prov_key} (ID: {voice_id})")
                return await self.chat_service.voice_service.generate_audio_only(
                    prompt, 
                    voice_id=voice_id, 
                    voice_provider=prov_key
                )
            elif prov == "ElevenLabs":
                # Placeholder para ElevenLabs (requiere adaptador futuro)
                return "Error: Adaptador ElevenLabs no configurado. Pronto disponible."
                
            elif prov == "Suno":
                # Placeholder para Suno (requiere adaptador futuro)
                return "Error: Adaptador Suno no configurado. Pronto disponible."
                
        elif mode == "3D":
             g_type = self.ctrl_panel.get_value("3d_type")
             prov = self.ctrl_panel.get_value("3d_provider")
             
             if prov == "ComfyUI":
                 w_file = self.ctrl_panel.get_value("3d_workflow")
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
                 
                 # Inputs
                 input_images = []
                 if g_type == "Imagen a 3D":
                     img_path = self.ctrl_panel.get_value("3d_input_image")
                     if img_path and img_path != "Ninguno":
                         input_images.append(img_path)
                 
                 return await adapter.generate_image(prompt, workflow_json=workflow_data, input_images=input_images)
             else:
                 return f"Error: Proveedor {prov} no disponible manualmente."

        elif mode == "Video":
            v_type = self.ctrl_panel.get_value("video_type")
            v_subtype = self.ctrl_panel.get_value("video_subtype")
            w_file = self.ctrl_panel.get_value("video_workflow")
            
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
                img = self.ctrl_panel.get_value("input_image")
                if img and img != "Ninguno": input_files.append(img)
                
                count = int(self.ctrl_panel.get_value("v_audio_count") or "1")
                for i in range(1, count + 1):
                    a_path = self.ctrl_panel.get_value(f"input_audio_{i}")
                    if a_path and a_path != "Ninguno":
                        input_files.append(a_path)
                
                # Inyección quirúrgica en el workflow para audios extra
                if workflow_data and count > 1:
                    multitalk_node = workflow_data.get("18")
                    if multitalk_node and "19" in workflow_data:
                        for i in range(2, count + 1):
                            new_id = str(100 + i)
                            # Clonar nodo de carga 19
                            new_node = json.loads(json.dumps(workflow_data["19"]))
                            workflow_data[new_id] = new_node
                            # Vincular en MultiTalk
                            multitalk_node["inputs"][f"audio_{i}"] = [new_id, 0]
                            print(f"[MediaGenerator] Inyectando nodo extra de audio {i} (ID: {new_id})")
            else:
                for k in ["input_image", "input_audio", "input_video"]:
                    val = self.ctrl_panel.get_value(k)
                    if val and val != "Ninguno":
                        input_files.append(val)
            
            # Resolución de Video
            preset = self.ctrl_panel.get_value("video_resolution")
            w, h = 640, 640 
            if preset == "Personalizado":
                w = self.ctrl_panel.get_value("video_resolution_w")
                h = self.ctrl_panel.get_value("video_resolution_h")
            elif preset:
                import re
                match = re.search(r"\((\d+)x(\d+)\)", preset)
                if match: w, h = match.groups()
            
            dur = self.ctrl_panel.get_value("video_duration") or 5
            neg_prompt = self.ctrl_panel.get_value("neg_prompt")
            
            print(f"[MediaGenerator] Generando video ({w}x{h}, {dur}s) con ComfyUI. Inputs: {len(input_files)}")
            adapter = self.image_service.get_adapter("ComfyUI")
            return await adapter.generate_image(prompt, 
                                                workflow_json=workflow_data, 
                                                input_images=input_files, 
                                                negative_prompt=neg_prompt,
                                                width=w, height=h, 
                                                duration=dur)
        
        elif mode == "3D":
            g_type = self.ctrl_panel.get_value("3d_type")
            g_provider = self.ctrl_panel.get_value("3d_provider")
            w_file = self.ctrl_panel.get_value("3d_workflow")
            
            folder_map = {"Texto a 3D": "text_to_3d", "Imagen a 3D": "img_to_3d"}
            sub = folder_map.get(g_type, "text_to_3d")
            
            if not w_file:
                return "Error: No se ha seleccionado ningún workflow 3D."
            
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
            img_input = self.ctrl_panel.get_value("3d_input_image")
            if img_input and img_input != "Ninguno":
                input_files.append(img_input)
            
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
            
            # Sincronizar proveedor si se especifica
            if provider:
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
                if txt_ctrl:
                    self.workspace.after(0, lambda: txt_ctrl.delete("1.0", tk.END))
                    self.workspace.after(0, lambda: txt_ctrl.insert("1.0", "✨ Componiendo letras... por favor espera..."))
                
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
                print(f"[MediaGenerator] Error en generación de letras: {e}")
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
            
        if not w_flow:
            w_flow = self.ctrl_panel.get_value("workflow")

        # 2. Limpiar panel por completo
        self.ctrl_panel.clear()

        # 3. Reconstruir dropdown Motor (siempre presente)
        engines = self.image_service.get_engines_list()
        self.ctrl_panel.add_dropdown("Motor de Imagen", "engine", engines, 
                                    default=engine_name,
                                    callback=lambda v: self._rebuild_image_panel(engine_name=v))

        if engine_name == "DALL-E 3":
            self.ctrl_panel.add_dropdown("Resolución", "res", ["1024x1024", "1024x1792", "1792x1024"])
        
        elif engine_name == "ComfyUI":
            # Botones de lanzamiento y estado ya no se añaden aquí, sino en el panel inferior
            
            # Jerarquía de Workflows
            base_w = os.path.join(os.path.dirname(__file__), "workflows")
            w_struct = self.image_service.scan_workflows(base_w)
            types = [t for t in w_struct.keys() if t.lower() not in ["audio", "video"]]
            
            if not w_type and types: w_type = types[0]
            
            # Selector Tipo (Simple/Compuesta)
            self.ctrl_panel.add_dropdown("Tipo", "type", types, default=w_type,
                                        callback=lambda v: self._rebuild_image_panel(w_type=v, w_subtype=None))
            
            # Selector Subtipo (text2img/img2img/etc)
            subtypes = w_struct.get(w_type, [])
            if subtypes:
                if not w_subtype: w_subtype = subtypes[0]
                self.ctrl_panel.add_dropdown("Subtipo", "subtype", subtypes, default=w_subtype,
                                            callback=lambda v: self._rebuild_image_panel(w_subtype=v, w_flow=None))
            
            # Selector de archivo Workflow (Movido aquí para que siempre se vea primero)
            self._update_workflow_files(w_type, w_subtype, current_flow=w_flow)

            # Según el subtipo, mostramos resolución o cargadores de imágenes
            if w_subtype and w_subtype.lower() == "img2img":
                self.ctrl_panel.add_dropdown("Nº Imágenes", "img_count", ["1", "2", "3"], 
                                            default=img_count,
                                            callback=lambda v: self._rebuild_image_panel(img_count=v))
                for i in range(1, int(img_count) + 1):
                    self.ctrl_panel.add_file_picker(f"Imagen {i}", f"input_image_{i}")
            else:
                res_options = [
                    "Cuadrada Pequeña (512x512)", "Cuadrada Grande (1024x1024)",
                    "Apaisada Pequeña (768x512)", "Apaisada Grande (1280x720)",
                    "Vertical Pequeña (512x768)", "Vertical Grande (720x1280)",
                    "Personalizado"
                ]
                self.ctrl_panel.add_resolution_control("Resolución", "resolution", res_options, 
                                                       default="Cuadrada Grande (1024x1024)")
            
            # 4. Campo de Prompt Negativo (para control avanzado)
            self.ctrl_panel.add_input("Prompt Negativo", "neg_prompt", 
                                     default="low quality, blurry, static, text, watermark, deformed, bad proportions")
            
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
                    self.lbl_comfy_status.after(0, lambda: self.lbl_comfy_status.config(text=f"Estado: {self.comfy_status}", fg=color))
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
            if default_val:
                self.ctrl_panel.controls["workflow"].set(default_val)

    def _on_provider_change(self, provider_name):
        self.chat_service.switch_provider(provider_name)
        def fetch_models():
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                models = loop.run_until_complete(self.chat_service.get_available_models())
                loop.close()
                self.workspace.after(0, lambda: self._update_models_dropdown(models))
            except Exception as e:
                print(f"[MediaGenerator] Error fetching models: {e}")
        threading.Thread(target=fetch_models, daemon=True).start()

    def _update_models_dropdown(self, models):
        if self.ctrl_panel:
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
                                               default="Cuadrada (640x640)")
        
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
        return {"generador": "show_main", "crear imagen": "gen_image", "generar texto": "gen_text"}

    def on_voice_command(self, action_slug, text):
        if action_slug == "gen_image": self.on_menu_change("Imagen")
        elif action_slug == "gen_text": self.on_menu_change("Texto")

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
