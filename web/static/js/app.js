const socket = io();
let currentPage = 'dashboard';
let cameras = [];
let events = [];
let cameraConfig = [];

function escapeHtml(str) {
    if (!str) return '';
    return String(str).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#039;');
}

document.addEventListener('DOMContentLoaded', () => {
    initNavigation();
    initClock();
    initModeSelect();
    initConfidenceSlider();
    loadDashboard();
    loadCameraConfig();
    setupSocketListeners();
    setInterval(refreshData, 5000);
    addLog('JARVIS Home Security System initialized');
});

// === NAVIGATION ===
function initNavigation() {
    document.querySelectorAll('.nav-links li[data-page]').forEach(item => {
        item.addEventListener('click', () => switchPage(item.dataset.page));
    });
}

function switchPage(page) {
    currentPage = page;
    document.querySelectorAll('.nav-links li').forEach(li => li.classList.remove('active'));
    const active = document.querySelector(`[data-page="${page}"]`);
    if (active) active.classList.add('active');
    document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
    const el = document.getElementById(`page-${page}`);
    if (el) el.classList.add('active');
    document.getElementById('page-title').textContent = getPageTitle(page);

    if (page === 'cameras') loadFullCameras();
    if (page === 'events') loadFullEvents();
    if (page === 'zones') loadZones();
    if (page === 'system') loadSystemInfo();
    if (page === 'chat') loadChatHistory();
    if (page === 'telegram-chat') loadTelegramChatHistory();
    if (page === 'setup-cameras') loadCameraConfig();
    if (page === 'setup-telegram') loadTelegramConfig();
    if (page === 'setup-llm') loadLLMConfig();
    if (page === 'settings') loadSettings();
}

function getPageTitle(p) {
    const t = { dashboard:'Dashboard', cameras:'Cameras', events:'Events', zones:'Zones', recordings:'Recordings', chat:'JARVIS AI', 'telegram-chat':'Telegram', system:'System', 'setup-cameras':'Camera Setup', 'setup-telegram':'Telegram Setup', 'setup-llm':'AI Setup', settings:'Settings' };
    return t[p] || p;
}

function initClock() {
    const u = () => { document.getElementById('clock').textContent = new Date().toLocaleString('en-US', {weekday:'short',month:'short',day:'numeric',hour:'2-digit',minute:'2-digit',second:'2-digit'}); };
    u(); setInterval(u, 1000);
}

function initModeSelect() {
    document.getElementById('mode-select').addEventListener('change', function() { setMode(this.value); });
}

function initConfidenceSlider() {
    const s = document.getElementById('set-confidence');
    const d = document.getElementById('confidence-value');
    if (s && d) s.addEventListener('input', () => d.textContent = s.value);
}

function setupSocketListeners() {
    socket.on('new_event', (event) => {
        events.unshift(event);
        if (events.length > 50) events.pop();
        if (currentPage === 'dashboard') renderRecentEvents();
        if (currentPage === 'events') loadFullEvents();
        updateEventCount();
        addLog(`Event: ${event.camera_name} - ${event.event_type}`);
    });
    socket.on('camera_status', (data) => { updateCameraStatus(data.name, data.status); });
    socket.on('mode_changed', (data) => { document.getElementById('mode-select').value = data.mode; });
    socket.on('log_entry', (entry) => {
        const l = document.getElementById('log-output');
        if (!l) return;
        const levelColor = entry.level === 'ERROR' ? '#ff4444' : entry.level === 'WARNING' ? '#ffaa00' : '#00ff88';
        l.innerHTML += `<div><span style="color:#666">[${entry.time}]</span> <span style="color:${levelColor}">[${entry.source}]</span> ${entry.message}</div>`;
        l.scrollTop = l.scrollHeight;
    });
    socket.on('telegram_message', (msg) => {
        addTelegramMessage(msg.message, msg.role, msg.time);
        const status = document.getElementById('tg-chat-status');
        if (status) status.textContent = 'Connected — messages synced';
    });
}

