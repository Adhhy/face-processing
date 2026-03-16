const state = {
    activeTab: 'general',
    engineRunning: false,
    ws: null,
    stats: {
        present: 0,
        registered: 0
    },
    isAdminAuthenticated: false,
    settingsLoaded: false,
    debugSettingsSynced: false,
    systemLogsInterval: null
};

function initDebugToggles() {
    ['toggle-log', 'toggle-fps', 'toggle-overlay'].forEach(id => {
        const el = document.getElementById(id);
        if (el) {
            el.addEventListener('change', (e) => {
                apiCall('/api/admin/debug/toggle', 'POST', {
                    feature: id,
                    enabled: e.target.checked
                });
            });
        }
    });
}

function showTab(tabId) {
    state.activeTab = tabId;

    // Update navigation
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.toggle('active', btn.innerText.toLowerCase() === tabId);
    });

    // Update panes
    document.querySelectorAll('.tab-pane').forEach(pane => {
        pane.classList.toggle('active', pane.id === tabId);
    });

    // Handle Admin Gating
    if (tabId === 'admin' && !state.isAdminAuthenticated) {
        // Give a tiny delay for the tab transition to start
        setTimeout(() => {
            document.getElementById('admin-modal').classList.add('active');
        }, 100);
    }

    if (tabId === 'info') {
        fetchPolicyLogs();
    }
}

async function fetchPolicyLogs() {
    const res = await apiCall('/api/system/policy_logs', 'GET');
    if (res && res.status === 'success') {
        renderPolicyLogs(res.logs);
    }
}

function renderPolicyLogs(logs) {
    const container = document.getElementById('log-viewer');
    container.innerHTML = ''; // Clear existing

    if (!logs || logs.length === 0) {
        container.innerHTML = '<div class="log-item"><span class="msg">No activity logs found.</span></div>';
        return;
    }

    logs.forEach(log => {
        const item = document.createElement('div');

        if (log.type === 'raw') {
            item.className = 'log-item success';
            const ts = document.createElement('span');
            ts.className = 'ts';
            ts.innerText = `[${log.timestamp}]`;

            const msg = document.createElement('span');
            msg.className = 'msg';
            const conf = log.confidence ? (log.confidence * 100).toFixed(1) + '%' : 'N/A';
            msg.innerText = `Face detected: ${log.name} - Confidence ${conf}`;

            item.appendChild(ts);
            item.appendChild(msg);
        } else {
            // Warning class if late approval required or bus delayed
            const isWarning = log.late_approval_required || log.bus_delay_flag || log.event_type === "EXIT";
            item.className = `log-item ${isWarning ? 'warning' : 'success'}`;

            const ts = document.createElement('span');
            ts.className = 'ts';
            ts.innerText = `[${log.timestamp}]`;

            const msg = document.createElement('span');
            msg.className = 'msg';

            // e.g. "ENTRY recorded for Matthew (ID: CS123) during P1"
            let msgText = `${log.event_type} recorded for ${log.name} (${log.student_id}) during ${log.period || 'Unknown'} (${log.session || 'Unknown'})`;

            const tags = [];
            if (log.late_approval_required) tags.push("LATE");
            if (log.bus_delay_flag) tags.push("BUS DELAY");

            if (tags.length > 0) {
                msgText += ` - [${tags.join(", ")}]`;
            }

            msg.innerText = msgText;

            item.appendChild(ts);
            item.appendChild(msg);
        }
        container.appendChild(item);
    });
}

function closeAdminModal() {
    document.getElementById('admin-modal').classList.remove('active');
}

async function performAdminLogin() {
    const user = document.getElementById('admin-user').value;
    const pass = document.getElementById('admin-pass').value;
    const errorEl = document.getElementById('login-error');

    if (!user || !pass) return;

    errorEl.style.display = 'none';

    const res = await apiCall('/api/admin/login', 'POST', { username: user, password: pass });

    if (res && res.token) {
        state.isAdminAuthenticated = true;

        // Remove blur effect
        document.getElementById('admin').classList.remove('locked');

        closeAdminModal();

        // Clear fields
        document.getElementById('admin-user').value = '';
        document.getElementById('admin-pass').value = '';
    } else {
        errorEl.style.display = 'block';
    }
}

function togglePasswordVisibility() {
    const passInput = document.getElementById('admin-pass');
    const toggleBtn = document.querySelector('.toggle-password');
    if (passInput.type === 'password') {
        passInput.type = 'text';
        toggleBtn.innerText = '🔒';
    } else {
        passInput.type = 'password';
        toggleBtn.innerText = '👁️';
    }
}

