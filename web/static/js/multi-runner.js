/**
 * Multi-Runner - Dashboard for executing flows across multiple emulators sequentially/concurrently
 */

const state = {
    devices: [],
    flows: [],
    runners: {}, // deviceId -> { panelEl, active: boolean, stopController: AbortController }
    currentFlowId: null
};

document.addEventListener('DOMContentLoaded', () => {
    loadFlowList();
    loadDevices();
    setInterval(loadDevices, 15000); // refresh devices occasionally
    setInterval(updateRunnerStatuses, 5000); // verify active runners with backend
});

function loadFlowList() {
    fetch('/api/flows')
        .then(r => r.json())
        .then(flows => {
            state.flows = flows;
            const select = document.getElementById('flow-select');
            select.innerHTML = '<option value="">-- Select Flow --</option>';
            flows.forEach(f => {
                select.innerHTML += `<option value="${f.id}">${f.name} (${f.steps} steps)</option>`;
            });
            
            select.addEventListener('change', (e) => {
                state.currentFlowId = e.target.value;
            });
        });
}

async function loadDevices() {
    try {
        const res = await fetch('/api/devices');
        const data = await res.json();
        state.devices = data.devices || [];
        
        const container = document.getElementById('device-checkboxes');
        
        if (state.devices.length === 0) {
            container.innerHTML = '<span class="hint">No devices connected</span>';
            return;
        }
        
        // Preserve checked state
        const checkedIds = Array.from(container.querySelectorAll('input:checked')).map(cb => cb.value);
        
        container.innerHTML = '';
        state.devices.forEach(d => {
            const isChecked = checkedIds.includes(d.id) ? 'checked' : '';
            const statusIcon = d.status === 'device' ? '🟢' : '🔴';
            
            container.innerHTML += `
                <label class="device-checkbox">
                    <input type="checkbox" value="${d.id}" ${isChecked}>
                    ${statusIcon} ${d.model || d.id}
                </label>
            `;
        });
    } catch (e) {
        console.error("Error loading devices", e);
    }
}

async function updateRunnerStatuses() {
    if (Object.keys(state.runners).length === 0) return;
    
    try {
        const res = await fetch('/api/multi-run/status');
        const data = await res.json();
        const activeIds = data.runners.map(r => r.device_id);
        
        // Check if any local runners have stopped on backend
        Object.keys(state.runners).forEach(devId => {
            if (state.runners[devId].active && !activeIds.includes(devId)) {
                // Backend says it's not running, update UI
                state.runners[devId].active = false;
                updatePanelStatus(devId, 'idle', 'Finished');
            }
        });
    } catch (e) {
        console.error("Error updating statuses", e);
    }
}

function getSelectedDevices() {
    const container = document.getElementById('device-checkboxes');
    return Array.from(container.querySelectorAll('input:checked')).map(cb => cb.value);
}

function runAll() {
    if (!state.currentFlowId) {
        alert("Please select a flow first");
        return;
    }
    
    const selectedDevices = getSelectedDevices();
    if (selectedDevices.length === 0) {
        alert("Please select at least one device");
        return;
    }
    
    // Clear unused panels or empty state
    const grid = document.getElementById('runners-grid');
    const emptyState = grid.querySelector('.empty-state');
    if (emptyState) {
        emptyState.remove();
    }
    
    // Start flow for each selected device
    selectedDevices.forEach(deviceId => {
        if (!state.runners[deviceId] || !state.runners[deviceId].active) {
            createOrResetPanel(deviceId);
            runDeviceFlow(deviceId, state.currentFlowId);
        }
    });
}

function stopAll() {
    const activeRunners = Object.keys(state.runners).filter(id => state.runners[id].active);
    if (activeRunners.length === 0) return;
    
    if (confirm(`Stop ${activeRunners.length} active runners?`)) {
        activeRunners.forEach(deviceId => {
            stopDeviceFlow(deviceId);
        });
    }
}