// === API CALLS ===
async function api(url, opts = {}) {
    try {
        const res = await fetch(url, { headers: {'Content-Type':'application/json'}, ...opts });
        if (res.status === 401) {
            if (opts._noRedirect) return {login_required: true};
            window.location.href = '/login';
            return null;
        }
        return await res.json();
    } catch(e) { console.error('API error:', e); return null; }
}

async function loadDashboard() {
    await Promise.all([loadStatus(), loadCameras(), loadRecentEvents(), loadStats()]);
}

async function refreshData() {
    if (currentPage === 'dashboard') await Promise.all([loadStatus(), loadRecentEvents(), loadStats()]);
    if (currentPage === 'system') loadSystemInfo();
}

async function loadStatus() {
    const d = await api('/api/status');
    if (d) {
        document.getElementById('cameras-online').textContent = `${d.cameras.online}/${d.cameras.total}`;
        document.getElementById('mode-select').value = d.security_mode;

        const secEl = document.getElementById('security-status');
        if (d.cameras.online === 0 && d.cameras.total > 0) {
            secEl.textContent = 'NO CAMERAS';
            secEl.style.color = '#ef4444';
        } else if (d.jarvis && d.jarvis.status === 'limited') {
            secEl.textContent = 'LIMITED';
            secEl.style.color = '#f59e0b';
        } else if (d.jarvis && d.jarvis.status === 'degraded') {
            secEl.textContent = 'PARTIAL';
            secEl.style.color = '#f59e0b';
        } else if (d.cameras.online === d.cameras.total) {
            secEl.textContent = 'SECURE';
            secEl.style.color = '#22c55e';
        } else {
            secEl.textContent = 'MONITORING';
            secEl.style.color = '#3b82f6';
        }

        if (d.jarvis) {
            const j = d.jarvis;
            const stateEl = document.getElementById('jarvis-state');
            const reactorEl = document.querySelector('.reactor');
            stateEl.textContent = j.status.toUpperCase();
            stateEl.className = 'status-state';
            if (j.status === 'online') { stateEl.style.color = 'var(--success)'; reactorEl.style.background = 'radial-gradient(circle, var(--success) 30%, transparent 70%)'; reactorEl.style.boxShadow = '0 0 15px rgba(34,197,94,0.3)'; }
            else if (j.status === 'degraded') { stateEl.style.color = 'var(--warning)'; reactorEl.style.background = 'radial-gradient(circle, var(--warning) 30%, transparent 70%)'; reactorEl.style.boxShadow = '0 0 15px rgba(245,158,11,0.3)'; }
            else { stateEl.style.color = 'var(--danger)'; reactorEl.style.background = 'radial-gradient(circle, var(--danger) 30%, transparent 70%)'; reactorEl.style.boxShadow = '0 0 15px rgba(239,68,68,0.3)'; }
            stateEl.title = j.message;
        }
    }
}

async function loadCameras() {
    const d = await api('/api/cameras');
    if (d) { cameras = d.cameras; renderCameraGrid(); }
}

function renderCameraGrid() {
    const g = document.getElementById('camera-grid');
    g.innerHTML = '';
    cameras.forEach(cam => {
        g.innerHTML += `<div class="camera-card"><div class="camera-header"><span class="camera-name">${cam.name}</span><span class="camera-status"><span class="dot ${cam.connected?'online':''}"></span>${cam.connected?'Online':'Offline'}</span></div><div class="camera-feed">${cam.connected?`<img src="/api/camera/${encodeURIComponent(cam.name)}/stream" onerror="this.parentElement.innerHTML='<div class=placeholder><i class=fas fa-video-slash></i><span>Error</span></div>'">`:'<div class="placeholder"><i class="fas fa-video-slash"></i><span>Offline</span></div>'}</div></div>`;
    });
}

