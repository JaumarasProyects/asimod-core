import os
import subprocess
import sys
import json
import time

def load_settings(settings_file=None):
    if settings_file is None:
        # Buscar en el root del proyecto (2 niveles arriba de core/tunnels)
        base_dir = os.path.dirname(os.path.abspath(__file__))
        settings_file = os.path.abspath(os.path.join(base_dir, "../../settings.json"))
        
    if os.path.exists(settings_file):
        try:
            with open(settings_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error al cargar {settings_file}: {e}")
    return {}

def get_tunnel_command(settings):
    """Genera el comando cloudflared según la configuración y retorna (comando, config_temporal)"""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    cf_path = os.path.join(base_dir, "cloudflared.exe")
    
    # Si no existe en el root, confiar en el PATH
    if not os.path.exists(cf_path):
        cf_path = "cloudflared.exe"

    # 1. Prioridad: ID de Túnel y Credenciales (Locally Managed)
    tunnel_id = settings.get("cloudflare_tunnel_id", "")
    credentials = settings.get("cloudflare_tunnel_credentials", "")
    hostname = settings.get("cloudflare_hostname", "")
    
    if tunnel_id and credentials:
        print(f"Comando detectado: Cloudflare ID {tunnel_id}...")
        temp_config = f"temp_cf_{int(time.time())}.yml"
        config_content = [
            f"tunnel: {tunnel_id}",
            f"credentials-file: {credentials}",
            "",
            "ingress:",
            f"  - hostname: {hostname}",
            "    service: http://127.0.0.1:8000",
            "  - service: http_status:404"
        ]
        
        print(f"URL de acceso configurada: https://{hostname}")
        
        with open(temp_config, "w") as f:
            f.write("\n".join(config_content))
            
        return [cf_path, "tunnel", "--config", temp_config, "run", tunnel_id], temp_config

    # 2. Siguiente: Token (Remotely Managed)
    token = settings.get("cloudflare_tunnel_token", "")
    # Evitar usar 'cfut_' como token válido ya que suele ser un ID interno
    if token and token.strip() and not token.startswith("cfut_"):
        print(f"Comando detectado: Cloudflare TOKEN...")
        return [cf_path, "tunnel", "run", "--token", token], None

    # 3. Fallback: Quick Tunnel (TryCloudflare)
    print("Comando detectado: Quick Tunnel temporal...")
    return [cf_path, "tunnel", "--url", "http://127.0.0.1:8000"], None

def run_tunnel():
    settings = load_settings()
    cmd, temp_file = get_tunnel_command(settings)
    
    try:
        subprocess.run(cmd)
    finally:
        if temp_file and os.path.exists(temp_file):
            try: os.remove(temp_file)
            except: pass

if __name__ == "__main__":
    try:
        run_tunnel()
    except KeyboardInterrupt:
        print("\nTúnel cerrado por el usuario.")
    except Exception as e:
        print(f"\nError al ejecutar el túnel: {e}")
        input("Presiona Enter para salir...")
