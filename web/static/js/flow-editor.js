/**
 * Flow Editor - Visual Node-based Automation Editor
 */

// ==================== State ====================
const state = {
    nodes: new Map(),
    connections: [],
    selectedNode: null,
    dragging: null,
    connecting: null,
    nodeIdCounter: 1,
    currentFlowId: null,
    // Zoom and pan
    scale: 1,
    translateX: 0,
    translateY: 0,
    isPanning: false,
    panStart: { x: 0, y: 0 }
};

// Node type configurations
const nodeTypes = {
    tap: {
        icon: '👆', title: 'Tap', color: '#3b82f6',
        params: [
            { name: 'text', type: 'text', label: 'Text' },
            { name: 'resource_id', type: 'text', label: 'Resource ID' },
            { name: 'index', type: 'number', label: 'Index' },
            { name: 'x', type: 'number', label: 'X' },
            { name: 'y', type: 'number', label: 'Y' },
            { name: 'timeout', type: 'number', label: 'Timeout', default: 10 }
        ]
    },
    type: {
        icon: '⌨️', title: 'Type', color: '#8b5cf6',
        params: [
            { name: 'text', type: 'text', label: 'Text' },
            { name: 'from_data', type: 'text', label: 'From Data Key' },
            { name: 'clear', type: 'checkbox', label: 'Clear First', default: true }
        ]
    },
    wait: {
        icon: '⏳', title: 'Wait', color: '#f59e0b',
        params: [
            { name: 'text', type: 'text', label: 'Wait for Text' },
            { name: 'timeout', type: 'number', label: 'Timeout (s)', default: 10 }
        ]
    },
    wait_gone: {
        icon: '👻', title: 'Wait Gone', color: '#94a3b8',
        params: [
            { name: 'text', type: 'text', label: 'Wait Until Gone' },
            { name: 'timeout', type: 'number', label: 'Timeout (s)', default: 30 }
        ]
    },
    key: {
        icon: '🔑', title: 'Key', color: '#10b981',
        params: [
            {
                name: 'key', type: 'select', label: 'Key',
                options: ['enter', 'back', 'home', 'recent', 'backspace', 'tab']
            }
        ]
    },
    scroll: {
        icon: '📜', title: 'Scroll', color: '#6366f1',
        params: [
            { name: 'direction', type: 'select', label: 'Direction', options: ['up', 'down'] },
            { name: 'distance', type: 'number', label: 'Distance', default: 500 }
        ]
    },
    delay: {
        icon: '⏱️', title: 'Delay', color: '#64748b',
        params: [
            { name: 'seconds', type: 'number', label: 'Seconds', default: 1 }
        ]
    },
    condition: {
        icon: '🔀', title: 'Condition', color: '#ec4899', hasMultipleOutputs: true,
        params: [
            { name: 'check_text', type: 'text', label: 'Check Text on Screen' },
            { name: 'check_data', type: 'text', label: 'Or Check Data Key' },
            { name: 'check_value', type: 'text', label: 'Compare Value' },
            {
                name: 'operator', type: 'select', label: 'Operator',
                options: ['exists', 'not_exists', 'equals', 'contains', 'not_contains'], default: 'exists'
            }
        ]
    },
    otp: {
        icon: '📬', title: 'OTP', color: '#06b6d4',
        params: [
            { name: 'timeout', type: 'number', label: 'Timeout (s)', default: 120 },
            { name: 'save_as', type: 'text', label: 'Save As', default: 'otp' }
        ]
    },
    totp: {
        icon: '🔐', title: 'TOTP', color: '#14b8a6',
        params: [
            { name: 'secret', type: 'text', label: 'Secret Key' },
            { name: 'from_data', type: 'text', label: 'From Data Key' },
            { name: 'save_as', type: 'text', label: 'Save As', default: 'totp' }
        ]
    },
    capture: {
        icon: '📝', title: 'Capture', color: '#a855f7',
        params: [
            { name: 'resource_id', type: 'text', label: 'Resource ID' },
            { name: 'text', type: 'text', label: 'Contains Text' },
            { name: 'index', type: 'number', label: 'Index' },
            { name: 'save_as', type: 'text', label: 'Save As' }
        ]
    },
    clipboard: {
        icon: '📋', title: 'Copy', color: '#14b8a6',
        params: [
            { name: 'index', type: 'number', label: 'Element Index' },
            { name: 'text', type: 'text', label: 'Button Text' },
            { name: 'resource_id', type: 'text', label: 'Resource ID' },
            { name: 'save_as', type: 'text', label: 'Save As', default: 'clipboard' }
        ]
    },
    launch: {
        icon: '🚀', title: 'Launch', color: '#ef4444',
        params: [
            { name: 'package', type: 'text', label: 'Package Name' }
        ]
    },
    http_request: {
        icon: '📡', title: 'HTTP Request', color: '#ec4899',
        params: [
            { name: 'url', type: 'text', label: 'URL' },
            { name: 'method', type: 'select', label: 'Method', options: ['POST', 'GET', 'PUT', 'DELETE'] },
            { name: 'include_data', type: 'checkbox', label: 'Send Data', default: true },
            { name: 'save_response', type: 'text', label: 'Save Response As' }
        ]
    },
    webhook: {
        icon: '🌐', title: 'Webhook Trigger', color: '#6366f1',
        isTrigger: true,
        params: [
            { name: 'path', type: 'text', label: 'Webhook Path', default: 'my-webhook' },
            { name: 'method', type: 'select', label: 'HTTP Method', options: ['POST', 'GET', 'PUT', 'ALL'], default: 'POST' },
            { name: 'response_mode', type: 'select', label: 'Response', options: ['immediate', 'wait_complete'], default: 'immediate' }
        ]
    },
    data_source: {
        icon: '📊', title: 'Data Source', color: '#f97316',
        isDataSource: true,
        params: [
            { name: 'columns', type: 'columns', label: 'Columns', default: ['email', 'password'] },
            { name: 'rows', type: 'rows', label: 'Data Rows', default: [] }
        ]
    },
    close: {
        icon: '🛑', title: 'Close App', color: '#dc2626',
        params: [
            { name: 'package', type: 'text', label: 'Package Name' }
        ]
    },
    clear_data: {
        icon: '🧹', title: 'Clear Data', color: '#f43f5e',
        params: [
            { name: 'package', type: 'text', label: 'Package Name' },
            { name: 'cache_only', type: 'checkbox', label: 'Cache Only', default: false }
        ]
    },
    ask_ai: {
        icon: '🤖', title: 'Ask AI', color: '#8b5cf6',
        params: [
            { name: 'prompt', type: 'textarea', label: 'Prompt' },
            { name: 'provider', type: 'select', label: 'Provider', options: ['gemini', 'openai', 'ollama'], default: 'gemini' },
            { name: 'model', type: 'text', label: 'Model', default: 'gemini-2.0-flash' },
            { name: 'include_screen', type: 'checkbox', label: 'Include Screen Context', default: false },
            { name: 'save_as', type: 'text', label: 'Save As', default: 'ai_response' }
        ]
    },
    shell: {
        icon: '📟', title: 'Shell', color: '#374151',
        params: [
            { name: 'command', type: 'text', label: 'ADB Shell Command' }
        ]
    },
    fingerprint: {
        icon: '👆', title: 'Fingerprint', color: '#0ea5e9',
        params: [
            { name: 'finger_id', type: 'select', label: 'Finger', options: ['1', '2', '3', '4', '5', '6', '7', '8', '9', '10'], default: '1' },
            { name: 'delay', type: 'number', label: 'Delay Before (sec)', default: 0.5 }
        ]
    }
};

// ==================== Initialization ====================
document.addEventListener('DOMContentLoaded', () => {
    initDragDrop();
    initNodeDrag();
    initConnections();
    initZoomPan();
    loadFlowList();
    checkConnection();

    // Start node is already in DOM
    state.nodes.set('start', { id: 'start', type: 'start', x: 50, y: 100, params: {} });
});

// ==================== Zoom & Pan ====================
function initZoomPan() {
    const container = document.querySelector('.canvas-container');
    const canvas = document.getElementById('canvas');
    const svg = document.getElementById('connections');

    // Mouse wheel zoom
    container.addEventListener('wheel', e => {
        e.preventDefault();

        const rect = container.getBoundingClientRect();
        const mouseX = e.clientX - rect.left;
        const mouseY = e.clientY - rect.top;

        const zoomFactor = e.deltaY > 0 ? 0.9 : 1.1;
        const newScale = Math.min(Math.max(state.scale * zoomFactor, 0.2), 3);

        // Adjust translate to zoom toward mouse position
        const scaleChange = newScale / state.scale;
        state.translateX = mouseX - (mouseX - state.translateX) * scaleChange;
        state.translateY = mouseY - (mouseY - state.translateY) * scaleChange;
        state.scale = newScale;

        applyTransform();
        updateZoomDisplay();
    });

    // Spacebar to enable pan mode
    let spacePressed = false;
    document.addEventListener('keydown', e => {
        if (e.code === 'Space' && !e.repeat) {
            spacePressed = true;
            container.style.cursor = 'grab';
            e.preventDefault();
        }
    });
    document.addEventListener('keyup', e => {
        if (e.code === 'Space') {
            spacePressed = false;
            if (!state.isPanning) {
                container.style.cursor = '';
            }
        }
    });

    // Pan with middle mouse, shift+drag, or spacebar+drag
    container.addEventListener('mousedown', e => {
        // Middle button, shift+left, or space+left
        if (e.button === 1 || (e.shiftKey && e.button === 0) || (spacePressed && e.button === 0)) {
            e.preventDefault();
            e.stopPropagation();
            state.isPanning = true;
            state.panStart = { x: e.clientX - state.translateX, y: e.clientY - state.translateY };
            container.style.cursor = 'grabbing';
        }
    });

    document.addEventListener('mousemove', e => {
        if (state.isPanning) {
            state.translateX = e.clientX - state.panStart.x;
            state.translateY = e.clientY - state.panStart.y;
            applyTransform();
        }
    });

    document.addEventListener('mouseup', () => {
        if (state.isPanning) {
            state.isPanning = false;
            container.style.cursor = spacePressed ? 'grab' : '';
        }
    });

    // Keyboard shortcuts
    document.addEventListener('keydown', e => {
        // Reset zoom: Ctrl+0 or Cmd+0
        if ((e.ctrlKey || e.metaKey) && e.key === '0') {
            e.preventDefault();
            resetZoom();
        }
        // Zoom in: Ctrl++ or Cmd++
        if ((e.ctrlKey || e.metaKey) && (e.key === '+' || e.key === '=')) {
            e.preventDefault();
            zoom(1.2);
        }
        // Zoom out: Ctrl+- or Cmd+-
        if ((e.ctrlKey || e.metaKey) && e.key === '-') {
            e.preventDefault();
            zoom(0.8);
        }
    });

    updateZoomDisplay();
}

function applyTransform() {
    const canvas = document.getElementById('canvas');
    const svg = document.getElementById('connections');

    const transform = `translate(${state.translateX}px, ${state.translateY}px) scale(${state.scale})`;
    canvas.style.transform = transform;
    svg.style.transform = transform;
    canvas.style.transformOrigin = '0 0';
    svg.style.transformOrigin = '0 0';
}

function zoom(factor) {
    const container = document.querySelector('.canvas-container');
    const rect = container.getBoundingClientRect();
    const centerX = rect.width / 2;
    const centerY = rect.height / 2;

    const newScale = Math.min(Math.max(state.scale * factor, 0.2), 3);
    const scaleChange = newScale / state.scale;

    state.translateX = centerX - (centerX - state.translateX) * scaleChange;
    state.translateY = centerY - (centerY - state.translateY) * scaleChange;
    state.scale = newScale;

    applyTransform();
    updateZoomDisplay();
}