function loadFullCameras() {
    const c = document.getElementById('cameras-full');
    c.innerHTML = '<div class="camera-grid" style="grid-template-columns:repeat(auto-fit,minmax(400px,1fr))">' + cameras.map(cam => `<div class="camera-card"><div class="camera-header"><span class="camera-name">${cam.name}</span><span class="camera-status"><span class="dot ${cam.connected?'online':''}"></span>${cam.connected?'Online':'Offline'}</span></div><div class="camera-feed" style="aspect-ratio:16/9">${cam.connected?`<img src="/api/camera/${encodeURIComponent(cam.name)}/stream">`:'<div class="placeholder"><i class="fas fa-video-slash"></i><span>Offline</span></div>'}</div></div>`).join('') + '</div>';
}

async function loadRecentEvents() {
    const d = await api('/api/events?hours=2&limit=10');
    if (d) { events = d.events; renderRecentEvents(); updateEventCount(); }
}

function renderRecentEvents() {
    const c = document.getElementById('recent-events');
    c.innerHTML = events.length === 0 ? '<div style="padding:20px;text-align:center;color:var(--text-secondary);font-size:13px">No recent events</div>' :
        events.map(e => `<div class="event-item"><div class="event-severity ${e.severity||'medium'}"></div><div class="event-time">${fmtTime(e.timestamp)}</div><div class="event-info"><div class="event-title">${e.camera_name}</div><div class="event-desc">${e.description||e.event_type}</div></div></div>`).join('');
}

function updateEventCount() { document.getElementById('events-today').textContent = events.length; }

async function loadFullEvents() {
    const h = document.getElementById('events-hours')?.value || 2;
    const d = await api(`/api/events?hours=${h}&limit=50`);
    if (d) {
        document.getElementById('events-full-list').innerHTML = d.events.map(e => `<div class="event-item"><div class="event-severity ${e.severity||'medium'}"></div><div class="event-time">${fmtTime(e.timestamp)}</div><div class="event-info"><div class="event-title">${e.camera_name} - ${e.event_type}</div><div class="event-desc">${e.description||''}</div></div></div>`).join('');
    }
}
document.getElementById('events-hours')?.addEventListener('change', loadFullEvents);

async function loadStats() {
    const d = await api('/api/stats');
    if (d?.disk) document.getElementById('storage-usage').textContent = `${d.disk.percent}%`;
}

async function loadSystemInfo() {
    const d = await api('/api/stats');
    if (!d) return;
    if (d.cpu) {
        document.querySelector('#cpu-gauge .gauge-value').textContent = `${d.cpu.percent}%`;
        document.getElementById('cpu-details').innerHTML = `<div class="info-row"><span>Cores:</span><span>${d.cpu.cores}</span></div>`;
    }
    if (d.ram) {
        document.querySelector('#ram-gauge .gauge-value').textContent = `${d.ram.percent}%`;
        document.getElementById('ram-details').innerHTML = `<div class="info-row"><span>Used:</span><span>${d.ram.used}</span></div><div class="info-row"><span>Total:</span><span>${d.ram.total}</span></div>`;
    }
    if (d.disk) {
        document.querySelector('#disk-gauge .gauge-value').textContent = `${d.disk.percent}%`;
        document.getElementById('disk-details').innerHTML = `<div class="info-row"><span>Used:</span><span>${d.disk.used_gb.toFixed(1)} GB</span></div><div class="info-row"><span>Free:</span><span>${d.disk.free_gb.toFixed(1)} GB</span></div>`;
    }
}

async function loadZones() {
    const d = await api('/api/zones');
    if (d?.zones) {
        document.getElementById('zones-grid').innerHTML = Object.entries(d.zones).map(([n,z]) => `<div class="zone-card"><h4>${n}</h4><div class="zone-info"><span>Camera: ${z.camera||'Any'}</span><span>Type: ${z.type||'Detection'}</span><span>Status: Active</span></div></div>`).join('');
    }
}

