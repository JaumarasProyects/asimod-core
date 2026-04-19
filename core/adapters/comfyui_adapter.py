import httpx
import json
import uuid
import os
import asyncio
import time
from core.ports.image_port import ImagePort

class ComfyUIAdapter(ImagePort):
    """
    Adaptador para generar imágenes usando ComfyUI (Local).
    """
    def __init__(self, base_url: str = "http://localhost:8188"):
        self.base_url = base_url
        self.client_id = str(uuid.uuid4())

    @property
    def name(self) -> str:
        return "ComfyUI"

    async def _upload_file(self, file_path):
        """Sube un archivo (Imagen/Audio/Video) al servidor de ComfyUI."""
        url = f"{self.base_url}/upload/image" # ComfyUI usa este endpoint para casi todo
        filename = os.path.basename(file_path)
        ext = os.path.splitext(filename)[1].lower()
        
        # Mapeo básico de mimetypes
        mime = "image/png"
        if ext in [".wav", ".mp3", ".ogg"]: mime = "audio/mpeg"
        elif ext in [".mp4", ".avi", ".mov"]: mime = "video/mp4"

        async with httpx.AsyncClient() as client:
            with open(file_path, "rb") as f:
                files = {"image": (filename, f, mime)}
                resp = await client.post(url, files=files, timeout=60.0)
                if resp.status_code == 200:
                    data = resp.json()
                    return data.get("name")
                else:
                    raise Exception(f"Error subiendo archivo a ComfyUI: {resp.text}")

    async def check_status(self) -> bool:
        """Verifica si ComfyUI está respondiendo en el puerto configurado."""
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(f"{self.base_url}/system_stats", timeout=2.0)
                return resp.status_code == 200
        except:
            return False

    async def generate_image(self, prompt: str, workflow_json: dict = None, **kwargs) -> str:
        """
        Envía un prompt a ComfyUI y espera por el resultado. 
        Si se pasa workflow_json, se usa; de lo contrario, falla.
        """
        if not workflow_json:
            return "Error: ComfyUI requiere un archivo de workflow (.json) para generar imágenes."

        try:
            # 0. Subir archivos si se proporcionan (Img2Img, Audio, Video)
            input_files = kwargs.get("input_images", []) # Mantenemos el nombre de la clave por compatibilidad
            server_filenames = []
            for path in input_files:
                if os.path.exists(path):
                    s_name = await self._upload_file(path)
                    server_filenames.append(s_name)
                    print(f"[ComfyUIAdapter] Archivo subido con éxito: {s_name}")

            # 1. Inyectar datos en el workflow JSON
            clean_workflow = {}
            for node_id, node_info in workflow_json.items():
                if isinstance(node_info, dict):
                    clean_workflow[node_id] = node_info.copy()
            
            if not clean_workflow:
                return "Error: El archivo de workflow no contiene ningún nodo válido."

            # 1. Escaneo inteligente de nodos y parámetros
            prompt_nodes = []
            resource_nodes = []
            
            target_width = kwargs.get("width")
            target_height = kwargs.get("height")
            
            for node_id, node_info in clean_workflow.items():
                inputs = node_info.get("inputs")
                if not isinstance(inputs, dict):
                    continue

                class_type = node_info.get("class_type")
                title = node_info.get("_meta", {}).get("title", "").lower()

                # Detectar diversos tipos de cargadores
                if class_type in ["LoadImage", "LoadAudio", "VHS_LoadVideo", "VideoLinearBatch"]:
                    resource_nodes.append((node_id, node_info))

                # Clasificar nodos de texto para inyección inteligente
                if class_type in ["CLIPTextEncode", "PrimitiveStringMultiline", "TextEncodeAceStepAudio1.5"]:
                    target_key = "tags" if class_type == "TextEncodeAceStepAudio1.5" else \
                                 "text" if "text" in inputs else "value" if "value" in inputs else None
                    
                    if target_key:
                        prompt_nodes.append({
                            "id": node_id,
                            "key": target_key,
                            "is_negative": "negative" in title,
                            "is_positive": "positive" in title
                        })

                # Inyectar Semilla (Seed) si existe en los argumentos
                seed = kwargs.get("seed")
                if seed is not None:
                    is_seed_node = "seed" in title or "semilla" in title
                    for s_key in ["seed", "noise_seed", "value"]:
                        if s_key in inputs:
                            if s_key == "value" and not is_seed_node: continue
                            try:
                                inputs[s_key] = int(seed)
                                print(f"[ComfyUIAdapter] Semilla {seed} inyectada en {node_id} ({title})")
                                break # Parar al inyectar en el primero válido
                            except: pass

                # Inyección de parámetros dinámicos extra
                # Detectamos por clave técnica O por título descriptivo para nodos 'Primitive'
                params_to_map = ["bpm", "duration", "lyrics", "seconds", "keyscale", "steps", "cfg"]
                for param_key in params_to_map:
                    if param_key in kwargs:
                        val = kwargs[param_key]
                        # 1. Intentar por clave técnica directa (o sinónimos como 'length' para video)
                        target_keys = [param_key]
                        if param_key == "duration": target_keys.extend(["length", "frame_count"])
                        
                        found_key = next((k for k in target_keys if k in inputs), None)
                        
                        if found_key:
                            try:
                                if param_key in ["bpm", "duration", "seconds", "steps", "cfg"]:
                                    val = float(val) if "." in str(val) else int(val)
                                    # Para 'length' o 'frame_count' en video asumiendo 24fps (estándar para Talking Heads/Avatares)
                                    if found_key in ["length", "frame_count"] and param_key == "duration":
                                        val = int(val * 24)
                                inputs[found_key] = val
                                print(f"[ComfyUIAdapter] Inyectado '{param_key}' en clave '{found_key}': {val} en {node_id}")
                            except: pass
                        # 2. Intentar por título (para nodos Primitive con clave 'value')
                        elif "value" in inputs and param_key in title:
                            try:
                                if param_key in ["bpm", "duration", "seconds", "steps", "cfg"]:
                                    val = float(val) if "." in str(val) else int(val)
                                inputs["value"] = val
                                print(f"[ComfyUIAdapter] Inyectado '{param_key}' via título en {node_id} ({title})")
                            except: pass

            # 2. Inyectar Prompt de forma inteligente (al finalizar el escaneo)
            target_node = next((n for n in prompt_nodes if n["is_positive"]), None)
            if not target_node:
                target_node = next((n for n in prompt_nodes if not n["is_negative"]), None)
            
            if target_node:
                clean_workflow[target_node["id"]]["inputs"][target_node["key"]] = prompt
                print(f"[ComfyUIAdapter] Prompt ('{prompt[:30]}...') inyectado en {target_node['id']}")
            
            # 3. Inyectar Prompt Negativo
            negative_prompt = kwargs.get("negative_prompt")
            if negative_prompt:
                neg_node = next((n for n in prompt_nodes if n["is_negative"]), None)
                if neg_node:
                    clean_workflow[neg_node["id"]]["inputs"][neg_node["key"]] = negative_prompt
                    print(f"[ComfyUIAdapter] Negative Prompt inyectado en {neg_node['id']}")

            # 2. Inyectar archivos subidos en los nodos de carga (Mapeo secuencial)
            for i, (node_id, node_info) in enumerate(resource_nodes):
                if i < len(server_filenames):
                    inputs = node_info["inputs"]
                    # ComfyUI suele usar 'image', 'audio', o 'video' como clave de entrada
                    target_key = "image" if "image" in inputs else "audio" if "audio" in inputs else "video" if "video" in inputs else None
                    if not target_key:
                         # Fallback for custom nodes
                         keys = list(inputs.keys())
                         if keys: target_key = keys[0] 

                    if target_key:
                        inputs[target_key] = server_filenames[i]
                        print(f"[ComfyUIAdapter] Archivo {server_filenames[i]} inyectado en {node_id} ({node_info['class_type']})")

            # Inyectar Dimensiones (Width/Height)
            for node_id, node_info in clean_workflow.items():
                inputs = node_info.get("inputs")
                if not isinstance(inputs, dict):
                    continue
                
                # Inyectamos dimensiones independientemente de si hay imágenes de entrada 
                # (Muy necesario para flujos Image-to-Video)
                if target_width and "width" in inputs:
                    try:
                        inputs["width"] = int(target_width)
                        print(f"[ComfyUIAdapter] Ancho ({target_width}) inyectado en el nodo {node_id}")
                    except: pass
                
                if target_height and "height" in inputs:
                    try:
                        inputs["height"] = int(target_height)
                        print(f"[ComfyUIAdapter] Alto ({target_height}) inyectado en el nodo {node_id}")
                    except: pass


            # 2. Enviar prompt
            p = {"prompt": clean_workflow, "client_id": self.client_id}
            url = f"{self.base_url}/prompt"

            async with httpx.AsyncClient() as client:
                resp = await client.post(url, json=p, timeout=30.0)
                if resp.status_code != 200:
                    return f"Error ComfyUI al enviar prompt: {resp.status_code} - {resp.text}"
                
                data = resp.json()
                prompt_id = data.get("prompt_id")
                print(f"[ComfyUIAdapter] Tarea enviada. Prompt ID: {prompt_id}. Esperando resultado...")

            # 3. Polling para obtener el resultado
            timeout = 7200 # 2 horas (para workflows de video o muy pesados)
            start_time = time.time()
            
            async with httpx.AsyncClient() as client:
                while (time.time() - start_time) < timeout:
                    hist_resp = await client.get(f"{self.base_url}/history/{prompt_id}")
                    if hist_resp.status_code == 200:
                        history = hist_resp.json()
                        if prompt_id in history:
                            print(f"[ComfyUIAdapter] Tarea {prompt_id} finalizada.")
                            return await self._download_results(history[prompt_id])
                    
                    await asyncio.sleep(2)
            
            return f"Timeout: La generación en ComfyUI tardó demasiado. ID: {prompt_id}"

        except Exception as e:
            import traceback
            traceback.print_exc()
            return f"Error de conexión con ComfyUI: {str(e)}"

    async def _download_results(self, history_entry: dict) -> list:
        """Descarga todas las imágenes resultantes de la historia de ComfyUI."""
        outputs = history_entry.get("outputs", {})
        image_info_list = []

        for node_id, node_output in outputs.items():
            # Escaneo agresivo de todos los campos de salida para buscar archivos
            for key, value in node_output.items():
                if isinstance(value, list):
                    for item in value:
                        if isinstance(item, dict) and "filename" in item:
                            image_info_list.append(item)
                        elif isinstance(item, str) and (item.endswith(".glb") or item.endswith(".obj")):
                            # Algunos nodos devuelven solo el string del nombre
                            image_info_list.append(item)
        
        if not image_info_list:
            return ["Error: No se encontraron resultados (Imagen/Audio/Video) en ComfyUI."]

        # Preparar directorios base
        adapter_file = os.path.abspath(__file__)
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(adapter_file)))
        base_output = os.path.join(project_root, "modules", "media_generator", "output")
        
        # Mapeo de extensiones a carpetas de salida
        ext_map = {
            ".mp3": "audio", ".wav": "audio", ".flac": "audio", ".ogg": "audio",
            ".mp4": "video", ".mov": "video", ".gif": "video", ".webm": "video",
            ".png": "imagen", ".jpg": "imagen", ".jpeg": "imagen", ".bmp": "imagen", ".webp": "imagen",
            ".glb": "3d", ".obj": "3d", ".stl": "3d", ".ply": "3d"
        }

        downloaded_paths = []

        async with httpx.AsyncClient() as client:
            for img_info in image_info_list:
                # Soporte para diferentes formatos de metadata (algunos nodos 3D devuelven strings)
                if isinstance(img_info, str):
                    filename = img_info
                    subfolder = ""
                    folder_type = "output"
                else:
                    filename = img_info.get("filename", "")
                    subfolder = img_info.get("subfolder", "")
                    folder_type = img_info.get("type", "output")
                
                if not filename: continue
                
                # Determinar carpeta de destino según extensión
                _, ext = os.path.splitext(filename.lower())
                sub_dir = ext_map.get(ext, "imagen")
                output_dir = os.path.join(base_output, sub_dir)
                os.makedirs(output_dir, exist_ok=True)

                view_url = f"{self.base_url}/view?filename={filename}&subfolder={subfolder}&type={folder_type}"
                
                local_filename = f"comfy_{int(time.time())}_{filename}"
                local_path = os.path.join(output_dir, local_filename)

                resp = await client.get(view_url, timeout=30.0)
                if resp.status_code == 200:
                    with open(local_path, "wb") as f:
                        f.write(resp.content)
                    print(f"[ComfyUIAdapter] Imagen descargada: {local_path}")
                    downloaded_paths.append(local_path)
                else:
                    print(f"[ComfyUIAdapter] Error descargando {filename}: {resp.status_code}")

        return downloaded_paths if downloaded_paths else ["Error: No se pudo descargar ninguna imagen de ComfyUI."]
