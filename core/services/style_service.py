import os
import json

class StyleService:
    """
    Gestiona el sistema de estilos modulares (temas) de ASIMOD.
    Escanea la carpeta 'styles' y carga los esquemas de colores.
    """
    def __init__(self, config_service, styles_dir="styles"):
        self.config = config_service
        self.styles_dir = styles_dir
        self.available_styles = {}
        self.current_theme = {}
        self.callbacks = [] # NUEVO: Lista de observadores
        
        # Asegurar que la carpeta existe
        if not os.path.exists(self.styles_dir):
            os.makedirs(self.styles_dir)
            
        self.refresh_available_styles()
        self.load_current_style()

    def subscribe(self, callback):
        """Registra un componente para ser notificado cuando el estilo cambie."""
        if not callable(callback):
             print(f"[StyleService][WARNING] Intento de suscribir objeto no ejecutable: {callback}")
             return
             
        if callback not in self.callbacks:
            self.callbacks.append(callback)

    def unsubscribe(self, callback):
        """Elimina un componente de la lista de notificaciones."""
        if callback in self.callbacks:
            self.callbacks.remove(callback)

    def notify(self):
        """Notifica a todos los suscriptores que el estilo ha cambiado."""
        print(f"[StyleService] Notificando cambio de estilo a {len(self.callbacks)} componentes.")
        
        dead_callbacks = []
        for cb in self.callbacks:
            try:
                cb()
            except Exception as e:
                # Si el error es un comando inválido de Tcl (widget destruido) 
                # o el objeto ya no es válido, lo marcamos para limpieza.
                error_msg = str(e).lower()
                if "invalid command name" in error_msg or "object is not callable" in error_msg:
                    dead_callbacks.append(cb)
                else:
                    print(f"[StyleService] Error notificando a observador: {e}")
        
        # Auto-limpieza de suscriptores huérfanos o inválidos
        if dead_callbacks:
            for dead in dead_callbacks:
                if dead in self.callbacks:
                    self.callbacks.remove(dead)
            print(f"[StyleService] Limpieza completada: se eliminaron {len(dead_callbacks)} suscriptores inválidos.")

    def refresh_available_styles(self):
        """Escanea la carpeta de estilos en busca de archivos JSON."""
        self.available_styles = {}
        for file in os.listdir(self.styles_dir):
            if file.endswith(".json"):
                path = os.path.join(self.styles_dir, file)
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        style_id = file.replace(".json", "")
                        self.available_styles[style_id] = data
                except Exception as e:
                    print(f"[StyleService] Error cargando estilo {file}: {e}")

    def load_current_style(self):
        """Carga el estilo guardado en la configuración o el por defecto."""
        style_id = self.config.get("current_style", "dark_carbon")
        if style_id in self.available_styles:
            self.current_theme = self.available_styles[style_id]
        else:
            # Fallback a un diccionario básico por si no hay archivos
            self.current_theme = {
                "name": "Fallback",
                "colors": {
                    "bg_main": "#2b2b2b",
                    "bg_dark": "#1e1e1e",
                    "bg_sidebar": "#1a1a1a",
                    "bg_header": "#2b2b2b",
                    "bg_input": "#333333",
                    "accent": "#0078d4",
                    "accent_hover": "#005a9e",
                    "text_main": "#ffffff",
                    "text_dim": "#888888",
                    "btn_bg": "#444444",
                    "btn_fg": "#ffffff"
                }
            }

    def get_color(self, key):
        """Retorna un color del tema actual."""
        return self.current_theme.get("colors", {}).get(key, "#ff00ff") # Magenta fallback para detectar errores

    def get_background(self, key):
        """Retorna la ruta de imagen de fondo para un componente si existe."""
        return self.current_theme.get("backgrounds", {}).get(key)

    def get_available_styles_names(self):
        """Retorna un diccionario de {id: nombre_legible}."""
        return {sid: data.get("name", sid) for sid, data in self.available_styles.items()}

    def apply_style(self, style_id):
        """Cambia el estilo actual y lo guarda en configuración."""
        if style_id in self.available_styles:
            self.config.set("current_style", style_id)
            self.load_current_style()
            self.notify() # NUEVO: Propagar cambio
            return True
        return False