function resetZoom() {
    state.scale = 1;
    state.translateX = 0;
    state.translateY = 0;
    applyTransform();
    updateZoomDisplay();
}

function updateZoomDisplay() {
    const status = document.getElementById('status');
    const zoomPercent = Math.round(state.scale * 100);
    status.textContent = `Zoom: ${zoomPercent}%`;
}

// ==================== Drag & Drop from Palette ====================
function initDragDrop() {
    const palette = document.querySelectorAll('.palette-node');
    const canvas = document.getElementById('canvas');

    palette.forEach(node => {
        node.addEventListener('dragstart', e => {
            e.dataTransfer.setData('nodeType', node.dataset.type);
        });
    });

    canvas.addEventListener('dragover', e => e.preventDefault());

    canvas.addEventListener('drop', e => {
        e.preventDefault();
        const type = e.dataTransfer.getData('nodeType');
        if (type) {
            const rect = canvas.getBoundingClientRect();
            const x = e.clientX - rect.left;
            const y = e.clientY - rect.top;
            createNode(type, x, y);
        }
    });
}

// ==================== Node Creation ====================
function createNode(type, x, y) {
    const config = nodeTypes[type];
    if (!config) return;

    const id = `node_${state.nodeIdCounter++}`;
    const nodeData = {
        id,
        type,
        x,
        y,
        params: {}
    };

    // Set default params
    config.params.forEach(p => {
        if (p.default !== undefined) {
            nodeData.params[p.name] = p.default;
        }
    });

    state.nodes.set(id, nodeData);

    // Create DOM element
    const node = document.createElement('div');
    node.className = 'node';
    node.dataset.id = id;
    node.dataset.type = type;
    node.style.left = x + 'px';
    node.style.top = y + 'px';
    node.draggable = true;

    node.innerHTML = `
        <div class="node-input" data-port="in"></div>
        <div class="node-header">
            <span class="node-icon">${config.icon}</span>
            <span class="node-title">${config.title}</span>
            <button class="node-delete" onclick="deleteNode('${id}')">×</button>
        </div>
        <div class="node-body"></div>
        ${config.hasMultipleOutputs ?
            `<div class="node-output-yes" data-port="yes" title="Yes"></div>
             <div class="node-output-no" data-port="no" title="No"></div>` :
            `<div class="node-output" data-port="out"></div>`}
    `;

    document.getElementById('canvas').appendChild(node);

    // Add event listeners
    node.addEventListener('click', e => {
        if (!e.target.classList.contains('node-delete')) {
            selectNode(id);
        }
    });

    initNodeDragEvents(node);
    initConnectionEvents(node);

    updateNodeBody(id);
    return id;
}

function deleteNode(id) {
    const node = document.querySelector(`.node[data-id="${id}"]`);
    if (node) {
        node.remove();
    }
    state.nodes.delete(id);

    // Remove connections
    state.connections = state.connections.filter(c => c.from !== id && c.to !== id);
    renderConnections();

    if (state.selectedNode === id) {
        state.selectedNode = null;
        showProperties(null);
    }
}

function updateNodeBody(id) {
    const nodeData = state.nodes.get(id);
    if (!nodeData) return;

    const node = document.querySelector(`.node[data-id="${id}"]`);
    if (!node) return;

    const body = node.querySelector('.node-body');
    const config = nodeTypes[nodeData.type];

    // Special handling for data_source
    if (config.isDataSource) {
        const columns = nodeData.params.columns || [];
        const rows = nodeData.params.rows || [];
        body.innerHTML = `<span style="color:#f97316">📋 ${columns.join(', ')}</span><br>
                          <span style="color:#888">${rows.length} rows</span>`;
        return;
    }

    // Helper to truncate text
    const truncate = (str, maxLen = 30) => {
        if (!str) return '';
        str = String(str);
        return str.length > maxLen ? str.substring(0, maxLen) + '...' : str;
    };

    // Show summary of params (truncated)
    let summary = [];
    config.params.forEach(p => {
        const val = nodeData.params[p.name];
        if (val) {
            summary.push(`${p.label}: ${truncate(val)}`);
        }
    });

    body.textContent = summary.slice(0, 2).join('\n') || 'Click to configure';
}

// ==================== Node Selection & Properties ====================
function selectNode(id) {
    // Deselect previous
    document.querySelectorAll('.node.selected').forEach(n => n.classList.remove('selected'));

    state.selectedNode = id;
    const node = document.querySelector(`.node[data-id="${id}"]`);
    if (node) {
        node.classList.add('selected');
    }

    showProperties(id);
}

function showProperties(id) {
    const panel = document.getElementById('properties-panel');

    if (!id) {
        panel.innerHTML = '<p class="hint">Select a node to edit</p>';
        return;
    }

    const nodeData = state.nodes.get(id);
    if (!nodeData || nodeData.type === 'start') {
        panel.innerHTML = '<p class="hint">Start node cannot be configured</p>';
        return;
    }

    const config = nodeTypes[nodeData.type];

    // Special handling for data_source node
    if (config.isDataSource) {
        showDataSourceProperties(id, nodeData, config);
        return;
    }

    // Special handling for webhook trigger node
    if (config.isTrigger && nodeData.type === 'webhook') {
        showWebhookProperties(id, nodeData, config);
        return;
    }

    let html = `<h4>${config.icon} ${config.title}</h4>`;

    config.params.forEach(p => {
        const value = nodeData.params[p.name] || '';
        html += `<div class="property-row">
            <label>${p.label}</label>`;

        if (p.type === 'select') {
            html += `<select onchange="updateParam('${id}', '${p.name}', this.value)">
                <option value="">-- Select --</option>
                ${p.options.map(o => `<option value="${o}" ${value === o ? 'selected' : ''}>${o}</option>`).join('')}
            </select>`;
        } else if (p.type === 'checkbox') {
            html += `<input type="checkbox" ${value ? 'checked' : ''} 
                     onchange="updateParam('${id}', '${p.name}', this.checked)">`;
        } else if (p.type === 'number') {
            html += `<input type="number" value="${value}" 
                     onchange="updateParam('${id}', '${p.name}', parseFloat(this.value))">`;
        } else if (p.type === 'textarea') {
            html += `<textarea rows="4" 
                     onchange="updateParam('${id}', '${p.name}', this.value)"
                     placeholder="Enter prompt...">${value}</textarea>`;
        } else {
            html += `<input type="text" value="${value}" 
                     onchange="updateParam('${id}', '${p.name}', this.value)">`;
        }

        html += `</div>`;
    });

    // Add Run button for testing single node
    html += `
        <div class="property-actions" style="display:flex; gap:8px;">
            <button class="btn-run-node" onclick="runSingleNode('${id}')" title="Test this node only">
                <span class="run-icon">▶</span> Test
            </button>
            <button class="btn-run-node" onclick="runFlow('${id}')" style="background:#059669; border-color:#059669;" title="Resume complete flow from here">
                <span class="run-icon">⏩</span> Resume
            </button>
        </div>
        <div id="run-result-${id}" class="run-result"></div>
    `;

    panel.innerHTML = html;
}

// Special properties panel for Webhook Trigger node
function showWebhookProperties(id, nodeData, config) {
    const panel = document.getElementById('properties-panel');
    const webhookPath = nodeData.params.path || 'my-webhook';
    const baseUrl = window.location.origin;
    const webhookUrl = `${baseUrl}/webhook/${webhookPath}`;

    let html = `<h4>${config.icon} ${config.title}</h4>`;

    // Webhook URL display (readonly)
    html += `
        <div class="webhook-url-section">
            <label>Webhook URL</label>
            <div class="webhook-url-display">
                <input type="text" id="webhook-url-${id}" value="${webhookUrl}" readonly 
                       style="font-family: monospace; font-size: 11px;">
                <button onclick="copyWebhookUrl('${id}')" title="Copy URL" class="btn-copy">📋</button>
            </div>
            <small class="hint">Panggil URL ini dari luar untuk trigger flow</small>
        </div>
    `;

    // Normal params
    config.params.forEach(p => {
        const value = nodeData.params[p.name] ?? p.default ?? '';
        html += `<div class="property-row">
            <label>${p.label}</label>`;

        if (p.type === 'select') {
            html += `<select onchange="updateWebhookParam('${id}', '${p.name}', this.value)">
                ${p.options.map(o => `<option value="${o}" ${value === o ? 'selected' : ''}>${o}</option>`).join('')}
            </select>`;
        } else {
            html += `<input type="text" value="${value}" 
                     onchange="updateWebhookParam('${id}', '${p.name}', this.value)"
                     placeholder="${p.default || ''}">`;
        }

        html += `</div>`;
    });

    // Response mode explanation
    const responseMode = nodeData.params.response_mode || 'immediate';
    html += `
        <div class="webhook-info">
            <h5>📖 Cara Kerja:</h5>
            <ul>
                <li><strong>immediate</strong>: Response langsung, flow jalan di background</li>
                <li><strong>wait_complete</strong>: Tunggu flow selesai, return hasil</li>
            </ul>
        </div>
    `;

    // Test webhook button
    html += `
        <div class="property-actions">
            <button class="btn-run-node" onclick="testWebhook('${id}')" title="Test webhook dengan sample data">
                <span class="run-icon">🧪</span> Test Webhook
            </button>
        </div>
        <div id="run-result-${id}" class="run-result"></div>
    `;

    panel.innerHTML = html;
}

function updateWebhookParam(id, key, value) {
    updateParam(id, key, value);
    // Refresh panel to update URL display if path changed
    if (key === 'path') {
        setTimeout(() => showProperties(id), 50);
    }
}

function copyWebhookUrl(id) {
    const input = document.getElementById(`webhook-url-${id}`);
    if (input) {
        input.select();
        document.execCommand('copy');
        setStatus('Webhook URL copied to clipboard!');
    }
}