function createOrResetPanel(deviceId) {
    const grid = document.getElementById('runners-grid');
    
    let panelEl = null;
    if (state.runners[deviceId]) {
        panelEl = state.runners[deviceId].panelEl;
    } else {
        const template = document.getElementById('runner-panel-template');
        panelEl = template.content.cloneNode(true).firstElementChild;
        panelEl.dataset.deviceId = deviceId;
        grid.appendChild(panelEl);
    }
    
    // Find device info
    const device = state.devices.find(d => d.id === deviceId);
    const name = device ? (device.model || device.id) : deviceId;
    
    // Setup UI
    panelEl.querySelector('.runner-title').textContent = `📱 ${name}`;
    panelEl.querySelector('.runner-log').innerHTML = ''; // Clear log
    panelEl.querySelector('.runner-current-step').textContent = 'Starting...';
    panelEl.querySelector('.runner-timer-container').innerHTML = '';
    
    // Link stop button
    const stopBtn = panelEl.querySelector('.btn-stop-runner');
    stopBtn.onclick = () => stopDeviceFlow(deviceId);
    stopBtn.style.display = 'block';
    
    // Update state
    updatePanelStatus(panelEl, 'running', 'Running');
    
    state.runners[deviceId] = {
        panelEl: panelEl,
        active: true,
        controller: new AbortController()
    };
    
    return panelEl;
}

function updatePanelStatus(deviceIdOrEl, statusType, statusText) {
    let panelEl = typeof deviceIdOrEl === 'string' ? 
        (state.runners[deviceIdOrEl] ? state.runners[deviceIdOrEl].panelEl : null) : 
        deviceIdOrEl;
        
    if (!panelEl) return;
    
    const statusBadge = panelEl.querySelector('.runner-status');
    statusBadge.className = `runner-status status-${statusType}`;
    statusBadge.textContent = statusText;
    
    if (statusType === 'idle' || statusType === 'error') {
        const stopBtn = panelEl.querySelector('.btn-stop-runner');
        if (stopBtn) stopBtn.style.display = 'none';
        
        const stepDisplay = panelEl.querySelector('.runner-current-step');
        if (stepDisplay) stepDisplay.textContent = statusText;
        
        const timerWrap = panelEl.querySelector('.runner-timer-container');
        if (timerWrap) timerWrap.innerHTML = '';
    }
}

function addPanelLog(deviceId, message, type = 'info') {
    if (!state.runners[deviceId]) return;
    const logBox = state.runners[deviceId].panelEl.querySelector('.runner-log');
    if (!logBox) return;
    
    const entry = document.createElement('div');
    entry.style.color = type === 'error' ? '#ef4444' : 
                        type === 'success' ? '#10b981' : 
                        type === 'warning' ? '#f59e0b' : '#a0a0a0';
    // Handle ANSI colors loosely if needed, for now just raw text
    entry.textContent = message;
    
    logBox.appendChild(entry);
    logBox.scrollTop = logBox.scrollHeight;
}

async function runDeviceFlow(deviceId, flowId) {
    const runner = state.runners[deviceId];
    if (!runner) return;
    
    addPanelLog(deviceId, `🚀 Starting flow: ${flowId}`, 'info');
    
    try {
        const payload = {
            device_id: deviceId,
            session_id: `multi_${deviceId}`,
            initialData: {} // We could add offset/total here if needed
        };
        
        const runRes = await fetch(`/api/flows/${flowId}/run`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
            signal: runner.controller.signal
        });
        
        if (!runRes.ok) {
            const errData = await runRes.json().catch(() => ({}));
            throw new Error(errData.error || `HTTP error ${runRes.status}`);
        }
        
        // Process NDJSON stream
        const reader = runRes.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        
        while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            
            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop(); // Keep incomplete line
            
            for (const line of lines) {
                if (!line.trim()) continue;
                try {
                    const msg = JSON.parse(line);
                    handleDeviceStreamMessage(deviceId, msg);
                } catch (e) {
                    console.error("Stream parse error", e, line);
                }
            }
        }
        
        if (state.runners[deviceId].active) {
            updatePanelStatus(deviceId, 'idle', 'Finished');
            state.runners[deviceId].active = false;
        }
        
    } catch (err) {
        if (err.name === 'AbortError') {
            addPanelLog(deviceId, '🛑 Run aborted centrally', 'warning');
        } else {
            addPanelLog(deviceId, `❌ Error: ${err.message}`, 'error');
            updatePanelStatus(deviceId, 'error', 'Error');
        }
        if (state.runners[deviceId]) {
            state.runners[deviceId].active = false;
        }
    }
}