// --- System Logs Functions ---
function openSystemLogsViewer() {
    document.getElementById('system-logs-modal').classList.add('active');
    fetchSystemLogs();

    // Auto-refresh every 5 seconds while modal is open
    if (state.systemLogsInterval) clearInterval(state.systemLogsInterval);
    state.systemLogsInterval = setInterval(fetchSystemLogs, 5000);
}

function closeSystemLogsViewer() {
    document.getElementById('system-logs-modal').classList.remove('active');
    if (state.systemLogsInterval) {
        clearInterval(state.systemLogsInterval);
        state.systemLogsInterval = null;
    }
}

async function fetchSystemLogs() {
    const res = await apiCall('/api/admin/system/logs', 'GET');
    const logsContainer = document.getElementById('admin-system-logs');

    if (res && res.logs) {
        logsContainer.innerHTML = '';
        if (res.logs.length === 0) {
            logsContainer.innerHTML = '<i>No system logs found.</i>';
            return;
        }

        let htmlBuffer = '<table style="width:100%; text-align:left; border-collapse: collapse;">';
        res.logs.forEach(line => {
            // Basic parsing expecting format: YYYY-MM-DD HH:MM:SS | LEVEL | Message
            const parts = line.split(' | ');
            if (parts.length >= 3) {
                const ts = parts[0].trim();
                const level = parts[1].trim();
                const msg = parts.slice(2).join(' | ').trim();

                let color = "var(--text-color)";
                if (level.includes('INFO')) color = "#4ade80"; // Bright Green
                if (level.includes('WARNING')) color = "#fbbf24"; // Bright Orange
                if (level.includes('ERROR')) color = "#f87171"; // Bright Red

                htmlBuffer += `
                    <tr style="border-bottom: 1px solid #333;">
                        <td style="padding: 4px; white-space: nowrap; color: #888; width: 140px;">${ts}</td>
                        <td style="padding: 4px; font-weight: bold; color: ${color}; width: 80px;">${level}</td>
                        <td style="padding: 4px;">${msg}</td>
                    </tr>
                `;
            } else {
                htmlBuffer += `<tr><td colspan="3" style="padding: 4px;">${line}</td></tr>`;
            }
        });
        htmlBuffer += '</table>';
        logsContainer.innerHTML = htmlBuffer;

        // Auto-scroll to bottom to show most recent logs
        logsContainer.scrollTop = logsContainer.scrollHeight;

    } else {
        logsContainer.innerHTML = '<span style="color: red;">Failed to fetch system logs. Check connection.</span>';
    }
}

// Add keyboard listeners for admin login
document.addEventListener('DOMContentLoaded', () => {
    const adminUser = document.getElementById('admin-user');
    const adminPass = document.getElementById('admin-pass');

    const handleEnter = (e) => {
        if (e.key === 'Enter') {
            performAdminLogin();
        }
    };

    if (adminUser) adminUser.addEventListener('keydown', handleEnter);
    if (adminPass) adminPass.addEventListener('keydown', handleEnter);
});

async function apiCall(url, method = 'GET', body = null) {
    try {
        const options = { method, headers: { 'Content-Type': 'application/json' } };
        if (body) options.body = JSON.stringify(body);

        const response = await fetch(url, options);
        const data = await response.json();

        if (url.includes('/engine/start')) updateEngineUI(true);
        if (url.includes('/engine/stop')) updateEngineUI(false);
        if (url.includes('/system/shutdown') && data.status === 'success') {
            alert("System shutting down. Closing tab...");
            window.close();
            // Fallback for some browsers
            setTimeout(() => { window.location.href = "about:blank"; }, 500);
        }

        return data;
    } catch (e) {
        console.error("API Error:", e);
    }
}

function updateEngineUI(running) {
    state.engineRunning = running;
    const dot = document.querySelector('.status-val .dot');
    const text = document.getElementById('engine-status-text');
    const playBtn = document.querySelector('.ctrl-btn.play');

    if (running) {
        dot.classList.add('running');
        text.innerText = "Running / Detecting";
        playBtn.style.opacity = "0.5";
        playBtn.style.pointerEvents = "none";
    } else {
        dot.classList.remove('running');
        text.innerText = "Stopped";
        playBtn.style.opacity = "1";
        playBtn.style.pointerEvents = "auto";
    }
}

function initWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    state.ws = new WebSocket(`${protocol}//${window.location.host}/ws`);

    state.ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        updateUI(data);
    };

    state.ws.onclose = () => {
        setTimeout(initWebSocket, 2000);
    };
}

