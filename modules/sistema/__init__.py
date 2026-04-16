import tkinter as tk
import os
from core.standard_module import StandardModule
from modules.widgets import MediaDisplayWidget

class SistemaModule(StandardModule):
    """
    Módulo de exploración de archivos del sistema.
    Permite navegar por C:, D: y Carpeta de Descargas.
    """
    def __init__(self, chat_service, config_service, style_service, data_service=None):
        super().__init__(chat_service, config_service, style_service, data_service=data_service)
        self.name = "Sistema"
        self.id = "sistema"
        self.icon = "🖥️"
        
        # Configuración de Layout
        self.show_menu = True
        self.show_gallery = True
        self.menu_items = ["Principal", "Secundario", "Descargas", "Escritorio"]
        self.gallery_title = "EXPLORADOR"
        
        # Estado de navegación
        self.current_path = ""
        self.base_roots = {
            "Principal": "C:/",
            "Secundario": "D:/",
            "Descargas": os.path.join(os.path.expanduser("~"), "Downloads"),
            "Escritorio": os.path.join(os.path.expanduser("~"), "Desktop")
        }
        self.media_display = None

    def render_workspace(self, parent):
        """Dibuja el visor de medios en el área principal."""
        self.media_display = MediaDisplayWidget(parent, style=self.style)
        self.media_display.pack(fill=tk.BOTH, expand=True)
        
        # EL MENÚ YA DISPARA EL PRIMER on_menu_change AUTOMÁTICAMENTE
        # NO HACER NADA AQUÍ PARA EVITAR RACE CONDITIONS

    def on_menu_change(self, mode):
        """Cambia la raíz de exploración según el botón del menú."""
        print(f"[Sistema] Cambiando a modo: {mode}")
        self.current_path = os.path.normpath(self.base_roots.get(mode, "C:/"))
        
        # Limpiar visor al cambiar de raíz
        if self.media_display:
            self.media_display.load_media(None)
            
        self._refresh_gallery()

    def _refresh_gallery(self):
        """Escanea el path actual y rellena la galería."""
        if not self.gallery: return
        self.gallery.clear()
        
        # Normalizar para comparaciones
        normalized_current = os.path.abspath(self.current_path).lower()
        
        # Configurar botón de retroceso si no estamos en una raíz base
        is_root = any(normalized_current == os.path.abspath(r).lower() for r in self.base_roots.values())
        self.gallery.on_back = self._on_gallery_back
        self.gallery.set_back_visibility(not is_root)

        print(f"[Sistema] Explorando: {self.current_path}")

        try:
            if not os.path.exists(self.current_path):
                self.gallery.add_item("Error", subtitle=f"Ruta no disponible: {self.current_path}", icon="⚠️")
                return

            items = os.listdir(self.current_path)
            # Ordenar: primero carpetas, luego archivos
            items.sort(key=lambda x: (not os.path.isdir(os.path.join(self.current_path, x)), x.lower()))

            count = 0
            for item in items:
                full_path = os.path.join(self.current_path, item)
                is_dir = os.path.isdir(full_path)
                
                # Intentar obtener info extra (tamaño o fecha)
                subtitle = ""
                try:
                    mtime = os.path.getmtime(full_path)
                    import datetime
                    date_str = datetime.datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M')
                    subtitle = date_str
                except:
                    pass

                self.gallery.add_item(
                    title=item,
                    subtitle=subtitle,
                    is_folder=is_dir,
                    callback=lambda p=full_path, d=is_dir: self._on_item_click(p, d)
                )
                count += 1
            print(f"[Sistema] {count} elementos listados.")
        except Exception as e:
            print(f"[Sistema] Error leyendo {self.current_path}: {e}")
            self.gallery.add_item("Error de acceso", subtitle=str(e), icon="🚫")

    def _on_item_click(self, path, is_dir):
        """Maneja el clic en un elemento de la galería."""
        if is_dir:
            self.current_path = path
            self._refresh_gallery()
        else:
            if self.media_display:
                self.media_display.load_media(path)

    def _on_gallery_back(self):
        """Sube un nivel en el árbol de directorios."""
        parent = os.path.dirname(self.current_path)
        
        # En Windows, dirname de "C:/" es "C:/" o vacío según la versión.
        # Nos aseguramos de no entrar en bucle y respetar las raíces.
        current_abs = os.path.abspath(self.current_path).lower()
        is_at_base = any(current_abs == os.path.abspath(r).lower() for r in self.base_roots.values())
        
        if not is_at_base and parent and os.path.abspath(parent).lower() != current_abs:
            self.current_path = parent
            self._refresh_gallery()

    # --- SOPORTE API WEB ---
    def handle_get_gallery(self, path=None):
        """Implementación delegada para el API Web (/v1/gallery)."""
        target = path if path else self.current_path
        if not target:
            target = self.base_roots["Principal"]
            
        target = os.path.normpath(target)
        print(f"[Sistema][Web] Listando galería para: {target}")
        
        items = []
        try:
            if not os.path.exists(target):
                return {"status": "error", "message": "Path no encontrado", "items": []}

            raw_items = os.listdir(target)
            raw_items.sort(key=lambda x: (not os.path.isdir(os.path.join(target, x)), x.lower()))
            
            for item in raw_items:
                full_path = os.path.join(target, item)
                is_dir = os.path.isdir(full_path)
                
                # Para la web, necesitamos URLs relativas o identificadores
                # Usaremos la ruta absoluta pero cifrada o codificada si fuera necesario, 
                # de momento pasamos la absoluta para simplificar.
                
                f_type = "folder" if is_dir else "file"
                if not is_dir:
                    ext = os.path.splitext(item)[1].lower()
                    if ext in {'.png', '.jpg', '.jpeg', '.webp', '.gif'}: f_type = "image"
                    elif ext in {'.wav', '.mp3'}: f_type = "audio"
                    elif ext in {'.mp4', '.avi', '.mov'}: f_type = "video"
                    elif ext == '.pdf': f_type = "pdf"
                    elif ext in {'.glb', '.obj'}: f_type = "3d"
                
                items.append({
                    "name": item,
                    "type": f_type,
                    "path": full_path.replace("\\", "/"),
                    "icon": "📁" if is_dir else "📄",
                    "url": f"/v1/fs/get?path={full_path}" if not is_dir else None
                })
        except Exception as e:
            return {"status": "error", "message": str(e), "items": []}

        # Comprobar si estamos en una raíz
        current_abs = os.path.abspath(target).lower()
        is_root = any(current_abs == os.path.abspath(r).lower() for r in self.base_roots.values())
        
        return {
            "status": "success",
            "items": items,
            "current_path": target.replace("\\", "/"),
            "is_root": is_root
        }