async function loadSettings() {
    const d = await api('/api/settings');
    if (!d?.settings) return;
    const s = d.settings;
    setVal('set-mode', s.security?.mode);
    setVal('set-alert-threshold', s.security?.alert_threshold);
    setVal('set-night-start', s.security?.night_hours?.start);
    setVal('set-night-end', s.security?.night_hours?.end);
    setVal('set-auto-night', s.security?.auto_night || 'false');
    setVal('set-alert-sound', s.security?.alert_sound || 'true');
    setVal('set-detect-model', s.detection?.model);
    setVal('set-confidence', s.detection?.confidence_threshold);
    setVal('confidence-value', s.detection?.confidence_threshold);
    setVal('set-frame-interval', s.detection?.frame_interval);
    setVal('set-target-objects', (s.detection?.classes_to_detect || s.detection?.target_classes || ['person','car','motorcycle','truck']).join(','));
    setVal('set-recording-path', s.recording?.base_path || 'data/recordings');
    setVal('set-clip-duration', s.recording?.max_clip_duration);
    setVal('set-pre-buffer', s.recording?.pre_event_buffer);
    setVal('set-cleanup-days', s.recording?.retention_days);
    setVal('set-snapshot-quality', s.recording?.snapshot_quality || 'medium');
    setVal('set-reconnect-interval', s.cameras?.reconnect_interval || 30);
    setVal('set-max-reconnect', s.cameras?.max_reconnect_attempts || 5);
    setVal('set-stream-timeout', s.cameras?.stream_timeout || 30);
    setVal('set-default-cam-mode', s.cameras?.default_mode || 'rtsp');
    setVal('set-tg-alerts', s.telegram?.alerts_enabled ?? 'true');
    setVal('set-cam-offline-alert', s.telegram?.camera_offline_alert ?? 'true');
    setVal('set-alert-cooldown', s.telegram?.alert_cooldown || 60);
    setVal('set-daily-summary', s.telegram?.daily_summary || 'false');
    setVal('set-web-port', s.web?.port);
    setVal('set-refresh-rate', s.web?.refresh_rate || 5);
    setVal('set-session-timeout', s.web?.session_timeout || 2);
    setVal('set-log-level', s.advanced?.log_level || 'INFO');
    setVal('set-max-log-size', s.advanced?.max_log_size || 10);
    setVal('set-disk-check', s.advanced?.disk_check_interval || 60);
    setVal('set-min-free-disk', s.advanced?.min_free_disk || 5);
    const st = await api('/api/stats');
    if (st?.storage) {
        const el = document.getElementById('recording-storage-info');
        if (el) el.textContent = `${st.storage.total_size_mb.toFixed(0)} MB (${st.storage.total_files} files)`;
    }
}

function setVal(id, v) { const e = document.getElementById(id); if (e && v !== undefined) e.value = v; }

// === CAMERA SETUP ===
async function loadCameraConfig() {
    const d = await api('/api/cameras/config');
    if (d) { cameraConfig = d.cameras || []; renderCameraManageList(); }
}

function renderCameraManageList() {
    const c = document.getElementById('cameras-manage-list');
    if (!c) return;
    if (cameraConfig.length === 0) {
        c.innerHTML = '<div style="text-align:center;padding:40px;color:var(--text-secondary)"><i class="fas fa-video-slash" style="font-size:40px;margin-bottom:12px;display:block;opacity:0.3"></i>No cameras configured. Click "Add Camera" to get started.</div>';
        return;
    }
    c.innerHTML = cameraConfig.map((cam, i) => {
        const connected = cameras.find(c => c.name === cam.name)?.connected;
        return `<div class="camera-manage-card"><div class="camera-manage-info"><div class="cam-status-dot ${connected?'online':''}"></div><div class="cam-details"><h4>${cam.name}</h4><span>${cam.connection_mode.toUpperCase()} - ${cam.ip||cam.device_id||cam.file_path||'N/A'}</span></div></div><div class="camera-manage-actions"><button onclick="editCamera(${i})" title="Edit"><i class="fas fa-pen"></i></button><button class="delete" onclick="deleteCamera(${i})" title="Delete"><i class="fas fa-trash"></i></button></div></div>`;
    }).join('');
}

