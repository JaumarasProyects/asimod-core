import tkinter as tk
import numpy as np
import struct
import json
import os

class Internal3DRenderer(tk.Canvas):
    """
    Motor de renderizado 3D por software integrado para Tkinter.
    Permite visualizar mallas 3D (.glb, .obj) sin dependencias externas.
    """
    def __init__(self, parent, **kwargs):
        self.bg_color = kwargs.get("bg", "#0b0f19")
        super().__init__(parent, **kwargs)
        
        self.vertices = None
        self.faces = None
        
        # Estado de la cámara
        self.angle_x = 0
        self.angle_y = 0
        self.scale = 1.0
        self.last_x = 0
        self.last_y = 0
        
        # Colores
        self.wire_color = "#00aaff"
        self.surface_color = "#1a2a4a"
        
        # Eventos
        self.bind("<Button-1>", self._on_click)
        self.bind("<B1-Motion>", self._on_drag)
        self.bind("<MouseWheel>", self._on_zoom)
        self.bind("<Configure>", lambda e: self.render())

    def load_model(self, path):
        """Carga el modelo dependiendo de la extensión."""
        ext = os.path.splitext(path)[1].lower()
        try:
            if ext == ".glb":
                self._load_glb(path)
            elif ext == ".obj":
                self._load_obj(path)
            self._center_and_normalize()
            self.render()
        except Exception as e:
            print(f"[3DRenderer] Error cargando modelo: {e}")

    def _load_glb(self, path):
        """Parser básico de archivos GLB binarios."""
        with open(path, "rb") as f:
            # Header
            magic = f.read(4)
            if magic != b'glTF': return
            version = struct.unpack("<I", f.read(4))[0]
            length = struct.unpack("<I", f.read(4))[0]
            
            # Chunk 0: JSON
            chunk_length = struct.unpack("<I", f.read(4))[0]
            chunk_type = f.read(4)
            if chunk_type != b'JSON': return
            
            json_data = json.loads(f.read(chunk_length).decode('utf-8'))
            
            # Chunk 1: BIN
            chunk_length = struct.unpack("<I", f.read(4))[0]
            chunk_type = f.read(4)
            bin_data = f.read(chunk_length)
            
            # Buscar accesores de posición e índices
            # (Asunción: Hunyuan3D suele usar el primer mesh)
            mesh = json_data.get("meshes", [{}])[0]
            primitive = mesh.get("primitives", [{}])[0]
            
            pos_acc_idx = primitive.get("attributes", {}).get("POSITION")
            idx_acc_idx = primitive.get("indices")
            
            if pos_acc_idx is None: return
            
            # Extraer vértices
            pos_acc = json_data["accessors"][pos_acc_idx]
            pos_bv = json_data["bufferViews"][pos_acc["bufferView"]]
            offset = pos_bv.get("byteOffset", 0) + pos_acc.get("byteOffset", 0)
            count = pos_acc["count"]
            self.vertices = np.frombuffer(bin_data, dtype=np.float32, count=count*3, offset=offset).reshape(-1, 3).copy()
            
            # Extraer índices (caras)
            if idx_acc_idx is not None:
                idx_acc = json_data["accessors"][idx_acc_idx]
                idx_bv = json_data["bufferViews"][idx_acc["bufferView"]]
                offset = idx_bv.get("byteOffset", 0) + idx_acc.get("byteOffset", 0)
                count = idx_acc["count"]
                
                # Determinar tipo de dato de índice (5123=ushort, 5125=uint)
                dtype = np.uint16 if idx_acc["componentType"] == 5123 else np.uint32
                self.faces = np.frombuffer(bin_data, dtype=dtype, count=count, offset=offset).reshape(-1, 3).copy()
            else:
                # Triangle soup: los vértices ya vienen en orden para formar triángulos
                count = len(self.vertices)
                if count % 3 == 0:
                    self.faces = np.arange(count, dtype=np.uint32).reshape(-1, 3)

    def _load_obj(self, path):
        """Parser básico de archivos OBJ."""
        verts = []
        faces = []
        with open(path, "r") as f:
            for line in f:
                parts = line.split()
                if not parts: continue
                if parts[0] == "v":
                    verts.append([float(parts[1]), float(parts[2]), float(parts[3])])
                elif parts[0] == "f":
                    # Simplificar a triángulos
                    f_idxs = [int(p.split("/")[0]) - 1 for p in parts[1:4]]
                    faces.append(f_idxs)
        self.vertices = np.array(verts, dtype=np.float32)
        self.faces = np.array(faces, dtype=np.uint32)

    def _center_and_normalize(self):
        """Centra el modelo y lo escala para que quepa en la vista."""
        if self.vertices is None: return
        
        # Centrar
        center = np.mean(self.vertices, axis=0)
        self.vertices -= center
        
        # Escalar
        max_dist = np.max(np.linalg.norm(self.vertices, axis=1))
        if max_dist > 0:
            self.vertices /= max_dist

    def render(self):
        """Renderiza la malla actual con sombreado plano y profundidad."""
        self.delete("all")
        if self.vertices is None: return
        
        w = self.winfo_width()
        h = self.winfo_height()
        if w < 10: return
        
        # 1. Matrices de rotación
        rx, ry = self.angle_x, self.angle_y
        rot_y = np.array([[np.cos(ry), 0, np.sin(ry)], [0, 1, 0], [-np.sin(ry), 0, np.cos(ry)]])
        rot_x = np.array([[1, 0, 0], [0, np.cos(rx), -np.sin(rx)], [0, np.sin(rx), np.cos(rx)]])
        
        # Transformar vértices (Rotación)
        transformed = self.vertices @ rot_y.T @ rot_x.T
        
        # 2. Proyección perspectiva
        z_offset = 3.5
        z = transformed[:, 2] + z_offset
        z[z < 0.1] = 0.1
        factor = (w / 2.2) * self.scale
        projected = transformed[:, :2] * (factor / z[:, None])
        projected[:, 0] += w / 2
        projected[:, 1] += h / 2

        # 3. Dibujar (Sólido con Sombreado Optimizado)
        if self.faces is not None:
            face_count = len(self.faces)
            
            # Limite para mantener interactividad razonable (~10k polígonos)
            limit = 10000
            stride = 1 if face_count < limit else (face_count // limit)
            
            # Submuestreo vectorizado de datos
            sampled_faces = self.faces[::stride]
            v_faces = transformed[sampled_faces]
            
            # Cálculo de normales y brillo vectorizado
            v10 = v_faces[:, 1] - v_faces[:, 0]
            v20 = v_faces[:, 2] - v_faces[:, 0]
            normals = np.cross(v10, v20)
            norm = np.linalg.norm(normals, axis=1, keepdims=True)
            norm[norm == 0] = 1.0
            normals /= norm
            
            light_dir = np.array([0.5, 0.5, 1.0])
            light_dir /= np.linalg.norm(light_dir)
            brightness = np.clip(np.sum(normals * light_dir, axis=1), 0.1, 1.0)
            z_mid = np.mean(v_faces[:, :, 2], axis=1)
            
            # Ordenar por profundidad (Pintor)
            indices = np.argsort(z_mid)
            
            # Color base (Azul ASIMOD)
            base_color = [0, 170, 255]
            
            # Culling - Caras mirando hacia adelante
            visible_mask = normals[:, 2] > -0.1
            
            for i in indices:
                if not visible_mask[i]: continue
                
                # Sombreado suave
                b = brightness[i]
                c = f"#{int(base_color[0]*b):02x}{int(base_color[1]*b):02x}{int(base_color[2]*b):02x}"
                
                # DIBUJO "FUSION": outline=c y width=1 (o width=0) para que no se vean huecos
                # Al dibujar el borde del mismo color que el relleno, los triángulos se tocan
                pts = projected[sampled_faces[i]].flatten().tolist()
                self.create_polygon(pts, fill=c, outline=c, width=1, tags="mesh")
        else:
            # Caso de nube de puntos si no hay caras (siempre muestreada)
            limit = 15000
            stride = 1 if len(projected) < limit else (len(projected) // limit)
            for i in range(0, len(projected), stride):
                p = projected[i]
                self.create_rectangle(p[0], p[1], p[0]+1, p[1]+1, fill=self.wire_color, outline="", tags="mesh")

    def _on_click(self, event):
        self.last_x = event.x
        self.last_y = event.y

    def _on_drag(self, event):
        dx = event.x - self.last_x
        dy = event.y - self.last_y
        
        self.angle_y += dx * 0.01
        self.angle_x += dy * 0.01
        
        self.last_x = event.x
        self.last_y = event.y
        self.render()

    def _on_zoom(self, event):
        if event.delta > 0:
            self.scale *= 1.1
        else:
            self.scale *= 0.9
        self.render()
