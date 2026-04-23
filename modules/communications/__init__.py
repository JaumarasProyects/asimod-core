import tkinter as tk
from tkinter import messagebox
import webbrowser
import os
import json
import sqlite3
from core.standard_module import StandardModule

class CommunicationsModule(StandardModule):
    """
    Módulo de Comunicaciones de ASIMOD.
    Gestiona contactos y accesos rápidos a servicios de mensajería y correo.
    """
    def __init__(self, chat_service, config_service, style_service, data_service=None):
        super().__init__(chat_service, config_service, style_service, data_service=data_service)
        self.name = "Comunicación"
        self.id = "communications"
        self.icon = "💬"
        self.has_web_ui = True
        
        # Configuración de Layout
        self.show_menu = True
        self.show_controllers = False
        self.show_gallery = True
        self.gallery_title = "CONTACTOS"
        self.menu_items = ["Mensajería", "Correo", "Redes"]
        
        self.current_mode = "Mensajería"
        self.selected_contact = None
        self.contacts = []
        
        # Cargar datos iniciales
        self._load_contacts()

    def _load_contacts(self):
        """Carga los contactos desde el DataService centralizado."""
        try:
            raw_contacts = self.data_service.get_contacts()
            self.contacts = []
            for c in raw_contacts:
                contact = dict(c)
                contact['social'] = json.loads(contact['social_json']) if contact['social_json'] else {}
                self.contacts.append(contact)
        except Exception as e:
            print(f"[Communications] Error cargando contactos: {e}")
            self.contacts = []

    def handle_get_gallery(self):
        """Genera la lista de contactos para la barra lateral web."""
        self._load_contacts()
        items = []
        for c in self.contacts:
            items.append({
                "id": c['id'],
                "title": c['name'],
                "subtitle": c.get('role', 'Contacto'),
                "type": "item",
                "icon": "👤",
                "callback_action": "handle_select_contact",
                "callback_params": {"contact_id": c['id']}
            })
        return {"items": items}

    async def handle_select_contact(self, contact_id: int):
        """Selecciona un contacto desde la web."""
        self._load_contacts()
        for c in self.contacts:
            if c['id'] == contact_id:
                self.selected_contact = c
                return {"status": "success", "contact": c}
        return {"status": "error", "message": "Contacto no encontrado"}

    async def handle_get_active_contact(self):
        """Retorna el contacto actualmente seleccionado."""
        if not self.selected_contact:
            # Seleccionar el primero por defecto si no hay uno
            self._load_contacts()
            if self.contacts:
                self.selected_contact = self.contacts[0]
        
        return {"status": "success", "contact": self.selected_contact}

    def render_workspace(self, parent):
        """Dibuja el área de comunicaciones."""
        self._refresh_gallery()
        
        if not self.selected_contact:
            if self.contacts:
                self.selected_contact = self.contacts[0]
            else:
                tk.Label(parent, text="Selecciona un contacto de la galería", 
                         bg=self.style.get_color("bg_main"), fg="#888").pack(pady=100)
                return

        # Header con info del contacto
        contact = self.selected_contact
        header_frame = tk.Frame(parent, bg=self.style.get_color("bg_main"))
        header_frame.pack(fill=tk.X, pady=(0, 20))
        
        tk.Label(header_frame, text=contact.get("name", "Contacto"), bg=self.style.get_color("bg_main"), fg=self.style.get_color("text_main"), 
                 font=("Arial", 18, "bold")).pack(side=tk.LEFT)
        
        # Contenedor de servicios
        services_frame = tk.Frame(parent, bg=self.style.get_color("bg_main"))
        services_frame.pack(fill=tk.BOTH, expand=True)
        
        self._render_service_cards(services_frame)

    def _render_service_cards(self, parent):
        mode = self.current_mode
        contact = self.selected_contact
        
        services = []
        if mode == "Mensajería":
            phone = contact.get("phone", "")
            if phone:
                services = [
                    ("WhatsApp", "💬", f"https://api.whatsapp.com/send?phone={phone}"),
                    ("Telegram", "✈️", "https://web.telegram.org"),
                    ("Discord", "🎮", "https://discord.com")
                ]
        elif mode == "Correo":
            email = contact.get("email", "")
            if email:
                services = [
                    ("Gmail", "📧", f"https://mail.google.com/mail/?view=cm&fs=1&to={email}"),
                    ("Outlook", "📨", f"mailto:{email}")
                ]
        elif mode == "Redes":
            social = contact.get("social", {})
            for plat, link in social.items():
                services.append((plat.title(), "🌐", link))

        if not services:
            tk.Label(parent, text=f"No hay servicios de {mode} disponibles para este contacto.", 
                     bg=self.style.get_color("bg_main"), fg="#666").pack(pady=50)
            return

        # Renderizar como grid
        for i, (s_name, icon, link) in enumerate(services):
            card = tk.Frame(parent, bg=self.style.get_color("bg_input"), padx=20, pady=20)
            card.pack(side=tk.LEFT, padx=10, pady=10)
            
            tk.Label(card, text=icon, font=("Arial", 32), bg=self.style.get_color("bg_input")).pack()
            tk.Label(card, text=s_name, font=("Arial", 11, "bold"), bg=self.style.get_color("bg_input"), fg="white").pack(pady=5)
            
            tk.Button(card, text="Abrir", bg=self.style.get_color("accent"), fg="white", bd=0, padx=10, 
                      command=lambda l=link: webbrowser.open(l)).pack(pady=5)

    def on_activate(self):
        self._load_contacts()
        self._refresh_gallery()

    def _refresh_gallery(self):
        if not self.gallery: return
        self.gallery.clear()
        for c in self.contacts:
            self.gallery.add_item(c['name'], c.get('role', ''), icon="👤", 
                                  callback=lambda data=c: self._select_contact(data))

    def _select_contact(self, data):
        self.selected_contact = data
        self.refresh_workspace()

    def on_menu_change(self, mode):
        self.current_mode = mode
        self.refresh_workspace()

def get_module_class():
    return CommunicationsModule