function showCameraForm(index = -1) {
    document.getElementById('camera-modal').style.display = 'flex';
    document.getElementById('cam-edit-index').value = index;
    if (index >= 0) {
        const cam = cameraConfig[index];
        document.getElementById('camera-form-title').textContent = 'Edit Camera';
        document.getElementById('cam-name').value = cam.name || '';
        document.getElementById('cam-mode').value = cam.connection_mode || 'rtsp';
        document.getElementById('cam-ip').value = cam.ip || '';
        document.getElementById('cam-port').value = cam.port || '';
        document.getElementById('cam-username').value = cam.username || '';
        document.getElementById('cam-password').value = cam.password || '';
        document.getElementById('cam-device-id').value = cam.device_id || 0;
        document.getElementById('cam-file-path').value = cam.file_path || '';
        document.getElementById('cam-rtsp-url').value = cam.rtsp_url || '';
        document.getElementById('cam-channel').value = cam.channel || 1;
        document.getElementById('cam-stream').value = cam.stream || 0;
    } else {
        document.getElementById('camera-form-title').textContent = 'Add Camera';
        document.getElementById('cam-name').value = '';
        document.getElementById('cam-mode').value = 'rtsp';
        document.getElementById('cam-ip').value = '';
        document.getElementById('cam-port').value = '554';
        document.getElementById('cam-username').value = '';
        document.getElementById('cam-password').value = '';
    }
    toggleCamModeFields();
}

function closeCameraForm() { document.getElementById('camera-modal').style.display = 'none'; }

function toggleCamModeFields() {
    const m = document.getElementById('cam-mode').value;
    document.getElementById('cam-fields-ip').style.display = ['usb','file'].includes(m) ? 'none' : 'block';
    document.getElementById('cam-fields-usb').style.display = m === 'usb' ? 'block' : 'none';
    document.getElementById('cam-fields-file').style.display = m === 'file' ? 'block' : 'none';
    document.getElementById('cam-fields-rtsp').style.display = ['rtsp','onvif'].includes(m) ? 'block' : 'none';
}

function editCamera(i) { showCameraForm(i); }

async function deleteCamera(i) {
    if (!confirm(`Delete camera "${cameraConfig[i].name}"?`)) return;
    await api('/api/cameras/config/delete', { method:'POST', body: JSON.stringify({index:i}) });
    loadCameraConfig();
}

async function saveCamera() {
    const cam = {
        name: document.getElementById('cam-name').value.trim(),
        connection_mode: document.getElementById('cam-mode').value,
        ip: document.getElementById('cam-ip').value.trim(),
        port: document.getElementById('cam-port').value.trim(),
        username: document.getElementById('cam-username').value.trim(),
        password: document.getElementById('cam-password').value,
        device_id: parseInt(document.getElementById('cam-device-id').value) || 0,
        file_path: document.getElementById('cam-file-path').value.trim(),
        rtsp_url: document.getElementById('cam-rtsp-url').value.trim(),
        channel: parseInt(document.getElementById('cam-channel').value) || 1,
        stream: parseInt(document.getElementById('cam-stream').value) || 0,
        recording: { enabled: document.getElementById('cam-recording').value !== 'disabled', mode: document.getElementById('cam-recording').value, quality: document.getElementById('cam-quality').value, retention_days: 7 }
    };
    if (!cam.name) { alert('Camera name is required'); return; }
    const idx = parseInt(document.getElementById('cam-edit-index').value);
    const d = await api('/api/cameras/config/save', { method:'POST', body: JSON.stringify({camera: cam, index: idx}) });
    closeCameraForm();
    await Promise.all([loadCameraConfig(), loadCameras(), loadStatus()]);
    addLog(d?.message || `Camera saved: ${cam.name}`);
}

async function testCamera() {
    const name = document.getElementById('cam-name').value.trim();
    if (!name) { alert('Enter camera name first'); return; }
    const cam = {
        name: name,
        ip: document.getElementById('cam-ip').value.trim(),
        port: document.getElementById('cam-port').value.trim(),
        connection_mode: document.getElementById('cam-mode').value,
        username: document.getElementById('cam-username').value.trim(),
        password: document.getElementById('cam-password').value
    };
    addLog(`Testing camera: ${name}...`);
    const r = document.getElementById('cam-test-result');
    if (r) r.innerHTML = '<div class="test-result">Connecting...</div>';
    const idx = parseInt(document.getElementById('cam-edit-index').value);
    const d = await api('/api/cameras/test', { method:'POST', body: JSON.stringify({camera: cam, index: idx}) });
    if (d?.success) {
        addLog(`Camera test OK: ${name} - ${d.message}`);
        if (r) r.innerHTML = `<div class="test-result success">${d.message}</div>`;
        if (d.connected) await Promise.all([loadCameras(), loadStatus()]);
    } else {
        addLog(`Camera test failed: ${name} - ${d.error}`);
        if (r) r.innerHTML = `<div class="test-result error">${d.error}</div>`;
    }
}

