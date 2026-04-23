from abc import ABC, abstractmethod
import tkinter as tk


class VisualizerPort(ABC):
    """
    Puerto abstracto para visualizadores de audio.
    Permite implementar diferentes tipos de visualizadores (waveform, espectro, etc.)
    """
    
    def __init__(self, parent: tk.Widget, width: int = 600, height: int = 60):
        self.parent = parent
        self.width = width
        self.height = height
        self.is_active = False
        self._frame = None
        self._canvas = None
        
    @property
    @abstractmethod
    def name(self) -> str:
        """Nombre del visualizador"""
        pass
    
    def create(self, parent: tk.Widget) -> tk.Frame:
        """Crea el contenedor base y el canvas del visualizador"""
        self.style = getattr(parent, 'style', None)
        
        # 1. SIEMPRE crear un Frame contenedor base
        # Usamos el color de fondo del tema para que, aunque no haya transparencia real en Tkinter,
        # el hueco coincida con el tono de la madera/pergamino.
        bg_color = self.style.get_color("bg_main") if self.style else parent.cget("bg")
        self._frame = tk.Frame(parent, bg=bg_color)
        
        # El frame se expande horizontalmente
        self._frame.pack(fill=tk.X)
        
        # 2. Crear el Canvas (o BackgroundFrame) como hijo del Frame
        from ui.background_frame import BackgroundFrame
        
        if self.style:
            # Usamos BackgroundFrame como hijo si hay estilo
            # Cambiamos "button" por "chat" para mayor consistencia con el panel de chat
            self._canvas = BackgroundFrame(self._frame, self.style, "chat", height=self.height)
            self._canvas.pack(fill=tk.X)
        else:
            bg_canvas = bg_color
            self._canvas = tk.Canvas(
                self._frame, 
                width=self.width, 
                height=self.height, 
                bg=bg_canvas, 
                highlightthickness=0
            )
            self._canvas.pack(fill=tk.X)
            
        # Inicializar el contenido del canvas
        self._init_canvas()
            
        return self._frame
    
    @abstractmethod
    def _init_canvas(self):
        """Inicializa el canvas (dibuja estado estático)"""
        pass
    
    @abstractmethod
    def start(self):
        """Inicia la animación del visualizador"""
        self.is_active = True
    
    @abstractmethod
    def stop(self):
        """Detiene la animación del visualizador"""
        self.is_active = False
    
    def destroy(self):
        """Destruye el visualizador"""
        self.is_active = False
        if self._frame:
            self._frame.destroy()
            self._frame = None
            self._canvas = None
    
    def on_audio_start(self):
        """Callback cuando empieza audio"""
        self.start()
    
    def on_audio_end(self):
        """Callback cuando termina audio"""
        self.stop()

    def set_character(self, character_data: dict):
        """
        Establece los datos del personaje actual para el visualizador.
        Debe ser implementado por visualizadores que necesiten esta info (ej. Avatares).
        """
        pass