function stopDeviceFlow(deviceId) {
    const runner = state.runners[deviceId];
    if (!runner || !runner.active) return;
    
    updatePanelStatus(deviceId, 'stopping', 'Stopping...');
    addPanelLog(deviceId, '🛑 Sending stop signal...', 'warning');
    
    fetch(`/api/flows/${state.currentFlowId}/stop`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ device_id: deviceId })
    })
    .then(r => r.json())
    .then(data => {
        addPanelLog(deviceId, 'Signal sent: ' + data.status, 'info');
    })
    .catch(err => {
        addPanelLog(deviceId, 'Error stopping: ' + err, 'error');
        updatePanelStatus(deviceId, 'error', 'Error Stop');
    });
}

function handleDeviceStreamMessage(deviceId, msg) {
    const runner = state.runners[deviceId];
    if (!runner) return;
    const panelEl = runner.panelEl;
    const stepEl = panelEl.querySelector('.runner-current-step');
    const timerWrap = panelEl.querySelector('.runner-timer-container');
    
    // Log messages
    if (msg.type === 'log') {
        addPanelLog(deviceId, msg.message, msg.level || 'info');
    } 
    // Step execution
    else if (msg.type === 'step_start') {
        stepEl.textContent = `⏳ ${msg.step}`;
        stepEl.style.color = '#60a5fa'; // Blue
    } 
    else if (msg.type === 'step_end') {
        const icon = msg.result === 'success' ? '✓' : '✗';
        const isError = msg.result !== 'success';
        stepEl.textContent = `${icon} ${msg.step}`;
        stepEl.style.color = isError ? '#ef4444' : '#10b981';
        timerWrap.innerHTML = ''; // clear timer
        
        addPanelLog(deviceId, `${msg.step} ${icon}`, isError ? 'error' : 'success');
    } 
    // Timers
    else if (msg.type === 'timer') {
        const remaining = Math.ceil(msg.remaining);
        const total = Math.ceil(msg.total);
        const pct = total > 0 ? ((total - remaining) / total) * 100 : 0;
        
        timerWrap.innerHTML = `
            <div style="background: rgba(0,0,0,0.3); border-radius: 4px; height: 16px; overflow: hidden; position: relative; margin-top: 5px;">
                <div style="background: #3b82f6; width: ${pct}%; height: 100%;"></div>
                <div style="position: absolute; width: 100%; top: 0; text-align: center; font-size: 11px; line-height: 16px; color: white;">
                    ${remaining}s
                </div>
            </div>
        `;
    } 
    // Batch process
    else if (msg.type === 'batch_row_start') {
        addPanelLog(deviceId, `\n📊 Row ${msg.row_index + 1}/${msg.total_rows}`, 'info');
        stepEl.textContent = `Row ${msg.row_index + 1}`;
    }
    // Completion/Stop
    else if (msg.type === 'completed' || msg.type === 'batch_completed') {
        addPanelLog(deviceId, `✅ Flow Completed`, 'success');
        updatePanelStatus(deviceId, 'idle', 'Completed');
        runner.active = false;
    }
    else if (msg.type === 'stopped' || msg.type === 'batch_stopped') {
        addPanelLog(deviceId, `🛑 Flow Stopped`, 'warning');
        updatePanelStatus(deviceId, 'idle', 'Stopped');
        runner.active = false;
    }
    else if (msg.type === 'error') {
        addPanelLog(deviceId, `❌ Server Error: ${msg.error}`, 'error');
        updatePanelStatus(deviceId, 'error', 'Server Error');
        runner.active = false;
    }
}