// === TELEGRAM SETUP ===
async function loadTelegramConfig() {
    const d = await api('/api/settings');
    if (d?.settings?.telegram) {
        const t = d.settings.telegram;
        document.getElementById('tg-token').value = t.bot_token || '';
        document.getElementById('tg-chat-id').value = t.chat_id || '';
    }
}

async function testTelegram() {
    const r = document.getElementById('tg-test-result');
    r.innerHTML = '<div class="test-result">Sending test message...</div>';
    const d = await api('/api/telegram/test', { method:'POST', body: JSON.stringify({ token: document.getElementById('tg-token').value, chat_id: document.getElementById('tg-chat-id').value }) });
    r.innerHTML = d?.success ? '<div class="test-result success">Test message sent! Check your Telegram.</div>' : `<div class="test-result error">Failed: ${d?.error||'Unknown error'}</div>`;
}

async function saveTelegram() {
    const d = await api('/api/settings', { method:'POST', body: JSON.stringify({ telegram: { bot_token: document.getElementById('tg-token').value, chat_id: document.getElementById('tg-chat-id').value } }) });
    addLog(d?.success ? 'Telegram settings saved' : 'Failed to save Telegram settings');
}

// === LLM SETUP ===
function toggleLLMFields() {
    const p = document.getElementById('llm-provider').value;
    document.getElementById('llm-fields-api').style.display = p === 'ollama' ? 'none' : 'block';
    document.getElementById('llm-fields-ollama').style.display = p === 'ollama' ? 'block' : 'none';
    if (p === 'gemini') document.getElementById('llm-step1').innerHTML = '<strong>API Key lo</strong><br><a href="https://aistudio.google.com/apikey" target="_blank">Google AI Studio</a> pe jao, free API key banao';
    if (p === 'openai') document.getElementById('llm-step1').innerHTML = '<strong>API Key lo</strong><br><a href="https://platform.openai.com/api-keys" target="_blank">OpenAI Platform</a> pe jao, API key banao';
}

async function loadLLMConfig() {
    const d = await api('/api/settings');
    if (d?.settings?.llm) {
        const l = d.settings.llm;
        document.getElementById('llm-provider').value = l.provider || 'gemini';
        document.getElementById('llm-personality').value = d.settings.jarvis?.personality || 'calm_reliable';
        const cfg = l[l.provider] || {};
        document.getElementById('llm-api-key').value = cfg.api_key || '';
        document.getElementById('llm-model-name').value = cfg.model || '';
        document.getElementById('llm-ollama-url').value = cfg.base_url || 'http://localhost:11434';
        document.getElementById('llm-ollama-model').value = cfg.model || '';
        toggleLLMFields();
    }
}

async function testLLM() {
    const r = document.getElementById('llm-test-result');
    r.innerHTML = '<div class="test-result">Testing AI connection...</div>';
    const d = await api('/api/llm/test', { method:'POST', body: JSON.stringify({ provider: document.getElementById('llm-provider').value, api_key: document.getElementById('llm-api-key').value, model: document.getElementById('llm-model-name').value || document.getElementById('llm-ollama-model').value }) });
    r.innerHTML = d?.success ? `<div class="test-result success">AI responded: ${d.response}` : `<div class="test-result error">Failed: ${d?.error||'Check API key and try again'}</div>`;
}

