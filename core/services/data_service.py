import sqlite3
import os
from datetime import datetime
from typing import List, Dict, Optional, Any

class DataService:
    """
    Servicio centralizado para la gestión de datos persistentes (SQLite).
    Combina las funcionalidades de DatabaseManager y Repository del proyecto original.
    """
    def __init__(self, config_service):
        self.config_service = config_service
        # Por defecto, usar app_data.db en la raíz del proyecto
        self.db_path = os.path.join(os.getcwd(), "app_data.db")
        self._initialize_db()

    def _get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _execute_query(self, query: str, params: tuple = (), fetch_one: bool = False, fetch_all: bool = False, commit: bool = False) -> Any:
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(query, params)
            if commit:
                conn.commit()
            
            if fetch_one:
                row = cursor.fetchone()
                return dict(row) if row else None
            if fetch_all:
                return [dict(row) for row in cursor.fetchall()]
            return cursor.lastrowid
        except Exception as e:
            print(f"[DataService] Error en base de datos: {e}")
            return None
        finally:
            conn.close()

    def _initialize_db(self):
        """Crea las tablas necesarias para todos los módulos migrados."""
        conn = self._get_connection()
        cursor = conn.cursor()

        # Proyectos
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                status TEXT DEFAULT 'active',
                root_folder TEXT,
                is_active INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Tareas de Proyecto
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS project_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER,
                title TEXT NOT NULL,
                status TEXT DEFAULT 'pending', -- pending, in_progress, completed
                content TEXT,
                sort_order INTEGER DEFAULT 0,
                start_date TEXT,
                end_date TEXT,
                FOREIGN KEY (project_id) REFERENCES projects (id)
            )
        """)

        # Sprints
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sprints (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER,
                name TEXT NOT NULL,
                objective TEXT,
                start_date TEXT,
                end_date TEXT,
                status TEXT DEFAULT 'planned', -- planned, active, completed
                FOREIGN KEY (project_id) REFERENCES projects (id)
            )
        """)

        # Hitos de Sprint
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sprint_milestones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sprint_id INTEGER,
                title TEXT NOT NULL,
                is_completed INTEGER DEFAULT 0,
                FOREIGN KEY (sprint_id) REFERENCES sprints (id)
            )
        """)

        # Logs de Salud / Estadísticas
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS health_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                category TEXT NOT NULL, -- 'exercise', 'nutrition', 'sleep', 'weight', etc.
                value REAL NOT NULL,
                unit TEXT,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Mensajes de Chat (Histórico)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS chat_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Lista de la Compra / Tareas rápidas
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS shopping_list (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item TEXT NOT NULL,
                is_suggestion INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Notas Rápidas
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                content TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Contactos (Migración de Communications)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS contacts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                role TEXT,
                email TEXT,
                phone TEXT,
                social_json TEXT, -- Almacenará un JSON con redes sociales
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.commit()
        conn.close()
        print(f"[DataService] Base de datos inicializada en {self.db_path}")
        
        # Auto-seed
        self.seed_sample_project()
        self.seed_sample_contacts()

    # --- API PARA PROYECTOS ---
    def get_all_projects(self) -> List[Dict]:
        return self._execute_query("SELECT * FROM projects ORDER BY created_at DESC", fetch_all=True)

    def get_project_details(self, project_id: int) -> Dict:
        return self._execute_query("SELECT * FROM projects WHERE id = ?", (project_id,), fetch_one=True)

    def create_project(self, name: str, description: str = "") -> int:
        # Desactivar otros para que el nuevo sea el activo
        self._execute_query("UPDATE projects SET is_active = 0", commit=True)
        return self._execute_query(
            "INSERT INTO projects (name, description, is_active) VALUES (?, ?, 1)",
            (name, description),
            commit=True
        )

    def set_active_project(self, project_id: int):
        self._execute_query("UPDATE projects SET is_active = 0", commit=True)
        self._execute_query("UPDATE projects SET is_active = 1 WHERE id = ?", (project_id,), commit=True)

    def get_active_project(self) -> Optional[Dict]:
        return self._execute_query("SELECT * FROM projects WHERE is_active = 1", fetch_one=True)

    def get_project_items(self, project_id: int) -> List[Dict]:
        return self._execute_query("SELECT * FROM project_items WHERE project_id = ? ORDER BY id DESC", (project_id,), fetch_all=True)

    def add_project_item(self, project_id: int, title: str, status: str = "pending"):
        return self._execute_query(
            "INSERT INTO project_items (project_id, title, status) VALUES (?, ?, ?)",
            (project_id, title, status),
            commit=True
        )

    def delete_project_item(self, item_id: int):
        return self._execute_query("DELETE FROM project_items WHERE id = ?", (item_id,), commit=True)

    def update_project_item_status(self, item_id: int, status: str):
        return self._execute_query(
            "UPDATE project_items SET status = ? WHERE id = ?",
            (status, item_id),
            commit=True
        )

    def update_project_item_dates(self, item_id: int, start_date: str, end_date: str):
        return self._execute_query(
            "UPDATE project_items SET start_date = ?, end_date = ? WHERE id = ?",
            (start_date, end_date, item_id),
            commit=True
        )

    # --- API PARA SPRINTS ---
    def get_project_sprints(self, project_id: int) -> List[Dict]:
        return self._execute_query("SELECT * FROM sprints WHERE project_id = ? ORDER BY start_date DESC", (project_id,), fetch_all=True)

    def get_active_sprint(self, project_id: int) -> Optional[Dict]:
        return self._execute_query("SELECT * FROM sprints WHERE project_id = ? AND status = 'active'", (project_id,), fetch_one=True)

    def create_sprint(self, project_id: int, name: str, objective: str, start_date: str, end_date: str):
        # Desactivar otros sprints activos para este proyecto
        self._execute_query("UPDATE sprints SET status = 'completed' WHERE project_id = ? AND status = 'active'", (project_id,), commit=True)
        return self._execute_query(
            "INSERT INTO sprints (project_id, name, objective, start_date, end_date, status) VALUES (?, ?, ?, ?, ?, 'active')",
            (project_id, name, objective, start_date, end_date),
            commit=True
        )

    def seed_sample_project(self):
        """Siembra un proyecto de ejemplo completo si no hay proyectos."""
        if self._execute_query("SELECT COUNT(*) FROM projects", fetch_one=True)['COUNT(*)'] > 0:
            return

        pid = self.create_project("ASIMOD Core Expansion", "Desarrollo de nuevas capacidades cognitivas y módulos de UI.")
        
        # Tareas
        tasks = [
            ("Diseñar Interfaz Kanban", "in_progress", "2026-04-20", "2026-04-25"),
            ("Implementar SQLite para Proyectos", "completed", "2026-04-15", "2026-04-18"),
            ("Refactorizar DataService", "completed", "2026-04-10", "2026-04-14"),
            ("Integrar Gráficos Gantt", "pending", "2026-04-26", "2026-05-02"),
            ("Optimizar Carga de Módulos", "pending", "2026-05-01", "2026-05-05")
        ]
        for title, status, start, end in tasks:
            self._execute_query(
                "INSERT INTO project_items (project_id, title, status, start_date, end_date) VALUES (?, ?, ?, ?, ?)",
                (pid, title, status, start, end),
                commit=True
            )

        # Sprints
        self.create_sprint(pid, "Sprint 1: Cimientos", "Establecer la base de datos y estructura de servicios.", "2026-04-10", "2026-04-24")
        self._execute_query(
            "INSERT INTO sprints (project_id, name, objective, start_date, end_date, status) VALUES (?, ?, ?, ?, ?, ?)",
            (pid, "Sprint 0: Setup", "Configuración inicial del entorno.", "2026-04-01", "2026-04-09", "completed"),
            commit=True
        )

    # --- API PARA SALUD ---
    def add_health_log(self, category: str, value: float, unit: str = "", notes: str = "", date: str = None):
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")
        return self._execute_query(
            "INSERT INTO health_logs (date, category, value, unit, notes) VALUES (?, ?, ?, ?, ?)",
            (date, category, value, unit, notes),
            commit=True
        )

    def get_health_logs(self, category: str = None, days: int = 7) -> List[Dict]:
        if category:
            query = "SELECT * FROM health_logs WHERE category = ? AND date >= date('now', ?) ORDER BY date ASC"
            return self._execute_query(query, (category, f'-{days} days'), fetch_all=True)
        else:
            query = "SELECT * FROM health_logs WHERE date >= date('now', ?) ORDER BY date ASC"
            return self._execute_query(query, (f'-{days} days',), fetch_all=True)

    # --- API PARA NOTAS/UTILIDADES ---
    def get_all_notes(self) -> List[Dict]:
        return self._execute_query("SELECT * FROM notes ORDER BY updated_at DESC", fetch_all=True)

    def save_note(self, title: str, content: str, note_id: int = None):
        if note_id:
            return self._execute_query(
                "UPDATE notes SET title = ?, content = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (title, content, note_id),
                commit=True
            )
        else:
            return self._execute_query(
                "INSERT INTO notes (title, content) VALUES (?, ?)",
                (title, content),
                commit=True
            )

    def delete_note(self, note_id: int):
        return self._execute_query("DELETE FROM notes WHERE id = ?", (note_id,), commit=True)

    # --- API PARA CONTACTOS ---
    def get_contacts(self) -> List[Dict]:
        return self._execute_query("SELECT * FROM contacts ORDER BY name ASC", fetch_all=True)

    def add_contact(self, name: str, role: str, email: str, phone: str, social: dict):
        import json
        return self._execute_query(
            "INSERT INTO contacts (name, role, email, phone, social_json) VALUES (?, ?, ?, ?, ?)",
            (name, role, email, phone, json.dumps(social)),
            commit=True
        )

    def seed_sample_contacts(self):
        """Siembra contactos de ejemplo si no hay ninguno."""
        if self._execute_query("SELECT COUNT(*) FROM contacts", fetch_one=True)['COUNT(*)'] > 0:
            return
        
        import json
        demo_contacts = [
            ("Elena Rodríguez", "Directora Creativa", "elena.rodriguez@creativa.es", "+34612345678", 
             {"instagram": "https://instagram.com", "linkedin": "https://linkedin.com"}),
            ("Marco Janssen", "Senior Developer", "m.janssen@techcorp.nl", "+31622334455", 
             {"github": "https://github.com", "discord": "https://discord.com"}),
            ("Sofía Chen", "Analista de Datos", "schen@datacorp.cn", "+8613812345678", 
             {"weibo": "https://weibo.com"}),
            ("Lucas Miller", "Asesor Financiero", "lucas.miller@wealth.us", "+15550123456", 
             {"twitter": "https://twitter.com", "facebook": "https://facebook.com"}),
            ("Yuki Tanaka", "Artista Conceptual", "yuki.art@studio.jp", "+819012345678", 
             {"artstation": "https://artstation.com", "discord": "https://discord.com"})
        ]
        for name, role, email, phone, social in demo_contacts:
            self.add_contact(name, role, email, phone, social)
