import os
import subprocess
import sys
import json
import time

def load_settings(settings_file="settings.json"):
    if os.path.exists(settings_file):
        try:
            with open(settings_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error al cargar {settings_file}: {e}")
    return {}

def run_tunnel():
    settings = load_settings()
    
    # 1. Prioridad: Token (Remotely Managed)
    token = settings.get("cloudflare_tunnel_token", "")
    if token and token.strip():
        print(f"Iniciando túnel de Cloudflare usando TOKEN...")
        cmd = ["cloudflared.exe", "tunnel", "run", "--token", token]
        subprocess.run(cmd)
        return

    # 2. Siguiente: ID de Túnel y Credenciales (Locally Managed)
    tunnel_id = settings.get("cloudflare_tunnel_id", "")
    credentials = settings.get("cloudflare_tunnel_credentials", "")
    hostname = settings.get("cloudflare_hostname", "")
    
    if tunnel_id and credentials:
        print(f"Iniciando túnel de Cloudflare {tunnel_id} ({hostname})...")
        # Generar comando con argumentos en lugar de archivo .yml
        # Nota: cloudflared run <name/id> requiere que el config esté o se pasen todos los parámetros.
        # Es más fácil si usamos 'tunnel run' con parámetros específicos si cloudflared lo permite,
        # pero usualmente 'run' busca un config.
        
        # Alternativa: Crear un archivo temporal de configuración para cloudflared
        temp_config = "temp_cloudflared.yml"
        config_content = [
            f"tunnel: {tunnel_id}",
            f"credentials-file: {credentials}",
            "",
            "ingress:",
            f"  - hostname: {hostname}",
            "    service: http://localhost:8000",
            "  - service: http_status:404"
        ]
        
        with open(temp_config, "w") as f:
            f.write("\n".join(config_content))
            
        print(f"Configuración temporal generada en {temp_config}")
        cmd = ["cloudflared.exe", "tunnel", "--config", temp_config, "run", tunnel_id]
        try:
            subprocess.run(cmd)
        finally:
            # Limpiar al terminar
            if os.path.exists(temp_config):
                try:
                    os.remove(temp_config)
                except:
                    pass
        return

    # 3. Fallback: Quick Tunnel (TryCloudflare)
    print("No se encontró configuración fija (Token o ID). Iniciando túnel temporal...")
    cmd = ["cloudflared.exe", "tunnel", "--url", "http://127.0.0.1:8000"]
    subprocess.run(cmd)

if __name__ == "__main__":
    try:
        run_tunnel()
    except KeyboardInterrupt:
        print("\nTúnel cerrado por el usuario.")
    except Exception as e:
        print(f"\nError al ejecutar el túnel: {e}")
        input("Presiona Enter para salir...")
