/**
 * ASIMOD Web Dashboard Engine
 * Gestor dinámico de temas y módulos.
 */

class AsimodApp {
    constructor() {
        this.modules = [];
        this.activeModule = null;
        this.style = null;

        // Elementos DOM Principales
        this.sidebarNav = document.getElementById('sidebarNav');
        this.sidebar = document.getElementById('sidebar');
        this.moduleName = document.getElementById('moduleName');
        this.moduleIcon = document.getElementById('moduleIcon');
        this.moduleTabs = document.getElementById('moduleTabs');
        this.galleryList = document.getElementById('galleryList');
        this.gallerySide = document.getElementById('gallerySide');
        this.galleryTitle = document.getElementById('galleryTitle');
        this.workspace = document.getElementById('workspaceContent');
        this.galleryToggle = document.getElementById('galleryToggle');
        this.backdrop = document.getElementById('backdrop');
        this.chatSide = document.getElementById('chatSide');
        
        // --- Sidebar Integrated Technical Panel ---
        this.techPanel = document.getElementById('techPanelContainer');
        this.toggleTechBtn = document.getElementById('toggleTechSidebar');
        this.btnRefreshFull = document.getElementById('btnRefreshFull');
        
        // Core Controls
        this.techMemory = document.getElementById('techMemory');
        this.btnNewThread = document.getElementById('btnNewThread');
        this.charNameInput = document.getElementById('charName');
        this.charPersInput = document.getElementById('charPers');
        this.charVoiceMotor = document.getElementById('charVoiceMotor');
        this.charVoiceId = document.getElementById('charVoiceId');
        this.btnSaveProfile = document.getElementById('btnSaveProfile');
        this.techProvider = document.getElementById('techProvider');
        this.techModel = document.getElementById('techModel');
        this.spinMaxTokens = document.getElementById('spinMaxTokens');
        this.sliderTemp = document.getElementById('sliderTemp');
        this.labelTemp = document.getElementById('labelTemp');
        this.ttsProvider = document.getElementById('ttsProvider');
        this.ttsMode = document.getElementById('ttsMode');
        this.ttsVoiceId = document.getElementById('ttsVoiceId');
        this.sttProviderSelect = document.getElementById('sttProvider');
        this.sttModeSelect = document.getElementById('sttMode');

        // Quick Controls
        this.micToggle = document.getElementById('micToggle');
        
        // --- NEW Relocated Controls ---
        this.audioStopBtn = document.getElementById('audioStopBtn');
        this.visionMode = document.getElementById('visionMode');
        this.imagePreview = document.getElementById('imagePreview');
        this.previewImg = document.getElementById('previewImg');
        this.removeImg = document.getElementById('removeImg');
        this.mobileChatBtn = document.getElementById('mobileChatTrigger');
        this.closeChatBtn = document.getElementById('closeChat');
        this.gallerySide = document.getElementById('gallerySide');
        this.galleryList = document.getElementById('galleryList');
        this.galleryToggle = document.getElementById('galleryToggle');
        this.currentImageBase64 = null;
        this.currentAudio = null; // Rastrear audio en reproducción

        // Si estamos en móvil, el chat y la librería empiezan ocultos por defecto
        if (window.innerWidth < 1024) {
            if (this.chatSide) this.chatSide.classList.add('hidden');
            if (this.gallerySide) {
                this.gallerySide.classList.add('collapsed');
                if (this.galleryToggle) this.galleryToggle.innerText = '▶';
            }
        }

        // --- NEW Adaptive UI Controls ---
        this.sidebarToggle = document.getElementById('sidebarToggle');
        this.coreTrigger = document.getElementById('coreTrigger');
        this.mobileToggle = document.getElementById('mobileToggle');

        this.init();
    }

    async init() {
        console.log("[ASIMOD] Inicializando sistema unificado...");
        
        // El registro de eventos debe ser lo primero para que la UI sea funcional
        this.setupEventListeners();
        
        await this.loadStyle();
        await this.loadModules();
        await this.syncFullTechnicalState();
        await this.loadChatHistory();
        
        document.body.classList.remove('loading');
    }

