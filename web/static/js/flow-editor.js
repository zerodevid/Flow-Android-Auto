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
        } else {
            html += `<input type="text" value="${value}" 
                     onchange="updateParam('${id}', '${p.name}', this.value)">`;
        }

        html += `</div>`;
    });

    panel.innerHTML = html;
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
            // Find if we're over an input port
            const inputPort = document.elementFromPoint(e.clientX, e.clientY);

            if (inputPort && inputPort.classList.contains('node-input')) {
                const targetNode = inputPort.closest('.node');
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
        addLog('🚀 Running flow...', 'info');
        setStatus('Running flow...');

        const runRes = await fetch(`/api/flows/${state.currentFlowId}/run`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({})
        });
        const data = await runRes.json();

        if (data.status === 'completed') {
            const successCount = data.results.filter(r => r.result === 'success').length;
            const totalCount = data.results.length;

            // Highlight nodes with animation
            await animateExecutionResults(data.results);

            // Log each step result
            data.results.forEach((step, i) => {
                const icon = step.result === 'success' ? '✓' : '✗';
                const cls = step.result === 'success' ? 'success' : 'error';
                const stepName = step.step || step.action || 'Step';
                addLog(`[${i + 1}/${totalCount}] ${stepName} ${icon}`, cls);
            });

            addLog(`\n✅ Complete: ${successCount}/${totalCount} steps`, 'success');
            setStatus(`Flow completed: ${successCount}/${totalCount} steps`);
        } else {
            addLog(`❌ Error: ${data.error}`, 'error');
            setStatus('Flow error: ' + data.error, true);
        }
    } catch (err) {
        hideLoading();
        addLog(`❌ Error: ${err}`, 'error');
        setStatus('Error: ' + err, true);
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
                    .map(e => `<div class="element-item" onclick="insertElement('${(e.text || '').replace(/'/g, "\\'")}', '${e.resource_id || ''}')">
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

function insertElement(text, resourceId) {
    if (state.selectedNode) {
        const nodeData = state.nodes.get(state.selectedNode);
        if (nodeData) {
            if (text) nodeData.params.text = text;
            if (resourceId) nodeData.params.resource_id = resourceId;
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
