import socket
import os
import subprocess
import re

def get_tailscale_ip():
    """
    Intenta obtener la IP de Tailscale de varias formas.
    Tailscale usa el rango 100.64.0.0/10 (CGNAT).
    """
    # 1. Intentar vía comando tailscale (si está en el PATH)
    try:
        result = subprocess.run(['tailscale', 'ip', '-4'], capture_output=True, text=True, timeout=2)
        if result.returncode == 0:
            ip = result.stdout.strip()
            if ip: return ip
    except:
        pass

    # 2. Escanear interfaces de red (fallback)
    try:
        # En Windows, ipconfig es confiable
        result = subprocess.run(['ipconfig'], capture_output=True, text=True)
        # Buscar patrones de IP que empiecen por 100. (rango Tailscale)
        matches = re.findall(r"100\.\d{1,3}\.\d{1,3}\.\d{1,3}", result.stdout)
        if matches:
            return matches[0]
    except:
        pass

    return None

def main():
    print("="*50)
    print(" ASIMOD - Verificador de Red Tailscale")
    print("="*50)
    
    ip = get_tailscale_ip()
    
    if ip:
        print(f"\n[OK] Tailscale detectado!")
        print(f"Tu IP privada es: {ip}")
        print(f"\nUsa esta URL en el navegador de tu móvil o tablet:")
        print(f"--> http://{ip}:8000/web/")
        print("\n(Asegúrate de que Tailscale esté activado en ambos dispositivos)")
    else:
        print("\n[!] Tailscale NO detectado.")
        print("Pasos a seguir:")
        print("1. Descarga Tailscale en este PC: https://tailscale.com/download")
        print("2. Instálalo e inicia sesión.")
        print("3. Instala la app de Tailscale en tu móvil e inicia sesión con la misma cuenta.")
        print("4. Una vez conectado, vuelve a ejecutar este script.")
        
    print("\n" + "="*50)
    input("Presiona Enter para cerrar...")

if __name__ == "__main__":
    main()
