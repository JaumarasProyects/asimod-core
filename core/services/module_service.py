import os
import sys
import importlib.util
import inspect
from typing import Optional
from core.base_module import BaseModule

class ModuleService:
    """
    Gestor de módulos de ASIMOD. Escanea, carga y gestiona el ciclo de vida de los plugins.
    """
    def __init__(self, chat_service, config_service, style_service, data_service=None):
        self.chat_service = chat_service
        self.config = config_service
        self.style = style_service
        self.data_service = data_service
        self.modules_dir = self.config.get("modules_path", "modules")
        self.loaded_modules = {}
        self.active_module = None
        self.on_module_activated = None  # Callback para notificar a la UI
        
        # Añadir la carpeta de módulos al path para que los módulos puedan importar widgets
        abs_modules_path = os.path.abspath(self.modules_dir)
        if abs_modules_path not in sys.path:
            sys.path.append(abs_modules_path)
        
        # Conectar con el servicio de voz
        self.chat_service.stt_service.set_voice_command_callback(self.handle_voice_command)
        
        # Asegurar que la carpeta existe
        if not os.path.exists(self.modules_dir):
            os.makedirs(self.modules_dir)
            
        self.load_modules()

    def load_modules(self):
        """Escanea la carpeta de módulos e importa dinámicamente las clases que heredan de BaseModule."""
        self.loaded_modules = {}
        if not os.path.exists(self.modules_dir):
            return

        for entry in os.listdir(self.modules_dir):
            if entry == "widgets" or entry.startswith("__"): # Reservado o caché
                continue
                
            full_path = os.path.join(self.modules_dir, entry)
            # Buscamos carpetas con __init__.py o archivos .py
            module_file = None
            if os.path.isdir(full_path):
                init_path = os.path.join(full_path, "__init__.py")
                if os.path.exists(init_path):
                    module_file = init_path
            elif entry.endswith(".py") and entry != "__init__.py":
                module_file = full_path

            if module_file:
                try:
                    module_name = entry.replace(".py", "")
                    spec = importlib.util.spec_from_file_location(module_name, module_file)
                    mod = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(mod)

                    # Buscar clases que hereden de BaseModule DEFINIDAS en este módulo
                    for name, obj in inspect.getmembers(mod):
                        if (inspect.isclass(obj) and 
                            issubclass(obj, BaseModule) and 
                            obj is not BaseModule and
                            obj.__module__ == mod.__name__): # <-- Solo clases locales
                            
                            instance = obj(self.chat_service, self.config, self.style, data_service=self.data_service)
                            self.loaded_modules[instance.id] = instance
                            print(f"[ModuleService] Módulo cargado: {instance.name} ({instance.id})")

                except Exception as e:
                    print(f"[ModuleService] Error cargando {entry}: {e}")
        
        # Registrar comandos base UNA SOLA VEZ al final del escaneo
        self._register_base_commands()

    def get_modules(self):
        """Devuelve la lista de módulos ordenados por prioridad (Home primero)."""
        all_mods = list(self.loaded_modules.values())
        
        # Prioridad personalizada: home e id de los modulos mas importantes
        priority = ["home", "agenda", "media_generator"]
        
        def sort_key(mod):
            try:
                # Si está en la lista de prioridad, su índice es el peso (0, 1, 2...)
                # Si no, un peso alto (99) + nombre alfabético
                if mod.id in priority:
                    return (priority.index(mod.id), mod.name)
                return (99, mod.name)
            except:
                return (100, mod.name)

        return sorted(all_mods, key=sort_key)

    def _register_base_commands(self):
        """Registra los nombres de los módulos como comandos globales de apertura."""
        base_cmds = {}
        for mid, mod in self.loaded_modules.items():
            trigger = mod.name.lower()
            base_cmds[trigger] = f"open_{mid}"
            base_cmds[f"abrir {trigger}"] = f"open_{mid}"
            base_cmds[f"activa el {trigger}"] = f"open_{mid}"
            base_cmds[f"activar {trigger}"] = f"open_{mid}"
            base_cmds[f"panel de {trigger}"] = f"open_{mid}"
        
        self.chat_service.stt_service.set_base_module_commands(base_cmds)

    def resync_module_commands(self):
        """Fuerza la actualización de los comandos del módulo activo en el servicio de voz."""
        if self.active_module:
            commands = self.active_module.get_voice_commands()
            self.chat_service.stt_service.set_contextual_commands(commands)
            print(f"[ModuleService] Comandos de {self.active_module.name} re-sincronizados.")

    def activate_module(self, module_id: str):
        """Activa un módulo y actualiza los comandos de voz contextuales."""
        # Protección contra recursión: si ya está activo el ID solicitado, no hacer nada
        if self.active_module and self.active_module.id == module_id:
            return self.active_module

        if self.active_module:
            self.active_module.on_deactivate()
            self.chat_service.stt_service.clear_contextual_commands()

        if module_id in self.loaded_modules:
            self.active_module = self.loaded_modules[module_id]
            self.active_module.on_activate()
            
            # Inyectar comandos de voz en el STTService
            commands = self.active_module.get_voice_commands()
            if commands:
                self.chat_service.stt_service.set_contextual_commands(commands)
            
            print(f"[ModuleService] Módulo activado: {self.active_module.name}")
            
            # Notificar a la UI si hay un callback registrado
            if self.on_module_activated:
                self.on_module_activated(module_id)

            return self.active_module
        
        self.active_module = None
        return None

    def deactivate_active_module(self):
        if self.active_module:
            self.active_module.on_deactivate()
            self.chat_service.stt_service.clear_contextual_commands()
            self.active_module = None
            print("[ModuleService] Módulo desactivado.")

    def handle_voice_command(self, action_slug: str, text: str):
        """Despacha el comando de voz al módulo activo o maneja la apertura de módulos."""
        if not action_slug:
            # Si no hay comando directo, lo pasamos al módulo activo por si está en modo espera (prompt/galería)
            if self.active_module:
                self.active_module.on_voice_command(None, text)
            return

        # 1. Comprobar si es un comando de apertura de módulo
        if action_slug.startswith("open_"):
            module_id = action_slug.replace("open_", "")
            print(f"[ModuleService] Petición de apertura recibida por voz: {module_id}")
            self.activate_module(module_id)
            return

        # 2. Despachar al módulo activo para comandos internos del módulo
        if self.active_module:
            self.active_module.on_voice_command(action_slug, text)

    def get_module(self, module_id: str) -> Optional[BaseModule]:
        """Busca y retorna un módulo por su ID."""
        return self.loaded_modules.get(module_id)
    def get_agent_tools_context(self) -> str:
        """
        Retorna un texto describiendo las herramientas (comandos) disponibles
        en el módulo activo y los comandos globales para el prompt del Agente.
        """
        tools_desc = "HERRAMIENTAS DISPONIBLES (COMMANDS):\n"
        
        # 1. Comandos globales (Apertura de módulos)
        tools_desc += "- GLOBAL: Puedes abrir módulos usando los comandos: "
        modules = self.get_modules()
        tools_desc += ", ".join([f"'abrir {mod.name.lower()}' (id: open_{mod.id})" for mod in modules])
        tools_desc += "\n"

        # 2. Comandos del módulo activo
        if self.active_module:
            tools_desc += f"- MÓDULO ACTUAL ({self.active_module.name}):\n"
            cmds = self.active_module.get_voice_commands()
            for trigger, action in cmds.items():
                tools_desc += f"  * '{trigger}' -> ejecuta acción: {action}\n"
        else:
            tools_desc += "- No hay un módulo específico activo actualmente.\n"

        tools_desc += "\nINSTRUCCIONES CRÍTICAS DE RESPUESTA:\n"
        tools_desc += "1. Responde SIEMPRE en ESPAÑOL.\n"
        tools_desc += "2. Genera ÚNICAMENTE un bloque JSON. NO añadas introducciones, narraciones ni explicaciones fuera del JSON.\n"
        tools_desc += "3. NO narres tus pasos (ej: evita 'Paso 1', 'I need to...', 'Step 2') en el campo 'response'. El campo 'response' debe ser una respuesta natural y corta para el usuario.\n"
        tools_desc += "4. Usa el campo 'thought' para tu razonamiento interno en español.\n"
        tools_desc += "5. Para la herramienta 'instruction', pon el texto del prompt deseado en el campo 'params'.\n"
        tools_desc += "6. Si el usuario pide crear/generar algo tras poner el prompt, usa la acción 'generate'.\n"
        tools_desc += "7. Formato JSON estricto:\n"
        tools_desc += '{\n  "thought": "tu plan interno en español",\n  "response": "tu mensaje amigable al usuario en español",\n  "action": "slug_de_la_accion_o_null",\n  "params": "texto_del_prompt_o_parametro_o_null"\n}\n'
        tools_desc += "IMPORTANTE: Si no hay una acción clara, usa 'action': null.\n"
        
        return tools_desc
