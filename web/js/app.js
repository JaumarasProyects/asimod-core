/**
 * ASIMOD Web Dashboard Engine
 * Gestor dinámico de temas y módulos.
 */

class AsimodApp {
    constructor() {
        this.modules = [];
        this.activeModule = null;
        this.style = null;
        
        // --- Motores de Audio (Web Audio API para Móviles) ---
        this.audioCtx = null;
        this.currentBufferSource = null;

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
        this.chatModeSelect = document.getElementById('chatMode');
        this.imagePreview = document.getElementById('imagePreview');
        this.previewImg = document.getElementById('previewImg');
        this.removeImg = document.getElementById('removeImg');
        this.closeChatBtn = document.getElementById('closeChat');
        this.chatMic = document.getElementById('chatMic'); // NUEVO
        
        // --- HUD Enrichment Elements ---
        this.hudLibraryBtn = document.getElementById('hudLibraryBtn');
        this.hudThreadSelect = document.getElementById('hudThreadSelect');
        this.hudNewThreadBtn = document.getElementById('hudNewThreadBtn');
        this.moodDots = {
            joy: document.querySelector('.mood-dot.joy'),
            anger: document.querySelector('.mood-dot.anger'),
            fear: document.querySelector('.mood-dot.fear'),
            stress: document.querySelector('.mood-dot.stress')
        };
        
        // --- PROPIEDADES DE AUDIO WEB ---
        this.mediaRecorder = null;
        this.audioChunks = [];
        this.isRecording = false;
        // Mobile chat trigger variable eliminada
        this.galleryToggle = document.getElementById('galleryToggle');
        this.currentGalleryPath = ''; // Track folder navigation
        this.currentImageBase64 = null;
        this.currentAudio = null; // Rastrear audio en reproducción
        this.currentCharVideo = {}; // Guardar configuración de video del personaje (NUEVO)
        this.mediaObjectURLs = new Set(); // Rastrear URLs para limpieza (NUEVO)

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

        // Referencia a personajes del registro para swaps rápidos
        this.characterRegistry = [];

        this.init();
    }

    async init() {
        console.log("[ASIMOD] Inicializando sistema unificado...");
        
        // 1. Sincronizar IDENTIDAD inmediatamente (Evita "Asimod" por defecto)
        await this.syncFullTechnicalState();
        
        this._injectGalleryStyles();
        
        // El registro de eventos debe ser lo primero para que la UI sea funcional
        this.setupEventListeners();
        
        await this.loadStyle();
        // Cargar módulos (operación lenta)
        await this.loadModules();
        await this.loadChatHistory();
        
        document.body.classList.remove('loading');

        // Polling constante para mantener la paridad (2s)
        setInterval(() => this.syncQuickStatus(), 2000);

        // --- CORE INTEGRATION: Escuchar mensajes de módulos (iFrames) ---
        window.addEventListener('message', (e) => this.handleModuleMessage(e));
    }

    async loadStyle() {
        try {
            const resp = await fetch('/v1/style?t=' + new Date().getTime());
            if (!resp.ok) throw new Error("Style Error");
            const data = await resp.json();
            this.style = data;
            
            const root = document.documentElement;
            if (data && data.colors) {

                Object.entries(data.colors).forEach(([key, value]) => {
                    const cssKey = `--${key.replace(/_/g, '-')}`;
                    root.style.setProperty(cssKey, value);
                });
            }

            // --- NUEVO: Cargar texturas si el estilo las define (Glass Neon) ---
            if (data && data.backgrounds) {
                const bgs = data.backgrounds;
                
                // Unificar si faltan algunos pero hay sidebar (consistencia para "las tres columnas")
                const fallbackBg = bgs.sidebar || bgs.center || null;
                
                const finalBgs = {
                    center: bgs.center || bgs.sidebar || null,
                    sidebar: bgs.sidebar || null,
                    chat: bgs.chat || bgs.sidebar || null,
                    module_box: bgs.module_box || bgs.sidebar || null,
                    button: bgs.button || null
                };

                const bgMapping = {
                    "center": "--bg-img-center",
                    "sidebar": "--bg-img-sidebar",
                    "chat": "--bg-img-chat",
                    "module_box": "--bg-img-box",
                    "button": "--bg-img-button"
                };

                Object.entries(finalBgs).forEach(([key, value]) => {
                    const cssVar = bgMapping[key];
                    if (cssVar) {
                        const urlValue = value ? `url('/${value.replace(/\\/g, '/')}')` : 'none';
                        root.style.setProperty(cssVar, urlValue);
                    }
                });
            } else {
                // Resetear si el tema no tiene imágenes
                ["--bg-img-center", "--bg-img-sidebar", "--bg-img-chat", "--bg-img-box"].forEach(v => {
                    root.style.setProperty(v, 'none');
                });
            }
        } catch (e) {
            console.error("[ASIMOD] El núcleo no proporcionó estilos.");
        }
    }

