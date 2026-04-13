import tkinter as tk
from tkinter import ttk, messagebox
import datetime
from core.standard_module import StandardModule

class ProjectsModule(StandardModule):
    """
    Módulo de Gestión de Proyectos, Tareas y Sprints.
    Migrado del proyecto original con soporte para DataService.
    """
    def __init__(self, chat_service, config_service, style_service, data_service=None):
        super().__init__(chat_service, config_service, style_service, data_service=data_service)
        self.name = "Proyectos"
        self.id = "projects"
        self.icon = "📂"
        self.has_web_ui = True
        
        # Configuración de Layout
        self.show_menu = True
        self.show_controllers = True
        self.show_gallery = True
        self.menu_items = ["Tareas", "Gantt", "Sprints"]
        self.gallery_title = "MIS PROYECTOS"
        
        self.current_mode = "Tareas"
        self.selected_project_id = None

    async def handle_get_projects(self):
        """Bridge para listar proyectos en la web."""
        return {"status": "success", "projects": self.data_service.get_all_projects()}

    async def handle_get_project_data(self, project_id: int):
        """Bridge para obtener detalles y tareas de un proyecto específico."""
        return {
            "status": "success",
            "project": self.data_service.get_project_details(project_id),
            "tasks": self.data_service.get_project_items(project_id)
        }

    async def handle_update_task(self, task_id: int, status: str):
        """Bridge para actualizar estado de tarea desde la web."""
        self.data_service.update_project_item_status(task_id, status)
        return {"status": "success", "new_status": status}

    def handle_get_gallery(self):
        """Genera la lista de proyectos para la barra lateral web."""
        projects = self.data_service.get_all_projects()
        items = []
        for p in projects:
            items.append({
                "id": p['id'],
                "title": p['name'],
                "subtitle": "Activo" if p['is_active'] else "Inactivo",
                "type": "item",
                "icon": "📁",
                "callback_action": "handle_select_project",
                "callback_params": {"project_id": p['id']}
            })
        return {"items": items}

    async def handle_select_project(self, project_id: int):
        """Selecciona un proyecto desde la web."""
        self.selected_project_id = project_id
        self.data_service.set_active_project(project_id)
        return {"status": "success", "project_id": project_id}
        self.selected_project_id = None

    def setup_controllers(self, panel):
        panel.clear()
        panel.add_dropdown("Filtrar Estado", "status_filter", ["Todos", "Pendientes", "En Progreso", "Completados"])
        
        # Botón para nuevo proyecto directamente en el panel de control
        header = panel.grid_container
        row = len(header.winfo_children()) // 2
        tk.Button(header, text="➕ Nuevo Proyecto", bg=self.style.get_color("accent"), fg="white", bd=0, padx=10, 
                  command=self._new_project_dialog).grid(row=row, column=2, pady=5, padx=10)

    def render_workspace(self, parent):
        if not self.selected_project_id:
            tk.Label(parent, text="Selecciona un proyecto de la galería para ver sus detalles", 
                     fg=self.style.get_color("text_dim"), bg=self.style.get_color("bg_main"), font=("Arial", 12)).pack(expand=True)
            return

        project = self.data_service.get_project_details(self.selected_project_id)
        
        # Título del Proyecto
        header_frame = tk.Frame(parent, bg=self.style.get_color("bg_main"))
        header_frame.pack(fill=tk.X, pady=(0, 20))
        
        tk.Label(header_frame, text=project['name'], fg=self.style.get_color("text_main"), bg=self.style.get_color("bg_main"), 
                 font=("Arial", 18, "bold")).pack(side=tk.LEFT)
        
        # Renderizado según el modo (Pestaña)
        if self.current_mode == "Tareas":
            self._render_tasks(parent)
        elif self.current_mode == "Gantt":
            self._render_gantt(parent)
        else:
            tk.Label(parent, text=f"Modo {self.current_mode} en desarrollo...", bg=self.style.get_color("bg_main"), fg="#888").pack(pady=50)

    def _render_tasks(self, parent):
        """Dibuja la lista de tareas."""
        # Botón Añadir Tarea
        btn_frame = tk.Frame(parent, bg=self.style.get_color("bg_main"))
        btn_frame.pack(fill=tk.X, pady=(0, 10))
        tk.Button(btn_frame, text="+ Añadir Tarea", bg="#444", fg="white", bd=0, padx=10, pady=5, 
                  command=self._add_task_dialog).pack(side=tk.RIGHT)

        # Contenedor Scrollable para tareas
        canvas = tk.Canvas(parent, bg=self.style.get_color("bg_main"), highlightthickness=0)
        scroll_y = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        task_frame = tk.Frame(canvas, bg=self.style.get_color("bg_main"))
        
        task_window = canvas.create_window((0, 0), window=task_frame, anchor="nw")
        canvas.configure(yscrollcommand=scroll_y.set)
        
        def _on_cfg(e):
            canvas.configure(scrollregion=canvas.bbox("all"))
            canvas.itemconfig(task_window, width=e.width)

        canvas.bind("<Configure>", _on_cfg)
        scroll_y.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        items = self.data_service.get_project_items(self.selected_project_id)
        if not items:
            tk.Label(task_frame, text="No hay tareas en este proyecto.", bg=self.style.get_color("bg_main"), fg="#666").pack(pady=20)
            return

        for item in items:
            self._draw_task_card(task_frame, item)

    def _draw_task_card(self, parent, item):
        card = tk.Frame(parent, bg=self.style.get_color("bg_input"), padx=15, pady=10)
        card.pack(fill=tk.X, pady=2, padx=5)
        
        # Checkbox simulado / Estado
        status_colors = {"pending": "#888", "in_progress": "#FFA500", "completed": "#4EC9B0"}
        color = status_colors.get(item['status'], "#888")
        
        tk.Label(card, text="●", fg=color, bg=self.style.get_color("bg_input"), font=("Arial", 12)).pack(side=tk.LEFT, padx=(0, 10))
        tk.Label(card, text=item['title'], fg=self.style.get_color("text_main"), bg=self.style.get_color("bg_input"), font=("Arial", 10)).pack(side=tk.LEFT)
        
        # Botones de acción
        btn_del = tk.Button(card, text="🗑️", bg=self.style.get_color("bg_input"), fg="#666", bd=0, cursor="hand2", 
                            command=lambda: self._delete_task(item['id']))
        btn_del.pack(side=tk.RIGHT)
        
        if item['status'] != 'completed':
            btn_done = tk.Button(card, text="✓", bg=self.style.get_color("bg_input"), fg="#4EC9B0", bd=0, cursor="hand2", 
                                 command=lambda: self._update_task_status(item['id'], "completed"))
            btn_done.pack(side=tk.RIGHT, padx=10)

    def _render_gantt(self, parent):
        """Implementación simplificada del diagrama de Gantt."""
        canvas = tk.Canvas(parent, bg=self.style.get_color("bg_dark"), highlightthickness=0)
        canvas.pack(fill=tk.BOTH, expand=True)
        
        items = self.data_service.get_project_items(self.selected_project_id)
        if not items: return

        y = 40
        x_start = 150
        day_w = 40
        
        # Dibujar cabecera de fechas
        today = datetime.date.today()
        for i in range(10):
            d = today + datetime.timedelta(days=i)
            canvas.create_text(x_start + i*day_w, 20, text=d.strftime("%d/%m"), fill="#888", font=("Arial", 7))
            canvas.create_line(x_start + i*day_w, 30, x_start + i*day_w, 400, fill="#333", dash=(2, 2))

        for i, item in enumerate(items):
            # Nombre de tarea
            canvas.create_text(20, y, text=item['title'][:15], anchor="w", fill="white", font=("Arial", 9))
            
            # Barra de progreso (ficticia o basada en fechas si existieran)
            # Para el ejemplo, usamos una duración aleatoria basada en el ID
            start_offset = (item['id'] % 5) * day_w
            duration = 2 * day_w
            
            color = "#4a90e2"
            if item['status'] == 'completed': color = "#4EC9B0"
            
            canvas.create_rectangle(x_start + start_offset, y - 8, x_start + start_offset + duration, y + 8, 
                                    fill=color, outline="")
            y += 30

    def on_menu_change(self, mode):
        self.current_mode = mode
        self.refresh_workspace()

    def on_activate(self):
        self._refresh_gallery_from_db()

    def _refresh_gallery_from_db(self):
        if not self.gallery or not self.gallery.winfo_exists(): return
        self.gallery.clear()
        
        projects = self.data_service.get_all_projects()
        for p in projects:
            subtitle = "Activo" if p['is_active'] else "Inactivo"
            icon = "📁"
            self.gallery.add_item(p['name'], subtitle, icon=icon, 
                                  callback=lambda pid=p['id']: self._select_project(pid))

    def _select_project(self, project_id):
        self.selected_project_id = project_id
        self.data_service.set_active_project(project_id)
        self.refresh_workspace()
        self._refresh_gallery_from_db()

    def _new_project_dialog(self):
        # Diálogo simple de entrada
        dialog = tk.Toplevel(self.workspace)
        dialog.title("Nuevo Proyecto")
        dialog.geometry("300x200")
        dialog.configure(bg=self.style.get_color("bg_main"))
        
        tk.Label(dialog, text="Nombre del Proyecto:", bg=self.style.get_color("bg_main"), fg="white").pack(pady=10)
        entry = tk.Entry(dialog, bg=self.style.get_color("bg_input"), fg="white", bd=0)
        entry.pack(pady=5, padx=20, fill=tk.X)
        entry.focus()
        
        def save():
            name = entry.get().strip()
            if name:
                self.data_service.create_project(name)
                self._refresh_gallery_from_db()
                dialog.destroy()
        
        tk.Button(dialog, text="Guardar", command=save, bg=self.style.get_color("accent"), fg="white").pack(pady=20)

    def _add_task_dialog(self):
        dialog = tk.Toplevel(self.workspace)
        dialog.title("Nueva Tarea")
        dialog.geometry("300x150")
        dialog.configure(bg=self.style.get_color("bg_main"))
        
        tk.Label(dialog, text="Título de la Tarea:", bg=self.style.get_color("bg_main"), fg="white").pack(pady=10)
        entry = tk.Entry(dialog, bg=self.style.get_color("bg_input"), fg="white", bd=0)
        entry.pack(pady=5, padx=20, fill=tk.X)
        
        def save():
            title = entry.get().strip()
            if title:
                self.data_service.add_project_item(self.selected_project_id, title)
                self.refresh_workspace()
                dialog.destroy()
        
        tk.Button(dialog, text="Añadir", command=save, bg=self.style.get_color("accent"), fg="white").pack(pady=10)

    def _update_task_status(self, task_id, status):
        self.data_service.update_project_item_status(task_id, status)
        self.refresh_workspace()

    def _delete_task(self, task_id):
        self.data_service.delete_project_item(task_id)
        self.refresh_workspace()

    def get_voice_commands(self):
        return {
            "proyectos": "show_projects",
            "nuevo proyecto": "new_project",
            "tareas": "show_tasks",
            "gantt": "show_gantt"
        }

    def on_voice_command(self, action_slug, text):
        if action_slug == "show_projects": self.on_activate() # Activa módulo
        elif action_slug == "new_project": self._new_project_dialog()
        elif action_slug == "show_tasks": self.on_menu_change("Tareas")
        elif action_slug == "show_gantt": self.on_menu_change("Gantt")

def get_module_class():
    return ProjectsModule
