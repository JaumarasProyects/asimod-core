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
        """Crea el frame del visualizador"""
        self._frame = tk.Frame(parent, bg="#000000", height=self.height)
        self._frame.pack(fill=tk.X)
        self._frame.pack_propagate(False)
        
        self._canvas = tk.Canvas(
            self._frame, 
            width=self.width, 
            height=self.height, 
            bg="#000000", 
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
