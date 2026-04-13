@echo off
echo ========================================
echo Test de WhatsApp - Enviar mensaje de prueba
echo ========================================
echo.

REM Pedir credenciales si no están definidas
set /p WHATSAPP_PHONE_ID="Phone ID (Enter para usar config): "
set /p WHATSAPP_ACCESS_TOKEN="Access Token (Enter para usar config): "
set /p WHATSAPP_TEST_TO="Número destino: "

python -c "
import os
import sys

phone_id = os.environ.get('WHATSAPP_PHONE_ID', '').strip() or None
access_token = os.environ.get('WHATSAPP_ACCESS_TOKEN', '').strip() or None
to_number = os.environ.get('WHATSAPP_TEST_TO', '').strip()

if not phone_id or not access_token:
    from core.services.config_service import ConfigService
    config = ConfigService()
    phone_id = phone_id or config.get('whatsapp_phone_id')
    access_token = access_token or config.get('whatsapp_access_token')

if not phone_id or not access_token:
    print('ERROR: Faltan credenciales de WhatsApp')
    print('Configúralas en: Ajustes > API Keys')
    sys.exit(1)

if not to_number:
    print('ERROR: Número destino requerido')
    sys.exit(1)

from core.adapters.whatsapp_adapter import WhatsAppAdapter

adapter = WhatsAppAdapter(phone_id, access_token)
print(f'Enviando mensaje a {to_number}...')
result = adapter.send_text(to_number, '🧪 Mensaje de prueba desde ASIMOD+')

if result:
    print('✅ Mensaje enviado correctamente!')
else:
    print('❌ Error al enviar mensaje')
    sys.exit(1)
"