    async loadStyle() {
        try {
            const resp = await fetch('/v1/style');
            if (!resp.ok) throw new Error("Style Error");
            const data = await resp.json();
            this.style = data;
            
            if (data && data.colors) {
                const root = document.documentElement;
                Object.entries(data.colors).forEach(([key, value]) => {
                    const cssKey = `--${key.replace(/_/g, '-')}`;
                    root.style.setProperty(cssKey, value);
                });
            }
        } catch (e) {
            console.error("[ASIMOD] El núcleo no proporcionó estilos.");
        }
    }

    async loadModules() {
        try {
            const resp = await fetch('/v1/modules');
            if (!resp.ok) return;
            const data = await resp.json();
            this.modules = data.modules || [];
            this.renderSidebar();
            
            const home = this.modules.find(m => m.id === 'home');
            if (home) this.activateModule(home.id);
            else if (this.modules.length > 0) this.activateModule(this.modules[0].id);
            
            this.loadGallery(); // Cargar galería al inicio
            setInterval(() => this.syncQuickStatus(), 3000);
        } catch (e) {
            console.error("[ASIMOD] Error al enlazar módulos.");
        }
    }

    async syncFullTechnicalState() {
        try {
            const status = await (await fetch('/v1/status')).json();
            const providers = await (await fetch('/v1/providers')).json();
            const vProviders = await (await fetch('/v1/voice_providers')).json();
            
            this.populateSelect(this.techProvider, providers.providers, status.provider);
            this.populateSelect(this.charVoiceMotor, vProviders.voice_providers, status.voice_provider);
            this.populateSelect(this.ttsProvider, vProviders.voice_providers, status.voice_provider);
            this.populateSelect(this.sttProviderSelect, ['None', 'Standard (Google)'], status.stt_provider);

            if (this.charNameInput) this.charNameInput.value = status.char_name || "";
            if (this.charPersInput) this.charPersInput.value = status.char_personality || "";
            if (this.spinMaxTokens) this.spinMaxTokens.value = status.max_tokens || 1024;
            if (this.sliderTemp) {
                this.sliderTemp.value = status.temperature || 0.7;
                if (this.labelTemp) this.labelTemp.innerText = status.temperature || 0.7;
            }
            if (this.ttsMode) this.ttsMode.value = status.voice_mode || "autoplay";
            if (this.sttModeSelect) this.sttModeSelect.value = status.stt_mode || "OFF";

            await this.refreshMemories(status.active_thread);
            await this.refreshModels(status.provider, status.model);
            await this.refreshVoices(status.voice_provider, status.voice_id);
        } catch (e) {
            console.warn("[ASIMOD] No se pudo sincronizar el estado técnico inicial.");
        }
    }

    populateSelect(el, list, currentValue) {
        if (!el) return;
        el.innerHTML = list.map(item => {
            const val = typeof item === 'string' ? item : item.id;
            const text = typeof item === 'object' ? (item.name || val) : item;
            return `<option value="${val}" ${val === currentValue ? 'selected' : ''}>${text}</option>`;
        }).join('');
    }

    async refreshMemories(currentId = null) {
        const resp = await fetch('/v1/memories');
        const data = await resp.json();
        this.populateSelect(this.techMemory, data.memories, currentId);
    }

    async refreshModels(provider, currentModel = null) {
        const resp = await fetch(`/v1/models?provider=${provider}`);
        const data = await resp.json();
        this.populateSelect(this.techModel, data.models, currentModel);
    }

    async refreshVoices(provider, currentVoice = null) {
        const resp = await fetch(`/v1/voices?provider=${provider}`);
        const data = await resp.json();
        this.populateSelect(this.charVoiceId, data.voices, currentVoice);
        this.populateSelect(this.ttsVoiceId, data.voices, currentVoice);
    }