async function saveLLM() {
    const p = document.getElementById('llm-provider').value;
    const cfg = p === 'ollama'
        ? { base_url: document.getElementById('llm-ollama-url').value, model: document.getElementById('llm-ollama-model').value }
        : { api_key: document.getElementById('llm-api-key').value, model: document.getElementById('llm-model-name').value };
    const d = await api('/api/settings', { method:'POST', body: JSON.stringify({ llm: { provider: p, [p]: cfg }, jarvis: { personality: document.getElementById('llm-personality').value } }) });
    addLog(d?.success ? 'AI settings saved' : 'Failed to save AI settings');
}

// === ACTIONS ===
async function setMode(mode) {
    await api('/api/mode', { method:'POST', body: JSON.stringify({mode}) });
}

async function saveSettings() {
    await api('/api/settings', { method:'POST', body: JSON.stringify({
        security: { mode: document.getElementById('set-mode').value, alert_threshold: document.getElementById('set-alert-threshold').value, night_hours: { start: document.getElementById('set-night-start').value, end: document.getElementById('set-night-end').value }, auto_night: document.getElementById('set-auto-night').value, alert_sound: document.getElementById('set-alert-sound').value },
        detection: { model: document.getElementById('set-detect-model').value, confidence_threshold: parseFloat(document.getElementById('set-confidence').value), frame_interval: parseInt(document.getElementById('set-frame-interval').value), classes_to_detect: document.getElementById('set-target-objects').value.split(',').map(s=>s.trim()) },
        recording: { base_path: document.getElementById('set-recording-path').value, max_clip_duration: parseInt(document.getElementById('set-clip-duration').value), pre_event_buffer: parseInt(document.getElementById('set-pre-buffer').value), retention_days: parseInt(document.getElementById('set-cleanup-days').value), snapshot_quality: document.getElementById('set-snapshot-quality').value },
        cameras: { reconnect_interval: parseInt(document.getElementById('set-reconnect-interval').value), max_reconnect_attempts: parseInt(document.getElementById('set-max-reconnect').value), stream_timeout: parseInt(document.getElementById('set-stream-timeout').value), default_mode: document.getElementById('set-default-cam-mode').value },
        telegram: { alerts_enabled: document.getElementById('set-tg-alerts').value, camera_offline_alert: document.getElementById('set-cam-offline-alert').value, alert_cooldown: parseInt(document.getElementById('set-alert-cooldown').value), daily_summary: document.getElementById('set-daily-summary').value },
        web: { port: parseInt(document.getElementById('set-web-port').value), refresh_rate: parseInt(document.getElementById('set-refresh-rate').value), session_timeout: parseInt(document.getElementById('set-session-timeout').value) },
        advanced: { log_level: document.getElementById('set-log-level').value, max_log_size: parseInt(document.getElementById('set-max-log-size').value), disk_check_interval: parseInt(document.getElementById('set-disk-check').value), min_free_disk: parseInt(document.getElementById('set-min-free-disk').value) }
    })});
    addLog('Settings saved');
}

async function changePassword() {
    const oldPw = document.getElementById('pw-old').value;
    const newPw = document.getElementById('pw-new').value;
    const confirmPw = document.getElementById('pw-confirm').value;
    if (!oldPw || !newPw) { addLog('Please fill all password fields'); return; }
    if (newPw.length < 8) { addLog('Password must be at least 8 characters'); return; }
    if (newPw !== confirmPw) { addLog('Passwords do not match'); return; }
    const d = await api('/api/password', { method:'POST', body: JSON.stringify({old_password:oldPw, new_password:newPw}) });
    if (d?.success) {
        addLog('Password changed successfully');
        document.getElementById('pw-old').value = '';
        document.getElementById('pw-new').value = '';
        document.getElementById('pw-confirm').value = '';
    } else {
        addLog('Password change failed: ' + (d?.error || 'Unknown error'));
    }
}

function takeSnapshotAll() {
    cameras.forEach(cam => {
        if (cam.connected) api(`/api/camera/${encodeURIComponent(cam.name)}/snapshot`);
    });
    addLog('Snapshot taken from all connected cameras');
}

function toggleRecording() { addLog('Manual recording started'); }

