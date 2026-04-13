import tkinter as tk
import random
import math
from core.ports.visualizer_port import VisualizerPort

class WaveformVisualizer(VisualizerPort):
    """
    Visualizador de forma de onda simple (Plugin Modular).
    Muestra una línea de onda blanca sobre fondo negro.
    """
    
    def __init__(self, parent: tk.Widget, width: int = 600, height: int = 60):
        super().__init__(parent, width, height)
        self.bar_count = 50
        self.bar_width = 0
        self.gap = 2
        self.animation_id = None
        self.phase = 0
        self.bars = []
        
    @property
    def name(self) -> str:
        return "Waveform"
    
    def _init_canvas(self):
        """Dibuja el estado estático inicial"""
        self.bar_width = (self.width - (self.bar_count - 1) * self.gap) / self.bar_count
        center_y = self.height / 2
        
        self.bars = []
        for i in range(self.bar_count):
            x = i * (self.bar_width + self.gap)
            bar = self._canvas.create_rectangle(
                x, center_y - 2,
                x + self.bar_width, center_y + 2,
                fill="#ffffff", outline=""
            )
            self.bars.append(bar)
    
    def start(self):
        """Inicia la animación de la onda"""
        if self.is_active:
            return
        self.is_active = True
        self._animate()
    
    def _animate(self):
        """Animación de la onda"""
        if not self.is_active:
            return
            
        center_y = self.height / 2
        max_amplitude = self.height / 2 - 5
        
        for i, bar in enumerate(self.bars):
            x = i * (self.bar_width + self.gap)
            
            wave1 = math.sin(self.phase + i * 0.3) * max_amplitude * 0.6
            wave2 = math.sin(self.phase * 1.5 + i * 0.5) * max_amplitude * 0.3
            wave3 = math.sin(self.phase * 0.7 + i * 0.2) * max_amplitude * 0.1
            
            amplitude = abs(wave1 + wave2 + wave3) + 3
            
            self._canvas.coords(
                bar,
                x, center_y - amplitude,
                x + self.bar_width, center_y + amplitude
            )
        
        self.phase += 0.15
        self.animation_id = self._canvas.after(30, self._animate)
    
    def stop(self):
        """Detiene la animación y vuelve al estado estático"""
        self.is_active = False
        if self.animation_id:
            self._canvas.after_cancel(self.animation_id)
            self.animation_id = None
        
        self._reset_bars()
    
    def _reset_bars(self):
        """Reinicia las barras al estado estático"""
        if not self._canvas or not self.bars:
            return
            
        center_y = self.height / 2
        for i, bar in enumerate(self.bars):
            x = i * (self.bar_width + self.gap)
            self._canvas.coords(
                bar,
                x, center_y - 2,
                x + self.bar_width, center_y + 2
            )
    
    def destroy(self):
        """Destruye el visualizador"""
        self.stop()
        super().destroy()