    async loadModules() {
        console.log("[ASIMOD] Iniciando carga de módulos desde /v1/modules...");
        try {
            const resp = await fetch('/v1/modules');
            if (!resp.ok) {
                console.error("[ASIMOD] Error HTTP al cargar módulos. Status:", resp.status);
                return;
            }
            const data = await resp.json();
            console.log("[ASIMOD] Respuesta de módulos recibida:", data);
            
            this.modules = data.modules || [];
            console.log(`[ASIMOD] Se han detectado ${this.modules.length} módulos.`);
            
            this.renderSidebar();
            
            // Auto-activar el primer módulo (o home si existe)
            const home = this.modules.find(m => m.id === 'home');
            if (home) {
                console.log("[ASIMOD] Activando módulo de inicio.");
                this.activateModule(home.id);
            } else if (this.modules.length > 0) {
                console.log(`[ASIMOD] Activando primer módulo disponible: ${this.modules[0].id}`);
                this.activateModule(this.modules[0].id);
            } else {
                console.warn("[ASIMOD] La lista de módulos está vacía.");
            }
            
            this.loadGallery(); // Cargar galería al inicio
            setInterval(() => this.syncQuickStatus(), 3000);
        } catch (e) {
            console.error("[ASIMOD] Error de excepción al cargar módulos:", e);
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

            // Actualizar Avatar HUD (NUEVO)
            this.updateAvatarHUD(status);

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

        // Sincronizar el selector del HUD
        this.populateSelect(this.hudThreadSelect, data.memories, currentId);
    }

    async syncQuickStatus() {
        try {
            const resp = await fetch('/v1/status');
            if (!resp.ok) return;
            const data = await resp.json();
            
            // 1. Detección de cambio de Estilo (Hot-Reload)
            if (data.current_style && this.style && data.current_style !== this.style.id) {
                console.log(`[ASIMOD] El tema ha cambiado a "${data.current_style}". Recargando...`);
                await this.loadStyle();
            }

            // 2. Detección de cambios técnicos críticos (Proveedor/Voz)
            if (this.techProvider && data.provider !== this.techProvider.value) {
                console.log(`[ASIMOD] El proveedor de IA ha cambiado a "${data.provider}".`);
                await this.refreshModels(data.provider, data.model);
            }
            if (this.charVoiceMotor && data.voice_provider !== this.charVoiceMotor.value) {
                console.log(`[ASIMOD] El motor de voz ha cambiado a "${data.voice_provider}".`);
                await this.refreshVoices(data.voice_provider, data.voice_id);
            }

            // 3. Sincronizar controles rápidos (Micrófono)
            if (this.micToggle) {
                const isActive = data.stt_mode !== 'OFF';
                this.micToggle.classList.toggle('active', isActive);
                this.micToggle.innerText = isActive ? '🎤' : '🎙️';
            }
            
            // 4. Sincronizar Avatar HUD e Identidad (Nombre, Personalidad, Videos)
            this.updateAvatarHUD(data);
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
        console.log(`[ASIMOD] Renderizando workspace para: ${mod.id} (${mod.name})`);

        const mid = mod.id.toLowerCase();

        // --- ESPECIAL: Media Generator Dashboard (Desktop Parity) ---
        if (mid === 'media_generator') {
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
                        <div id="mgIngredientsContainer" class="mg-ingredients-box" style="display:none;">
                            <label>📦 REFERENCIAS / INGREDIENTES</label>
                            <div id="mgIngredientsList" class="mg-ingredients-list"></div>
                        </div>
                        <div class="mg-prompt-side">
                            <textarea id="mgPrompt" placeholder="Describe lo que quieres crear... (PROMPT POSITIVO)"></textarea>
                            <textarea id="mgNegPrompt" placeholder="Lo que NO quieres que aparezca... (PROMPT NEGATIVO)" class="mg-neg-prompt"></textarea>
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
        
        // --- ESPECIAL: Sistema Module (Explorer Dashboard) ---
        if (mid === 'sistema' || mod.name.toLowerCase() === 'sistema') {
            const initialPath = "C:/";
            this.workspace.innerHTML = `
                <div class="sis-container">
                    <div class="sis-header">
                        <div class="sis-tabs" id="sisRoots">
                            <button class="sis-tab active" data-root="Principal">🏠 Principal</button>
                            <button class="sis-tab" data-root="Secundario">📀 Secundario</button>
                            <button class="sis-tab" data-root="Descargas">📥 Descargas</button>
                            <button class="sis-tab" data-root="Escritorio">🖥️ Escritorio</button>
                        </div>
                        <div class="sis-path-bar">
                            <button id="sisBtnBack" class="icon-btn" title="Atrás">⬅</button>
                            <span id="sisCurrentPath" class="path-text">${initialPath}</span>
                            <button id="sisBtnRefresh" class="icon-btn" title="Refrescar">🔄</button>
                        </div>
                    </div>
                    
                    <div class="sis-body">
                        <div class="sis-gallery-panel">
                            <div class="sis-file-list" id="sisFileList">
                                <div style="padding:40px; text-align:center; color:var(--text-dim);">Cargando explorador...</div>
                            </div>
                        </div>
                        <div class="sis-viewer-panel" id="sisViewer">
                            <div class="viewer-placeholder">
                                <div class="icon">📂</div>
                                <p>Selecciona un archivo del sistema para previsualizar</p>
                            </div>
                        </div>
                    </div>
                </div>
            `;
            this.initSistemaPanel();
            return;
        }

        // --- Otros módulos: Carga Modular Dinámica via IFRAME (Aisla estilos y scripts) ---
        if (mod.has_web_ui) {
            const assetPath = `/modules/${mod.id}/index.html?t=${Date.now()}`;
            console.log(`[ASIMOD] Cargando iframe para ${mod.id}: ${assetPath}`);
            this.workspace.innerHTML = `
                <iframe src="${assetPath}" 
                        style="width:100%; height:100%; border:none; background:transparent;" 
                        title="ASIMOD Module: ${mod.name}"
                        allow="camera; microphone; display-capture; clipboard-read; clipboard-write;">
                </iframe>
            `;
            return;
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
                    <div style="margin-top:20px; font-size:0.7rem; color:var(--accent); font-family:monospace;">DEBUG: ID=${mod.id} | NAME=${mod.name}</div>
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
            const audioUrl = `/v1/audio/file/${audioFilename}`;
            const playBtn = document.createElement('button');
            playBtn.className = 'icon-btn';
            playBtn.innerHTML = '▶ Reproducir';
            playBtn.style.marginTop = '10px';
            playBtn.style.fontSize = '0.8rem';
            playBtn.onclick = () => this.playAudioFile(audioUrl, true);
            msg.appendChild(playBtn);
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
                if (this.hudThreadSelect) this.hudThreadSelect.value = e.target.value;
                await this.loadChatHistory();
            };
        }

        if (this.hudThreadSelect) {
            this.hudThreadSelect.onchange = async (e) => {
                await fetch('/v1/memories', {
                    method: 'POST', headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({thread_id: e.target.value})
                });
                if (this.techMemory) this.techMemory.value = e.target.value;
                await this.loadChatHistory();
            };
        }

        if (this.btnNewThread) {
            this.btnNewThread.onclick = async () => this.createNewThread();
        }

        if (this.hudNewThreadBtn) {
            this.hudNewThreadBtn.onclick = async () => this.createNewThread();
        }

        if (this.hudLibraryBtn) {
            this.hudLibraryBtn.onclick = () => {
                 this.sendChatMessage("/biblioteca");
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

        if (this.micToggle) {
            this.micToggle.onclick = async () => {
                const currentMode = this.sttModeSelect ? this.sttModeSelect.value : 'OFF';
                const nextMode = currentMode === 'OFF' ? 'CHAT' : 'OFF';
                await fetch('/v1/stt/mode', {
                    method: 'POST', headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({mode: nextMode})
                });
                await this.syncQuickStatus();
            };
        }

        // Character Library Events (NUEVO)
        const openLibBtn = document.getElementById('avatarVisualizer');
        const libModal = document.getElementById('charLibraryModal');
        const closeLibBtn = document.getElementById('closeCharLibrary');

        if (openLibBtn) openLibBtn.onclick = () => this.openCharacterLibrary();
        if (closeLibBtn) closeLibBtn.onclick = () => libModal.style.display = "none";
        window.onclick = (event) => {
            if (event.target == libModal) libModal.style.display = "none";
        };

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

        // --- Voice Recording Logic (NUEVO) ---
        if (this.chatMic) {
            this.chatMic.onclick = () => this.toggleVoiceRecording();
        }

        // Chat Logic
        const chatInput = document.getElementById('chatInput');
        const chatSend = document.getElementById('chatSend');
        const sendMessage = async () => {
            const text = chatInput.value.trim();
            if (!text) return;
            
            this.addChatMessage('user', text);
            chatInput.value = '';

            // WAKE UP AUDIO (REQUERIDO PARA MÓVILES): Reiniciar el contexto en la interacción
            this.initAudioContext();
            
            const typingMsg = this.addChatMessage('assistant', 'Escribiendo...', true);
            
            // Timeout de 120 segundos (2 minutos)
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), 120000);
            
            console.log(`[ASIMOD] Enviando petición: "${text.substring(0, 20)}..."`);
            
            try {
                const formData = new FormData();
                formData.append('text', text);
                formData.append('play_audio', 'true');
                
                if (this.chatModeSelect) {
                    formData.append('stt_mode', this.chatModeSelect.value);
                }
                
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
                    
                    // Mostrar emojis (NUEVO)
                    if (result.emojis && result.emojis.length > 0) {
                        this.showAvatarEmojis(result.emojis);
                    }
                    
                    // PRIORIDAD ATÓMICA: Reproducir Base64 si existe para evitar red extra
                    if (result.audio_b64) {
                        console.log("[ASIMOD] Reproduciendo audio atómico (Base64)");
                        const b64Data = result.audio_b64;
                        const mimeType = result.audio_path?.endsWith('.wav') ? 'audio/wav' : 'audio/mpeg';
                        this.playAudioFile(`data:${mimeType};base64,${b64Data}`, true);
                    } 
                    // Fallback a archivos si no hay B64 (Galerías, etc)
                    else if (result.audio_path) {
                        const audioUrl = `/v1/audio/file/${result.audio_path}`;
                        this.playAudioFile(audioUrl, true);
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
                backBtn.innerHTML = `<span class="icon">⬅</span> Atrás (Subir nivel)`;
                backBtn.onclick = (e) => {
                    e.stopPropagation();
                    const parts = this.currentGalleryPath.split(/[/\\]/);
                    if (parts.length > 0) {
                        parts.pop();
                        this.loadGallery(parts.join('/'));
                    }
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
            
            const tabs = ["Texto", "Imagen", "Audio", "Video", "3D", "Compuesta"];
            
            const renderTabs = () => {
                mgTabs.innerHTML = tabs.map(t => {
                    const id = t.toLowerCase();
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

            const fetchIngredients = async () => {
                try {
                    const resp = await fetch(`/v1/modules/media_generator/action`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ action: 'list_all_compound_pieces' })
                    });
                    const res = await resp.json();
                    if (res.status === 'success') {
                        const ingredients = res.result.ingredients || [];
                        const list = document.getElementById('mgIngredientsList');
                        if (list) {
                            list.innerHTML = ingredients.map(ing => `
                                <div class="ingredient-item">
                                    <input type="checkbox" class="mg-ing-check" id="ing_${ing.path}" value="${ing.path}">
                                    <label for="ing_${ing.path}"> ${ing.category === 'Personaje' ? '👤' : (ing.category === 'Escenario' ? '🌄' : '⛺')} ${ing.name}</label>
                                </div>
                            `).join('');
                        }
                    }
                } catch (e) { console.error("Error fetching ingredients:", e); }
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

                // Controlar visibilidad de ingredientes
                const ingBox = document.getElementById('mgIngredientsContainer');
                if (currentMode === 'compuesta') {
                    if (ingBox) ingBox.style.display = 'flex';
                    fetchIngredients();
                } else {
                    if (ingBox) ingBox.style.display = 'none';
                }

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
                const negPrompt = document.getElementById('mgNegPrompt')?.value || "";
                
                // Recoger ingredientes seleccionados
                const selectedRefs = [];
                document.querySelectorAll('.mg-ing-check:checked').forEach(cb => {
                    selectedRefs.push(cb.value);
                });

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
                        type: currentMode === 'imagen' ? 'Simple' : (currentMode === 'compuesta' ? 'Compuesto' : currentMode),
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
                        audio_type: currentMode === 'audio' ? currentSub : null,
                        neg_prompt: negPrompt
                    },
                    compound: {
                        type: currentMode === 'compuesta' ? 'Compuesto' : 'Simple',
                        subtype: 'Productos', 
                        category: currentSub.split('/')[0].charAt(0).toUpperCase() + currentSub.split('/')[0].slice(1), 
                        references: selectedRefs
                    },
                    source_doc: currentMode === 'compuesta' ? (imgBase || imgFiles[0] || null) : null
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

    // --- Sistema Module Logic ---
    // --- Sistema Module Logic ---
    async initSistemaPanel() {
        const sisRoots = document.getElementById('sisRoots');
        const sisFileList = document.getElementById('sisFileList');
        const sisCurrentPath = document.getElementById('sisCurrentPath');
        const sisBtnBack = document.getElementById('sisBtnBack');
        const sisBtnRefresh = document.getElementById('sisBtnRefresh');
        if (!sisRoots || !sisFileList) return;

        let currentPath = '';

        const loadGallery = async (path = "") => {
            sisFileList.innerHTML = '<div style="padding:40px; text-align:center; color:var(--text-dim);"><span class="loading-spinner"></span></div>';
            try {
                const url = `/v1/gallery?module_id=sistema&path=${encodeURIComponent(path)}`;
                const resp = await fetch(url);
                const data = await resp.json();
                if (data.status === 'success') {
                    currentPath = data.current_path;
                    if (sisCurrentPath) sisCurrentPath.innerText = currentPath;
                    if (sisBtnBack) {
                        sisBtnBack.style.opacity = data.is_root ? '0.3' : '1';
                        sisBtnBack.style.pointerEvents = data.is_root ? 'none' : 'auto';
                    }
                    renderItems(data.items, data.is_root);
                } else {
                    sisFileList.innerHTML = `<div style="padding:40px; text-align:center; color:var(--accent);">${data.message || 'Error'}</div>`;
                }
            } catch (e) {
                sisFileList.innerHTML = `<div style="padding:40px; text-align:center; color:red;">Fallo de conexión al sistema</div>`;
            }
        };

        const renderItems = (items, isRoot) => {
            if (!items || items.length === 0) {
                sisFileList.innerHTML = '<div style="padding:40px; text-align:center; color:var(--text-dim); opacity:0.5;">VACÍO</div>';
                return;
            }

            let html = '';
            html += items.map(item => `
                <div class="sis-item ${item.type === 'folder' ? 'is-folder' : 'is-file'}" 
                     data-path="${item.path}" 
                     data-type="${item.type}" 
                     data-url="${item.url || ''}"
                     title="${item.name}">
                    <div class="sis-icon">${this.getIconForType(item.type)}</div>
                    <div class="sis-name">${item.name}</div>
                </div>
            `).join('');

            sisFileList.innerHTML = html;

            sisFileList.querySelectorAll('.sis-item').forEach(el => {
                el.onclick = () => {
                    const type = el.getAttribute('data-type');
                    const path = el.getAttribute('data-path');
                    const url = el.getAttribute('data-url');
                    
                    if (type === 'folder') {
                        loadGallery(path);
                    } else {
                        // Resaltar seleccionado
                        sisFileList.querySelectorAll('.sis-item').forEach(i => i.classList.remove('selected'));
                        el.classList.add('selected');
                        this.previewSistemaMedia({
                            name: el.querySelector('.sis-name').innerText,
                            type: type,
                            url: url,
                            path: path
                        });
                    }
                };
            });
        };

        // Eventos de Navegación (Tabs de Raíz)
        sisRoots.querySelectorAll('.sis-tab').forEach(btn => {
            btn.onclick = async () => {
                sisRoots.querySelectorAll('.sis-tab').forEach(t => t.classList.remove('active'));
                btn.classList.add('active');
                const rootMode = btn.getAttribute('data-root');
                console.log(`[Sistema] Cambiando raíz a: ${rootMode}`);
                // Disparar acción en el backend para que el módulo actualice su estado interno
                await this.executeModuleAction('on_menu_change', {mode: rootMode});
                loadGallery(""); // Cargar la nueva raíz enviada por el backend
            };
        });

        if (sisBtnBack) {
            sisBtnBack.onclick = () => {
                const parts = currentPath.split(/[/\\]/);
                if (parts.length > 1) {
                    parts.pop();
                    const parent = parts.join('/') || '/';
                    loadGallery(parent);
                }
            };
        }

        if (sisBtnRefresh) sisBtnRefresh.onclick = () => loadGallery(currentPath);

        // Carga inicial (Usar la raíz activa por defecto)
        await loadGallery("");
    }

    getIconForType(type) {
        switch(type) {
            case 'folder': return '📁';
            case 'image': return '🖼️';
            case 'video': return '🎬';
            case 'audio': return '🎵';
            case 'pdf': return '📄';
            case '3d': return '🧊';
            default: return '📄';
        }
    }

    async previewSistemaMedia(item) {
        const viewer = document.getElementById('sisViewer');
        if (!viewer) return;

        viewer.innerHTML = `
            <div style="height:100%; display:flex; flex-direction:column; align-items:center; justify-content:center; opacity:0.5;">
                <span class="loading-spinner"></span>
                <p style="margin-top:10px; font-size:0.8rem;">Procesando archivo...</p>
            </div>
        `;

        let contentHtml = '';
        const title = `<h3 style="margin-bottom:20px; color:var(--text-dim); font-size:0.75rem; letter-spacing:1px; text-transform:uppercase;">ARCHIVO: ${item.name}</h3>`;

        try {
            if (item.type === 'image') {
                contentHtml = `<img src="${item.url}" alt="${item.name}" style="max-height:80vh; border-radius:10px; box-shadow:0 10px 40px rgba(0,0,0,0.4);">`;
            } else if (item.type === 'video') {
                contentHtml = `<video src="${item.url}" controls autoplay loop style="max-width:100%; max-height:80vh; border-radius:10px;"></video>`;
            } else if (item.type === 'audio') {
                contentHtml = `
                    <div class="audio-player-premium" style="width:100%; max-width:500px;">
                        <span style="font-size:3rem; margin-bottom:20px;">🔊</span>
                        <div style="width:100%; text-align:center;">
                            <div style="font-weight:700; margin-bottom:5px; color:var(--accent);">${item.name}</div>
                            <audio src="${item.url}" controls autoplay style="width:100%; margin-top:20px;"></audio>
                        </div>
                    </div>
                `;
            } else if (item.type === 'pdf') {
                contentHtml = `<iframe src="${item.url}" style="width:100%; height:75vh; border:none; border-radius:10px; background:white;"></iframe>`;
            } else {
                // Intentar leer como texto si no es una de las anteriores
                try {
                    const resp = await fetch(item.url);
                    const head = resp.headers.get('content-type') || '';
                    if (head.includes('text') || head.includes('json') || head.includes('javascript') || item.name.endsWith('.md') || item.name.endsWith('.log')) {
                        const text = await resp.text();
                        contentHtml = `
                            <div style="width:100%; height:100%; background:rgba(0,0,0,0.3); padding:30px; border-radius:15px; overflow:auto; text-align:left; border: 1px solid rgba(255,255,255,0.05);">
                                <pre style="margin:0; font-family:'Consolas', monospace; font-size:0.85rem; color:var(--accent); line-height:1.6;">${text.replace(/</g, '&lt;').replace(/>/g, '&gt;')}</pre>
                            </div>
                        `;
                    } else {
                        throw new Error("Generic file");
                    }
                } catch (e) {
                    // Fallback para archivos binarios o desconocidos
                    contentHtml = `
                        <div class="card" style="padding:100px; text-align:center; background:rgba(255,255,255,0.02); border-radius:30px; border:1px dashed rgba(255,255,255,0.1);">
                            <div style="font-size:4.5rem; margin-bottom:25px; filter: grayscale(1);">📄</div>
                            <h3 style="margin-bottom:10px;">${item.name}</h3>
                            <p style="color:var(--text-dim); margin-bottom:30px; font-size:0.9rem;">Formato de visualización directa no soportado en web.</p>
                            <a href="${item.url}" download="${item.name}" class="btn-primary" style="display:inline-block; padding:12px 30px; text-decoration:none; border-radius:10px; font-weight:700;">DESCARGAR ARCHIVO</a>
                        </div>
                    `;
                }
            }
        } catch (e) {
            contentHtml = `<div style="color:var(--accent);">Error al previsualizar el archivo.</div>`;
        }
        
        viewer.innerHTML = `
            <div class="media-viewer-premium" style="width:100%; height:100%; display:flex; flex-direction:column; padding:20px;">
                ${title}
                <div style="flex:1; display:flex; align-items:center; justify-content:center; min-height:0;">
                    ${contentHtml}
                </div>
            </div>
        `;
    }

    updateAvatarHUD(status) {
        const nameEl = document.getElementById('avatarName');
        if (nameEl) nameEl.innerText = status.char_name || "Sistema";
        
        // 1. Guardar configuración actual para cambios de estado (IMPESCINDIBLE ANTES DE NADA)
        this.currentCharAvatar = status.char_avatar || {};
        this.currentCharVideo = status.char_video || {};
        this.currentCalibration = status.calibration || []; 
        
        // Sincronizar entradas del panel técnico si están visibles
        if (this.charNameInput && document.activeElement !== this.charNameInput) {
            this.charNameInput.value = status.char_name || "";
        }
        if (this.charPersInput && document.activeElement !== this.charPersInput) {
            this.charPersInput.value = status.char_personality || "";
        }
        
        // 2. ACTUALIZACIÓN DE MARCADORES DE HUMOR (CALIBRACIÓN) con Failsafe
        if (this.moodDots) {
            const calib = Array.isArray(status.calibration) ? status.calibration : [];
            const activeMoods = new Set();
            
            calib.forEach(c => {
                if (c && c.type) activeMoods.add(c.type);
            });

            // Detectar emoción actual basada en emojis si existen
            let currentEmotion = "normal";
            try {
                // Intentar detectar si hay mensaje reciente con emojis
                const lastMsg = status.last_msg || "";
                const emojis = lastMsg.match(/\p{Emoji_Presentation}/gu) || [];
                if (emojis.length > 0) {
                    currentEmotion = this._detectEmotion(emojis);
                }
            } catch(e) { console.warn("Error en detección de emoción ligera:", e); }
            
            for (const [mood, dot] of Object.entries(this.moodDots)) {
                if (dot) {
                    if (activeMoods.has(mood) || currentEmotion === mood) {
                        dot.classList.add('active');
                    } else {
                        dot.classList.remove('active');
                    }
                }
            }
        }
        
        // 3. LÓGICA DE Detección de Cambios y Renderizado de Vídeos
        const hud = document.getElementById('avatarContainer');
        const newStateHash = JSON.stringify({
            id: status.active_thread,
            name: status.char_name,
            video: status.char_video,
            avatar: status.char_avatar,
            emotion: hud ? hud.dataset.emotion : "normal",
            speaking: hud ? hud.classList.contains('speaking') : false
        });

        if (this.lastAvatarStateHash === newStateHash) return;
        this.lastAvatarStateHash = newStateHash;

        this.updateAvatarHUDState();
    }

    _detectEmotion(emojis) {
        if (!emojis || emojis.length === 0 || !this.currentCalibration) return "normal";
        
        const scores = { joy: 0, anger: 0, fear: 0, stress: 0 };
        emojis.forEach(emo => {
            const cal = this.currentCalibration[emo];
            if (cal) {
                Object.keys(scores).forEach(key => scores[key] += (cal[key] || 0));
            }
        });

        // Determinar ganadora por encima de un umbral (ej: 0.3)
        if (scores.anger > scores.joy && scores.anger > 0.3) return "anger";
        if (scores.joy > scores.anger && scores.joy > 0.3) return "joy";
        
        return "normal";
    }

    updateAvatarHUDState() {
        const hud = document.getElementById('avatarContainer');
        const fallbackEl = document.getElementById('avatarFallback');
        const imgEl = document.getElementById('avatarImage');
        
        // Videos Normales
        const vIdle = document.getElementById('avatarVideoIdle');
        const vTalking = document.getElementById('avatarVideoTalking');
        // Videos Joy
        const vIdleJoy = document.getElementById('avatarVideoIdle_joy');
        const vTalkingJoy = document.getElementById('avatarVideoTalking_joy');
        // Videos Anger
        const vIdleAnger = document.getElementById('avatarVideoIdle_anger');
        const vTalkingAnger = document.getElementById('avatarVideoTalking_anger');
        
        const allVideos = [vIdle, vTalking, vIdleJoy, vTalkingJoy, vIdleAnger, vTalkingAnger];
        
        if (!hud || !imgEl || !vIdle || !vTalking) return;

        const isSpeaking = hud.classList.contains('speaking');
        const currentEmotion = hud.dataset.emotion || "normal";
        
        const avatar = this.currentCharAvatar || {};
        const videoCfg = this.currentCharVideo || {};

        // Función interna para limpiar y normalizar URLs
        const toWebUrl = (path, bustCache = false) => {
            if (!path) return null;
            if (path.startsWith('http')) return path;
            const cleanPath = path.replace(/\\/g, '/');
            const url = cleanPath.startsWith('/') ? cleanPath : `/${cleanPath}`;
            return bustCache ? `${url}?t=${Date.now()}` : url;
        };

        // Reset visibility (ocultar todo por defecto)
        if (fallbackEl) fallbackEl.style.display = 'block';
        imgEl.style.display = 'none';
        allVideos.forEach(v => { if(v) v.style.display = 'none'; });

        // Mapeo de recursos por estado emocional
        const getResource = (emotion, type) => {
            // type: "idle" or "talking"
            if (emotion === "joy") {
                return videoCfg[`${type}_joy_url`] || videoCfg[`${type}_joy`] || videoCfg[`video_${type}_joy`];
            } else if (emotion === "anger") {
                return videoCfg[`${type}_anger_url`] || videoCfg[`${type}_anger`] || videoCfg[`video_${type}_anger`];
            }
            return videoCfg[`${type}_url`] || videoCfg[`${type}`] || videoCfg[`video_${type}`] || (type === "idle" ? videoCfg.video_loop : null);
        };

        const idleVideoUrl = toWebUrl(getResource("normal", "idle"));
        const talkingVideoUrl = toWebUrl(getResource("normal", "talking"));
        const joyIdleUrl = toWebUrl(getResource("joy", "idle"));
        const joyTalkingUrl = toWebUrl(getResource("joy", "talking"));
        const angerIdleUrl = toWebUrl(getResource("anger", "idle"));
        const angerTalkingUrl = toWebUrl(getResource("anger", "talking"));

        // Actualizar sources de video si han cambiado
        const updateSrc = (el, url) => {
            if (!el || !url) return;
            const currentPath = el.src ? new URL(el.src).pathname : '';
            if (currentPath !== url.split('?')[0]) {
                el.src = url;
                el.load();
            }
        };

        updateSrc(vIdle, idleVideoUrl);
        updateSrc(vTalking, talkingVideoUrl);
        updateSrc(vIdleJoy, joyIdleUrl);
        updateSrc(vTalkingJoy, joyTalkingUrl);
        updateSrc(vIdleAnger, angerIdleUrl);
        updateSrc(vTalkingAnger, angerTalkingUrl);

        // Seleccionar video activo basado en estado
        let activeVideo = null;
        if (isSpeaking) {
            if (currentEmotion === "joy" && joyTalkingUrl) activeVideo = vTalkingJoy;
            else if (currentEmotion === "anger" && angerTalkingUrl) activeVideo = vTalkingAnger;
            else activeVideo = vTalking;
        } else {
            if (currentEmotion === "joy" && joyIdleUrl) activeVideo = vIdleJoy;
            else if (currentEmotion === "anger" && angerIdleUrl) activeVideo = vIdleAnger;
            else activeVideo = vIdle;
        }

        // --- OPTIMIZACIÓN: Solo ocultar/mostrar si ha cambiado el video activo ---
        if (activeVideo && activeVideo.src) {
            // Solo pausar y ocultar los que NO son el activo
            allVideos.forEach(v => { 
                if (v && v !== activeVideo) {
                    if (v.style.display !== 'none') {
                        v.style.display = 'none';
                        v.pause();
                    }
                } 
            });

            // Solo mostrar y dar play si no estaba ya visible/reproduciendo
            if (activeVideo.style.display !== 'block') {
                activeVideo.style.display = 'block';
            }
            
            if (activeVideo.paused) {
                activeVideo.muted = true;
                activeVideo.playsInline = true;
                activeVideo.play().catch(() => {});
            }
            
            if (fallbackEl) fallbackEl.style.display = 'none';
            if (imgEl) imgEl.style.display = 'none';
        } else {
            // Fallback a imagen si no hay videos para el estado actual
            const idleImg = avatar.idle_url || avatar.idle || avatar.imagen_principal;
            const talkingImg = avatar.talking_url || avatar.talking || avatar.imagen_hablando;
            const currentImg = isSpeaking ? (talkingImg || idleImg) : idleImg;

            if (currentImg) {
                const imgUrl = toWebUrl(currentImg, true); // Cache bust para imágenes sí es útil si cambian
                if (imgEl.src !== imgUrl) imgEl.src = imgUrl;
                if (imgEl.style.display !== 'block') imgEl.style.display = 'block';
                
                allVideos.forEach(v => { if(v) { v.style.display = 'none'; v.pause(); } });
                if (fallbackEl) fallbackEl.style.display = 'none';
            }
        }
    }

    /**
     * Reproduce un archivo de audio mediante Fetch + Blob para máxima estabilidad
     * e incluye un monitor de diagnósticos avanzado para detectar cortes.
     */
    // Inicializa el motor de audio de bajo nivel
    initAudioContext() {
        if (!this.audioCtx) {
            this.audioCtx = new (window.AudioContext || window.webkitAudioContext)();
        }
        if (this.audioCtx.state === 'suspended') {
            this.audioCtx.resume();
        }
    }

    // Convierte Base64 a ArrayBuffer (para Web Audio API)
    base64ToArrayBuffer(base64) {
        const binaryString = window.atob(base64.split(',')[1] || base64);
        const len = binaryString.length;
        const bytes = new Uint8Array(len);
        for (let i = 0; i < len; i++) {
            bytes[i] = binaryString.charCodeAt(i);
        }
        return bytes.buffer;
    }

    /**
     * Reproduce un archivo de audio.
     * Si es Base64 (data:), usa el motor de bajo nivel Web Audio API para estabilidad móvil.
     * Si es una URL, usa el elemento <audio> con reintentos (para galerías).
     */
    async playAudioFile(url, linkToAvatar = false) {
        if (!url) return;
        console.log(`[Audio-Monitor] Playback solicitado: ${url.startsWith('data:') ? 'DATA_URI' : url}`);
        
        // 1. Limpieza de reproducciones anteriores
        if (this.currentAudio) {
            this.currentAudio.pause();
            this.currentAudio = null;
        }
        if (this.currentBufferSource) {
            try { this.currentBufferSource.stop(); } catch(e) {}
            this.currentBufferSource = null;
        }

        // --- CAMINO A: MOTOR WEB AUDIO API (Para Base64 / Chat) ---
        if (url.startsWith('data:')) {
            try {
                this.initAudioContext();
                const arrayBuffer = this.base64ToArrayBuffer(url);
                const audioBuffer = await this.audioCtx.decodeAudioData(arrayBuffer);
                
                const source = this.audioCtx.createBufferSource();
                source.buffer = audioBuffer;
                source.connect(this.audioCtx.destination);
                
                this.currentBufferSource = source;
                
                // Sincronización Avatar
                if (linkToAvatar) {
                    source.onended = () => {
                        const hud = document.getElementById('avatarContainer');
                        if (hud) {
                            hud.classList.remove('speaking');
                            this.updateAvatarHUDState();
                        }
                    };
                    
                    // Disparar HUD
                    setTimeout(() => {
                        const hud = document.getElementById('avatarContainer');
                        if (hud) {
                            hud.classList.add('speaking');
                            this.updateAvatarHUDState();
                        }
                    }, 100);
                }

                source.start(0);
                console.log("[Audio-Monitor] Motor WebAudio iniciado con éxito.");
                return;
            } catch (e) {
                console.error("[Audio-Monitor] Fallo en motor WebAudio:", e);
                // Fallback al elemento audio si falla el motorPro
            }
        }

        // --- CAMINO B: REPRODUCTOR ESTÁNDAR (Para URLs externas / Fallback) ---
        let blob = null;
        let objectUrl = null;
        let attempts = 0;
        const maxAttempts = 3;

        while (attempts < maxAttempts) {
                try {
                    attempts++;
                    // Añadir cache-busting para evitar versiones truncadas en el tunel
                    const fetchUrl = `${url}${url.includes('?') ? '&' : '?'}t_retry=${Date.now()}`;
                    console.log(`[Audio-Monitor] Intento ${attempts}/${maxAttempts} para: ${fetchUrl}`);
                    
                    const response = await fetch(fetchUrl);
                    if (!response.ok) throw new Error(`HTTP Error ${response.status}`);
                    
                    blob = await response.blob();
                    
                    // Validación estricta de integridad
                    if (blob.size < 100) {
                        throw new Error("Blob demasiado pequeño, posible truncamiento en túnel.");
                    }
                    
                    // Si llegamos aquí, el blob parece válido
                    objectUrl = URL.createObjectURL(blob);
                    this.mediaObjectURLs.add(objectUrl);
                    break; // Éxito, salimos del bucle
                    
                } catch (err) {
                    console.warn(`[Audio-Monitor] Fallo en intento ${attempts}: ${err.message}`);
                    if (attempts >= maxAttempts) throw err;
                    // Espera incremental antes del reintento
                    await new Promise(r => setTimeout(r, 200 * attempts));
                }
            }
        
        try {
            // 3. Configuración del Elemento de Audio
            const audio = new Audio(objectUrl);
            audio.preload = "auto";
            this.currentAudio = audio;
            
            // --- Monitor de Eventos (Diagnóstico) ---
            audio.onplay = () => console.log("[Audio-Monitor] Playback iniciado con éxito.");
            audio.onpause = () => {
                if (audio.currentTime > 0 && audio.currentTime < audio.duration) {
                    console.warn(`[Audio-Monitor] Pausa inesperada en seg ${audio.currentTime}.`);
                }
            };
            audio.onstalled = () => console.warn("[Audio-Monitor] Buffer estancado (stalled).");
            audio.onwaiting = () => console.log("[Audio-Monitor] Esperando datos (waiting)...");
            audio.onerror = (e) => {
                const err = audio.error;
                let msg = "Error desconocido";
                if (err) {
                    if (err.code === 1) msg = "Abortado por el usuario/sistema.";
                    if (err.code === 2) msg = "Error de red.";
                    if (err.code === 3) msg = "Error de decodificación (Formato no soportado).";
                    if (err.code === 4) msg = "Recurso no disponible.";
                }
                console.error(`[Audio-Monitor] ERROR CRÍTICO: ${msg}`, err);
            };

            // 4. Configuración de Sesión y Avatar
            if (linkToAvatar) {
                // MediaSession API para prioridad de sistema (Speech)
                if ('mediaSession' in navigator) {
                    navigator.mediaSession.metadata = new MediaMetadata({
                        title: 'Respuesta ASIMOD',
                        artist: this.charNameInput ? this.charNameInput.value : 'Avatar',
                        album: 'ASIMOD Core'
                    });
                    navigator.mediaSession.playbackState = "playing";
                }

                audio.addEventListener('play', () => {
                    // DESACOPLAMIENTO: Retrasamos el inicio del vídeo para no competir por CPU/Red
                    setTimeout(() => {
                        const hud = document.getElementById('avatarContainer');
                        if (hud) {
                            hud.classList.add('speaking');
                            this.updateAvatarHUDState();
                        }
                    }, 400); // 400ms de "ventaja" para el audio
                });

                audio.addEventListener('ended', () => {
                    const hud = document.getElementById('avatarContainer');
                    if (hud) {
                        hud.classList.remove('speaking');
                        this.updateAvatarHUDState();
                    }
                    if ('mediaSession' in navigator) navigator.mediaSession.playbackState = "none";
                    URL.revokeObjectURL(objectUrl);
                    this.mediaObjectURLs.delete(objectUrl);
                });
            }

            // 5. Reproducción
            await audio.play();
            
        } catch (e) {
            console.error("[Audio-Monitor] Fallo en pipeline estable:", e);
            // Fallback directo sin HUD si todo lo demás falla
            this.currentAudio = new Audio(url);
            this.currentAudio.play().catch(err => console.error("[Audio-Monitor] Fallback fallido también:", err));
        }
    }

    showAvatarEmojis(emojis) {
        const emojiEl = document.getElementById('avatarEmoji');
        if (!emojiEl) return;

        // Detectar emoción y aplicar al HUD (NUEVO)
        const emotion = this._detectEmotion(emojis);
        const hud = document.getElementById('avatarContainer');
        if (hud) {
            hud.dataset.emotion = emotion;
            console.log(`[ASIMOD] Emoción detectada en emojis: ${emotion}`);
        }

        emojiEl.innerText = emojis.join('');
        emojiEl.classList.add('visible');

        // Ocultar después de 5 segundos
        if (this.emojiTimeout) clearTimeout(this.emojiTimeout);
        this.emojiTimeout = setTimeout(() => {
            emojiEl.classList.remove('visible');
        }, 5000);
    }

    // --- CHARACTER HUB LOGIC (NUEVO) ---

    async openCharacterLibrary() {
        const modal = document.getElementById('charLibraryModal');
        const list = document.getElementById('charLibraryList');
        if (!modal || !list) return;

        modal.style.display = "block";
        list.innerHTML = `<div style="color:var(--accent); text-align:center; grid-column: 1/-1;">Cargando biblioteca...</div>`;

        try {
            const resp = await fetch('/v1/characters');
            const data = await resp.json();
            const characters = data.characters || [];

            if (characters.length === 0) {
                list.innerHTML = `<div style="color:#888; text-align:center; grid-column: 1/-1;">No hay personajes registrados.</div>`;
                return;
            }

            list.innerHTML = "";
            characters.forEach(char => {
                const card = document.createElement('div');
                card.className = "character-card";
                card.style = `
                    background: rgba(40,40,60,0.5);
                    border: 1px solid rgba(255,255,255,0.1);
                    border-radius: 12px;
                    padding: 15px;
                    cursor: pointer;
                    transition: all 0.3s ease;
                    text-align: center;
                `;
                
                const avatarImg = char.avatar && char.avatar.idle_url ? char.avatar.idle_url : '';
                
                card.innerHTML = `
                    <div style="width:70px; height:70px; border-radius:50%; background:#1a1a25; margin:0 auto 10px; overflow:hidden; border:2px solid var(--accent);">
                        ${avatarImg ? `<img src="${avatarImg}" style="width:100%; height:100%; object-fit:cover;">` : `<span style="font-size:30px; line-height:70px;">👤</span>`}
                    </div>
                    <div style="font-weight:bold; color:white; font-size:14px; margin-bottom:5px;">${char.name}</div>
                    <div style="font-size:11px; color:#aaa; line-height:1.2;">${(char.personality || 'Sin descripción').substring(0, 50)}...</div>
                `;

                card.onmouseenter = () => card.style.background = "rgba(100,200,180,0.1)";
                card.onmouseleave = () => card.style.background = "rgba(40,40,60,0.5)";
                
                card.onclick = () => this.applyCharacterFromHub(char);
                
                list.appendChild(card);
            });

        } catch (e) {
            list.innerHTML = `<div style="color:red; text-align:center; grid-column: 1/-1;">Error al cargar: ${e.message}</div>`;
        }
    }

    async applyCharacterFromHub(char) {
        console.log("[CharacterHub] Aplicando personaje:", char.name);
        
        // Cerrar modal
        const modal = document.getElementById('charLibraryModal');
        if (modal) modal.style.display = "none";

        // Crear/Actualizar memoria con los datos del personaje
        try {
            const payload = {
                thread_id: "New", // Forzar nuevo hilo o usar nombre
                name: char.name,
                personality: char.personality,
                voice_id: char.voice_id || char.voice?.id || "None",
                voice_provider: char.voice_provider || char.voice?.provider || "None",
                avatar: char.avatar || {},
                video: char.video || {}
            };

            const resp = await fetch('/v1/memories', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(payload)
            });

            if (resp.ok) {
                // Forzar sincronización total para actualizar HUD y UI
                await this.syncFullTechnicalState();
                this._appendSystemMessage(`Identidad: ${char.name} activa.`);
            } else {
                throw new Error("No se pudo aplicar el personaje");
            }

        } catch (e) {
            console.error("[CharacterHub] Error al aplicar:", e);
        }
    }

    /**
     * Maneja mensajes entrantes de módulos en iFrames
     */
    async handleModuleMessage(event) {
        const data = event.data;
        if (!data || !data.module) return;

        console.log(`[Core] Mensaje recibido del módulo ${data.module}:`, data);

        if (data.type === 'SWITCH_CHARACTER') {
            // Intentar buscar en el registro si no viene el objeto completo
            let char = data.character;
            if (!char && data.character_id) {
                if (this.characterRegistry.length === 0) {
                    const resp = await fetch('/v1/characters');
                    const d = await resp.json();
                    this.characterRegistry = d.characters || [];
                }
                char = this.characterRegistry.find(c => c.id === data.character_id || c.character_id === data.character_id);
            }

            if (char) {
                await this.applyCharacterFromHub(char);
            } else if (data.name) {
                // Si no está en el registro, usar los datos básicos enviados
                await this.applyCharacterFromHub({
                    name: data.name,
                    personality: data.personality || "Personaje de investigación",
                    avatar: data.avatar || {},
                    video: data.video || {}
                });
            }
        } else if (data.type === 'SYSTEM_MESSAGE') {
            this._appendSystemMessage(data.text);
        }
    }

    _appendSystemMessage(text) {
        this.addChatMessage("system", text);
    }

    // =========================================================
    // VOICE RECORDING (NUEVO)
    // =========================================================
    async toggleVoiceRecording() {
        if (this.isRecording) {
            this.stopWebRecording();
        } else {
            await this.startWebRecording();
        }
    }

    async startWebRecording() {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            this.audioChunks = [];
            this.mediaRecorder = new MediaRecorder(stream);
            
            this.mediaRecorder.ondataavailable = (event) => {
                this.audioChunks.push(event.data);
            };

            this.mediaRecorder.onstop = async () => {
                const audioBlob = new Blob(this.audioChunks, { type: 'audio/webm' });
                await this.uploadAudioForTranscription(audioBlob);
                
                // Cerrar stream para apagar el LED del micro
                stream.getTracks().forEach(track => track.stop());
            };

            this.mediaRecorder.start();
            this.isRecording = true;
            this.chatMic.classList.add('recording');
            this.chatMic.innerText = '⏹️'; // Cambiar icono a stop
            console.log("[ASIMOD] Grabación de voz iniciada...");
        } catch (err) {
            console.error("[ASIMOD] Error al acceder al micrófono:", err);
            alert("No se pudo acceder al micrófono. Por favor, revisa los permisos del navegador.");
        }
    }

    stopWebRecording() {
        if (this.mediaRecorder && this.isRecording) {
            this.mediaRecorder.stop();
            this.isRecording = false;
            this.chatMic.classList.remove('recording');
            this.chatMic.innerText = '🎤'; // Restaurar icono
            console.log("[ASIMOD] Grabación de voz detenida.");
        }
    }

    async uploadAudioForTranscription(blob) {
        const formData = new FormData();
        formData.append('file', blob, 'web_audio.webm');

        try {
            console.log("[ASIMOD] Enviando audio para transcripción...");
            const resp = await fetch('/v1/stt/transcribe', {
                method: 'POST',
                body: formData
            });

            const result = await resp.json();
            if (result.status === 'success' && result.text) {
                console.log("[ASIMOD] Transcripción recibida:", result.text);
                
                const chatInput = document.getElementById('chatInput');
                if (chatInput) {
                    chatInput.value = result.text;
                    // Auto-enviar el mensaje si el usuario lo desea
                    const chatSend = document.getElementById('chatSend');
                    if (chatSend) chatSend.click();
                }
            } else {
                console.warn("[ASIMOD] Transcripción fallida o vacía.");
            }
        } catch (err) {
            console.error("[ASIMOD] Error al subir audio:", err);
        }
    }
}

window.onload = () => { window.app = new AsimodApp(); };