function updateUI(data) {
    // Engine Status Sync
    if (typeof data.engine_running !== 'undefined') {
        if (data.engine_running !== state.engineRunning) {
            updateEngineUI(data.engine_running);
        }
    }

    // Connection Status Sync
    if (typeof data.connection_status !== 'undefined') {
        updateConnectionUI(data.connection_status, data.device_key);
    }

    // Frame Stream
    if (data.frame) {
        document.getElementById('camera-stream').src = `data:image/jpeg;base64,${data.frame}`;
    } else if (!state.engineRunning) {
        document.getElementById('camera-stream').src = "/static/img/profile_icon.png";
    }

    // System Stats
    if (data.stats) {
        // Footer stats
        document.getElementById('footer-pi').innerText = `● ${data.stats.model.toUpperCase()} - ${data.stats.cpu_usage}% LOAD`;

        // Tab specific stats
        if (state.activeTab === 'general') {
            document.getElementById('overlay-temp').innerText = `${data.stats.temp}°C`;

            // Update Overview Stats
            if (typeof data.stats.student_count !== 'undefined') {
                document.getElementById('stats-registered').innerText = data.stats.student_count;
                state.stats.registered = data.stats.student_count;
            }
            if (typeof data.stats.log_count !== 'undefined') {
                document.getElementById('stats-present').innerText = data.stats.log_count;
                state.stats.present = data.stats.log_count;
            }
        }

        if (state.activeTab === 'info') {
            document.getElementById('info-model').innerText = data.stats.model;
            document.getElementById('info-temp').innerText = `${data.stats.temp}°C`;

            if (data.stats.storage) {
                document.getElementById('info-storage').innerText = `${data.stats.storage.used} GB / ${data.stats.storage.total} GB`;
                const storageBar = document.querySelector('.storage-card .progress');
                if (storageBar) storageBar.style.width = `${data.stats.storage.percent}%`;
            }

            const uptimeEl = document.getElementById('info-uptime');
            if (uptimeEl) uptimeEl.innerText = data.stats.uptime;

            const ipEl = document.getElementById('info-ip');
            if (ipEl) ipEl.innerText = data.stats.ip;
        }

        // Admin specific settings sync
        if (state.activeTab === 'admin') {
            const startInput = document.getElementById('start-time');
            const endInput = document.getElementById('end-time');

            // Only sync once per session or after a manual save to avoid fighting user input
            if (!state.settingsLoaded && data.stats.start_time && data.stats.end_time) {
                startInput.value = data.stats.start_time;
                if (data.stats.end_time && document.activeElement !== endInput) {
                    endInput.value = data.stats.end_time;
                }
                state.settingsLoaded = true;
            }

            // Debug toggles sync (once)
            if (!state.debugSettingsSynced) {
                const logToggle = document.getElementById('toggle-log');
                if (logToggle && typeof data.stats.log_capture !== 'undefined') logToggle.checked = data.stats.log_capture;

                const fpsToggle = document.getElementById('toggle-fps');
                if (fpsToggle && typeof data.stats.show_fps !== 'undefined') fpsToggle.checked = data.stats.show_fps;

                const overlayToggle = document.getElementById('toggle-overlay');
                if (overlayToggle && typeof data.stats.show_overlay !== 'undefined') overlayToggle.checked = data.stats.show_overlay;

                state.debugSettingsSynced = true;
            }

            if (data.stats.temp) document.getElementById('admin-temp').innerText = `${data.stats.temp}°C`;
            if (data.stats.ram_usage) document.getElementById('admin-ram').innerText = `${data.stats.ram_usage}% used`;
            if (data.stats.uptime) document.getElementById('admin-uptime').innerText = data.stats.uptime;
        }

        // Footer db status
        if (typeof data.stats.db_connected !== 'undefined') {
            const dbFooter = document.getElementById('footer-db');
            if (dbFooter) {
                dbFooter.innerText = `● DATABASE: ${data.stats.db_connected ? 'CONNECTED' : 'DISCONNECTED'}`;
                dbFooter.style.color = data.stats.db_connected ? 'inherit' : 'var(--danger)';
            }
        }
    }

    // Recognition Events
    if (data.events && data.events.length > 0) {
        let hasRecognition = false;
        data.events.forEach(event => {
            appendLog(event);
            showRecognitionOverlay(event);
            if (event.type === 'recognition') {
                hasRecognition = true;
            }
        });

        // If a new face was recognized and we're on the info tab, refresh policy logs
        if (hasRecognition && state.activeTab === 'info') {
            // Slight delay to allow PolicyManager to process the event
            setTimeout(fetchPolicyLogs, 1500);
        }
    }

    // Hardware Status

    const hwVal = document.querySelector('.hw-val');
    if (hwVal && typeof data.camera_ok !== 'undefined') {
        hwVal.innerText = data.camera_ok ? "Camera OK" : "Camera Error";
        hwVal.style.color = data.camera_ok ? "inherit" : "var(--danger)";
    }
}

