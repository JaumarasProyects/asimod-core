import sys
import os
import tkinter as tk

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.services.config_service import ConfigService
from core.services.module_service import ModuleService
from core.services.style_service import StyleService
from core.chat_service import ChatService
from core.api_server import APIServer
from core.services.data_service import DataService
from core.services.character_service import CharacterService
from ui.chat_widget import ChatWidget
from ui.background_frame import BackgroundFrame
from modules.widgets import ImageButton

def center_window(root, width=450, height=750):
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    x = (screen_width // 2) - (width // 2)
    y = (screen_height // 2) - (height // 2)
    root.geometry(f'{width}x{height}+{x}+{y}')

def main():
    root = tk.Tk()
    root.title("ASIMOD")
    
    # Comprobar si el sistema modular está activo
    config_service = ConfigService(filename="settings.json")
    data_service = DataService(config_service=config_service)
    style_service = StyleService(config_service=config_service)
    character_service = CharacterService()
    modular_active = config_service.get("modules_enabled", True)
    
    if modular_active:
        # Ventana más ancha para acomodar sidebar + módulos + chat
        center_window(root, 1000, 750)
    else:
        # Ventana estándar original (chat solo)
        center_window(root, 450, 750)
        
    root.configure(bg=style_service.get_color("bg_main"))

    # Inicializar variables de estilo con valores por defecto
    ghost_bg = style_service.get_color("bg_main")
    has_btn_img = style_service.get_background("button") is not None

    try:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        icon_path = os.path.join(current_dir, "Resources", "logo.ico")
        if os.path.exists(icon_path):
            root.iconbitmap(icon_path)
    except Exception as e:
        print(f"Error cargando icono: {e}")

    chat_engine = ChatService(config_service=config_service)

    # sincronización TTS <-> STT
    chat_engine.voice_service.set_stt_service(chat_engine.stt_service)

    api_port = config_service.get("api_port", 8000)
    
    # Inicializar servicios de módulos y estilo antes que la API para inyección
    module_service = None
    if modular_active:
        module_service = ModuleService(
            chat_service=chat_engine, 
            config_service=config_service, 
            style_service=style_service,
            data_service=data_service
        )
        # Sincronizar el motor de chat con el de módulos para modo AGENTE
        chat_engine.set_module_service(module_service)

    api_server = APIServer(
        chat_service=chat_engine, 
        port=int(api_port),
        module_service=module_service,
        style_service=style_service
    )

    # conectar resultados STT de juego a la cola expuesta por API
    chat_engine.on_stt_result_cb = api_server.push_stt_result

    api_server.run()

    if modular_active:

        # --- LAYOUT PRINCIPAL MODULAR ---
        # Contenedor horizontal
        main_container = tk.Frame(root, bg=style_service.get_color("bg_dark"))
        main_container.pack(fill=tk.BOTH, expand=True)
        
        # Variables de estilo compartidas
        # Ya inicializadas arriba

        # 1. Sidebar de Módulos (Izquierda)
        sidebar = BackgroundFrame(main_container, style_service, "sidebar", width=150)
        sidebar.pack(side=tk.LEFT, fill=tk.Y)
        sidebar.pack_propagate(False)

        # 2. Chat Widget (Derecha) - LO PONEMOS ANTES DEL CONTENIDO PARA QUE SEA FIJO
        chat_frame = BackgroundFrame(main_container, style_service, "chat", width=350)
        chat_frame.pack(side=tk.RIGHT, fill=tk.BOTH)
        chat_frame.pack_propagate(False)

        # 3. Área de Contenido del Módulo (Centro)
        # Al tener expand=True, ocupará todo el espacio restante entre la sidebar y el chat
        content_area = BackgroundFrame(main_container, style_service, "center")
        content_area.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # 4. Barra de restauración de Chat (Derecha - Oculta por defecto)
        chat_collapsed_bar = tk.Frame(main_container, bg=style_service.get_color("bg_header"), width=40)
        
        def toggle_chat(visible):
            if visible:
                chat_collapsed_bar.pack_forget()
                # Re-empaquetar chat_frame (asegurando side RIGHT)
                chat_frame.pack(side=tk.RIGHT, fill=tk.BOTH)
            else:
                chat_frame.pack_forget()
                chat_collapsed_bar.pack(side=tk.RIGHT, fill=tk.Y)
                chat_collapsed_bar.pack_propagate(False)

        tk.Button(chat_collapsed_bar, text="◀", bg=style_service.get_color("bg_header"), 
                  fg=style_service.get_color("accent"), bd=0, font=("Arial", 12), cursor="hand2",
                  command=lambda: toggle_chat(True)).pack(fill=tk.X, pady=10)

        chat_ui = ChatWidget(chat_frame, chat_engine=chat_engine, config_service=config_service, 
                             style_service=style_service, character_service=character_service,
                             on_collapse_cmd=lambda: toggle_chat(False))
        chat_ui.pack(fill=tk.BOTH, expand=True)

        # --- Lógica de navegación de módulos ---
        sidebar_expanded = True
        sidebar_btns = []

        def toggle_sidebar():
            nonlocal sidebar_expanded
            sidebar_expanded = not sidebar_expanded
            
            new_width = 150 if sidebar_expanded else 60
            sidebar.config(width=new_width)
            
            # Actualizar botones
            for btn, mod_icon, mod_name, mod_id in sidebar_btns:
                if sidebar_expanded:
                    btn.config(text=f" {mod_icon}  {mod_name}", anchor="center", padx=10)
                else:
                    btn.config(text=mod_icon, anchor="center", padx=0)

        # Botón Toggle superior con imagen si está disponible
        if has_btn_img:
            toggle_btn = ImageButton(sidebar, text=" ☰ ", style=style_service, 
                                     callback=toggle_sidebar, 
                                     font=("Arial", 12, "bold"), pady=10)
        else:
            toggle_btn = tk.Button(sidebar, text="☰", bg=ghost_bg, 
                                   fg=style_service.get_color("accent") if style_service else "#4EC9B0",
                                   bd=0, font=("Arial", 12, "bold"), cursor="hand2", pady=10,
                                   command=toggle_sidebar)
        toggle_btn.pack(fill=tk.X)
        
        tk.Frame(sidebar, bg="#333", height=1).pack(fill=tk.X, pady=(0, 5))

        def update_module_ui(module_id):
            """Actualiza únicamente la interfaz de usuario (área central)."""
            # Limpiar área de contenido
            for widget in content_area.winfo_children():
                widget.destroy()
            
            module = module_service.loaded_modules.get(module_id)

            if module:
                # Envolver el módulo en un cuadro (box) con imagen si el tema lo permite
                has_box = style_service.get_background("module_box") is not None
                has_center_bg = style_service.get_background("center") is not None
                outer_pad = 30 if has_center_bg else 0
                
                if has_box:
                    # Contenedor con textura boxMain.png
                    box_frame = BackgroundFrame(content_area, style_service, "module_box")
                    box_frame.pack(fill=tk.BOTH, expand=True, padx=outer_pad, pady=outer_pad)
                    
                    # El widget del módulo se empaqueta dentro del cuadro
                    m_widget = module.get_widget(box_frame)
                    m_widget.pack(fill=tk.BOTH, expand=True)
                    
                    # Intentar que el fondo del módulo no tape la textura (si es un tk.Frame)
                    try:
                        m_widget.config(bg="") # Intentar transparencia si es posible o simplemente dejarlo
                    except: pass
                else:
                    m_widget = module.get_widget(content_area)
                    m_widget.pack(fill=tk.BOTH, expand=True, padx=outer_pad, pady=outer_pad)
            else:
                welcome = tk.Label(content_area, text="ASIMOD MODULAR", fg=style_service.get_color("text_dim"), 
                                   bg=style_service.get_color("bg_main"), font=("Arial", 24, "bold"))
                welcome.pack(expand=True)

        def select_module(module_id):
            """Inicia la activación de un módulo en el servicio y actualiza sidebar."""
            module_service.activate_module(module_id)
            
            # Actualizar estado visual de los botones de la sidebar
            for btn_tuple in sidebar_btns:
                btn_obj = btn_tuple[0]
                mod_id = btn_tuple[3] # Necesitamos guardar el id en la tupla
                is_active = (mod_id == module_id)
                
                if isinstance(btn_obj, ImageButton):
                    btn_obj.set_active(is_active)
                else:
                    btn_obj.config(bg="#222" if is_active else ghost_bg)

        # Llenar sidebar con botones
        
        for mod in module_service.get_modules():
            if has_btn_img:
                btn = ImageButton(sidebar, text=f" {mod.icon}  {mod.name}", 
                                  style=style_service, 
                                  callback=lambda m=mod.id: select_module(m),
                                  font=("Segoe UI Emoji", 10, "bold"), anchor="center", padx=10, pady=15)
            else:
                # Botón modular - Estilo Ghost original
                btn = tk.Button(sidebar, text=f" {mod.icon}  {mod.name}", 
                                bg=ghost_bg, 
                                fg=style_service.get_color("text_main"), bd=0, 
                                command=lambda m=mod.id: select_module(m),
                                font=("Segoe UI Emoji", 10, "bold"), cursor="hand2", 
                                anchor="center", padx=10, pady=15,
                                activebackground="#222")
            
            btn.pack(fill=tk.X, pady=1)
            sidebar_btns.append((btn, mod.icon, mod.name, mod.id))
            
            # Tooltip simple
            btn.bind("<Enter>", lambda e, n=mod.name: root.title(f"ASIMOD - {n}"))
            btn.bind("<Leave>", lambda e: root.title("ASIMOD"))

        # Configurar callback de activación (ES EL ÚNICO que actualiza la UI)
        module_service.on_module_activated = update_module_ui

        # Mostrar bienvenida por defecto
        update_module_ui(None)
    else:
        # --- LAYOUT ESTÁNDAR (SOLO CHAT) ---
        chat_ui = ChatWidget(root, chat_engine=chat_engine, config_service=config_service, 
                             style_service=style_service, character_service=character_service)
        chat_ui.pack(fill=tk.BOTH, expand=True)

    root.mainloop()

if __name__ == "__main__":
    import traceback
    try:
        main()
    except Exception as e:
        print("\n" + "="*50)
        print("❗ ERROR CRÍTICO AL INICIAR/EJECUTAR LA APP:")
        traceback.print_exc()
        print("="*50 + "\n")
        input("Presiona Enter para cerrar...")