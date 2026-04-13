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
        this.sttBox = document.getElementById('sttBox');
        
        // Estado de selección para referencias (Media Generator)
        this.lastSelectedGalleryPath = null;
        this.lastSelectedGalleryType = null;
        
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
        this.galleryToggle = document.getElementById('galleryToggle');
        this.currentGalleryPath = ''; // Track folder navigation
        this.currentImageBase64 = null;
        this.currentAudio = null;
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
        this._injectGalleryStyles();
        
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
        
        const isMG = id === 'media_generator';
        if (this.gallerySide) {
            // Ocultamos la galería global si el módulo tiene su propia galería interna (como MG)
            this.gallerySide.style.display = isMG ? 'none' : '';
            if (this.galleryToggle) this.galleryToggle.style.display = isMG ? 'none' : '';
        }

        // Cargar galería contextual (solo si no es MG, que la maneja internamente)
        if (!isMG) this.loadGallery();

        // Asegurar que el workspace sea visible
        this.renderWorkspace(mod);
    }

    async renderWorkspace(mod) {
        if (!this.workspace) return;

        // --- ESPECIAL: Media Generator Dashboard (Desktop Parity) ---
        if (mod.id === 'media_generator') {
            this.workspace.innerHTML = `
                <div class="mg-container">
                    <div class="mg-tabs" id="mgTabs">
                        <!-- Pestañas cargadas por init() -->
                    </div>
                    <!-- Botón toggle para móvil -->
                    <button class="mg-gallery-toggle" id="mgLocalGalleryToggle" title="Abrir Galería">📁</button>
                    <div class="mg-body">
                        <div class="mg-gallery" id="mgLocalGalleryDrawer">
                            <div class="mg-gallery-list" id="mgLocalGallery">
                                <div style="padding:20px; color:var(--text-dim); text-align:center;">Cargando...</div>
                            </div>
                        </div>
                        <div class="mg-viewer" id="mgViewerContainer">
                            <div style="text-align:center; color:var(--text-dim);">
                                <div style="font-size:4rem; margin-bottom:20px; opacity:0.3;">🖼️</div>
                                <p>Selecciona un archivo o genera uno nuevo</p>
                            </div>
                        </div>
                    </div>
                    <div class="mg-footer">
                        <div class="mg-params-grid" id="mgParams"></div>
                        <div class="mg-prompt-side">
                            <textarea id="mgPrompt" placeholder="Describe lo que quieres crear..."></textarea>
                            <button id="mgBtnGenerate" class="mg-btn-generate">
                                <span class="icon">✨</span> GENERAR CONTENIDO
                            </button>
                        </div>
                    </div>
                </div>
            `;
            await this.initMediaGeneratorPanel();
            return;
        }
        
        // --- Otros módulos: Carga Modular Dinámica ---
        if (mod.has_web_ui) {
            try {
                const assetPath = `/v1/modules/${mod.id}/assets/index.html?t=${Date.now()}`;
                const resp = await fetch(assetPath);
                if (!resp.ok) throw new Error("Fallo al cargar visualizador");
                const htmlText = await resp.text();
                this.workspace.innerHTML = htmlText;
                this.scanAndExecuteScripts(this.workspace);
                return;
            } catch (e) {
                console.error(`[ASIMOD] Error cargando UI de ${mod.id}:`, e);
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

    /* Inyectar CSS para numeración de galería */
    _injectGalleryStyles() {
        const style = document.createElement('style');
        style.innerHTML = `
            .gallery-item { position: relative; }
            .gallery-item-index {
                position: absolute; top: 10px; left: 10px; background: var(--accent); color: var(--bg-dark);
                font-weight: 800; font-size: 0.7rem; padding: 2px 6px; border-radius: 4px; z-index: 2;
                box-shadow: 0 2px 10px rgba(0,0,0,0.5); pointer-events: none;
            }
        `;
        document.head.appendChild(style);
    }

    async loadGallery(path = null, moduleIdParam = null) {
        if (!this.galleryList) return;
        
        // Estado inicial de carga
        this.galleryList.innerHTML = '<div style="padding:40px; text-align:center;"><span class="loading-spinner"></span><div style="margin-top:10px; font-size:0.8rem; opacity:0.5;">Cargando Galería...</div></div>';
        
        // Reset path si cambiamos de módulo
        if (path === null) {
            const defaultMap = { 'media_generator': 'imagen', 'communications': 'audio' };
            this.currentGalleryPath = defaultMap[this.activeModule?.id] || '';
        } else {
            this.currentGalleryPath = path;
        }

        try {
            const moduleId = moduleIdParam || (this.activeModule ? this.activeModule.id : '');
            console.log(`[ASIMOD] Solicitando galería: mod=${moduleId}, path=${this.currentGalleryPath}`);
            const url = `/v1/gallery?module_id=${moduleId}&path=${encodeURIComponent(this.currentGalleryPath)}`;
            
            const resp = await fetch(url);
            
            // Limpiar el mensaje de carga antes de procesar el éxito o error
            this.galleryList.innerHTML = '';

            if (!resp.ok) {
                const errData = await resp.json().catch(() => ({}));
                this.galleryList.innerHTML = `<div style="padding:20px; color:var(--accent); text-align:center; font-size:0.8rem;">Error ${resp.status}: ${errData.message || 'No se pudo cargar la galería'}</div>`;
                return;
            }
            
            const data = await resp.json();
            const items = data.items || [];
            this.currentGalleryItems = items; // Guardar para acceso por voz/índice
            let currentIndex = 1;
            
            // 1. Botón "Atrás" si no estamos en la raíz
            if (data.can_go_back) {
                const backBtn = document.createElement('div');
                backBtn.className = 'gallery-nav-back';
                backBtn.innerHTML = `<span>⬅</span> ATRÁS / PARENT`;
                backBtn.onclick = (e) => {
                    e.stopPropagation();
                    const parts = this.currentGalleryPath.split('/');
                    parts.pop();
                    this.loadGallery(parts.join('/'));
                };
                this.galleryList.appendChild(backBtn);
            }

            if (items.length === 0 && !data.can_go_back) {
                this.galleryList.innerHTML = '<div style="padding:40px; color:var(--text-dim); text-align:center; font-size:0.8rem; opacity:0.5;">VACÍO</div>';
                return;
            }

            // 2. Renderizar Carpetas y Archivos
            items.forEach(item => {
                const el = document.createElement('div');
                el.className = `gallery-item ${item.type === 'folder' ? 'folder' : ''}`;
                
                const name = item.name;
                const type = item.type;
                const icon = item.icon || (type === 'image' ? '🖼️' : (type === 'audio' ? '🎵' : (type === 'video' ? '🎬' : (type === '3d' ? '🧊' : '📄'))));
                
                if (type === 'image' && item.url) {
                    el.innerHTML = `
                        <img src="${item.url}" class="gallery-thumb" loading="lazy">
                        <div class="gallery-meta">${name}</div>
                    `;
                } else if (type === 'folder') {
                    el.innerHTML = `
                        <div class="gallery-thumb-icon">📁</div>
                        <div class="gallery-meta" style="color:var(--accent); font-weight:700;">${name}</div>
                    `;
                } else {
                    el.innerHTML = `
                        <div class="gallery-thumb-icon">${icon}</div>
                        <div class="gallery-meta">${name}</div>
                    `;
                }

                el.onclick = (e) => {
                    e.stopPropagation();
                    if (type === 'folder') {
                        this.loadGallery(item.path);
                    } else {
                        this.previewMedia(item);
                    }
                };

                // Añadir número de índice
                const indexSpan = document.createElement('span');
                indexSpan.className = 'gallery-item-index';
                indexSpan.innerText = currentIndex++;
                el.appendChild(indexSpan);

                this.galleryList.appendChild(el);
            });
        } catch (e) {
            console.error("[ASIMOD] Error cargando galería:", e);
            if (this.galleryList) {
                this.galleryList.innerHTML = `<div style="padding:20px; color:red; text-align:center; font-size:0.8rem;">Excepción: ${e.message}</div>`;
            }
        }
    }

    previewMedia(item) {
        if (!this.workspace) return;
        
        console.log(`[ASIMOD] Visualizando: ${item.name} (${item.type})`);
        
        // Guardar como selección actual para Media Generator
        this.lastSelectedGalleryPath = item.path;
        this.lastSelectedGalleryType = item.type;
        
        // Cerrar galería local si estamos en móvil (Media Generator)
        const mgDrawer = document.getElementById('mgLocalGalleryDrawer');
        if (mgDrawer && window.innerWidth <= 768) {
            mgDrawer.classList.remove('open');
        }

        // Efecto visual en la galería
        document.querySelectorAll('.gallery-item').forEach(el => el.classList.remove('selected'));
        // (Sería ideal marcar el elemento clicado, pero previewMedia recibe el objeto data)
        
        let html = `
            <div class="media-viewer-premium">
                <h3 style="margin-bottom:20px; color:var(--text-dim); font-size:0.8rem;">VISTA PREVIA: ${item.name}</h3>
        `;

        if (item.type === 'image') {
            html += `<img src="${item.url}" alt="${item.name}">`;
        } else if (item.type === 'video') {
            html += `<video src="${item.url}" controls autoplay loop></video>`;
        } else if (item.type === 'audio') {
            html += `
                <div class="audio-player-premium">
                    <span style="font-size:2rem;">🔊</span>
                    <div style="flex:1; text-align:left;">
                        <div style="font-weight:700; margin-bottom:5px;">Archivo de Audio</div>
                        <div style="font-size:0.7rem; color:var(--text-dim);">${item.name}</div>
                    </div>
                </div>
                <audio id="activePlayer" src="${item.url}" controls autoplay style="width:100%; max-width:500px; margin-top:20px;"></audio>
            `;
        } else if (item.type === '3d') {
            html += `
                <div class="card" style="padding:100px; text-align:center;">
                    <div style="font-size:4rem; margin-bottom:20px;">🧊</div>
                    <h3>Modelo 3D Detectado</h3>
                    <p style="color:var(--text-dim);">La visualización 3D en web está en desarrollo.</p>
                </div>
            `;
        } else {
            html += `
                <div class="card" style="padding:50px; background:var(--bg-input); border-radius:15px; text-align:left;">
                    <pre style="white-space:pre-wrap; font-size:0.8rem; color:var(--accent);">${item.name}</pre>
                </div>
            `;
        }

        // Si el módulo es Media Generator, queremos usar su contenedor específico
        if (this.activeModule?.id === 'media_generator') {
            const viewer = document.getElementById('mgViewerContainer');
            if (viewer) viewer.innerHTML = html;
        } else {
                        this.workspace.innerHTML = html;
        }
    }

    // --- Media Generator Panel Logic ---
    async initMediaGeneratorPanel() {
        const mgTabs = document.getElementById('mgTabs');
        const mgParams = document.getElementById('mgParams');
        const mgLocalGallery = document.getElementById('mgLocalGallery');
        const mgLocalGalleryDrawer = document.getElementById('mgLocalGalleryDrawer');
        const mgLocalGalleryToggle = document.getElementById('mgLocalGalleryToggle');
        const mgPrompt = document.getElementById('mgPrompt');
        const mgBtnGen = document.getElementById('mgBtnGenerate');
        if (!mgTabs || !mgParams) return;

        // Manejo de drawer móvil
        if (mgLocalGalleryToggle && mgLocalGalleryDrawer) {
            mgLocalGalleryToggle.onclick = (e) => {
                e.stopPropagation();
                mgLocalGalleryDrawer.classList.toggle('open');
            };
            // Cerrar al hacer clic fuera en móvil
            document.addEventListener('click', (e) => {
                if (window.innerWidth <= 768 && mgLocalGalleryDrawer.classList.contains('open')) {
                    if (!mgLocalGalleryDrawer.contains(e.target) && e.target !== mgLocalGalleryToggle) {
                        mgLocalGalleryDrawer.classList.remove('open');
                    }
                }
            });
        }

        try {
            const resp = await fetch(`/v1/modules/media_generator/workflows`);
            const data = await resp.json();
            const workflows = data.workflows || {};

            let currentMode = 'imagen'; // imagen, audio, video, 3d, composta, texto
            let currentSub = 'simple';
            let currentImgCount = 1;
            
            // Redirigir la galería global a la local temporalmente
            const oldGalleryList = this.galleryList;
            this.galleryList = mgLocalGallery;
            
            const tabs = ["Texto", "Imagen", "Audio", "Video", "3D"];
            
            const renderTabs = () => {
                mgTabs.innerHTML = tabs.map(t => {
                    const id = t.toLowerCase() === 'imagen' ? 'imagen' : t.toLowerCase();
                    return `<button class="mg-tab-btn ${currentMode === id ? 'active' : ''}" data-mode="${id}">${t}</button>`;
                }).join('');
                
                mgTabs.querySelectorAll('.mg-tab-btn').forEach(btn => {
                    btn.onclick = () => {
                        currentMode = btn.getAttribute('data-mode');
                        renderTabs();
                        renderControls();
                        this.loadGallery(currentMode === 'imagen' ? 'imagen' : (currentMode === 'texto' ? 'texto' : currentMode));
                    };
                });
            };

            const renderControls = () => {
                const subOptions = workflows[currentMode] || {};
                const isGrouped = subOptions && !Array.isArray(subOptions) && Object.keys(subOptions).length > 0;
                const subKeys = isGrouped ? Object.keys(subOptions) : [];

                if (isGrouped && !subKeys.includes(currentSub)) {
                    currentSub = subKeys[0];
                }

                const currentFiles = (isGrouped ? subOptions[currentSub] : subOptions) || [];

                mgParams.innerHTML = `
                    <div class="gen-field">
                        <label>Subtipo / Categoría</label>
                        ${isGrouped ? `
                            <select id="mgSub">
                                ${subKeys.map(k => `<option value="${k}" ${k === currentSub ? 'selected' : ''}>${k.toUpperCase()}</option>`).join('')}
                            </select>
                        ` : `
                            <div style="padding:10px; opacity:0.5; font-size:0.8rem;">Estándar</div>
                        `}
                    </div>

                    ${currentMode !== 'texto' ? `
                    <div class="gen-field">
                        <label>Workflow / Modelo</label>
                        <select id="mgWorkflow">
                            ${currentFiles.map(w => `<option value="${w}">${w}</option>`).join('')}
                        </select>
                    </div>

                    <div class="gen-field">
                        <label>Resolución / Formato</label>
                        <select id="mgRes">
                            <option value="512x512">512x512</option>
                            <option value="1024x1024" selected>1024x1024</option>
                            <option value="1216x832">1216x832 (Landscape)</option>
                            <option value="832x1216">832x1216 (Portrait)</option>
                        </select>
                    </div>
                    ` : `
                    <div class="gen-field">
                        <label>Estilo Literario</label>
                        <select id="mgStyle">
                            <option value="Creativo">Creativo</option>
                            <option value="Técnico">Técnico</option>
                            <option value="Poético">Poético</option>
                        </select>
                    </div>
                    `}

                    <!-- INPUTS DINÁMICOS PARA REFERENCIAS -->
                    ${(currentMode === 'imagen' && currentSub === 'img2img') ? `
                        <div class="gen-field">
                            <label>Nº Imágenes</label>
                            <select id="mgImgCount">
                                <option value="1" ${currentImgCount === 1 ? 'selected' : ''}>1</option>
                                <option value="2" ${currentImgCount === 2 ? 'selected' : ''}>2</option>
                                <option value="3" ${currentImgCount === 3 ? 'selected' : ''}>3</option>
                            </select>
                        </div>
                        ${Array.from({length: currentImgCount}).map((_, i) => `
                            <div class="gen-field">
                                <label>Imagen ${i+1}</label>
                                <div class="input-with-btn">
                                    <input type="text" id="mgInputImage${i+1}" placeholder="Ej: imagen/foto.png">
                                    <button class="btn-link-gallery" data-target="mgInputImage${i+1}" title="Usar seleccionada de galería">🔗</button>
                                </div>
                            </div>
                        `).join('')}
                    ` : ''}

                    ${(currentMode === '3d' && currentSub === 'img_to_3d') || (currentMode === 'video' && ['img2video', 'Img+Audio2Video'].includes(currentSub)) ? `
                        <div class="gen-field">
                            <label>Imagen Base</label>
                            <div class="input-with-btn">
                                <input type="text" id="mgInputImageBase" placeholder="Selecciona de galería...">
                                <button class="btn-link-gallery" data-target="mgInputImageBase" title="Usar seleccionada">🔗</button>
                            </div>
                        </div>
                    ` : ''}

                    ${currentMode === 'video' && currentSub === 'Img+Audio2Video' ? `
                        <div class="gen-field">
                            <label>Audio de Referencia</label>
                            <div class="input-with-btn">
                                <input type="text" id="mgInputAudioBase" placeholder="Selecciona un audio...">
                                <button class="btn-link-gallery" data-target="mgInputAudioBase" title="Usar seleccionado">🔗</button>
                            </div>
                        </div>
                    ` : ''}
                `;

                // Eventos de botones de enlace
                mgParams.querySelectorAll('.btn-link-gallery').forEach(btn => {
                    btn.onclick = () => {
                        const targetId = btn.getAttribute('data-target');
                        const targetInput = document.getElementById(targetId);
                        if (this.lastSelectedGalleryPath) {
                            targetInput.value = this.lastSelectedGalleryPath;
                            targetInput.classList.add('highlight-flash');
                            setTimeout(() => targetInput.classList.remove('highlight-flash'), 500);
                        } else {
                            alert("Primero haz clic en una imagen o audio de la galería para seleccionarlo.");
                        }
                    };
                });

                // Eventos de controles
                const mgSub = document.getElementById('mgSub');
                if (mgSub) {
                    mgSub.onchange = (e) => {
                        currentSub = e.target.value;
                        renderControls();
                    };
                }

                const mgImgCount = document.getElementById('mgImgCount');
                if (mgImgCount) {
                    mgImgCount.onchange = (e) => {
                        currentImgCount = parseInt(e.target.value);
                        renderControls();
                    };
                }
            };

            mgBtnGen.onclick = async () => {
                const prompt = mgPrompt.value;
                if (!prompt) return alert("Escribe un prompt.");

                mgBtnGen.disabled = true;
                const originalText = mgBtnGen.innerHTML;
                mgBtnGen.innerHTML = '<span class="loading-spinner"></span> ENVIANDO...';

                const workflowEl = document.getElementById('mgWorkflow');
                const resEl = document.getElementById('mgRes');
                
                // Recoger inputs de referencia
                const imgFiles = [];
                for(let i=1; i<=3; i++) {
                    const val = document.getElementById(`mgInputImage${i}`)?.value;
                    if(val) imgFiles.push(val);
                }
                const imgBase = document.getElementById('mgInputImageBase')?.value;
                const audBase = document.getElementById('mgInputAudioBase')?.value;

                const params = {
                    prompt: prompt,
                    mode: currentMode === 'imagen' ? 'Imagen' : (currentMode.charAt(0).toUpperCase() + currentMode.slice(1)),
                    params: {
                        engine: "ComfyUI",
                        workflow: workflowEl ? workflowEl.value : null,
                        res: resEl ? resEl.value : "1024x1024",
                        type: currentMode === 'imagen' ? 'Simple' : currentMode,
                        subtype: currentSub,
                        img_count: currentImgCount,
                        input_image_1: imgFiles[0] || imgBase || null,
                        input_image_2: imgFiles[1] || null,
                        input_image_3: imgFiles[2] || null,
                        input_image: imgBase || imgFiles[0] || null,
                        input_audio_1: audBase || null,
                        input_audio: audBase || null,
                        "3d_input_image": imgBase || null,
                        video_subtype: currentMode === 'video' ? currentSub : null,
                        audio_type: currentMode === 'audio' ? currentSub : null
                    }
                };

                try {
                    console.log("[ASIMOD][MG] Enviando petición a:", `/v1/modules/media_generator/action`);
                    console.log("[ASIMOD][MG] Payload:", params);

                    const resp = await fetch(`/v1/modules/media_generator/action`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ action: 'handle_generate_from_web', params })
                    });
                    const resData = await resp.json();
                    
                    if (resData.status === 'success') {
                        if (resData.result?.type === 'file') {
                            this.previewMedia({
                                name: resData.result.filename,
                                url: resData.result.url,
                                type: currentMode === 'video' ? 'video' : (currentMode === 'audio' ? 'audio' : 'image')
                            });
                        } else if (resData.result?.type === 'text') {
                            // Si es texto, suele ser un error retornado como texto o una respuesta LLM
                            const content = resData.result.content;
                            if (content.startsWith("Error:") || content.startsWith("Fallo:")) {
                                alert("Error del Servidor: " + content);
                            } else {
                                this.previewMedia({
                                    name: "Resultado de Texto",
                                    type: 'text',
                                    content: content
                                });
                            }
                        }
                        this.loadGallery(currentMode === 'imagen' ? 'imagen' : (currentMode === 'texto' ? 'texto' : currentMode));
                    } else {
                        alert("Error: " + resData.message);
                    }
                } catch (e) {
                    alert("Error de red.");
                } finally {
                    mgBtnGen.disabled = false;
                    mgBtnGen.innerHTML = originalText;
                }
            };

            // Restaurar galería global al salir del módulo
            const originalActivate = this.activateModule.bind(this);
            this.activateModule = (id) => {
                this.galleryList = oldGalleryList;
                originalActivate(id);
            };

            // Init
            renderTabs();
            renderControls();
            console.log("[ASIMOD] Inicializando galería de Media Generator...");
            this.loadGallery('imagen', 'media_generator');

        } catch (e) {
            mgParams.innerHTML = `<div style="color:red; padding:20px;">Error inicializando panel.</div>`;
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
