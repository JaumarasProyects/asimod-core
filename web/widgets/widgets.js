/**
 * ASIMOD SHARED WIDGET SYSTEM - JS LIBRARY
 * Lógica reutilizable para componentes de la web.
 */

window.asimod = window.asimod || {};

/**
 * Crea una lista de eventos tipo timeline.
 * @param {string} containerId - ID del contenedor HTML.
 * @param {Array} events - Lista de objetos {time, title, desc}.
 */
asimod.renderEventList = (containerId, events) => {
    const container = document.getElementById(containerId);
    if (!container) return;

    if (!events || events.length === 0) {
        container.innerHTML = `<div style="padding:20px; color:var(--text-dim); text-align:center;">No hay eventos programados.</div>`;
        return;
    }

    let html = '<div class="event-timeline">';
    events.forEach(ev => {
        html += `
            <div class="event-entry">
                <div class="event-time">${ev.time || '--:--'}</div>
                <div class="event-info">
                    <div class="event-title">${ev.title || 'Sin Título'}</div>
                    ${ev.desc ? `<div class="event-desc">${ev.desc}</div>` : ''}
                </div>
            </div>
        `;
    });
    html += '</div>';
    
    container.innerHTML = html;
};

/**
 * Helper para enviar mensajes al chat desde cualquier módulo.
 */
asimod.sendChat = (text) => {
    const input = document.getElementById('chatInput');
    const send = document.getElementById('chatSend');
    if (input && send) {
        input.value = text;
        send.click();
        // Intentar abrir el panel de chat si está oculto y estamos en modo app.js global
        if (window.app && window.app.toggleChat && window.app.chatSide && window.app.chatSide.classList.contains('hidden')) {
            window.app.toggleChat();
        }
    } else {
        console.error("[ASIMOD Bridge] No se encontró el input de chat.");
    }
};

console.log("[ASIMOD] Sistema de Widgets cargado.");
