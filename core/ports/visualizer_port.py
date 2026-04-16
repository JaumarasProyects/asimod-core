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
        """Crea el frame del visualizador con soporte para texturas de fondo"""
        # Intentar obtener el style_service desde el parent (algunos widgets lo guardan)
        style = getattr(parent, 'style', None)
        
        from ui.background_frame import BackgroundFrame
        if style:
            self._frame = BackgroundFrame(parent, style, "button")
            self._frame.config(height=self.height)
        else:
            bg_color = parent.cget("bg")
            self._frame = tk.Frame(parent, bg=bg_color, height=self.height)
            
        self._frame.pack(fill=tk.X)
        self._frame.pack_propagate(False)
        
        # El canvas debe ser transparente si el fondo es una imagen
        # (Tkinter no soporta transparencia real fácil, pero simulamos con el mismo color o intentamos)
        bg_canvas = self._frame.cget("bg") if not style else "#000000" 
        # Si hay imagen de fondo en el Frame (Canvas), el canvas hijo tapará. 
        # En Tkinter, lo ideal es dibujar directamente en el Canvas del BackgroundFrame.
        
        if style and isinstance(self._frame, BackgroundFrame):
            # Usamos el propio canvas del BackgroundFrame para el visualizador
            self._canvas = self._frame
            self._init_canvas()
        else:
            self._canvas = tk.Canvas(
                self._frame, 
                width=self.width, 
                height=self.height, 
                bg=bg_canvas, 
                highlightthickness=0
            )
            self._canvas.pack(fill=tk.BOTH, expand=True)
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
