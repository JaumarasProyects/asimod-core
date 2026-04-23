import tkinter as tk
from tkinter import ttk, messagebox
import datetime
from core.standard_module import StandardModule

class ProjectsModule(StandardModule):
    """
    Módulo de Gestión de Proyectos, Tareas y Sprints.
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
        self.menu_items = ["Tareas", "Gantt", "Sprints", "Gráficas"]
        self.gallery_title = "MIS PROYECTOS"
        
        self.current_mode = "Tareas"
        self.selected_project_id = None
        
        # Asegurar datos de ejemplo
        if self.data_service:
            self.data_service.seed_sample_project()


    async def handle_get_projects(self):
        """Bridge para listar proyectos en la web."""
        return {"status": "success", "projects": self.data_service.get_all_projects()}

    async def handle_get_project_data(self, project_id: int):
        """Bridge para obtener detalles, tareas y sprints de un proyecto específico."""
        return {
            "status": "success",
            "project": self.data_service.get_project_details(project_id),
            "tasks": self.data_service.get_project_items(project_id),
            "active_sprint": self.data_service.get_active_sprint(project_id),
            "sprint_history": self.data_service.get_project_sprints(project_id)
        }

    async def handle_update_task(self, task_id: int, status: str):
        """Bridge para actualizar estado de tarea desde la web."""
        self.data_service.update_project_item_status(task_id, status)
        return {"status": "success", "new_status": status}

    async def handle_update_gantt(self, task_id: int, start_date: str, end_date: str):
        """Bridge para actualizar fechas de una tarea (Gantt)."""
        self.data_service.update_project_item_dates(task_id, start_date, end_date)
        return {"status": "success"}

    async def handle_create_sprint(self, project_id: int, name: str, objective: str, start_date: str, end_date: str):
        """Bridge para crear un nuevo sprint."""
        sid = self.data_service.create_sprint(project_id, name, objective, start_date, end_date)
        return {"status": "success", "sprint_id": sid}

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

    def setup_controllers(self, panel):
        panel.clear()
        panel.add_dropdown("Filtrar Estado", "status_filter", ["Todos", "Pendientes", "En Progreso", "Completados"])
        
        # Botón para nuevo proyecto directamente en el panel de control
        header = panel.grid_container
        row = len(header.winfo_children()) // 2
        tk.Button(header, text="➕ Nuevo Proyecto", bg=self.style.get_color("accent"), fg="white", bd=0, padx=10, 
                  command=self._new_project_dialog).grid(row=row, column=2, pady=5, padx=10)

    def render_workspace(self, parent):
        # Limpiar área para evitar duplicados
        for child in parent.winfo_children():
            child.destroy()
            
        # Asegurar que la galería esté poblada
        self._refresh_gallery_from_db()

        if not self.selected_project_id:
            active = self.data_service.get_active_project()
            if active:
                self.selected_project_id = active['id']
            else:
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
        elif self.current_mode == "Sprints":
            self._render_sprints_overview(parent)
        elif self.current_mode == "Gráficas":
            self._render_charts(parent)
        else:
            tk.Label(parent, text=f"Modo {self.current_mode} en desarrollo...", bg=self.style.get_color("bg_main"), fg="#888").pack(pady=50)

    def _render_charts(self, parent):
        """Dibuja estadísticas visuales del proyecto."""
        tasks = self.data_service.get_project_items(self.selected_project_id)
        if not tasks:
            tk.Label(parent, text="No hay datos suficientes para generar gráficas.", 
                     bg=self.style.get_color("bg_main"), fg="#666").pack(pady=50)
            return

        # Procesar datos
        total = len(tasks)
        completed = len([t for t in tasks if t['status'] == 'completed'])
        in_progress = len([t for t in tasks if t['status'] == 'in_progress'])
        pending = len([t for t in tasks if t['status'] == 'pending'])

        # Layout de 2 columnas para gráficas
        charts_container = tk.Frame(parent, bg=self.style.get_color("bg_main"))
        charts_container.pack(fill=tk.BOTH, expand=True)

        left_col = tk.Frame(charts_container, bg=self.style.get_color("bg_main"))
        left_col.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        right_col = tk.Frame(charts_container, bg=self.style.get_color("bg_main"))
        right_col.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # 1. Estado Global (Anillo)
        tk.Label(left_col, text="DISTRIBUCIÓN DE TAREAS", font=("Arial", 10, "bold"), 
                 bg=self.style.get_color("bg_main"), fg=self.style.get_color("text_dim")).pack(pady=(0, 10))
        
        self._draw_stat_ring(left_col, "Completado", completed, total, self.style.get_color("success")).pack(pady=10)
        self._draw_stat_ring(left_col, "En Progreso", in_progress, total, "#FFA500").pack(pady=10)

        # 2. Historial / Comparativa (Barras)
        tk.Label(right_col, text="BALANCE PENDIENTE VS REALIZADO", font=("Arial", 10, "bold"), 
                 bg=self.style.get_color("bg_main"), fg=self.style.get_color("text_dim")).pack(pady=(0, 10))
        
        canvas = tk.Canvas(right_col, bg=self.style.get_color("bg_dark"), highlightthickness=0, height=250)
        canvas.pack(fill=tk.X, padx=20, pady=10)
        
        self._draw_bar_chart(canvas, [pending, in_progress, completed], ["Backlog", "Work", "Done"])

    def _draw_stat_ring(self, parent, label, value, total, color):
        frame = tk.Frame(parent, bg=self.style.get_color("bg_main"))
        canvas = tk.Canvas(frame, width=120, height=120, bg=self.style.get_color("bg_main"), highlightthickness=0)
        canvas.pack()
        
        # Círculo fondo
        canvas.create_oval(15, 15, 105, 105, outline="#222", width=10)
        # Arco progreso
        if total > 0:
            extent = -(value / total) * 359.9
            canvas.create_arc(15, 15, 105, 105, start=90, extent=extent, outline=color, width=10, style="arc")
        
        percentage = f"{int((value/total)*100)}%" if total > 0 else "0%"
        canvas.create_text(60, 60, text=percentage, fill="white", font=("Arial", 16, "bold"))
        tk.Label(frame, text=f"{label}: {value}/{total}", fg="#888", bg=self.style.get_color("bg_main"), font=("Arial", 9)).pack()
        return frame

    def _draw_bar_chart(self, canvas, data, labels):
        canvas.update()
        w = 250
        h = 200
        
        max_val = max(data) if any(data) else 1
        bar_w = 40
        gap = 30
        
        colors = ["#F44336", "#FFA500", "#4EC9B0"]
        
        for i, val in enumerate(data):
            x0 = 40 + i * (bar_w + gap)
            bar_h = (val / max_val) * (h - 40)
            y0 = h - bar_h
            x1 = x0 + bar_w
            y1 = h
            
            canvas.create_rectangle(x0, y0, x1, y1, fill=colors[i], outline="")
            canvas.create_text((x0+x1)/2, h + 15, text=labels[i], fill="#888", font=("Arial", 8))
            canvas.create_text((x0+x1)/2, y0 - 10, text=str(val), fill="white", font=("Arial", 9, "bold"))

    def _render_sprints_overview(self, parent):
        """Vista de Sprints con botón de creación."""
        # Botón Nuevo Sprint
        btn_frame = tk.Frame(parent, bg=self.style.get_color("bg_main"))
        btn_frame.pack(fill=tk.X, pady=(0, 15))
        tk.Button(btn_frame, text="+ Planificar Sprint", bg=self.style.get_color("accent"), fg="black", bd=0, padx=10, 
                  font=("Arial", 9, "bold"), command=self._new_sprint_dialog).pack(side=tk.RIGHT)

        active = self.data_service.get_active_sprint(self.selected_project_id)
        if not active:
            tk.Label(parent, text="No hay un sprint activo.", bg=self.style.get_color("bg_main"), fg="#888").pack(pady=50)
        else:
            card = tk.Frame(parent, bg=self.style.get_color("bg_input"), padx=25, pady=25)
            card.pack(fill=tk.X, padx=10)
            
            tk.Label(card, text=f"SPRINT: {active['name']}", font=("Arial", 16, "bold"), 
                     bg=self.style.get_color("bg_input"), fg=self.style.get_color("accent")).pack(anchor="w")
            tk.Label(card, text=active['objective'], wraplength=400, justify="left", 
                     bg=self.style.get_color("bg_input"), fg="white").pack(anchor="w", pady=10)
        
        # Historial simple
        tk.Label(parent, text="Historial de Sprints", font=("Arial", 12, "bold"), 
                 bg=self.style.get_color("bg_main"), fg="white").pack(anchor="w", pady=(30, 10))
        
        history = self.data_service.get_project_sprints(self.selected_project_id)
        for s in history:
            if s['status'] == 'completed':
                row = tk.Frame(parent, bg=self.style.get_color("bg_main"))
                row.pack(fill=tk.X, pady=2)
                tk.Label(row, text=f"✓ {s['name']}", fg="#4EC9B0", bg=self.style.get_color("bg_main")).pack(side=tk.LEFT)
                tk.Label(row, text=f"{s['start_date']} - {s['end_date']}", fg="#666", bg=self.style.get_color("bg_main")).pack(side=tk.RIGHT)

    def _render_tasks(self, parent):
        """Dibuja un tablero Kanban de 3 columnas."""
        # Botón Añadir Tarea
        btn_frame = tk.Frame(parent, bg=self.style.get_color("bg_main"))
        btn_frame.pack(fill=tk.X, pady=(0, 10))
        tk.Button(btn_frame, text="+ Añadir Tarea", bg=self.style.get_color("accent"), fg="black", bd=0, padx=10, pady=5, 
                  font=("Arial", 9, "bold"), command=self._add_task_dialog).pack(side=tk.RIGHT)

        # Tablero de columnas (Grid para control exacto)
        kanban_frame = tk.Frame(parent, bg=self.style.get_color("bg_main"))
        kanban_frame.pack(fill=tk.BOTH, expand=True)
        kanban_frame.columnconfigure((0, 1, 2), weight=1)
        kanban_frame.rowconfigure(0, weight=1)

        cols = [
            ("POR HACER", "pending", "#888"),
            ("EN PROGRESO", "in_progress", "#FFA500"),
            ("YA REALIZADA", "completed", "#4EC9B0")
        ]

        tasks = self.data_service.get_project_items(self.selected_project_id)

        for i, (title, status_key, color) in enumerate(cols):
            # Columna con ancho dinámico vía grid
            col_frame = tk.Frame(kanban_frame, bg=self.style.get_color("bg_dark"), borderwidth=1, relief="flat")
            col_frame.grid(row=0, column=i, sticky="nsew", padx=2, pady=5)
            
            # Header de columna
            lbl = tk.Label(col_frame, text=title, bg=self.style.get_color("bg_dark"), fg=color, font=("Arial", 9, "bold"))
            lbl.pack(pady=10)
            
            # Contenedor para tarjetas
            canvas = tk.Canvas(col_frame, bg=self.style.get_color("bg_dark"), highlightthickness=0)
            scroll_y = ttk.Scrollbar(col_frame, orient="vertical", command=canvas.yview)
            inner_frame = tk.Frame(canvas, bg=self.style.get_color("bg_dark"))
            
            canvas.create_window((0, 0), window=inner_frame, anchor="nw", tags="inner")
            canvas.configure(yscrollcommand=scroll_y.set)
            
            # Ajuste dinámico de ancho interno y wraplength
            def _on_col_resize(e, c=canvas, f=inner_frame): 
                c.itemconfig("inner", width=e.width)
                c.configure(scrollregion=c.bbox("all"))
                # Actualizar wraplength de todos los labels de tareas en esta columna
                for widget in f.winfo_children():
                    if isinstance(widget, tk.Frame): # La tarjeta
                        for sub in widget.winfo_children():
                            if isinstance(sub, tk.Frame): # Info frame
                                for label in sub.winfo_children():
                                    if isinstance(label, tk.Label) and label.cget("wraplength") > 0:
                                        label.config(wraplength=e.width - 40)

            col_frame.bind("<Configure>", _on_col_resize)
            scroll_y.pack(side=tk.RIGHT, fill=tk.Y)
            canvas.pack(fill=tk.BOTH, expand=True)

            # Filtrar tareas para esta columna
            for item in [t for t in tasks if t['status'] == status_key]:
                self._draw_task_card_v2(inner_frame, item)

    def _draw_task_card_v2(self, parent, item):
        card = tk.Frame(parent, bg=self.style.get_color("bg_input"), padx=12, pady=12)
        card.pack(fill=tk.X, pady=5, padx=2)
        
        # Color lateral según estado
        status_colors = {"pending": "#555", "in_progress": "#FFA500", "completed": "#4EC9B0"}
        side_color = status_colors.get(item['status'], "#555")
        
        tk.Frame(card, bg=side_color, width=4).pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        
        info_frame = tk.Frame(card, bg=self.style.get_color("bg_input"))
        info_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        tk.Label(info_frame, text=item['title'], fg="white", bg=self.style.get_color("bg_input"), 
                 font=("Arial", 9, "bold"), wraplength=120, justify="left").pack(anchor="w")
        
        if item['end_date']:
            tk.Label(info_frame, text=f"📅 {item['end_date']}", fg="#888", bg=self.style.get_color("bg_input"), font=("Arial", 8)).pack(anchor="w")

        # Botones de acción rápida
        btn_box = tk.Frame(card, bg=self.style.get_color("bg_input"))
        btn_box.pack(side=tk.RIGHT)

        if item['status'] == 'pending':
            tk.Button(btn_box, text="▶", bg="#333", fg="white", bd=0, padx=5, 
                      command=lambda: self._update_task_status(item['id'], "in_progress")).pack()
        elif item['status'] == 'in_progress':
            tk.Button(btn_box, text="✓", bg="#333", fg="#4EC9B0", bd=0, padx=5, 
                      command=lambda: self._update_task_status(item['id'], "completed")).pack()
        
        tk.Button(btn_box, text="🗑️", bg="#333", fg="#ff5555", bd=0, padx=5, 
                  command=lambda: self._delete_task(item['id'])).pack(pady=5)

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
        # Sembrar datos de ejemplo si no existen
        self.data_service.seed_sample_project()
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
        dialog.geometry("350x250")
        dialog.configure(bg=self.style.get_color("bg_main"))
        
        tk.Label(dialog, text="Título de la Tarea:", bg=self.style.get_color("bg_main"), fg="white").pack(pady=(15, 5))
        entry = tk.Entry(dialog, bg=self.style.get_color("bg_input"), fg="white", bd=1, relief="solid")
        entry.pack(pady=5, padx=20, fill=tk.X)
        entry.focus()

        tk.Label(dialog, text="Estado Inicial:", bg=self.style.get_color("bg_main"), fg="white").pack(pady=(10, 5))
        status_var = tk.StringVar(value="pending")
        status_combo = ttk.Combobox(dialog, textvariable=status_var, state="readonly", 
                                    values=["pending", "in_progress", "completed"])
        # Map values to user-friendly names
        status_combo['values'] = ('pending', 'in_progress', 'completed')
        status_combo.set('pending')
        # Styling combobox
        style = ttk.Style()
        style.theme_use('combobox_asimod' if 'combobox_asimod' in style.theme_names() else 'default')
        status_combo.pack(pady=5, padx=20, fill=tk.X)
        
        def save():
            title = entry.get().strip()
            status = status_var.get()
            if title:
                self.data_service.add_project_item(self.selected_project_id, title, status=status)
                self.refresh_workspace()
                dialog.destroy()
        
        tk.Button(dialog, text="Añadir Tarea", command=save, bg=self.style.get_color("accent"), 
                  fg="black", font=("Arial", 10, "bold"), bd=0, padx=20, pady=10).pack(pady=20)

    def _new_sprint_dialog(self):
        dialog = tk.Toplevel(self.workspace)
        dialog.title("Planificar Sprint")
        dialog.geometry("400x400")
        dialog.configure(bg=self.style.get_color("bg_main"))
        
        # Formulario
        fields = ["Nombre del Sprint", "Objetivo", "Fecha Inicio (YYYY-MM-DD)", "Fecha Fin (YYYY-MM-DD)"]
        entries = {}
        
        for f in fields:
            tk.Label(dialog, text=f, bg=self.style.get_color("bg_main"), fg="white").pack(pady=(10, 0))
            e = tk.Entry(dialog, bg=self.style.get_color("bg_input"), fg="white", bd=1)
            e.pack(pady=5, padx=30, fill=tk.X)
            entries[f] = e
        
        def save():
            name = entries["Nombre del Sprint"].get().strip()
            obj = entries["Objetivo"].get().strip()
            start = entries["Fecha Inicio (YYYY-MM-DD)"].get().strip()
            end = entries["Fecha Fin (YYYY-MM-DD)"].get().strip()
            
            if name and obj:
                self.data_service.create_sprint(self.selected_project_id, name, obj, start, end)
                self.refresh_workspace()
                dialog.destroy()
        
        tk.Button(dialog, text="Crear Sprint", command=save, bg=self.style.get_color("accent"), 
                  fg="black", font=("Arial", 10, "bold"), bd=0, padx=20, pady=10).pack(pady=20)

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
