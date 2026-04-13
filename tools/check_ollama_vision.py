import requests
import json

def check_vision():
    base_url = "http://localhost:11434"
    try:
        # 1. Obtener lista de modelos
        tags_res = requests.get(f"{base_url}/api/tags", timeout=5)
        if tags_res.status_code != 200:
            print(f"Error conectando a Ollama: {tags_res.status_code}")
            return
        
        models = tags_res.json().get("models", [])
        vision_models = []
        
        print(f"Buscando modelos con visión en {len(models)} modelos de Ollama...\n")
        
        for m in models:
            m_name = m["name"]
            # 2. Consultar detalles de cada modelo
            show_payload = {"name": m_name}
            show_res = requests.post(f"{base_url}/api/show", json=show_payload, timeout=5)
            
            if show_res.status_code == 200:
                details = show_res.json()
                # Verificar 'modality' o menciones en el sistema
                projector = details.get("projector_info", None)
                model_info = details.get("model_info", {})
                
                # Criterios para visión:
                # - Tiene información de proyector (vision projector)
                # - El formato es multimodal
                # - El nombre contiene 'llava', 'vision', 'moondream'
                is_vision = False
                if projector:
                    is_vision = True
                
                if "vision" in m_name.lower() or "llava" in m_name.lower() or "moondream" in m_name.lower():
                    is_vision = True
                
                # Algunos modelos nuevos usan un campo 'details' -> 'families'
                families = details.get("details", {}).get("families", [])
                if families and any("vision" in f.lower() for f in families):
                    is_vision = True
                
                if is_vision:
                    vision_models.append(m_name)
                    print(f"[✓] {m_name}: Soporta VISIÓN")
                else:
                    print(f"[ ] {m_name}: Solo Texto")
        
        print("\nRESUMEN:")
        if vision_models:
            print(f"Modelos con capacidad visual encontrados: {', '.join(vision_models)}")
        else:
            print("No se han encontrado modelos locales de Ollama con capacidad de visión.")
            print("Tip: Puedes instalar uno con 'ollama run llava' o 'ollama run moondream'")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_vision()