    async syncQuickStatus() {
        try {
            const resp = await fetch('/v1/status');
            if (!resp.ok) return;
            const data = await resp.json();
            if (this.micToggle) {
                const isActive = data.stt_mode !== 'OFF';
                this.micToggle.classList.toggle('active', isActive);
                this.micToggle.innerText = isActive ? '🎤' : '🎙️';
            }
        } catch (e) {}
    }

    renderSidebar() {
        if (!this.sidebarNav) return;
        this.sidebarNav.innerHTML = '';
        this.modules.forEach(mod => {
            const item = document.createElement('div');
            item.className = 'nav-item';
            item.setAttribute('data-id', mod.id);
            item.innerHTML = `<span class="icon">${mod.icon}</span><span class="name">${mod.name}</span>`;
            item.onclick = () => this.activateModule(mod.id);
            this.sidebarNav.appendChild(item);
        });
    }

    activateModule(id) {
        const mod = this.modules.find(m => m.id === id);
        if (!mod) return;
        
        console.log(`[ASIMOD] Activando módulo: ${mod.name}`);
        this.activeModule = mod;
        
        document.querySelectorAll('.nav-item').forEach(el => {
            el.classList.toggle('active', el.getAttribute('data-id') === id);
        });
        
        if (this.moduleName) this.moduleName.innerText = mod.name;
        if (this.moduleIcon) this.moduleIcon.innerText = mod.icon;
        
        // En móvil, cerrar menús al cambiar de módulo
        if (this.sidebar) this.sidebar.classList.remove('open');
        this.closeBackdrop();
        
        // Cargar galería contextual para este módulo
        this.loadGallery();

        // Asegurar que el workspace sea visible
        this.renderWorkspace(mod);
    }

    async renderWorkspace(mod) {
        if (!this.workspace) return;
        
        // --- NUEVO: Carga Modular Dinámica ---
        if (mod.has_web_ui) {
            try {
                // Añadimos un parámetro de tiempo para evitar el caché del navegador
                const assetPath = `/v1/modules/${mod.id}/assets/index.html?t=${Date.now()}`;
                console.log(`[ASIMOD] Cargando interfaz modular: ${assetPath}`);
                
                const resp = await fetch(assetPath);
                if (!resp.ok) throw new Error("Fallo al cargar visualizador");
                
                const htmlText = await resp.text();
                this.workspace.innerHTML = htmlText;
                
                // Ejecutar scripts del módulo
                this.scanAndExecuteScripts(this.workspace);
                return;
            } catch (e) {
                console.error(`[ASIMOD] Error cargando UI de ${mod.id}:`, e);
                // Fallback al placeholder si falla
            }
        }

        // Fallback: Placeholder estándar
        this.workspace.innerHTML = `
            <div class="module-web-view">
                <header style="margin-bottom:30px;">
                    <h2 style="font-size:1.8rem;">${mod.name}</h2>
                    <p style="color:var(--text-dim);">Entorno de trabajo sincronizado.</p>
                </header>
                <div class="card" style="background:var(--bg-header); padding:60px; border-radius:30px; text-align:center; border: 1px solid rgba(255,255,255,0.05);">
                    <div style="font-size:4rem; margin-bottom:30px;">${mod.icon}</div>
                    <p style="color:var(--text-dim);">El módulo de ${mod.name} está bajo control.</p>
                </div>
            </div>
        `;
    }

    scanAndExecuteScripts(container) {
        const scripts = container.querySelectorAll('script');
        scripts.forEach(oldScript => {
            const newScript = document.createElement('script');
            Array.from(oldScript.attributes).forEach(attr => newScript.setAttribute(attr.name, attr.value));
            newScript.appendChild(document.createTextNode(oldScript.innerHTML));
            oldScript.parentNode.replaceChild(newScript, oldScript);
        });
    }

