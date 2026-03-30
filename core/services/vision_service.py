import os
import time
import atexit
from pathlib import Path
from tkinter import filedialog

try:
    import cv2
except ImportError:
    cv2 = None

try:
    from PIL import ImageGrab
except ImportError:
    ImageGrab = None

class VisionService:
    """
    Servicio encargado de capturar imágenes desde la webcam, 
    pantallazos o selección de archivos para el contexto visual.
    """
    def __init__(self, output_dir="output/vision"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        # Limpieza automática al salir del programa
        atexit.register(self.clear_all_captures)

    def _gen_path(self, prefix: str) -> str:
        """Genera una ruta de archivo única."""
        ts = time.strftime("%Y%m%d_%H%M%S")
        return str(self.output_dir / f"{prefix}_{ts}.jpg")

    def capture_cam(self) -> str:
        """Captura una foto de la webcam predeterminada."""
        if cv2 is None:
            print("[Vision] Error: OpenCV no instalado.")
            return None
        
        # En Windows DSHOW es mucho más rápido para abrir la cámara
        cap = cv2.VideoCapture(0, cv2.CAP_DSHOW) if os.name == 'nt' else cv2.VideoCapture(0)
        if not cap.isOpened():
            print("[Vision] Error: No se pudo abrir la webcam.")
            return None

        # Descartar los primeros frames para permitir el auto-enfoque/exposición
        frame = None
        for _ in range(10):
            ret, frame = cap.read()
            time.sleep(0.05)
        
        cap.release()

        if frame is not None:
            path = self._gen_path("cam")
            cv2.imwrite(path, frame)
            return os.path.abspath(path)
        return None

    def capture_screen(self) -> str:
        """Captura un pantallazo de la pantalla principal."""
        if ImageGrab is None:
            print("[Vision] Error: Pillow (ImageGrab) no instalado.")
            return None
        
        try:
            path = self._gen_path("screen")
            screenshot = ImageGrab.grab()
            screenshot = screenshot.convert("RGB")
            screenshot.save(path, "JPEG", quality=85)
            return os.path.abspath(path)
        except Exception as e:
            print(f"[Vision] Error capturando pantalla: {e}")
            return None

    def pick_image(self) -> str:
        """Abre un diálogo de sistema para seleccionar una imagen existente."""
        path = filedialog.askopenfilename(
            filetypes=[("Imágenes", "*.jpg *.png *.jpeg *.webp")]
        )
        return os.path.abspath(path) if path else None

    def clear_all_captures(self):
        """Elimina todos los archivos en la carpeta de capturas temporales."""
        try:
            for file in self.output_dir.glob("*"):
                if file.is_file():
                    file.unlink()
            print(f"[Vision] Limpieza de temporales completada en {self.output_dir}")
        except Exception as e:
            print(f"[Vision] Error en limpieza: {e}")