async function testWebhook(id) {
    const nodeData = state.nodes.get(id);
    if (!nodeData) return;

    const webhookPath = nodeData.params.path || 'my-webhook';
    const method = nodeData.params.method || 'POST';
    const webhookUrl = `/webhook/${webhookPath}`;

    const resultDiv = document.getElementById(`run-result-${id}`);
    if (resultDiv) {
        resultDiv.innerHTML = '<span class="result-pending">💾 Saving flow first...</span>';
        resultDiv.className = 'run-result pending';
    }

    try {
        // Auto-save flow first (webhook must be registered)
        const flowName = document.getElementById('flow-name').value || 'my_flow';
        const flow = buildFlowJSON();
        flow.name = flowName;
        flow.id = state.currentFlowId || flowName.toLowerCase().replace(/\s+/g, '_');

        const saveRes = await fetch(`/api/flows/${flow.id}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(flow)
        });

        if (!saveRes.ok) {
            throw new Error('Failed to save flow');
        }

        state.currentFlowId = flow.id;

        if (resultDiv) {
            resultDiv.innerHTML = '<span class="result-pending">⏳ Testing webhook...</span>';
        }

        // Now test the webhook
        const options = {
            method: method === 'ALL' ? 'POST' : method,
            headers: { 'Content-Type': 'application/json' }
        };

        if (['POST', 'PUT'].includes(options.method)) {
            options.body = JSON.stringify({
                test: true,
                message: 'Test from Flow Editor',
                timestamp: new Date().toISOString()
            });
        }

        const response = await fetch(webhookUrl, options);
        const data = await response.json();

        if (response.ok) {
            if (resultDiv) {
                resultDiv.innerHTML = `✅ Webhook responded!<br><small>${JSON.stringify(data)}</small>`;
                resultDiv.className = 'run-result success';
            }
            setStatus('Webhook test successful!');
        } else {
            if (resultDiv) {
                // More helpful error message
                let errorMsg = data.error || response.statusText;
                if (errorMsg === 'Webhook not found') {
                    errorMsg = 'Webhook not found. Make sure flow is saved and has a Webhook Trigger node.';
                }
                resultDiv.innerHTML = `❌ ${errorMsg}`;
                resultDiv.className = 'run-result error';
            }
        }
    } catch (e) {
        if (resultDiv) {
            resultDiv.innerHTML = `❌ Error: ${e.message}`;
            resultDiv.className = 'run-result error';
        }
    }
}

// ==================== Run Single Node ====================
async function runSingleNode(nodeId) {
    const nodeData = state.nodes.get(nodeId);
    if (!nodeData) return;

    const config = nodeTypes[nodeData.type];
    if (!config) return;

    const btn = document.querySelector('.btn-run-node');
    const resultDiv = document.getElementById(`run-result-${nodeId}`);
    const nodeEl = document.querySelector(`.node[data-id="${nodeId}"]`);

    // UI feedback - running
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = '<span class="run-icon spinning">⟳</span> Running...';
    }
    if (nodeEl) {
        nodeEl.classList.remove('node-success', 'node-error');
        nodeEl.classList.add('node-running');
    }
    if (resultDiv) {
        resultDiv.innerHTML = '<span class="result-pending">⏳ Executing...</span>';
        resultDiv.className = 'run-result pending';
    }

    try {
        const response = await fetch('/api/run-step', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                type: nodeData.type,
                params: nodeData.params,
                session_id: 'test_' + Date.now(),
                context_data: {}
            })
        });

        const data = await response.json();

        // Remove running state
        if (nodeEl) {
            nodeEl.classList.remove('node-running');
        }

        if (response.ok && data.result === 'success') {
            // Success
            if (btn) {
                btn.innerHTML = '<span class="run-icon">✓</span> Success!';
                btn.classList.add('success');
            }
            if (nodeEl) {
                nodeEl.classList.add('node-success');
            }
            if (resultDiv) {
                let msg = '✅ Step executed successfully';
                if (data.captured_data && Object.keys(data.captured_data).length > 0) {
                    msg += '<br><small>Captured: ' + JSON.stringify(data.captured_data) + '</small>';
                }
                resultDiv.innerHTML = msg;
                resultDiv.className = 'run-result success';
            }
        } else {
            // Failed
            if (btn) {
                btn.innerHTML = '<span class="run-icon">✗</span> Failed';
                btn.classList.add('error');
            }
            if (nodeEl) {
                nodeEl.classList.add('node-error');
            }
            if (resultDiv) {
                resultDiv.innerHTML = `❌ ${data.error || data.result || 'Step failed'}`;
                resultDiv.className = 'run-result error';
            }
        }

    } catch (err) {
        // Error
        if (nodeEl) {
            nodeEl.classList.remove('node-running');
            nodeEl.classList.add('node-error');
        }
        if (btn) {
            btn.innerHTML = '<span class="run-icon">✗</span> Error';
            btn.classList.add('error');
        }
        if (resultDiv) {
            resultDiv.innerHTML = `❌ Error: ${err.message}`;
            resultDiv.className = 'run-result error';
        }
    }

    // Reset button after delay
    setTimeout(() => {
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = '<span class="run-icon">▶</span> Run';
            btn.classList.remove('success', 'error');
        }
    }, 2000);
}

// ==================== Data Source Table Editor ====================
function showDataSourceProperties(id, nodeData, config) {
    const panel = document.getElementById('properties-panel');

    // Initialize defaults if not set
    if (!nodeData.params.columns || !Array.isArray(nodeData.params.columns)) {
        nodeData.params.columns = ['email', 'password'];
    }
    if (!nodeData.params.rows || !Array.isArray(nodeData.params.rows)) {
        nodeData.params.rows = [];
    }

    const columns = nodeData.params.columns;
    const rows = nodeData.params.rows;

    let html = `<h4>${config.icon} ${config.title}</h4>`;

    // Columns editor
    html += `<div class="property-section">
        <label>Columns</label>
        <div class="columns-editor">
            ${columns.map((col, i) => `
                <div class="column-tag">
                    <input type="text" value="${col}" 
                           onchange="updateColumn('${id}', ${i}, this.value)"
                           class="column-input">
                    <button onclick="removeColumn('${id}', ${i})" title="Remove">×</button>
                </div>
            `).join('')}
            <button class="btn-add-column" onclick="addColumn('${id}')">+ Column</button>
        </div>
    </div>`;

    // Data table
    html += `<div class="property-section">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
            <label style="margin:0;">Data (${rows.length} rows)</label>
            <div style="font-size:0.8rem;">
                Resume from #<input type="number" value="${nodeData.params.start_index || 0}" 
                       onchange="updateParam('${id}', 'start_index', parseInt(this.value))"
                       style="width:50px; padding:2px; margin-left:4px;">
            </div>
        </div>
        <div class="data-table-container">
            <table class="data-table">
                <thead>
                    <tr>
                        ${columns.map(col => `<th>${col}</th>`).join('')}
                        <th class="actions-col"></th>
                    </tr>
                </thead>
        <tbody>
            ${rows.map((row, rowIdx) => `
                        <tr>
                            ${columns.map(col => `
                                <td>
                                    <input type="text" value="${row[col] || ''}" 
                                           onchange="updateRowCell('${id}', ${rowIdx}, '${col}', this.value)">
                                </td>
                            `).join('')}
                            <td class="actions-col">
                                <button onclick="removeRow('${id}', ${rowIdx})" title="Delete row">🗑️</button>
                            </td>
                        </tr>
                    `).join('')}
        </tbody>
            </table>
        </div>
        <div class="data-actions">
            <button onclick="addRow('${id}')" class="btn-small">+ Add Row</button>
            <button onclick="showDataSourceModal('${id}')" class="btn-small" style="background:var(--node-type)">✏️ Expand Editor</button>
            <button onclick="importCSV('${id}')" class="btn-small">📄 Import CSV</button>
            <button onclick="clearAllRows('${id}')" class="btn-small btn-danger-small">🗑️ Clear</button>
            <button onclick="runFlow('${id}')" class="btn-small" style="background:#059669; border-color:#059669; margin-left:auto;">⏩ Resume</button>
        </div>
    </div>`;

    // Hidden file input for CSV import
    html += `<input type="file" id="csv-input-${id}" accept=".csv,.txt"
    onchange="handleCSVImport('${id}', this)" style="display:none">`;

    panel.innerHTML = html;
}

// Column management
function addColumn(nodeId) {
    const nodeData = state.nodes.get(nodeId);
    if (!nodeData) return;

    const newName = prompt('Column name:', `col${nodeData.params.columns.length + 1} `);
    if (newName && newName.trim()) {
        nodeData.params.columns.push(newName.trim());
        showProperties(nodeId);
        updateNodeBody(nodeId);
    }
}

function removeColumn(nodeId, index) {
    const nodeData = state.nodes.get(nodeId);
    if (!nodeData || nodeData.params.columns.length <= 1) return;

    const colName = nodeData.params.columns[index];
    nodeData.params.columns.splice(index, 1);

    // Remove column data from rows
    nodeData.params.rows.forEach(row => {
        delete row[colName];
    });

    showProperties(nodeId);
    updateNodeBody(nodeId);
}

function updateColumn(nodeId, index, newName) {
    const nodeData = state.nodes.get(nodeId);
    if (!nodeData || !newName.trim()) return;

    const oldName = nodeData.params.columns[index];
    nodeData.params.columns[index] = newName.trim();

    // Rename column in all rows
    nodeData.params.rows.forEach(row => {
        if (row[oldName] !== undefined) {
            row[newName.trim()] = row[oldName];
            delete row[oldName];
        }
    });

    updateNodeBody(nodeId);
}

// Row management
function addRow(nodeId) {
    const nodeData = state.nodes.get(nodeId);
    if (!nodeData) return;

    const newRow = {};
    nodeData.params.columns.forEach(col => {
        newRow[col] = '';
    });
    nodeData.params.rows.push(newRow);

    showProperties(nodeId);
    updateNodeBody(nodeId);
}

function removeRow(nodeId, rowIndex) {
    const nodeData = state.nodes.get(nodeId);
    if (!nodeData) return;

    nodeData.params.rows.splice(rowIndex, 1);
    showProperties(nodeId);
    updateNodeBody(nodeId);
}

function updateRowCell(nodeId, rowIndex, column, value) {
    const nodeData = state.nodes.get(nodeId);
    if (!nodeData) return;

    nodeData.params.rows[rowIndex][column] = value;
    updateNodeBody(nodeId);
}

function clearAllRows(nodeId) {
    const nodeData = state.nodes.get(nodeId);
    if (!nodeData) return;

    if (confirm('Clear all data rows?')) {
        nodeData.params.rows = [];
        showProperties(nodeId);
        updateNodeBody(nodeId);
    }
}

// CSV Import
function importCSV(nodeId) {
    document.getElementById(`csv - input - ${nodeId} `).click();
}

function handleCSVImport(nodeId, input) {
    const file = input.files[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (e) => {
        const text = e.target.result;
        parseCSVToNode(nodeId, text);
    };
    reader.readAsText(file);
}

function parseCSVToNode(nodeId, csvText) {
    const nodeData = state.nodes.get(nodeId);
    if (!nodeData) return;

    const lines = csvText.trim().split('\n');
    if (lines.length === 0) return;

    // Parse header
    const delimiter = lines[0].includes('\t') ? '\t' : ',';
    const headers = lines[0].split(delimiter).map(h => h.trim().replace(/^["']|["']$/g, ''));

    // Parse rows
    const rows = [];
    for (let i = 1; i < lines.length; i++) {
        const values = parseCSVLine(lines[i], delimiter);
        if (values.length === headers.length) {
            const row = {};
            headers.forEach((h, idx) => {
                row[h] = values[idx];
            });
            rows.push(row);
        }
    }

    // Update node
    nodeData.params.columns = headers;
    nodeData.params.rows = rows;

    showProperties(nodeId);
    updateNodeBody(nodeId);
    setStatus(`Imported ${rows.length} rows from CSV`);
}

function parseCSVLine(line, delimiter) {
    const values = [];
    let current = '';
    let inQuotes = false;

    for (let i = 0; i < line.length; i++) {
        const char = line[i];

        if (char === '"' && !inQuotes) {
            inQuotes = true;
        } else if (char === '"' && inQuotes) {
            if (line[i + 1] === '"') {
                current += '"';
                i++;
            } else {
                inQuotes = false;
            }
        } else if (char === delimiter && !inQuotes) {
            values.push(current.trim());
            current = '';
        } else {
            current += char;
        }
    }
    values.push(current.trim());

    return values;
}

function updateParam(id, param, value) {
    const nodeData = state.nodes.get(id);
    if (nodeData) {
        nodeData.params[param] = value;
        updateNodeBody(id);
    }
}

// ==================== Data Source Modal (Expanded Editor) ====================

function showDataSourceModal(nodeId) {
    const nodeData = state.nodes.get(nodeId);
    if (!nodeData) return;

    // Create modal if not exists
    let modal = document.getElementById('data-source-modal');
    if (!modal) {
        modal = document.createElement('div');
        modal.id = 'data-source-modal';
        modal.className = 'modal-overlay';
        modal.innerHTML = `
        <div class="modal-content">
                <div class="modal-header">
                    <h2>📊 Data Source Editor</h2>
                    <button class="modal-close" onclick="closeDataSourceModal()">×</button>
                </div>
                <div class="modal-body">
                    <!-- Paste Section -->
                    <div class="modal-section">
                        <h3>📋 Paste Data (Excel / Text)</h3>
                        <div class="paste-container">
                            <textarea id="modal-paste-area" class="paste-area" 
                                placeholder="Paste your data here...&#10;For single column: one item per line&#10;For multiple columns: tab or comma separated"></textarea>
                            <div class="paste-controls">
                                <button onclick="handlePasteData('${nodeId}')" class="btn-paste-confirm">Start Import</button>
                                <button onclick="document.getElementById('modal-paste-area').value = ''">Clear Paste</button>
                            </div>
                        </div>
                    </div>

                    <!-- Table Section -->
                    <div class="modal-section" style="flex:1; overflow:hidden; display:flex; flex-direction:column;">
                        <h3>
                            Data Preview
                            <span class="hint" id="modal-row-count">0 rows</span>
                        </h3>
                        <div class="data-table-container" style="max-height:100%; height:100%;">
                            <div id="modal-table-content"></div>
                        </div>
                    </div>
                </div>
                <div class="modal-footer">
                    <button onclick="closeDataSourceModal()">Close</button>
                    <button onclick="saveAndCloseModal('${nodeId}')" class="btn-primary">Apply Changes</button>
                </div>
            </div>
        `;
        document.body.appendChild(modal);

        // Close on escape
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && modal.classList.contains('show')) {
                closeDataSourceModal();
            }
        });
    }

    // Reset paste area
    const pasteArea = document.getElementById('modal-paste-area');
    if (pasteArea) {
        pasteArea.value = '';
        // Update onclick handler for current node
        const pasteBtn = modal.querySelector('.btn-paste-confirm');
        pasteBtn.onclick = () => handlePasteData(nodeId);

        const applyBtn = modal.querySelector('.btn-primary');
        applyBtn.onclick = () => saveAndCloseModal(nodeId);
    }

    renderModalTable(nodeId);

    // Show modal
    modal.style.display = 'flex'; // Ensure generic display is flex
    // Trigger reflow
    modal.offsetHeight;
    modal.classList.add('show');
}

function closeDataSourceModal() {
    const modal = document.getElementById('data-source-modal');
    if (modal) {
        modal.classList.remove('show');
        setTimeout(() => {
            modal.style.display = 'none';
        }, 200);
    }
}

function saveAndCloseModal(nodeId) {
    closeDataSourceModal();
    // Refresh sidebar properties
    showProperties(nodeId);
    updateNodeBody(nodeId);
}

function renderModalTable(nodeId) {
    const nodeData = state.nodes.get(nodeId);
    if (!nodeData) return;

    const container = document.getElementById('modal-table-content');
    const columns = nodeData.params.columns || [];
    const rows = nodeData.params.rows || [];

    document.getElementById('modal-row-count').textContent = `${rows.length} rows`;

    let html = `
        <table class="large-data-table">
            <thead>
                <tr>
                    <th style="width:40px">#</th>
                    ${columns.map(col => `<th>${col}</th>`).join('')}
                    <th class="actions-col"></th>
                </tr>
            </thead>
            <tbody>
                ${rows.map((row, rowIdx) => `
                    <tr>
                        <td style="color:var(--text-secondary); font-size:0.8em">${rowIdx + 1}</td>
                        ${columns.map(col => `
                            <td>
                                <input type="text" value="${row[col] || ''}" 
                                       onchange="updateRowCell('${nodeId}', ${rowIdx}, '${col}', this.value)">
                            </td>
                        `).join('')}
                        <td class="actions-col">
                            <button onclick="removeRowFromModal('${nodeId}', ${rowIdx})" title="Delete row" style="background:transparent; border:none; color:#ef4444;">🗑️</button>
                        </td>
                    </tr>
                `).join('')}
            </tbody>
        </table>
        `;

    container.innerHTML = html;
}

function removeRowFromModal(nodeId, rowIdx) {
    const nodeData = state.nodes.get(nodeId);
    if (!nodeData) return;

    nodeData.params.rows.splice(rowIdx, 1);
    renderModalTable(nodeId);
    updateNodeBody(nodeId);
}

function handlePasteData(nodeId) {
    const nodeData = state.nodes.get(nodeId);
    if (!nodeData) return;

    const textarea = document.getElementById('modal-paste-area');
    const text = textarea.value;

    if (!text.trim()) return;

    const lines = text.trim().split(/\r?\n/);
    const columns = nodeData.params.columns;
    let addedCount = 0;

    lines.forEach(line => {
        if (!line.trim()) return;

        const row = {};

        // Auto-detect delimiter
        let values = [];
        if (columns.length > 1) {
            if (line.includes('\t')) {
                values = line.split('\t');
            } else if (line.includes(',')) {
                // Simple CSV split (not handling quotes here for simplicity, or use parseCSVLine)
                values = line.split(',');
            } else {
                // Treat as single value
                values = [line.trim()];
            }
        } else {
            // Single column
            values = [line.trim()];
        }

        columns.forEach((col, idx) => {
            row[col] = (values[idx] || '').trim();
        });

        nodeData.params.rows.push(row);
        addedCount++;
    });

    textarea.value = '';
    renderModalTable(nodeId);
    updateNodeBody(nodeId);

    // Provide feedback
    const btn = document.querySelector('.btn-paste-confirm');
    const originalText = btn.innerText;
    btn.innerText = `✅ Added ${addedCount} rows!`;
    setTimeout(() => {
        btn.innerText = originalText;
    }, 2000);
}

// ==================== Node Dragging ====================
function initNodeDrag() {
    // Handle existing start node
    const startNode = document.querySelector('.start-node');
    if (startNode) {
        initNodeDragEvents(startNode);
        initConnectionEvents(startNode);
    }
}

function initNodeDragEvents(node) {
    let offsetX, offsetY;

    node.addEventListener('mousedown', e => {
        if (e.target.classList.contains('node-input') ||
            e.target.classList.contains('node-output') ||
            e.target.classList.contains('node-output-yes') ||
            e.target.classList.contains('node-output-no') ||
            e.target.classList.contains('node-delete')) {
            return;
        }

        state.dragging = node;
        offsetX = e.clientX - node.offsetLeft;
        offsetY = e.clientY - node.offsetTop;
        node.style.zIndex = 100;
    });

    document.addEventListener('mousemove', e => {
        if (state.dragging === node) {
            const x = e.clientX - offsetX;
            const y = e.clientY - offsetY;
            node.style.left = Math.max(0, x) + 'px';
            node.style.top = Math.max(0, y) + 'px';

            // Update node data
            const id = node.dataset.id;
            const nodeData = state.nodes.get(id);
            if (nodeData) {
                nodeData.x = x;
                nodeData.y = y;
            }

            renderConnections();
        }
    });

    document.addEventListener('mouseup', () => {
        if (state.dragging) {
            state.dragging.style.zIndex = 10;
            state.dragging = null;
        }
    });
}

// ==================== Connections ====================
function initConnections() {
    const container = document.querySelector('.canvas-container');
    const svg = document.getElementById('connections');

    // Draw temp line while connecting
    document.addEventListener('mousemove', e => {
        if (state.connecting) {
            let tempLine = document.getElementById('temp-line');
            if (!tempLine) {
                tempLine = document.createElementNS('http://www.w3.org/2000/svg', 'path');
                tempLine.id = 'temp-line';
                tempLine.setAttribute('stroke', '#e94560');
                tempLine.setAttribute('stroke-width', '3');
                tempLine.setAttribute('stroke-dasharray', '5,5');
                tempLine.setAttribute('fill', 'none');
                svg.appendChild(tempLine);
            }

            const containerRect = container.getBoundingClientRect();
            const startX = state.connecting.startX - containerRect.left;
            const startY = state.connecting.startY - containerRect.top;
            const endX = e.clientX - containerRect.left;
            const endY = e.clientY - containerRect.top;
            const midX = (startX + endX) / 2;

            tempLine.setAttribute('d', `M ${startX} ${startY} C ${midX} ${startY}, ${midX} ${endY}, ${endX} ${endY} `);
        }
    });

    // Handle connection end - use document level to catch any mouseup
    document.addEventListener('mouseup', e => {
        if (state.connecting) {
            // Find if we're over an input port - use larger hit area
            const hitRadius = 25;
            let targetInput = null;

            // Check all input ports for proximity
            document.querySelectorAll('.node-input').forEach(port => {
                const rect = port.getBoundingClientRect();
                const centerX = rect.left + rect.width / 2;
                const centerY = rect.top + rect.height / 2;
                const distance = Math.sqrt(
                    Math.pow(e.clientX - centerX, 2) +
                    Math.pow(e.clientY - centerY, 2)
                );
                if (distance < hitRadius) {
                    targetInput = port;
                }
            });

            if (targetInput) {
                const targetNode = targetInput.closest('.node');
                if (targetNode && state.connecting.from !== targetNode.dataset.id) {
                    const conn = {
                        from: state.connecting.from,
                        fromPort: state.connecting.port,
                        to: targetNode.dataset.id,
                        toPort: 'in'
                    };

                    // Check if connection already exists
                    const exists = state.connections.some(c =>
                        c.from === conn.from && c.to === conn.to && c.fromPort === conn.fromPort);

                    if (!exists) {
                        state.connections.push(conn);
                        renderConnections();
                        console.log('Connection created:', conn);
                    }
                }
            }

            state.connecting = null;
            document.getElementById('temp-line')?.remove();
        }
    });
}

function initConnectionEvents(node) {
    const outputs = node.querySelectorAll('.node-output, .node-output-yes, .node-output-no');

    outputs.forEach(output => {
        output.addEventListener('mousedown', e => {
            e.stopPropagation();
            e.preventDefault();

            const rect = output.getBoundingClientRect();
            state.connecting = {
                from: node.dataset.id,
                port: output.dataset.port,
                startX: rect.left + rect.width / 2,
                startY: rect.top + rect.height / 2
            };

            console.log('Started connecting from:', state.connecting);
        });
    });
}

// Global segments registry to track drawn paths for collision/jump logic
let drawnSegments = [];

function renderConnections() {
    const svg = document.getElementById('connections');
    svg.innerHTML = '';

    // Reset segments registry
    drawnSegments = [];

    const canvas = document.getElementById('canvas');
    const canvasRect = canvas.getBoundingClientRect();

    // Collect all node bounding boxes for obstacle avoidance
    const nodeBoxes = [];
    document.querySelectorAll('.node').forEach(node => {
        const rect = node.getBoundingClientRect();
        nodeBoxes.push({
            id: node.dataset.id,
            left: (rect.left - canvasRect.left) / state.scale,
            top: (rect.top - canvasRect.top) / state.scale,
            right: (rect.right - canvasRect.left) / state.scale,
            bottom: (rect.bottom - canvasRect.top) / state.scale,
            width: rect.width / state.scale,
            height: rect.height / state.scale
        });
    });

    state.connections.forEach(conn => {
        const fromNode = document.querySelector(`.node[data-id="${conn.from}"]`);
        const toNode = document.querySelector(`.node[data-id="${conn.to}"]`);

        if (!fromNode || !toNode) return;

        // Get port elements
        let fromPort = fromNode.querySelector(`.node-output[data-port="${conn.fromPort}"]`) ||
            fromNode.querySelector(`.node-output-${conn.fromPort}`);
        let toPort = toNode.querySelector('.node-input');

        if (!fromPort) fromPort = fromNode.querySelector('.node-output');
        if (!fromPort || !toPort) return;

        const fromRect = fromPort.getBoundingClientRect();
        const toRect = toPort.getBoundingClientRect();

        // Convert to canvas coordinates
        const x1 = (fromRect.left + fromRect.width / 2 - canvasRect.left) / state.scale;
        const y1 = (fromRect.top + fromRect.height / 2 - canvasRect.top) / state.scale;
        const x2 = (toRect.left + toRect.width / 2 - canvasRect.left) / state.scale;
        const y2 = (toRect.top + toRect.height / 2 - canvasRect.top) / state.scale;

        // Get node boxes for source and target
        const fromBox = nodeBoxes.find(b => b.id === conn.from);
        const toBox = nodeBoxes.find(b => b.id === conn.to);

        // Calculate smart route path
        const pathData = calculateSmartRoute(x1, y1, x2, y2, fromBox, toBox, nodeBoxes, conn);
        const pathD = pathData.d;

        const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
        path.setAttribute('d', pathD);
        path.setAttribute('stroke', conn.fromPort === 'yes' ? '#4ade80' :
            conn.fromPort === 'no' ? '#ef4444' : '#e94560');
        path.setAttribute('stroke-width', '3');
        path.setAttribute('fill', 'none');
        path.style.cursor = 'pointer';
        path.style.pointerEvents = 'stroke';
        path.style.transition = 'stroke-width 0.2s';

        // Hover effect
        path.addEventListener('mouseenter', () => {
            path.setAttribute('stroke-width', '6');
            path.setAttribute('stroke', '#ff0000');
            path.style.zIndex = 1000;
        });
        path.addEventListener('mouseleave', () => {
            path.setAttribute('stroke-width', '3');
            path.setAttribute('stroke', conn.fromPort === 'yes' ? '#4ade80' :
                conn.fromPort === 'no' ? '#ef4444' : '#e94560');
            path.style.zIndex = '';
        });

        // Click to delete
        path.addEventListener('click', (e) => {
            e.stopPropagation();
            if (confirm('Hapus connection ini?')) {
                deleteConnection(conn.from, conn.to, conn.fromPort);
            }
        });

        svg.appendChild(path);

        // Register segments for future avoidance/jumps
        if (pathData.segments) {
            drawnSegments.push(...pathData.segments);
        }
    });
}

// Smart routing algorithm that avoids nodes
// Smart routing algorithm that avoids nodes and existing lines
function calculateSmartRoute(x1, y1, x2, y2, fromBox, toBox, nodeBoxes, conn) {
    const MARGIN = 25; // Margin around nodes
    const CURVE_RADIUS = 12; // Radius for rounded corners

    // Exclude source and target nodes from obstacles
    const obstacles = nodeBoxes.filter(b => b.id !== conn.from && b.id !== conn.to);

    let waypoints = [];

    // Determine relative positions
    const goingRight = x2 > x1;
    const dx = x2 - x1;
    const dy = y2 - y1;

    // Simple case: direct horizontal connection (nodes on same row)
    let directPossible = false;
    if (Math.abs(y1 - y2) < 50 && goingRight) {
        // Check if path is clear
        const pathClear = !obstacles.some(obs =>
            lineIntersectsBox(x1, y1, x2, y2, obs, MARGIN)
        );
        if (pathClear) directPossible = true;
    }

    if (directPossible) {
        waypoints = [[x1, y1], [x2, y2]];
    } else {
        // Calculate orthogonal path with obstacle avoidance
        waypoints = calculateOrthogonalPath(x1, y1, x2, y2, fromBox, toBox, obstacles, MARGIN);
    }

    // Process waypoints to add jumps at intersections
    const result = addJumpsAndRoundCorners(waypoints, CURVE_RADIUS, drawnSegments);

    return {
        d: result.path,
        segments: result.segments // Return new segments to registry
    };
}

// Check vertical channel
function findClearVerticalChannel(minX, maxX, minY, maxY, obstacles, margin) {
    const startX = Math.min(minX, maxX);
    const endX = Math.max(minX, maxX);
    const startY = Math.min(minY, maxY);
    const endY = Math.max(minY, maxY);

    // Try middle first
    let testX = (startX + endX) / 2;

    const intersectsObstacle = (x) => obstacles.some(obs =>
        x >= obs.left - margin &&
        x <= obs.right + margin &&
        !(startY > obs.bottom + margin || endY < obs.top - margin)
    );

    // Also check against existing vertical segments to avoid overlay
    const intersectsLine = (x) => drawnSegments.some(seg =>
        seg.orient === 'v' &&
        Math.abs(seg.c - x) < 10 && // Check proximity (10px buffer)
        Math.max(startY, seg.start) < Math.min(endY, seg.end) // Overlap in Y
    );

    // If middle is clear, use it
    if (!intersectsObstacle(testX) && !intersectsLine(testX)) return testX;

    // Search outward from middle for a clear channel
    const step = 15;
    const range = Math.abs(endX - startX) / 2;

    for (let offset = 1; offset * step <= range + 100; offset++) {
        // Try right
        let tx = testX + offset * step;
        if (tx <= endX + 100) {
            if (!intersectsObstacle(tx) && !intersectsLine(tx)) return tx;
        }

        // Try left
        tx = testX - offset * step;
        if (tx >= startX - 100) {
            if (!intersectsObstacle(tx) && !intersectsLine(tx)) return tx;
        }
    }

    // Fallback
    return testX;
}

// Check horizontal channel
function findClearHorizontalChannel(minY, maxY, minX, maxX, obstacles, margin) {
    const startY = Math.min(minY, maxY);
    const endY = Math.max(minY, maxY);
    const startX = Math.min(minX, maxX);
    const endX = Math.max(minX, maxX);

    let testY = (startY + endY) / 2;

    const intersectsObstacle = (y) => obstacles.some(obs =>
        y >= obs.top - margin &&
        y <= obs.bottom + margin &&
        !(startX > obs.right + margin || endX < obs.left - margin)
    );

    // Check line overlap
    const intersectsLine = (y) => drawnSegments.some(seg =>
        seg.orient === 'h' &&
        Math.abs(seg.c - y) < 10 &&
        Math.max(startX, seg.start) < Math.min(endX, seg.end)
    );

    if (!intersectsObstacle(testY) && !intersectsLine(testY)) return testY;

    const step = 15;
    for (let offset = 1; offset <= 20; offset++) {
        let ty = testY + offset * step;
        if (!intersectsObstacle(ty) && !intersectsLine(ty)) return ty;

        ty = testY - offset * step;
        if (!intersectsObstacle(ty) && !intersectsLine(ty)) return ty;
    }

    // Go further if needed
    for (let y = endY + 20; y <= endY + 300; y += 20) {
        if (!intersectsObstacle(y) && !intersectsLine(y)) return y;
    }
    for (let y = startY - 20; y >= startY - 300; y -= 20) {
        if (!intersectsObstacle(y) && !intersectsLine(y)) return y;
    }

    return testY;
}

// Calculate orthogonal (right-angle) path avoiding obstacles
function calculateOrthogonalPath(x1, y1, x2, y2, fromBox, toBox, obstacles, margin) {
    const points = [[x1, y1]];

    const dx = x2 - x1;
    const dy = y2 - y1;

    // Determine exit and entry directions
    // Output ports are typically on right/bottom, input ports on left/top

    if (Math.abs(dy) < 30 && dx > 0) {
        // Same row, going right - simple horizontal
        points.push([x2, y2]);
    } else if (dx > 0 && dy > 0) {
        // Target is down-right
        // Go right first, then down
        const exitX = fromBox ? fromBox.right + margin : x1 + 30;
        const entryY = toBox ? toBox.top - margin : y2 - 30;

        // Check for obstacles and find clear path
        const midX = findClearVerticalChannel(exitX, x2, y1, y2, obstacles, margin);

        points.push([midX, y1]); // Go right
        points.push([midX, y2]); // Go down
        points.push([x2, y2]);   // Go left to target

    } else if (dx > 0 && dy < 0) {
        // Target is up-right
        const midX = findClearVerticalChannel(x1 + 30, x2, y2, y1, obstacles, margin);

        points.push([midX, y1]); // Go right
        points.push([midX, y2]); // Go up
        points.push([x2, y2]);   // Go left to target

    } else if (dx <= 0 && dy > 0) {
        // Target is down-left (wrap around)
        const belowFromY = fromBox ? fromBox.bottom + margin : y1 + 60;
        const aboveToY = toBox ? toBox.top - margin : y2 - 30;
        const rightOfFrom = fromBox ? fromBox.right + margin : x1 + 30;
        const leftOfTo = toBox ? toBox.left - margin : x2 - 30;

        // Route: right -> down -> left -> down -> to target
        points.push([rightOfFrom, y1]);

        // Find a Y level that's clear
        const clearY = findClearHorizontalChannel(belowFromY, aboveToY, rightOfFrom, leftOfTo, obstacles, margin);

        points.push([rightOfFrom, clearY]);
        points.push([leftOfTo, clearY]);
        points.push([leftOfTo, y2]);
        points.push([x2, y2]);

    } else if (dx <= 0 && dy < 0) {
        // Target is up-left (wrap around)
        const belowToY = toBox ? toBox.bottom + margin : y2 + 60;
        const aboveFromY = fromBox ? fromBox.top - margin : y1 - 30;
        const rightOfFrom = fromBox ? fromBox.right + margin : x1 + 30;
        const leftOfTo = toBox ? toBox.left - margin : x2 - 30;

        // Route: right -> up -> left -> up -> to target
        points.push([rightOfFrom, y1]);

        const clearY = findClearHorizontalChannel(aboveFromY, belowToY, Math.min(leftOfTo, rightOfFrom), Math.max(leftOfTo, rightOfFrom), obstacles, margin);

        points.push([rightOfFrom, clearY]);
        points.push([leftOfTo, clearY]);
        points.push([leftOfTo, y2]);
        points.push([x2, y2]);

    } else {
        // Default: direct with offset
        const midY = (y1 + y2) / 2;
        points.push([x1, midY]);
        points.push([x2, midY]);
        points.push([x2, y2]);
    }

    // Clean up redundant points (same x or y as neighbors)
    return simplifyPath(points);
}

// Find a vertical channel (x position) that's clear of obstacles
function findClearVerticalChannel(minX, maxX, minY, maxY, obstacles, margin) {
    const startX = Math.min(minX, maxX);
    const endX = Math.max(minX, maxX);
    const startY = Math.min(minY, maxY);
    const endY = Math.max(minY, maxY);

    // Try middle first
    let testX = (startX + endX) / 2;

    // Check if this x position intersects any obstacle
    const intersects = (x) => obstacles.some(obs =>
        x >= obs.left - margin &&
        x <= obs.right + margin &&
        !(startY > obs.bottom + margin || endY < obs.top - margin)
    );

    if (!intersects(testX)) return testX;

    // Try positions at every 40px
    for (let x = startX; x <= endX; x += 40) {
        if (!intersects(x)) return x;
    }

    // Fallback: use midpoint anyway
    return testX;
}

// Find a horizontal channel (y position) that's clear of obstacles
function findClearHorizontalChannel(minY, maxY, minX, maxX, obstacles, margin) {
    const startY = Math.min(minY, maxY);
    const endY = Math.max(minY, maxY);
    const startX = Math.min(minX, maxX);
    const endX = Math.max(minX, maxX);

    // Try middle first
    let testY = (startY + endY) / 2;

    // Check if this y position intersects any obstacle
    const intersects = (y) => obstacles.some(obs =>
        y >= obs.top - margin &&
        y <= obs.bottom + margin &&
        !(startX > obs.right + margin || endX < obs.left - margin)
    );

    if (!intersects(testY)) return testY;

    // Try positions at every 40px
    for (let y = startY; y <= endY; y += 40) {
        if (!intersects(y)) return y;
    }

    // Fallback: go further down/up to find clear space
    for (let y = endY + 40; y <= endY + 200; y += 40) {
        if (!intersects(y)) return y;
    }
    for (let y = startY - 40; y >= startY - 200; y -= 40) {
        if (!intersects(y)) return y;
    }

    return testY;
}

// Check if a line segment intersects a box
function lineIntersectsBox(x1, y1, x2, y2, box, margin) {
    const left = box.left - margin;
    const right = box.right + margin;
    const top = box.top - margin;
    const bottom = box.bottom + margin;

    // Simple bounding box check for horizontal/vertical lines
    const minX = Math.min(x1, x2);
    const maxX = Math.max(x1, x2);
    const minY = Math.min(y1, y2);
    const maxY = Math.max(y1, y2);

    // Check if line bounding box overlaps with obstacle box
    return !(maxX < left || minX > right || maxY < top || minY > bottom);
}

// Remove redundant points from path
function simplifyPath(points) {
    if (points.length <= 2) return points;

    const simplified = [points[0]];

    for (let i = 1; i < points.length - 1; i++) {
        const prev = simplified[simplified.length - 1];
        const curr = points[i];
        const next = points[i + 1];

        // Keep point if direction changes
        const dx1 = curr[0] - prev[0];
        const dy1 = curr[1] - prev[1];
        const dx2 = next[0] - curr[0];
        const dy2 = next[1] - curr[1];

        // Direction changed if one delta becomes zero while other becomes non-zero
        const horizontal1 = Math.abs(dx1) > Math.abs(dy1);
        const horizontal2 = Math.abs(dx2) > Math.abs(dy2);

        if (horizontal1 !== horizontal2 || (dx1 === 0 && dy1 === 0) || (dx2 === 0 && dy2 === 0)) {
            // Skip point if it's essentially the same as previous
            if (Math.abs(curr[0] - prev[0]) > 1 || Math.abs(curr[1] - prev[1]) > 1) {
                simplified.push(curr);
            }
        } else if (horizontal1 === horizontal2) {
            // Same direction - might be able to skip, but keep if positions differ significantly
            if (horizontal1) {
                if (Math.abs(curr[1] - prev[1]) > 1) simplified.push(curr);
            } else {
                if (Math.abs(curr[0] - prev[0]) > 1) simplified.push(curr);
            }
        }
    }

    simplified.push(points[points.length - 1]);
    return simplified;
}

// Build SVG path with rounded corners AND jumps
function addJumpsAndRoundCorners(points, radius, existingSegments) {
    if (points.length < 2) return { path: '', segments: [] };

    // Simplify collinear points first
    points = simplifyPath(points);

    let d = `M ${points[0][0]} ${points[0][1]} `; // Move to start
    let currentSegments = [];
    const JUMP_RADIUS = 8;
    const CORNER_RADIUS = 12;

    for (let i = 0; i < points.length - 1; i++) {
        const curr = points[i];
        const next = points[i + 1];

        // Determine current segment properties
        const isHorizontal = Math.abs(curr[1] - next[1]) < 0.1;
        const startVal = isHorizontal ? Math.min(curr[0], next[0]) : Math.min(curr[1], next[1]);
        const endVal = isHorizontal ? Math.max(curr[0], next[0]) : Math.max(curr[1], next[1]);
        const constantVal = isHorizontal ? curr[1] : curr[0];

        // Register this segment for future collision detection
        currentSegments.push({
            orient: isHorizontal ? 'h' : 'v',
            c: constantVal,
            start: startVal,
            end: endVal
        });

        // Findings intersections with existing segments
        let intersections = [];
        existingSegments.forEach(seg => {
            // Check for perpendicular intersection
            if (seg.orient === (isHorizontal ? 'v' : 'h')) {
                // Must cross within segment bounds (with margin for jump)
                if (startVal < seg.c - JUMP_RADIUS && endVal > seg.c + JUMP_RADIUS &&
                    constantVal > seg.start && constantVal < seg.end) {
                    intersections.push(seg.c);
                }
            }
        });

        // Sort intersections based on direction of travel
        const isForward = isHorizontal ? (next[0] > curr[0]) : (next[1] > curr[1]);
        intersections.sort((a, b) => isForward ? (a - b) : (b - a));

        // Determine end point of this straight segment (before corner or at target)
        let segmentEndX = next[0];
        let segmentEndY = next[1];

        // If not the last segment, stop short for rounded corner
        let hasCorner = false;
        if (i < points.length - 2) {
            const afterNext = points[i + 2];
            // Calculate corner start point
            if (isHorizontal) {
                const cornerDist = Math.min(Math.abs(next[0] - curr[0]) / 2, CORNER_RADIUS);
                segmentEndX = isForward ? next[0] - cornerDist : next[0] + cornerDist;
                hasCorner = true;
            } else {
                const cornerDist = Math.min(Math.abs(next[1] - curr[1]) / 2, CORNER_RADIUS);
                segmentEndY = isForward ? next[1] - cornerDist : next[1] + cornerDist;
                hasCorner = true;
            }
        }

        // Draw line segments and jumps
        let currentX = isHorizontal ? (isForward ? startVal : endVal) : constantVal;
        let currentY = isHorizontal ? constantVal : (isForward ? startVal : endVal);

        // Correct start position if we just did a corner?
        // The SVG path cursor is already at the start of this segment (end of previous turn).
        // If i > 0, we started this segment 'CORNER_RADIUS' away from 'curr'.
        if (i > 0) {
            if (isHorizontal) {
                currentX = isForward ? curr[0] + CORNER_RADIUS : curr[0] - CORNER_RADIUS;
            } else {
                currentY = isForward ? curr[1] + CORNER_RADIUS : curr[1] - CORNER_RADIUS;
            }
        } else {
            currentX = curr[0];
            currentY = curr[1];
        }

        // Iterate through jumps
        for (let j = 0; j < intersections.length; j++) {
            const crossVal = intersections[j];

            // Check if jump is within the actual drawing range (accounting for corners)
            let inRange = false;
            // Range is from currentX/Y to segmentEndX/Y
            if (isHorizontal) {
                const minX = Math.min(currentX, segmentEndX);
                const maxX = Math.max(currentX, segmentEndX);
                if (crossVal > minX + JUMP_RADIUS && crossVal < maxX - JUMP_RADIUS) inRange = true;
            } else {
                const minY = Math.min(currentY, segmentEndY);
                const maxY = Math.max(currentY, segmentEndY);
                if (crossVal > minY + JUMP_RADIUS && crossVal < maxY - JUMP_RADIUS) inRange = true;
            }

            if (inRange) {
                // Line to jump start
                if (isHorizontal) {
                    const jumpStart = isForward ? crossVal - JUMP_RADIUS : crossVal + JUMP_RADIUS;
                    const jumpEnd = isForward ? crossVal + JUMP_RADIUS : crossVal - JUMP_RADIUS;
                    d += ` L ${jumpStart} ${currentY}`;
                    // Jump arc
                    d += ` A ${JUMP_RADIUS} ${JUMP_RADIUS} 0 0 1 ${jumpEnd} ${currentY}`;
                    currentX = jumpEnd;
                } else {
                    const jumpStart = isForward ? crossVal - JUMP_RADIUS : crossVal + JUMP_RADIUS;
                    const jumpEnd = isForward ? crossVal + JUMP_RADIUS : crossVal - JUMP_RADIUS;
                    d += ` L ${currentX} ${jumpStart}`;
                    // Jump arc
                    d += ` A ${JUMP_RADIUS} ${JUMP_RADIUS} 0 0 1 ${currentX} ${jumpEnd}`;
                    currentY = jumpEnd;
                }
            }
        }

        // Draw remaining line to end of straight segment (or corner start)
        d += ` L ${segmentEndX} ${segmentEndY} `;

        // Draw corner if needed
        if (hasCorner) {
            const afterNext = points[i + 2];
            // Determine end of corner (start of next segment)
            let cornerEndTargetX = next[0];
            let cornerEndTargetY = next[1];

            // Direction of next segment
            const nextIsHorizontal = Math.abs(next[1] - afterNext[1]) < 0.1;
            const nextIsForward = nextIsHorizontal ? (afterNext[0] > next[0]) : (afterNext[1] > next[1]);

            if (nextIsHorizontal) {
                const dist = Math.min(Math.abs(afterNext[0] - next[0]) / 2, CORNER_RADIUS);
                cornerEndTargetX = nextIsForward ? next[0] + dist : next[0] - dist;
            } else {
                const dist = Math.min(Math.abs(afterNext[1] - next[1]) / 2, CORNER_RADIUS);
                cornerEndTargetY = nextIsForward ? next[1] + dist : next[1] - dist;
            }

            d += ` Q ${next[0]} ${next[1]} ${cornerEndTargetX} ${cornerEndTargetY} `;
        }
    }

    return { path: d, segments: currentSegments };
}

// Delete a specific connection
function deleteConnection(from, to, fromPort) {
    state.connections = state.connections.filter(c =>
        !(c.from === from && c.to === to && c.fromPort === fromPort));
    renderConnections();
    setStatus('Connection deleted');
}

// ==================== Flow Operations ====================
function saveFlow() {
    const flowName = document.getElementById('flow-name').value || 'my_flow';
    const flow = buildFlowJSON();
    flow.name = flowName;
    flow.id = state.currentFlowId || flowName.toLowerCase().replace(/\s+/g, '_');

    fetch(`/api/flows/${flow.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(flow)
    })
        .then(r => r.json())
        .then(data => {
            state.currentFlowId = flow.id;
            setStatus(`Flow saved: ${flow.id} `);
            loadFlowList();
        })
        .catch(err => setStatus('Error saving flow: ' + err, true));
}

async function runFlow(startNodeId = null, initialData = {}) {
    showLoading('Saving flow...');

    try {
        // Always save first
        const flowName = document.getElementById('flow-name').value || 'my_flow';
        const flow = buildFlowJSON();
        flow.name = flowName;
        flow.id = state.currentFlowId || flowName.toLowerCase().replace(/\s+/g, '_');

        const saveRes = await fetch(`/api/flows/${flow.id}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(flow)
        });
        const saveData = await saveRes.json();
        state.currentFlowId = saveData.id;
        hideLoading(); // Hide after save complete

        // Now run (no loading dialog)
        clearLog();
        // UI State: Running
        document.getElementById('btn-run').style.display = 'none';
        document.getElementById('btn-stop').style.display = 'inline-block';

        addLog(startNodeId ? `🚀 Resuming flow from node: ${startNodeId}...` : '🚀 Running flow...', 'info');
        setStatus(startNodeId ? 'Resuming flow...' : 'Running flow...');

        // Remove previous status classes
        document.querySelectorAll('.node').forEach(n => {
            n.classList.remove('node-running', 'node-success', 'node-error');
        });

        const payload = {};
        if (startNodeId) payload.startNodeId = startNodeId;
        if (initialData && Object.keys(initialData).length > 0) payload.initialData = initialData;

        const runRes = await fetch(`/api/flows/${state.currentFlowId}/run`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        // Reader for streaming response
        const reader = runRes.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        // Get node order to map steps to nodes
        const executionOrder = getExecutionOrder();

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
                    handleStreamMessage(msg, executionOrder);
                } catch (e) {
                    console.error("Stream parse error", e, line);
                }
            }
        }
    } catch (err) {
        hideLoading();
        addLog(`❌ Error: ${err}`, 'error');
        setStatus('Error: ' + err, true);
    } finally {
        // UI State: Stopped
        document.getElementById('btn-run').style.display = 'inline-block';
        document.getElementById('btn-stop').style.display = 'none';
    }
}

function stopRun() {
    if (!state.currentFlowId) return;

    addLog('🛑 Stopping...', 'warning');
    setStatus('Stopping flow...');

    fetch(`/api/flows/${state.currentFlowId}/stop`, {
        method: 'POST'
    })
        .then(r => r.json())
        .then(data => {
            addLog('Signal sent: ' + data.status, 'info');
        })
        .catch(err => addLog('Error stopping: ' + err, 'error'));
}

function handleStreamMessage(msg, executionOrder) {
    // Batch progress messages
    if (msg.type === 'batch_row_start') {
        const rowNum = msg.row_index + 1;
        const total = msg.total_rows;
        const dataPreview = Object.entries(msg.row_data || {})
            .slice(0, 2)
            .map(([k, v]) => `${k}: ${v}`)
            .join(', ');

        addLog(`\n📊 Row ${rowNum}/${total}: ${dataPreview}`, 'info');
        setStatus(`Running row ${rowNum}/${total}...`);

        // Reset node states for new row
        document.querySelectorAll('.node').forEach(n => {
            n.classList.remove('node-running', 'node-success', 'node-error');
        });

    } else if (msg.type === 'batch_row_end') {
        const rowNum = msg.row_index + 1;
        const icon = msg.success ? '✅' : '❌';
        addLog(`${icon} Row ${rowNum} ${msg.success ? 'completed' : 'failed'}`, msg.success ? 'success' : 'error');

    } else if (msg.type === 'batch_completed') {
        addLog(`\n🎉 Batch Complete: ${msg.successful_rows}/${msg.total_rows} rows successful`, 'success');
        setStatus(`Batch completed: ${msg.successful_rows}/${msg.total_rows}`);

    } else if (msg.type === 'batch_stopped') {
        addLog(`🛑 Batch stopped at row ${msg.row + 1}`, 'warning');

        // Single flow messages
    } else if (msg.type === 'step_start') {
        const stepName = msg.step;

        // Reset visual status if requested (e.g. new loop iteration)
        if (msg.reset_flow) {
            document.querySelectorAll('.node').forEach(n => {
                n.classList.remove('node-success', 'node-error');
            });
            addLog(`\n🔄 Starting new data iteration...`, 'info');
        }

        addLog(`⏳ Executing: ${stepName}...`, 'info');

        // Highlight node
        const nodeId = msg.id || executionOrder[msg.index];
        if (nodeId) {
            const nodeEl = document.querySelector(`.node[data-id="${nodeId}"]`);
            if (nodeEl) nodeEl.classList.add('node-running');
        }

    } else if (msg.type === 'step_end') {
        const nodeId = msg.id || executionOrder[msg.index];
        const icon = msg.result === 'success' ? '✓' : '✗';
        const cls = msg.result === 'success' ? 'success' : 'error';
        const stepName = msg.step;

        // Update Log
        addLog(`${stepName} ${icon}`, cls);

        // Update Node
        if (nodeId) {
            const nodeEl = document.querySelector(`.node[data-id="${nodeId}"]`);
            if (nodeEl) {
                nodeEl.classList.remove('node-running');
                nodeEl.classList.add(msg.result === 'success' ? 'node-success' : 'node-error');
            }
        }

    } else if (msg.type === 'completed') {
        const successCount = msg.results.filter(r => r.result === 'success').length;
        const totalCount = msg.results.length;
        addLog(`\n✅ Flow Finished: ${successCount}/${totalCount}`, 'success');
        setStatus(`Flow completed`);

    } else if (msg.type === 'error') {
        addLog(`❌ Server Error: ${msg.error}`, 'error');
    }
}

// Animate nodes during/after execution
async function animateExecutionResults(results) {
    // Get execution order from connections
    const executionOrder = getExecutionOrder();

    for (let i = 0; i < results.length; i++) {
        const step = results[i];
        const nodeId = executionOrder[i];
        if (!nodeId) continue;

        const nodeEl = document.querySelector(`.node[data-id="${nodeId}"]`);
        if (!nodeEl) continue;

        // Remove previous states
        nodeEl.classList.remove('node-running', 'node-success', 'node-error');

        // Add running state briefly
        nodeEl.classList.add('node-running');
        await sleep(200);

        // Add result state
        nodeEl.classList.remove('node-running');
        if (step.result === 'success') {
            nodeEl.classList.add('node-success');
        } else {
            nodeEl.classList.add('node-error');
        }

        await sleep(300);
    }
}

function getExecutionOrder() {
    const order = [];
    const visited = new Set();

    function traverse(nodeId) {
        if (visited.has(nodeId)) return;
        visited.add(nodeId);

        const nodeData = state.nodes.get(nodeId);
        if (!nodeData) return;

        if (nodeData.type !== 'start') {
            order.push(nodeId);
        }

        const nextConns = state.connections.filter(c => c.from === nodeId);
        nextConns.forEach(c => traverse(c.to));
    }

    traverse('start');
    return order;
}

function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

// Loading modal functions
function showLoading(message = 'Loading...') {
    let modal = document.getElementById('loading-modal');
    if (!modal) {
        modal = document.createElement('div');
        modal.id = 'loading-modal';
        modal.className = 'loading-modal';
        modal.innerHTML = `
            <div class="loading-content">
                <div class="loading-spinner"></div>
                <p class="loading-text">${message}</p>
            </div>
        `;
        document.body.appendChild(modal);
    } else {
        modal.querySelector('.loading-text').textContent = message;
    }
    modal.style.display = 'flex';
}

function hideLoading() {
    const modal = document.getElementById('loading-modal');
    if (modal) modal.style.display = 'none';
}

function clearLog() {
    document.getElementById('run-log').innerHTML = '';
}

function addLog(message, type = 'info') {
    const log = document.getElementById('run-log');
    const entry = document.createElement('div');
    entry.className = `log-entry ${type}`;
    entry.textContent = message;
    log.appendChild(entry);
    log.scrollTop = log.scrollHeight;
}

function exportFlow() {
    const flow = buildFlowJSON();
    const json = JSON.stringify(flow, null, 2);

    // Download
    const blob = new Blob([json], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = (document.getElementById('flow-name').value || 'flow') + '.json';
    a.click();
    URL.revokeObjectURL(url);

    setStatus('Flow exported');
}

function buildFlowJSON() {
    const steps = [];
    const visited = new Set();

    // Build execution order from connections
    function traverse(nodeId, fromPort = 'out') {
        if (visited.has(nodeId + fromPort)) return;
        visited.add(nodeId + fromPort);

        const nodeData = state.nodes.get(nodeId);
        if (!nodeData || nodeData.type === 'start') {
            // Find next from start
            const nextConn = state.connections.find(c => c.from === nodeId);
            if (nextConn) traverse(nextConn.to);
            return;
        }

        const config = nodeTypes[nodeData.type];

        // Get meaningful param for step name (prioritize text > resource_id > index > etc)
        const getStepLabel = (params) => {
            return params.text || params.resource_id ||
                (params.index !== undefined && params.index !== '' ? `[${params.index}]` : '') ||
                params.key || params.package || params.check_text || params.save_as ||
                (params.x !== undefined && params.y !== undefined ? `${params.x},${params.y}` : '') ||
                '';
        };

        const step = {
            name: `${config.title}: ${getStepLabel(nodeData.params)}`.trim(),
            action: nodeData.type,
            params: { ...nodeData.params }
        };

        // Clean empty params
        Object.keys(step.params).forEach(k => {
            if (step.params[k] === '' || step.params[k] === undefined) {
                delete step.params[k];
            }
        });

        steps.push(step);

        // Find next connection
        const nextConns = state.connections.filter(c => c.from === nodeId);
        nextConns.forEach(c => traverse(c.to, c.fromPort));
    }

    traverse('start');

    return {
        name: document.getElementById('flow-name').value || 'flow',
        description: 'Created with Flow Editor',
        data: {},
        steps,
        // Store visual layout
        _editor: {
            nodes: Array.from(state.nodes.entries()).map(([id, data]) => ({
                id, ...data
            })),
            connections: state.connections
        }
    };
}

function loadFlow(flowId) {
    fetch(`/api/flows/${flowId}`)
        .then(r => r.json())
        .then(flow => {
            // Clear current
            document.querySelectorAll('.node:not(.start-node)').forEach(n => n.remove());
            state.nodes.clear();
            state.connections = [];
            state.nodeIdCounter = 1;

            // Reset start
            state.nodes.set('start', { id: 'start', type: 'start', x: 50, y: 100, params: {} });

            state.currentFlowId = flowId;
            document.getElementById('flow-name').value = flow.name || flowId;

            // Load from editor layout if available
            if (flow._editor) {
                flow._editor.nodes.forEach(nodeData => {
                    if (nodeData.type !== 'start') {
                        state.nodes.set(nodeData.id, nodeData);
                        // Update counter
                        const num = parseInt(nodeData.id.split('_')[1]);
                        if (num >= state.nodeIdCounter) state.nodeIdCounter = num + 1;
                    }
                });
                state.connections = flow._editor.connections || [];

                // Create DOM nodes
                state.nodes.forEach((nodeData, id) => {
                    if (id === 'start') return;
                    createNodeFromData(nodeData);
                });
            } else {
                // Convert steps to nodes
                let y = 100;
                let prevId = 'start';

                flow.steps.forEach((step, i) => {
                    const id = createNode(step.action, 200 + i * 180, y);
                    const nodeData = state.nodes.get(id);
                    if (nodeData) {
                        nodeData.params = step.params || {};
                        updateNodeBody(id);
                    }

                    state.connections.push({ from: prevId, fromPort: 'out', to: id, toPort: 'in' });
                    prevId = id;
                });
            }

            renderConnections();
            setStatus(`Loaded: ${flow.name}`);
        })
        .catch(err => setStatus('Error loading flow: ' + err, true));
}

function createNodeFromData(nodeData) {
    const config = nodeTypes[nodeData.type];
    if (!config) return;

    const node = document.createElement('div');
    node.className = 'node';
    node.dataset.id = nodeData.id;
    node.dataset.type = nodeData.type;
    node.style.left = nodeData.x + 'px';
    node.style.top = nodeData.y + 'px';
    node.draggable = true;

    node.innerHTML = `
        <div class="node-input" data-port="in"></div>
        <div class="node-header">
            <span class="node-icon">${config.icon}</span>
            <span class="node-title">${config.title}</span>
            <button class="node-delete" onclick="deleteNode('${nodeData.id}')">×</button>
        </div>
        <div class="node-body"></div>
        ${config.hasMultipleOutputs ?
            `<div class="node-output-yes" data-port="yes" title="Yes"></div>
             <div class="node-output-no" data-port="no" title="No"></div>` :
            `<div class="node-output" data-port="out"></div>`}
    `;

    document.getElementById('canvas').appendChild(node);

    node.addEventListener('click', e => {
        if (!e.target.classList.contains('node-delete')) {
            selectNode(nodeData.id);
        }
    });

    initNodeDragEvents(node);
    initConnectionEvents(node);
    updateNodeBody(nodeData.id);
}

function loadFlowList() {
    fetch('/api/flows')
        .then(r => r.json())
        .then(flows => {
            const select = document.getElementById('flow-select');
            select.innerHTML = '<option value="">New Flow</option>';
            flows.forEach(f => {
                select.innerHTML += `<option value="${f.id}">${f.name} (${f.steps} steps)</option>`;
            });

            select.onchange = () => {
                if (select.value) loadFlow(select.value);
            };
        });
}

// ==================== Device Integration ====================
function refreshScreen() {
    setStatus('Loading screenshot...');

    Promise.all([
        fetch('/api/device/screenshot').then(r => r.json()),
        fetch('/api/device/elements').then(r => r.json())
    ])
        .then(([screenshot, elements]) => {
            if (screenshot.image) {
                document.getElementById('screenshot').src = screenshot.image;
            }

            if (elements.elements) {
                document.getElementById('device-info').innerHTML = `
                <small>📱 ${elements.package.split('.').pop()}</small><br>
                <small>Elements: ${elements.elements.length}</small>
            `;

                const list = document.getElementById('elements-list');
                list.innerHTML = elements.elements
                    .filter(e => e.text || e.resource_id)
                    .map(e => `<div class="element-item" onclick="insertElement('${(e.text || '').replace(/'/g, "\\'")}', '${e.resource_id || ''}', ${e.index})">
                    [${e.index}] ${e.text || e.resource_id}
                </div>`).join('');
            }

            setStatus('Screen refreshed');
            document.getElementById('connection-status').textContent = '🟢 Connected';
            document.getElementById('connection-status').classList.add('connected');
        })
        .catch(err => {
            setStatus('Error: ' + err, true);
            document.getElementById('connection-status').textContent = '🔴 Disconnected';
            document.getElementById('connection-status').classList.remove('connected');
        });
}

function insertElement(text, resourceId, index) {
    if (state.selectedNode) {
        const nodeData = state.nodes.get(state.selectedNode);
        if (nodeData) {
            // Clear previous values first
            delete nodeData.params.text;
            delete nodeData.params.resource_id;
            delete nodeData.params.index;

            // Priority: resource_id > text > index
            if (resourceId) {
                nodeData.params.resource_id = resourceId;
            } else if (text) {
                nodeData.params.text = text;
            } else if (index !== undefined) {
                nodeData.params.index = index;
            }

            updateNodeBody(state.selectedNode);
            showProperties(state.selectedNode);
        }
    }
}

function checkConnection() {
    fetch('/api/device/elements')
        .then(r => {
            if (r.ok) {
                document.getElementById('connection-status').textContent = '🟢 Connected';
                document.getElementById('connection-status').classList.add('connected');
            }
        })
        .catch(() => { });
}

// ==================== Utilities ====================
function setStatus(msg, isError = false) {
    const el = document.getElementById('status');
    el.textContent = msg;
    el.style.color = isError ? '#ef4444' : '#a0a0a0';
}

// ==================== Floating Preview Panel ====================
let autoRefreshInterval = null;
let previewVisible = false;
let previewMode = 'screenshot'; // 'screenshot' or 'scrcpy'

function togglePreviewPanel() {
    const panel = document.getElementById('floating-preview');
    const btn = document.querySelector('.btn-preview');
    previewVisible = !previewVisible;

    if (previewVisible) {
        panel.style.display = 'block';
        btn.textContent = '📱 Hide Preview';

        // Load saved scrcpy URL
        const savedUrl = localStorage.getItem('scrcpy_url');
        if (savedUrl) {
            document.getElementById('scrcpy-url').value = savedUrl;
        }

        // Load saved preview mode
        const savedMode = localStorage.getItem('preview_mode') || 'screenshot';
        setPreviewMode(savedMode, true);

        initFloatingPanelDrag();
    } else {
        panel.style.display = 'none';
        btn.textContent = '📱 Show Preview';
        stopAutoRefresh();
    }
}

function setPreviewMode(mode, initial = false) {
    previewMode = mode;
    localStorage.setItem('preview_mode', mode);

    const screenshotDiv = document.getElementById('preview-screenshot');
    const scrcpyDiv = document.getElementById('preview-scrcpy');
    const autoRefreshSelect = document.getElementById('auto-refresh');
    const modeSelect = document.getElementById('preview-mode');

    if (modeSelect && !initial) {
        modeSelect.value = mode;
    } else if (modeSelect && initial) {
        modeSelect.value = mode;
    }

    if (mode === 'scrcpy') {
        screenshotDiv.style.display = 'none';
        scrcpyDiv.style.display = 'flex';
        autoRefreshSelect.style.display = 'none'; // Hide auto-refresh for scrcpy
        stopAutoRefresh();

        // Auto-load scrcpy if URL is set
        const url = document.getElementById('scrcpy-url').value;
        const iframe = document.getElementById('scrcpy-iframe');
        if (url && !iframe.src) {
            loadScrcpy();
        }

        setStatus('Scrcpy mode - realtime streaming');
    } else {
        screenshotDiv.style.display = 'block';
        scrcpyDiv.style.display = 'none';
        autoRefreshSelect.style.display = 'inline-block';
        refreshScreen();
        setStatus('Screenshot mode');
    }
}

function loadScrcpy() {
    const urlInput = document.getElementById('scrcpy-url');
    const iframe = document.getElementById('scrcpy-iframe');
    let url = urlInput.value.trim();

    if (!url) {
        setStatus('Please enter ws-scrcpy URL', true);
        return;
    }

    // Ensure URL has protocol
    if (!url.startsWith('http://') && !url.startsWith('https://')) {
        url = 'http://' + url;
        urlInput.value = url;
    }

    // Save URL for later
    localStorage.setItem('scrcpy_url', url);

    // Load iframe
    iframe.src = url;
    setStatus(`Loading scrcpy from ${url}...`);

    // Check if loaded
    iframe.onload = () => {
        setStatus('Scrcpy loaded - realtime streaming active');
        document.getElementById('connection-status').textContent = '🟢 Scrcpy Connected';
        document.getElementById('connection-status').classList.add('connected');
    };

    iframe.onerror = () => {
        setStatus('Failed to load scrcpy', true);
    };
}

function setAutoRefresh(interval) {
    stopAutoRefresh();

    const ms = parseInt(interval);
    if (ms > 0) {
        autoRefreshInterval = setInterval(refreshScreen, ms);
        setStatus(`Auto-refresh: ${ms / 1000}s`);
    } else {
        setStatus('Auto-refresh: Manual');
    }
}

function stopAutoRefresh() {
    if (autoRefreshInterval) {
        clearInterval(autoRefreshInterval);
        autoRefreshInterval = null;
    }
}

function initFloatingPanelDrag() {
    const panel = document.getElementById('floating-preview');
    const header = document.getElementById('floating-header');

    let isDragging = false;
    let startX, startY, initialLeft, initialTop;

    header.onmousedown = (e) => {
        if (e.target.tagName === 'BUTTON' || e.target.tagName === 'SELECT') return;

        isDragging = true;
        startX = e.clientX;
        startY = e.clientY;
        initialLeft = panel.offsetLeft;
        initialTop = panel.offsetTop;

        document.onmousemove = (e) => {
            if (!isDragging) return;

            const dx = e.clientX - startX;
            const dy = e.clientY - startY;

            panel.style.left = (initialLeft + dx) + 'px';
            panel.style.top = (initialTop + dy) + 'px';
            panel.style.right = 'auto';
        };

        document.onmouseup = () => {
            isDragging = false;
            document.onmousemove = null;
            document.onmouseup = null;
        };
    };
}


// ==================== Auto Layout Algorithm ====================
function autoLayout() {
    // 1. Sort nodes topologically or by BFS order to get linear sequence
    const adj = new Map();
    const nodes = Array.from(state.nodes.values());

    // Initialize adjacency list
    nodes.forEach(node => {
        adj.set(node.id, []);
    });

    // Populate edges
    state.connections.forEach(conn => {
        if (adj.has(conn.from)) {
            adj.get(conn.from).push(conn.to);
        }
    });

    // Find start node
    let startNodeId = 'start';
    if (!state.nodes.has('start')) {
        const inDegree = new Map();
        nodes.forEach(n => inDegree.set(n.id, 0));
        state.connections.forEach(conn => {
            inDegree.set(conn.to, (inDegree.get(conn.to) || 0) + 1);
        });
        const root = nodes.find(n => inDegree.get(n.id) === 0);
        if (root) startNodeId = root.id;
    }

    // BFS to get linear order
    const orderedNodes = [];
    const visited = new Set();
    const queue = [startNodeId];

    while (visited.size < nodes.length) {
        if (queue.length === 0) {
            // Handle disconnected parts
            const unvisited = nodes.find(n => !visited.has(n.id));
            if (unvisited) {
                queue.push(unvisited.id);
            } else {
                break;
            }
        }

        const id = queue.shift();

        if (visited.has(id)) continue;
        visited.add(id);
        orderedNodes.push(id);

        const neighbors = adj.get(id) || [];
        neighbors.forEach(nid => {
            if (!visited.has(nid)) queue.push(nid);
        });
    }

    // 2. Variable Width Grid Layout
    const MAX_COLS = 4;
    const START_X = 50;
    const START_Y = 100;
    const GAP_X = 50;
    const ROW_HEIGHT = 180;

    let currentRow = 0;
    let currentCol = 0;
    let nextX = START_X;

    orderedNodes.forEach((nodeId) => {
        const nodeData = state.nodes.get(nodeId);
        if (!nodeData) return;

        // Get actual element width from DOM to account for long text
        const el = document.querySelector(`.node[data-id="${nodeId}"]`);
        let width = 200; // Default fallback

        if (el) {
            // offsetWidth returns the CSS layout width (including borders map padding)
            // This is ideal because we want to space based on visual size
            width = el.offsetWidth;
        }

        // Ensure a healthy minimum for calculation
        width = Math.max(width, 160);

        // Check if we need to wrap to new row
        // If we are past MAX_COLS
        if (currentCol >= MAX_COLS) {
            currentRow++;
            currentCol = 0;
            nextX = START_X;
        }

        nodeData.x = nextX;
        nodeData.y = START_Y + (currentRow * ROW_HEIGHT);

        // Update DOM Position
        if (el) {
            el.style.left = nodeData.x + 'px';
            el.style.top = nodeData.y + 'px';
        }

        // Calculate next X position
        nextX += width + GAP_X;
        currentCol++;
    });

    renderConnections();
    setStatus("Auto layout complete (Smart Spacing) ✨");
}

// ==================== Package List ====================
let cachedPackages = [];

async function loadPackages() {
    const list = document.getElementById('packages-list');
    const info = document.getElementById('packages-info');

    list.innerHTML = '<div class="hint">Loading...</div>';

    try {
        // Load user apps (third-party)
        const response = await fetch('/api/device/packages?filter=user');
        const data = await response.json();

        if (data.error) {
            list.innerHTML = `<div class="hint">Error: ${data.error}</div>`;
            return;
        }

        cachedPackages = data.packages || [];

        // Update info like elements
        if (info) {
            info.innerHTML = `<small>Apps: ${cachedPackages.length}</small>`;
        }

        renderPackages(cachedPackages);

    } catch (err) {
        list.innerHTML = `<div class="hint">Failed to load</div>`;
    }
}

function renderPackages(packages) {
    const list = document.getElementById('packages-list');

    if (packages.length === 0) {
        list.innerHTML = '<div class="hint">No packages found</div>';
        return;
    }

    // Use same style as elements list
    list.innerHTML = packages.map(pkg => {
        // Get clean app name from package (last segment, capitalize)
        const parts = pkg.split('.');
        const appName = parts[parts.length - 1];

        return `<div class="element-item" onclick="insertPackage('${pkg}')" title="${pkg}">${appName}</div>`;
    }).join('');
}

function insertPackage(packageName) {
    // Check if a node is selected and supports package param
    if (state.selectedNode) {
        const nodeData = state.nodes.get(state.selectedNode);
        if (nodeData) {
            const config = nodeTypes[nodeData.type];
            // Only for nodes that have 'package' parameter
            if (config && config.params.some(p => p.name === 'package')) {
                nodeData.params.package = packageName;
                updateNodeBody(state.selectedNode);
                showProperties(state.selectedNode);
                setStatus(`✓ Package: ${packageName}`);
                return;
            }
        }
    }

    // If no supported node selected, copy to clipboard
    navigator.clipboard.writeText(packageName).then(() => {
        setStatus(`📋 Copied: ${packageName}`);
    });
}

// Load packages on init (delayed)
setTimeout(loadPackages, 2000);