function addZone() { addLog('Zone editor coming soon'); }

function restartSystem() {
    if (confirm('Restart JARVIS system?')) {
        addLog('Restarting JARVIS...');
        api('/api/restart', {method: 'POST'}).then(d => addLog(d?.message || 'Restart signal sent'));
    }
}

// === CHAT ===
async function loadChatHistory() {
    const c = document.getElementById('chat-messages');
    if (!c) return;
    const d = await api('/api/chat/history');
    if (d?.messages && d.messages.length > 0) {
        c.innerHTML = '';
        d.messages.forEach(m => {
            const icon = m.role === 'user' ? 'fa-user' : 'fa-robot';
            const cls = m.role;
            const time = m.time ? new Date(m.time).toLocaleTimeString() : '';
            c.innerHTML += `<div class="message ${cls}"><div class="message-avatar"><i class="fas ${icon}"></i></div><div class="message-content"><p>${m.message}</p><span class="message-time">${time}</span></div></div>`;
        });
        c.scrollTop = c.scrollHeight;
    }
}

async function sendMessage() {
    const input = document.getElementById('chat-input');
    const msg = input.value.trim();
    if (!msg) return;
    addChatMessage(msg, 'user');
    input.value = '';
    const d = await api('/api/chat', { method:'POST', body: JSON.stringify({message:msg}) });
    if (d?.configured === false) {
        addChatMessage(d.response, 'jarvis-warning');
    } else {
        addChatMessage(d?.response || 'Systems experiencing interference. Please try again.', 'jarvis');
    }
}

function addChatMessage(text, sender) {
    const c = document.getElementById('chat-messages');
    const icon = sender === 'user' ? 'fa-user' : 'fa-robot';
    const cls = sender === 'jarvis-warning' ? 'jarvis warning' : sender;
    c.innerHTML += `<div class="message ${cls}"><div class="message-avatar"><i class="fas ${icon}"></i></div><div class="message-content"><p>${text}</p><span class="message-time">${new Date().toLocaleTimeString()}</span></div></div>`;
    c.scrollTop = c.scrollHeight;
}

// === TELEGRAM CHAT ===
async function loadTelegramChatHistory() {
    const c = document.getElementById('telegram-messages');
    if (!c) return;
    const d = await api('/api/telegram/chat/history');
    if (d?.messages && d.messages.length > 0) {
        c.innerHTML = '';
        d.messages.forEach(m => {
            addTelegramMessage(m.message, m.role, m.time, false);
        });
        c.scrollTop = c.scrollHeight;
    }
}

function addTelegramMessage(text, role, time, scroll = true) {
    const c = document.getElementById('telegram-messages');
    if (!c) return;
    const cls = role === 'user' ? 'user' : role === 'bot' ? 'jarvis' : role === 'alert' ? 'jarvis warning' : 'system';
    const icon = role === 'user' ? 'fa-user' : role === 'bot' ? 'fa-robot' : role === 'alert' ? 'fa-shield-alt' : 'fa-info-circle';
    const t = time ? new Date(time).toLocaleTimeString() : new Date().toLocaleTimeString();
    c.innerHTML += `<div class="message ${cls}"><div class="message-avatar"><i class="fas ${icon}"></i></div><div class="message-content"><p>${text}</p><span class="message-time">${t}</span></div></div>`;
    if (scroll) c.scrollTop = c.scrollHeight;
}

// === LOGS ===
function addLog(text) {
    const l = document.getElementById('log-output');
    if (!l) return;
    l.innerHTML += `<div>[${new Date().toLocaleTimeString()}] ${text}</div>`;
    l.scrollTop = l.scrollHeight;
}

function updateCameraStatus(name, status) {
    const cam = cameras.find(c => c.name === name);
    if (cam) { cam.connected = status === 'online'; renderCameraGrid(); addLog(`Camera ${name}: ${status}`); }
}

function fmtTime(ts) {
    if (!ts) return 'N/A';
    try { return new Date(ts).toLocaleTimeString('en-US', {hour:'2-digit',minute:'2-digit'}); } catch { return ts; }
}