function showRecognitionOverlay(event) {
    const overlay = document.getElementById('id-overlay');
    const idSpan = document.getElementById('overlay-id');
    const nameSpan = document.getElementById('overlay-name');

    idSpan.innerText = "STD-" + event.name.substring(0, 3).toUpperCase();
    nameSpan.innerText = event.name.toUpperCase();

    overlay.style.display = 'block';
    setTimeout(() => {
        overlay.style.display = 'none';
    }, 3000);
}

function appendLog(event) {
    const container = document.getElementById('log-viewer');
    const item = document.createElement('div');
    item.className = `log-item ${event.status === 'Warning' ? 'warning' : 'success'}`;

    const ts = document.createElement('span');
    ts.className = 'ts';
    ts.innerText = `[${event.timestamp}]`;

    const msg = document.createElement('span');
    msg.className = 'msg';

    if (event.type === 'recognition') {
        msg.innerText = `Face detected: ${event.name} - Confidence 98.4%`;
    } else {
        msg.innerText = event.message;
    }

    item.appendChild(ts);
    item.appendChild(msg);
    container.prepend(item);
}

async function registerStudent() {
    const name = document.getElementById('reg-name').value;
    const id = document.getElementById('reg-id').value;
    const isBus = document.getElementById('reg-bus').checked;
    const btn = document.querySelector('.submit-btn');

    if (!name || !id) return alert("Name and ID required");

    btn.disabled = true;
    btn.innerText = "Processing...";

    const res = await apiCall('/api/student/register', 'POST', {
        name,
        id,
        is_bus_student: isBus
    });

    if (res && res.status === 'success') {
        alert("Registered successfully!");
        document.getElementById('reg-name').value = '';
        document.getElementById('reg-id').value = '';
        document.getElementById('reg-bus').checked = false;
        state.stats.registered++;
        document.getElementById('stats-registered').innerText = state.stats.registered;
    } else {
        alert("Registration failed.");
    }

    btn.disabled = false;
    btn.innerText = "Submit Registration";
}

async function saveSettings() {
    const startTime = document.getElementById('start-time').value;
    const endTime = document.getElementById('end-time').value;

    const res = await apiCall('/api/admin/settings', 'POST', {
        start_time: startTime,
        end_time: endTime
    });

    if (res && res.status === 'success') {
        state.settingsLoaded = false; // Trigger a fresh sync from server data
        alert("Settings saved successfully! The tracker will now follow this schedule.");
    } else {
        alert("Failed to save settings.");
    }
}

async function requestConnection() {
    const btn = document.getElementById('connect-btn');
    if (!btn) return;
    btn.disabled = true;

    const res = await apiCall('/api/system/connect', 'POST');
    console.log(res);
    if (res && res.status === 'success') {
        alert(`Connection request sent. Waiting for admin approval.`);
    } else if (res && res.message) {
        alert(res.message);
    } else {
        alert("Connection request failed.");
    }
    btn.disabled = false;
}

async function disconnectDevice() {
    if (!confirm("Are you sure you want to disconnect this device from the dashboard?")) return;

    const res = await apiCall('/api/system/disconnect', 'POST');
    if (res && res.status === 'success') {
        alert("Device disconnected.");
    } else {
        alert("Disconnection request failed or returned err.");
    }
}

function updateConnectionUI(status, device_key) {
    const btn = document.getElementById('connect-btn');
    const keyDisplay = document.getElementById('device-key-display');
    if (!btn) return;

    if (status === 'disconnected') {
        btn.innerHTML = '<span class="link-icon">🔗</span> Connect';
        btn.onclick = requestConnection;
        btn.className = 'status-btn';
        if (keyDisplay) keyDisplay.style.display = 'none';
    } else if (status === 'pending') {
        btn.innerHTML = '<span class="link-icon">⏳</span> Pending...';
        btn.onclick = null;
        btn.className = 'status-btn pending';
        if (keyDisplay && device_key) {
            keyDisplay.innerText = `Key: ${device_key}`;
            keyDisplay.style.display = 'inline-block';
        }
    } else if (status === 'connected') {
        btn.innerHTML = '<span class="link-icon">✅</span> Connected';
        btn.onclick = null;
        btn.className = 'status-btn success';
        if (keyDisplay) keyDisplay.style.display = 'none';
    }
}

// Start everything
initWebSocket();
initDebugToggles();
showTab('general');
