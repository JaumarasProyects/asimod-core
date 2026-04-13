import webview
import threading
import os
import time

class Viewer3DService:
    _instance = None
    
    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(Viewer3DService, cls).__new__(cls)
        return cls._instance

    def __init__(self, style_service=None):
        if hasattr(self, '_initialized'): return
        self.style = style_service
        self.window = None
        self._initialized = True
        self.html_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 
                                     "modules", "widgets", "3d_viewer.html")

    def open_viewer(self, model_path):
        """Abre el visor para un modelo específico."""
        if not os.path.exists(model_path):
            print(f"[3DViewer] Error: No existe el archivo {model_path}")
            return

        # Convertir ruta a formato URL para el WebView
        # En Windows, para cargar archivos locales en un WebView ( Three.js ), 
        # a veces es mejor servirlos o usar el esquema file://
        abs_path = os.path.abspath(model_path).replace("\\", "/")
        file_url = f"file:///{abs_path}"

        if self.window:
            try:
                self.window.evaluate_js(f"loadExternalModel('{file_url}')")
                self.window.show()
                return
            except:
                self.window = None # Reiniciar si se cerró

        # Si no hay ventana, crearla en un hilo aparte
        threading.Thread(target=self._launch_webview, args=(file_url,), daemon=True).start()

    def _launch_webview(self, initial_model_url):
        try:
            # Crear ventana
            self.window = webview.create_window(
                'ASIMOD 3D Viewer', 
                self.html_path,
                width=1000, height=800,
                background_color='#0b0f19'
            )
            
            # Al cargar, inyectar el modelo inicial
            def on_loaded():
                time.sleep(1) # Esperar a que Three.js inicialice
                self.window.evaluate_js(f"loadExternalModel('{initial_model_url}')")

            # Iniciar webview (esto bloquea el hilo pero estamos en uno aparte)
            webview.start(on_loaded, debug=True, gui='cef' if os.name == 'nt' else 'gtk')
        except Exception as e:
            print(f"[3DViewer] Error lanzando WebView: {e}")
            self.window = None

# Singleton expuesto
viewer_service = Viewer3DService()
