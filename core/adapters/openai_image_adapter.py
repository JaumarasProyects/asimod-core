import httpx
import os
import time
from core.ports.image_port import ImagePort

class OpenAIImageAdapter(ImagePort):
    """
    Adaptador para generación de imágenes con OpenAI (DALL-E 3).
    """
    def __init__(self, api_key: str):
        self.api_key = api_key

    @property
    def name(self) -> str:
        return "DALL-E 3"

    async def generate_image(self, prompt: str, resolution: str = "1024x1024", **kwargs) -> str:
        if not self.api_key:
            return "Error: No se ha configurado la API Key de OpenAI."

        try:
            url = "https://api.openai.com/v1/images/generations"
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            # Determinar resolución
            w = kwargs.get("width")
            h = kwargs.get("height")
            if w and h:
                size = f"{w}x{h}"
            else:
                size = resolution

            payload = {
                "model": "dall-e-3",
                "prompt": prompt,
                "n": 1,
                "size": size,
                "response_format": "url" # DALL-E 3 suele devolver URL o b64_json
            }

            async with httpx.AsyncClient() as client:
                resp = await client.post(url, headers=headers, json=payload, timeout=60.0)
            
            if resp.status_code == 200:
                img_url = resp.json()["data"][0]["url"]
                
                # Descargar la imagen localmente
                output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "modules", "media_generator", "output")
                if not os.path.exists(output_dir):
                    os.makedirs(output_dir)
                
                filename = f"dalle_{int(time.time())}.png"
                local_path = os.path.join(output_dir, filename)
                
                async with httpx.AsyncClient() as client:
                    img_resp = await client.get(img_url, timeout=30.0)
                    if img_resp.status_code == 200:
                        with open(local_path, "wb") as f:
                            f.write(img_resp.content)
                        return local_path
                    else:
                        return f"Imagen generada, pero error al descargar: {img_url}"
            else:
                return f"Error OpenAI Image: {resp.status_code} - {resp.text}"

        except Exception as e:
            return f"Error en generación DALL-E: {str(e)}"
