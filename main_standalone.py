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
from ui.chat_widget import ChatWidget

def center_window(root, width=450, height=750):
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    x = (screen_width // 2) - (width // 2)
    y = (screen_height // 2) - (height // 2)
    root.geometry(f'{width}x{height}+{x}+{y}')

def main():
    root = tk.Tk()
    root.title("ASIMOD Core")
    
    # Comprobar si el sistema modular está activo
    config_service = ConfigService(filename="settings.json")
    data_service = DataService(config_service=config_service)
    style_service = StyleService(config_service=config_service)
    modular_active = config_service.get("modules_enabled", True)
    
    if modular_active:
        # Ventana más ancha para acomodar sidebar + módulos + chat
        center_window(root, 1000, 750)
    else:
        # Ventana estándar original (chat solo)
        center_window(root, 450, 750)
        
    root.configure(bg=style_service.get_color("bg_main"))

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

        # 1. Sidebar de Módulos (Izquierda)
        sidebar = tk.Frame(main_container, bg=style_service.get_color("bg_dark"), width=150)
        sidebar.pack(side=tk.LEFT, fill=tk.Y)
        sidebar.pack_propagate(False)

        # 2. Chat Widget (Derecha) - LO PONEMOS ANTES DEL CONTENIDO PARA QUE SEA FIJO
        chat_frame = tk.Frame(main_container, width=350)
        chat_frame.pack(side=tk.RIGHT, fill=tk.BOTH)
        chat_frame.pack_propagate(False)

        # 3. Área de Contenido del Módulo (Centro)
        # Al tener expand=True, ocupará todo el espacio restante entre la sidebar y el chat
        content_area = tk.Frame(main_container, bg=style_service.get_color("bg_main"))
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

        tk.Button(chat_collapsed_bar, text="💬", bg=style_service.get_color("bg_header"), 
                  fg=style_service.get_color("accent"), bd=0, font=("Arial", 12), cursor="hand2",
                  command=lambda: toggle_chat(True)).pack(fill=tk.X, pady=10)

        chat_ui = ChatWidget(chat_frame, chat_engine=chat_engine, config_service=config_service, 
                             style_service=style_service, on_collapse_cmd=lambda: toggle_chat(False))
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
            for btn, mod_icon, mod_name in sidebar_btns:
                if sidebar_expanded:
                    btn.config(text=f" {mod_icon}  {mod_name}", anchor="w", padx=10)
                else:
                    btn.config(text=mod_icon, anchor="center", padx=0)

        # Botón Toggle superior
        tk.Button(sidebar, text="☰", bg=style_service.get_color("bg_header") if style_service else "#111", 
                  fg=style_service.get_color("accent") if style_service else "#4EC9B0",
                  bd=0, font=("Arial", 12, "bold"), cursor="hand2", pady=10,
                  command=toggle_sidebar).pack(fill=tk.X)

        tk.Frame(sidebar, bg="#333", height=1).pack(fill=tk.X, pady=(0, 10))

        def update_module_ui(module_id):
            """Actualiza únicamente la interfaz de usuario (área central)."""
            # Limpiar área de contenido
            for widget in content_area.winfo_children():
                widget.destroy()
            
            # Obtener el módulo (ya activado en el servicio)
            module = module_service.loaded_modules.get(module_id)

            if module:
                m_widget = module.get_widget(content_area)
                m_widget.pack(fill=tk.BOTH, expand=True)
            else:
                # Mostrar pantalla de bienvenida si no hay módulo
                welcome = tk.Label(content_area, text="ASIMOD MODULAR", fg=style_service.get_color("text_dim"), bg=style_service.get_color("bg_main"), font=("Arial", 24, "bold"))
                welcome.pack(expand=True)

        def select_module(module_id):
            """Inicia la activación de un módulo en el servicio."""
            module_service.activate_module(module_id)

        # Llenar sidebar con botones
        for mod in module_service.get_modules():
            # Botón modular
            btn = tk.Button(sidebar, text=f" {mod.icon}  {mod.name}", 
                            bg=style_service.get_color("bg_dark"), 
                            fg=style_service.get_color("text_main"), bd=0, 
                            command=lambda m=mod.id: select_module(m),
                            font=("Segoe UI Emoji", 10, "bold"), cursor="hand2", 
                            anchor="w", padx=10, pady=10)
            btn.pack(fill=tk.X)
            sidebar_btns.append((btn, mod.icon, mod.name))
            
            # Tooltip simple
            btn.bind("<Enter>", lambda e, n=mod.name: root.title(f"ASIMOD - {n}"))
            btn.bind("<Leave>", lambda e: root.title("ASIMOD Core"))

        # Configurar callback de activación (ES EL ÚNICO que actualiza la UI)
        module_service.on_module_activated = update_module_ui

        # Mostrar bienvenida por defecto
        update_module_ui(None)
    else:
        # --- LAYOUT ESTÁNDAR (SOLO CHAT) ---
        chat_ui = ChatWidget(root, chat_engine=chat_engine, config_service=config_service, style_service=style_service)
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