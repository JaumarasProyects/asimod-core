import os
import sys
import subprocess
import threading
import time
import argparse
import json
from pathlib import Path

# Configuración
CORE_PORT = 8000
MODULE_API_START_PORT = 8001

def get_tailscale_ip():
    """Obtiene la IP de Tailscale usando el comando status."""
    try:
        # Intentar comando nativo
        result = subprocess.run(['tailscale', 'status', '--json'], capture_output=True, text=True, timeout=3)
        if result.returncode == 0:
            data = json.loads(result.stdout)
            if "Self" in data and "TailscaleIPs" in data["Self"]:
                return data["Self"]["TailscaleIPs"][0]
    except:
        pass
    
    # Fallback: check_tailscale logic si existe
    try:
        import re
        result = subprocess.run(['ipconfig'], capture_output=True, text=True)
        matches = re.findall(r"100\.\d{1,3}\.\d{1,3}\.\d{1,3}", result.stdout)
        if matches: return matches[0]
    except:
        pass
    return None

def stream_logs(process, prefix, color_code):
    """Lee el stdout/stderr de un proceso y lo imprime con prefijo."""
    for line in iter(process.stdout.readline, ''):
        if line:
            # Formato: [PREFIX] mensaje
            # Usar códigos de color ANSI simples (opcional)
            print(f"\033[{color_code}m[{prefix}]\033[0m {line.strip()}")
    process.stdout.close()

def main():
    parser = argparse.ArgumentParser(description="ASIMOD Unified Launcher")
    parser.add_argument("--gui", action="store_true", help="Lanzar en modo aplicación de escritorio")
    args = parser.parse_args()

    print("\033[1;36m" + "="*60)
    print(" ASIMOD - Lanzador Unificado")
    print("="*60 + "\033[0m")

    # 1. Comprobar Red
    ts_ip = get_tailscale_ip()
    if ts_ip:
        print(f"\033[1;32m[NET] Tailscale activo: {ts_ip}\033[0m")
        print(f"[URL] Dashboard Web: http://{ts_ip}:{CORE_PORT}/web/")
    else:
        print("\033[1;33m[NET] Tailscale no detectado. Acceso remoto limitado a red local.\033[0m")
    
    print("-" * 60)

    processes = []
    
    # 2. Descubrir APIs de módulos
    module_apis = []
    modules_dir = Path("modules")
    if modules_dir.exists():
        for mod_dir in modules_dir.iterdir():
            if mod_dir.is_dir():
                api_file = mod_dir / "api.py"
                if api_file.exists():
                    module_apis.append(api_file)

    # 3. Lanzar APIs de módulos (8001+)
    current_port = MODULE_API_START_PORT
    colors = ["33", "35", "34", "36"] # Amarillo, Magenta, Azul, Cyan
    
    for i, api_path in enumerate(module_apis):
        mod_name = api_path.parent.name.upper()
        print(f"[LAUNCH] Iniciando API de Módulo: {mod_name} en puerto {current_port}")
        
        proc = subprocess.Popen(
            [sys.executable, str(api_path), "--port", str(current_port)],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        processes.append(proc)
        
        color = colors[i % len(colors)]
        thread = threading.Thread(target=stream_logs, args=(proc, mod_name, color), daemon=True)
        thread.start()
        
        current_port += 1

    # 4. Lanzar Core (8000) o GUI
    if args.gui:
        main_script = "main_standalone.py"
        prefix = "GUI"
        color = "32" # Verde
    else:
        main_script = "run_api.py"
        prefix = "CORE"
        color = "32" # Verde

    print(f"[LAUNCH] Iniciando {prefix} ({main_script})...")
    
    # El proceso principal lo lanzamos de forma que si muere, el script termine
    main_proc = subprocess.Popen(
        [sys.executable, main_script],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )
    processes.append(main_proc)
    
    # Hilo para logs del proceso principal
    threading.Thread(target=stream_logs, args=(main_proc, prefix, color), daemon=True).start()

    print("\033[1;32m" + "="*60)
    print(f" SISTEMA INICIADO CORRECTAMENTE")
    print(" Presiona Ctrl+C para cerrar todos los servicios")
    print("="*60 + "\033[0m\n")

    try:
        # Mantener el script vivo mientras el proceso principal corra
        while main_proc.poll() is None:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\n[SHUTDOWN] Cerrando todos los procesos...")
    finally:
        for p in processes:
            p.terminate()
            try:
                p.wait(timeout=3)
            except:
                p.kill()
        print("[SHUTDOWN] Limpieza completada.")

if __name__ == "__main__":
    main()
