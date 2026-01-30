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
            { name: 'check_text', type: 'text', label: 'Check Text Exists' }
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
    webhook: {
        icon: '🌐', title: 'Webhook', color: '#ec4899',
        params: [
            { name: 'url', type: 'text', label: 'URL' },
            { name: 'method', type: 'select', label: 'Method', options: ['POST', 'GET', 'PUT'] },
            { name: 'include_data', type: 'checkbox', label: 'Send Data', default: true }
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

    // Show summary of params
    let summary = [];
    config.params.forEach(p => {
        const val = nodeData.params[p.name];
        if (val) {
            summary.push(`${p.label}: ${val}`);
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
        <div class="property-actions">
            <button class="btn-run-node" onclick="runSingleNode('${id}')">
                <span class="run-icon">▶</span> Run
            </button>
        </div>
        <div id="run-result-${id}" class="run-result"></div>
    `;

    panel.innerHTML = html;
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
        <label>Data (${rows.length} rows)</label>
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
            <button onclick="importCSV('${id}')" class="btn-small">📄 Import CSV</button>
            <button onclick="clearAllRows('${id}')" class="btn-small btn-danger-small">🗑️ Clear</button>
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

    const newName = prompt('Column name:', `col${nodeData.params.columns.length + 1}`);
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
    document.getElementById(`csv-input-${nodeId}`).click();
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

            tempLine.setAttribute('d', `M ${startX} ${startY} C ${midX} ${startY}, ${midX} ${endY}, ${endX} ${endY}`);
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

function renderConnections() {
    const svg = document.getElementById('connections');
    svg.innerHTML = '';

    const containerRect = document.querySelector('.canvas-container').getBoundingClientRect();
    const canvas = document.getElementById('canvas');
    const canvasRect = canvas.getBoundingClientRect();

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

        // Account for zoom scale - coordinates from getBoundingClientRect are already scaled
        // so we need to convert them to canvas coordinates
        const x1 = (fromRect.left + fromRect.width / 2 - canvasRect.left) / state.scale;
        const y1 = (fromRect.top + fromRect.height / 2 - canvasRect.top) / state.scale;
        const x2 = (toRect.left + toRect.width / 2 - canvasRect.left) / state.scale;
        const y2 = (toRect.top + toRect.height / 2 - canvasRect.top) / state.scale;

        // Bezier curve
        const midX = (x1 + x2) / 2;
        const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
        path.setAttribute('d', `M ${x1} ${y1} C ${midX} ${y1}, ${midX} ${y2}, ${x2} ${y2}`);
        path.setAttribute('stroke', conn.fromPort === 'yes' ? '#4ade80' :
            conn.fromPort === 'no' ? '#ef4444' : '#e94560');
        path.setAttribute('stroke-width', '3');
        path.style.cursor = 'pointer';
        path.style.pointerEvents = 'stroke';
        path.style.transition = 'stroke-width 0.2s';

        // Hover effect
        path.addEventListener('mouseenter', () => {
            path.setAttribute('stroke-width', '6');
            path.setAttribute('stroke', '#ff0000');
        });
        path.addEventListener('mouseleave', () => {
            path.setAttribute('stroke-width', '3');
            path.setAttribute('stroke', conn.fromPort === 'yes' ? '#4ade80' :
                conn.fromPort === 'no' ? '#ef4444' : '#e94560');
        });

        // Click to delete
        path.addEventListener('click', (e) => {
            e.stopPropagation();
            if (confirm('Hapus connection ini?')) {
                deleteConnection(conn.from, conn.to, conn.fromPort);
            }
        });

        svg.appendChild(path);
    });
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
            setStatus(`Flow saved: ${flow.id}`);
            loadFlowList();
        })
        .catch(err => setStatus('Error saving flow: ' + err, true));
}

async function runFlow() {
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

        addLog('🚀 Running flow...', 'info');
        setStatus('Running flow...');

        // Remove previous status classes
        document.querySelectorAll('.node').forEach(n => {
            n.classList.remove('node-running', 'node-success', 'node-error');
        });

        const runRes = await fetch(`/api/flows/${state.currentFlowId}/run`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({})
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

function togglePreviewPanel() {
    const panel = document.getElementById('floating-preview');
    const btn = document.querySelector('.btn-preview');
    previewVisible = !previewVisible;

    if (previewVisible) {
        panel.style.display = 'block';
        btn.textContent = '📱 Hide Preview';
        refreshScreen();
        initFloatingPanelDrag();
    } else {
        panel.style.display = 'none';
        btn.textContent = '📱 Show Preview';
        stopAutoRefresh();
    }
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
