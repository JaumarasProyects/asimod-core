import tkinter as tk
from tkinter import messagebox
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
        self.has_web_ui = True
        
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

    async def handle_read_file(self, path: str):
        """Lee el contenido de un archivo de texto."""
        try:
            if not os.path.exists(path):
                return {"status": "error", "message": "Archivo no existe"}
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            return {"status": "success", "content": content}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    async def handle_write_file(self, path: str, content: str):
        """Escribe contenido en un archivo de texto."""
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            return {"status": "success"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    async def handle_delete_file(self, path: str):
        """Elimina un archivo o carpeta."""
        try:
            if os.path.isdir(path):
                import shutil
                shutil.rmtree(path)
            else:
                os.remove(path)
            return {"status": "success"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    async def handle_create_item(self, path: str, name: str, is_folder: bool = False):
        """Crea un nuevo archivo o carpeta."""
        try:
            full_path = os.path.join(path, name)
            if is_folder:
                os.makedirs(full_path, exist_ok=True)
            else:
                with open(full_path, "w") as f:
                    pass
            return {"status": "success"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    async def handle_search(self, query: str, root_path: str = None):
        """Busca archivos recursivamente."""
        if not root_path: root_path = self.current_path
        results = []
        query = query.lower()
        try:
            for root, dirs, files in os.walk(root_path):
                if len(results) > 100: break # Límite de seguridad
                for name in dirs + files:
                    if query in name.lower():
                        full_path = os.path.join(root, name).replace("\\", "/")
                        results.append({
                            "name": name,
                            "path": full_path,
                            "type": "folder" if os.path.isdir(full_path) else "file"
                        })
            return {"status": "success", "results": results}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def render_workspace(self, parent):
        """Dibuja el área de trabajo profesional con visor y editor."""
        # Limpiar área para evitar duplicados
        for child in parent.winfo_children():
            child.destroy()
            
        self.workspace_root = parent
        
        # Toolbar Superior
        self.toolbar = tk.Frame(parent, bg=self.style.get_color("bg_dark"), pady=10, padx=20)
        self.toolbar.pack(fill=tk.X)
        
        self.lbl_path = tk.Label(self.toolbar, text="Selecciona un archivo...", fg=self.style.get_color("text_dim"), 
                                 bg=self.style.get_color("bg_dark"), font=("Arial", 9))
        self.lbl_path.pack(side=tk.LEFT, padx=20)
        
        # Botones de Acción (ocultos inicialmente)
        self.btn_save = tk.Button(self.toolbar, text="💾 Guardar", bg=self.style.get_color("accent"), fg="black", bd=0, padx=10,
                                 command=self._save_current_text)
        self.btn_delete = tk.Button(self.toolbar, text="🗑️ Eliminar", bg="#ff5555", fg="white", bd=0, padx=10,
                                   command=self._delete_current_file)
        
        # Contenedor para visores
        self.viewer_container = tk.Frame(parent, bg=self.style.get_color("bg_main"))
        self.viewer_container.pack(fill=tk.BOTH, expand=True)

        # 1. Visor Multimedia (Widgets existentes)
        self.media_display = MediaDisplayWidget(self.viewer_container, style=self.style)
        
        # 2. Editor de Texto
        self.text_editor = tk.Text(self.viewer_container, bg=self.style.get_color("bg_input"), fg="white", 
                                   insertbackground="white", undo=True, font=("Consolas", 11), bd=0, padx=20, pady=20)
        
        self.current_editing_path = None

    def on_activate(self):
        """Asegura que la galería se refresque al entrar."""
        if not self.current_path:
            self.current_path = self.base_roots["Principal"]
        self._refresh_gallery()

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
        """Maneja el clic en un elemento de la galería Desktop."""
        if is_dir:
            self.current_path = path
            self._refresh_gallery()
            return

        self.current_editing_path = path
        self.lbl_path.config(text=os.path.basename(path))
        self.btn_delete.pack(side=tk.RIGHT, padx=5)
        
        # Comprobar si es texto
        ext = os.path.splitext(path)[1].lower()
        if ext in {'.txt', '.py', '.json', '.md', '.css', '.js', '.html'}:
            self.media_display.pack_forget()
            self.text_editor.pack(fill=tk.BOTH, expand=True)
            self.btn_save.pack(side=tk.RIGHT, padx=5)
            
            try:
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                self.text_editor.delete("1.0", tk.END)
                self.text_editor.insert("1.0", content)
            except Exception as e:
                messagebox.showerror("Error", f"No se pudo leer el archivo: {e}")
        else:
            self.text_editor.pack_forget()
            self.btn_save.pack_forget()
            self.media_display.pack(fill=tk.BOTH, expand=True)
            self.media_display.load_media(path)

    def _save_current_text(self):
        if not self.current_editing_path: return
        content = self.text_editor.get("1.0", tk.END)
        try:
            with open(self.current_editing_path, "w", encoding="utf-8") as f:
                f.write(content)
            messagebox.showinfo("Sistema", "Archivo guardado correctamente.")
        except Exception as e:
            messagebox.showerror("Error", f"Error al guardar: {e}")

    def _delete_current_file(self):
        if not self.current_editing_path: return
        if messagebox.askyesno("Confirmar", f"¿Eliminar permanentemente {os.path.basename(self.current_editing_path)}?"):
            try:
                os.remove(self.current_editing_path)
                self.media_display.load_media(None)
                self.text_editor.delete("1.0", tk.END)
                self._refresh_gallery()
                self.btn_save.pack_forget()
                self.btn_delete.pack_forget()
                self.lbl_path.config(text="Selecciona un archivo...")
            except Exception as e:
                messagebox.showerror("Error", f"No se pudo eliminar: {e}")

    def _on_gallery_back(self):
        """Sube un nivel en el árbol de directorios."""
        parent = os.path.dirname(self.current_path)
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
                    elif ext in {'.txt', '.py', '.json', '.md', '.css', '.js', '.html'}: f_type = "text"
                    elif ext == '.pdf': f_type = "pdf"
                
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
