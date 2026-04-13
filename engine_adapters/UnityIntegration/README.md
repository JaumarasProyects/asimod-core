# ASIMOD Unity Integration

Este módulo proporciona la conectividad entre el motor **ASIMOD Core** y proyectos de **Unity** para permitir la interacción con avatares inteligentes y control remoto del sistema.

## Componentes Principales

### 1. AsimodClient.cs
El cliente base encargado de la comunicación HTTP/RESTA con el servidor ASIMOD.
- **Gestión de Memoria:** Permite cambiar el hilo de conversación activo o crear nuevos personajes.
- **Envío de Chat:** Procesa las respuestas de texto y los eventos de audio/emociones.
- **Actualización de Perfil:** Permite modificar dinámicamente el nombre, la personalidad, la historia y la configuración de voz del personaje actual.
- **Control Remoto:** Incluye el comando `StopAudio` para detener la reproducción de voz en el PC remoto.

### 2. AsimodTestTool.cs (e Inspector)
Una herramienta de pruebas visual instalada en el Inspector de Unity que permite:
- **Sincronización:** Carga el estado actual del servidor (Modelo LLM, Voz, Motor de Voz).
- **Setup de Personaje:** Configura nuevos hilos con motores específicos (Edge TTS o Local TTS) y voces neuronales.
- **Debug Chat:** Un panel para enviar prompts y ver la respuesta de texto y emojis recibidos.
- **Parada de Emergencia:** Botón rojo para detener el audio en el PC remoto instantáneamente.

## Configuración Rápida

1. Asegúrate de que **ASIMOD Core** se esté ejecutando (por defecto en `http://localhost:8000`).
2. Arrastra el script `AsimodClient` a un GameObject en tu escena de Unity.
3. Añade el script `AsimodTestTool` al mismo objeto.
4. En el Inspector, pulsa **"1. Sync State"** para verificar la conexión.
5. Usa el desplegable **"Active Memory"** para cambiar entre personajes.

## Gestión de Voces por Personaje
Cada personaje puede tener su propia **voz** y **motor** (Voz Persistente). 
- Si seleccionas un motor (ej: Local TTS) y una voz para un personaje y pulsas **"Update Current Profile"**, ASIMOD recordará esa identidad vocal independientemente de la configuración global del sistema.

---
*Desarrollado para la integración de ASIMOD en entornos 3D y VR.*