    async setConfig(key, value) {
        const body = {}; body[key] = value;
        try {
            await fetch('/v1/config', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(body)
            });
        } catch (e) {}
    }

    addChatMessage(sender, text, isTemporary = false, audioFilename = null) {
        const msg = document.createElement('div');
        msg.className = `message ${sender}`;
        msg.style.padding = '12px 18px';
        msg.style.borderRadius = '20px';
        msg.style.maxWidth = '85%';
        msg.style.marginBottom = '12px';
        msg.style.fontSize = '0.9rem';
        msg.style.lineHeight = '1.5';
        msg.style.wordBreak = 'break-word';
        msg.style.boxShadow = '0 5px 20px rgba(0,0,0,0.15)';
        
        if (sender === 'user') {
            msg.style.background = 'var(--accent, #4EC9B0)';
            msg.style.color = 'var(--bg-dark, #0a0a0a)';
            msg.style.alignSelf = 'flex-end';
            msg.style.borderBottomRightRadius = '4px';
        } else {
            msg.style.background = 'rgba(255,255,255,0.05)';
            msg.style.color = 'var(--text-main, #fff)';
            msg.style.alignSelf = 'flex-start';
            msg.style.borderBottomLeftRadius = '4px';
            if (isTemporary) msg.style.opacity = '0.5';
        }
        
        // Texto del mensaje
        const textSpan = document.createElement('span');
        textSpan.innerText = text;
        msg.appendChild(textSpan);

        // Reproductor de audio si existe
        if (audioFilename) {
            const player = document.createElement('audio');
            player.controls = true;
            player.className = 'message-audio';
            player.src = `/v1/audio/file/${audioFilename}`;
            msg.appendChild(player);
        }

        const container = document.getElementById('chatMessages');
        if (container) {
            container.appendChild(msg);
            container.scrollTop = container.scrollHeight;
        }
        return msg;
    }

    async loadChatHistory() {
        try {
            const resp = await fetch('/v1/history');
            if (!resp.ok) return;
            const data = await resp.json();
            const container = document.getElementById('chatMessages');
            if (container) {
                container.innerHTML = '';
                data.forEach(msg => {
                    const role = msg.sender === 'IA' || msg.sender === 'assistant' ? 'assistant' : 'user';
                    this.addChatMessage(role, msg.content);
                });
            }
        } catch (e) {}
    }

    closeBackdrop() { if (this.backdrop) this.backdrop.style.display = 'none'; }

    setupEventListeners() {
        // --- Adaptive Navigation Logic ---
        if (this.sidebarToggle) {
            this.sidebarToggle.onclick = () => {
                this.sidebar.classList.toggle('collapsed');
            };
        }

        if (this.mobileToggle) {
            this.mobileToggle.onclick = () => {
                this.sidebar.classList.toggle('open');
                if (this.backdrop) this.backdrop.style.display = this.sidebar.classList.contains('open') ? 'block' : 'none';
            };
        }

        if (this.coreTrigger) {
            this.coreTrigger.onclick = () => this.toggleChat();
        }

        if (this.mobileChatBtn) {
            this.mobileChatBtn.onclick = () => this.toggleChat();
        }

        if (this.closeChatBtn) {
            this.closeChatBtn.onclick = () => this.toggleChat();
        }

        if (this.galleryToggle && this.gallerySide) {
            this.galleryToggle.onclick = () => {
                const isCollapsed = this.gallerySide.classList.toggle('collapsed');
                this.galleryToggle.innerText = isCollapsed ? '▶' : '◀';
                
                // En móvil, manejar el backdrop para el overlay de la galería
                if (window.innerWidth <= 768) {
                    if (this.backdrop) {
                        this.backdrop.style.display = isCollapsed ? 'none' : 'block';
                    }
                    // Si abrimos la galería, cerramos el menú sidebar si estaba abierto
                    if (!isCollapsed && this.sidebar) {
                        this.sidebar.classList.remove('open');
                    }
                }
                
                console.log(`[ASIMOD] Galería ${isCollapsed ? 'contraída' : 'expandida'}`);
            };
        }

        // Toggle Sidebar Top Panel
        if (this.techPanel) {
            const header = this.techPanel.querySelector('.tech-panel-header');
            if (header) {
                header.onclick = (e) => {
                    // Prevenir que el click se procese si es en un botón interno
                    if (e.target.closest('.icon-btn') || e.target.closest('.btn-toggle-panel')) return;
                    this.techPanel.classList.toggle('collapsed');
                };
            }
            if (this.toggleTechBtn) {
                this.toggleTechBtn.onclick = (e) => {
                    e.stopPropagation();
                    this.techPanel.classList.toggle('collapsed');
                };
            }
        }

        if (this.backdrop) this.backdrop.onclick = () => this.closeBackdrop();
        if (this.btnRefreshFull) this.btnRefreshFull.onclick = () => this.syncFullTechnicalState();
        
        if (this.techMemory) {
            this.techMemory.onchange = async (e) => {
                await fetch('/v1/memories', {
                    method: 'POST', headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({thread_id: e.target.value})
                });
                await this.loadChatHistory();
            };
        }
        if (this.btnNewThread) {
            this.btnNewThread.onclick = async () => {
                const name = prompt("Defina la identidad del nuevo hilo:");
                if (!name) return;
                await fetch('/v1/memories', {
                    method: 'POST', headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({name: name})
                });
                await this.refreshMemories(name);
            };
        }
        if (this.btnSaveProfile) {
            this.btnSaveProfile.onclick = async () => {
                await fetch('/v1/memories', {
                    method: 'POST', headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        name: this.charNameInput.value,
                        personality: this.charPersInput.value,
                        voice_id: this.charVoiceId.value,
                        voice_provider: this.charVoiceMotor.value
                    })
                });
                alert("Identidad sincronizada.");
            };
        }
        if (this.charVoiceMotor) this.charVoiceMotor.onchange = (e) => this.refreshVoices(e.target.value);
        if (this.techProvider) {
            this.techProvider.onchange = async (e) => {
                await this.setConfig('last_provider', e.target.value);
                await this.refreshModels(e.target.value);
            };
        }
        if (this.techModel) this.techModel.onchange = (e) => this.setConfig('last_model', e.target.value);
        if (this.spinMaxTokens) this.spinMaxTokens.onchange = (e) => this.setConfig('max_tokens', parseInt(e.target.value));
        if (this.sliderTemp) {
            this.sliderTemp.oninput = (e) => { if (this.labelTemp) this.labelTemp.innerText = e.target.value; };
            this.sliderTemp.onchange = (e) => this.setConfig('temperature', parseFloat(e.target.value));
        }
        if (this.ttsProvider) this.ttsProvider.onchange = (e) => this.refreshVoices(e.target.value);
        if (this.ttsMode) this.ttsMode.onchange = (e) => this.setConfig('voice_mode', e.target.value);
        if (this.ttsVoiceId) this.ttsVoiceId.onchange = (e) => this.setConfig('voice_id', e.target.value);
        if (this.sttProviderSelect) this.sttProviderSelect.onchange = (e) => this.setConfig('stt_provider', e.target.value);
        if (this.sttModeSelect) {
            this.sttModeSelect.onchange = async (e) => {
                await fetch('/v1/stt/mode', {
                    method: 'POST', headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({mode: e.target.value})
                });
            };
        }

        // Quick Controls
        if (this.micToggle) {
            this.micToggle.onclick = async () => {
                const currentMode = this.sttModeSelect ? this.sttModeSelect.value : 'OFF';
                const nextMode = currentMode === 'OFF' ? 'CHAT' : 'OFF';
                await fetch('/v1/stt/mode', {
                    method: 'POST', headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({mode: nextMode})
                });
                if (this.sttModeSelect) this.sttModeSelect.value = nextMode;
                this.syncQuickStatus();
            };
        }
        // --- NEW Relocated Controls Logic ---
        if (this.audioStopBtn) {
            this.audioStopBtn.onclick = () => {
                // 1. Parar audio en el servidor
                fetch('/v1/audio/stop', {method: 'POST'});
                
                // 2. Parar audio en el navegador
                if (this.currentAudio) {
                    this.currentAudio.pause();
                    this.currentAudio.currentTime = 0;
                    this.currentAudio = null;
                }
                
                // 3. Parar cualquier otro elemento audio (por si acaso)
                document.querySelectorAll('audio').forEach(a => {
                    a.pause();
                    a.currentTime = 0;
                });
                
                console.log("[ASIMOD] Audio detenido local y remotamente.");
            };
        }

        if (this.visionMode) {
            this.visionMode.onchange = async (e) => {
                const mode = e.target.value;
                if (mode === 'OFF') {
                    this.clearVision();
                    return;
                }
                
                if (mode === 'FILE') {
                    this.triggerFileUpload();
                    return;
                }

                // Captura de Cámara o Pantalla
                try {
                    const resp = await fetch('/v1/vision/capture', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({ mode: mode })
                    });
                    const data = await resp.json();
                    if (data.status === 'success') {
                        this.showVisionPreview(data.image);
                    } else {
                        alert("Error: " + data.message);
                        this.visionMode.value = 'OFF';
                    }
                } catch (e) {
                    console.error("Vision Capture Error:", e);
                }
            };
        }

        if (this.removeImg) {
            this.removeImg.onclick = () => this.clearVision();
        }

        // Chat Logic
        const chatInput = document.getElementById('chatInput');
        const chatSend = document.getElementById('chatSend');
        const sendMessage = async () => {
            const text = chatInput.value.trim();
            if (!text) return;
            
            this.addChatMessage('user', text);
            chatInput.value = '';
            
            const typingMsg = this.addChatMessage('assistant', 'Escribiendo...', true);
            
            // Timeout de 50 segundos (ligeramente más que el del backend)
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), 50000);
            
            console.log(`[ASIMOD] Enviando petición: "${text.substring(0, 20)}..."`);
            
            try {
                const formData = new FormData();
                formData.append('text', text);
                formData.append('play_audio', 'true');
                
                // Adjuntar imagen de visión si existe
                if (this.currentImageBase64) {
                    formData.append('image_b64', this.currentImageBase64);
                }
                
                const resp = await fetch('/v1/chat', { 
                    method: 'POST', 
                    body: formData,
                    signal: controller.signal
                });
                
                clearTimeout(timeoutId);
                
                if (!resp.ok) {
                    throw new Error(`HTTP Error ${resp.status}`);
                }
                
                const result = await resp.json();
                console.log("[ASIMOD] Respuesta del núcleo:", result);
                
                if (typingMsg && typingMsg.parentNode) typingMsg.remove();
                
                if (result.status === 'success') {
                    this.addChatMessage('assistant', result.response, false, result.audio_path);
                    
                    // Reproducir automáticamente si hay audio
                    if (result.audio_path) {
                        if (this.currentAudio) this.currentAudio.pause(); // Parar previo
                        this.currentAudio = new Audio(`/v1/audio/file/${result.audio_path}`);
                        this.currentAudio.play().catch(e => console.warn("Auto-playback blocked by browser:", e));
                    }
                } else {
                    this.addChatMessage('assistant', `⚠️ ${result.message || 'Error desconocido'}`);
                }
            } catch (e) {
                clearTimeout(timeoutId);
                if (typingMsg && typingMsg.parentNode) typingMsg.remove();
                
                if (e.name === 'AbortError') {
                    console.error("[ASIMOD] La petición excedió el tiempo de espera.");
                    this.addChatMessage('assistant', '⌛ El motor de IA está tardando mucho o no responde (Timeout).');
                } else {
                    console.error("[ASIMOD] Error de comunicación:", e);
                    this.addChatMessage('assistant', '🔌 No se pudo conectar con el núcleo de ASIMOD.');
                }
            }
        };
        if (chatSend && chatInput) {
            chatSend.onclick = sendMessage;
            chatInput.onkeypress = (e) => { if (e.key === 'Enter') sendMessage(); };
        }
    }

    // --- Vision Helper Methods ---
    triggerFileUpload() {
        const input = document.createElement('input');
        input.type = 'file';
        input.accept = 'image/*';
        input.onchange = async (e) => {
            const file = e.target.files[0];
            if (!file) return;
            const formData = new FormData();
            formData.append('file', file);
            const resp = await fetch('/v1/vision/upload', { method: 'POST', body: formData });
            const data = await resp.json();
            if (data.status === 'success') this.showVisionPreview(data.image);
        };
        input.click();
    }

    showVisionPreview(base64) {
        this.currentImageBase64 = base64;
        if (this.previewImg) this.previewImg.src = `data:image/jpeg;base64,${base64}`;
        if (this.imagePreview) this.imagePreview.style.display = 'block';
    }

    clearVision() {
        this.currentImageBase64 = null;
        if (this.imagePreview) this.imagePreview.style.display = 'none';
        if (this.visionMode) this.visionMode.value = 'OFF';
    }

    // --- General Toggle Helpers ---
    toggleChat() {
        const isHidden = this.chatSide.classList.toggle('hidden');
        if (this.coreTrigger) this.coreTrigger.classList.toggle('active', !isHidden);
        
        // En móvil, si abrimos el CORE, cerramos la sidebar si estaba abierta
        if (window.innerWidth < 1024 && !isHidden) {
            this.sidebar.classList.remove('open');
            this.closeBackdrop();
        }
        
        console.log(`[ASIMOD] Chat ${isHidden ? 'oculto' : 'visible'}`);
    }

    async loadGallery() {
        if (!this.galleryList) return;
        try {
            const moduleId = this.activeModule ? this.activeModule.id : '';
            const resp = await fetch(`/v1/gallery?module_id=${moduleId}`);
            if (!resp.ok) return;
            const data = await resp.json();
            
            this.galleryList.innerHTML = '';
            // Combinar files o items según lo que envíe el API
            const items = data.files || data.items || [];
            
            if (items.length === 0) {
                this.galleryList.innerHTML = '<div style="padding:20px; color:var(--text-dim); text-align:center; font-size:0.8rem;">VACTÍO</div>';
                return;
            }

            items.forEach(item => {
                const el = document.createElement('div');
                el.className = 'gallery-item';
                
                const name = item.name || item.title || "Sin nombre";
                const sub = item.subtitle || (item.size ? `${(item.size/1024).toFixed(1)} KB` : "");
                const type = item.type || "file";
                const icon = item.icon || (type === 'image' ? '🖼️' : (type === 'audio' ? '🎵' : '📄'));
                
                if (type === 'image' && item.url) {
                    el.innerHTML = `
                        <img src="${item.url}" class="gallery-thumb" loading="lazy">
                        <div class="gallery-meta">${name}</div>
                    `;
                } else {
                    el.innerHTML = `
                        <div class="gallery-thumb-icon">${icon}</div>
                        <div class="gallery-meta">${name}</div>
                        <div style="font-size:0.6rem; color:var(--text-dim);">${sub}</div>
                    `;
                }

                el.onclick = () => {
                    if (item.callback_action) {
                        this.executeModuleAction(item.callback_action, item.callback_params);
                    } else if (item.url) {
                        window.open(item.url, '_blank');
                    }
                };
                this.galleryList.appendChild(el);
            });
        } catch (e) {
            console.error("[ASIMOD] Error cargando galería:", e);
        }
    }

    async executeModuleAction(action, params) {
        if (!this.activeModule) return;
        try {
            const resp = await fetch(`/v1/modules/${this.activeModule.id}/action`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ action, params })
            });
            if (resp.ok) {
                // Refrescar workspace y galería para ver cambios
                this.renderWorkspace(this.activeModule);
                this.loadGallery();
            }
        } catch (e) {
            console.error("[ASIMOD] Error en acción de módulo:", e);
        }
    }
}

window.onload = () => { window.app = new AsimodApp(); };
