#!/usr/bin/env python3
"""
Flow Editor Web Server
Visual node-based editor for Android automation flows
"""

import os
import sys
import json
import uuid
import base64
import threading
from datetime import datetime
from pathlib import Path

from flask import Flask, request, jsonify, send_from_directory, send_file
from flask_cors import CORS

sys.path.insert(0, '/home/zeroserver/Project/auto_register')
from utils import connect, DroidrunPortal
from utils.android_utils import get_device
from core.flow_runner import FlowRunner
from server.otp_server import start_server as start_otp_server, otp_store

app = Flask(__name__, static_folder='static')
CORS(app)

# Paths
FLOWS_DIR = Path('/home/zeroserver/Project/auto_register/flows')
FLOWS_DIR.mkdir(exist_ok=True)

# Global portal instance
portal = None

def get_portal():
    global portal
    if portal is None:
        portal = connect()
    return portal


# ==================== Static Files ====================

@app.route('/')
def index():
    return send_from_directory('static', 'index.html')

@app.route('/static/<path:path>')
def static_files(path):
    return send_from_directory('static', path)


# ==================== Flow CRUD ====================

@app.route('/api/flows', methods=['GET'])
def list_flows():
    """List all saved flows"""
    flows = []
    for f in FLOWS_DIR.glob('*.json'):
        try:
            with open(f) as fp:
                data = json.load(fp)
            flows.append({
                'id': f.stem,
                'name': data.get('name', f.stem),
                'description': data.get('description', ''),
                'steps': len(data.get('steps', [])),
                'modified': datetime.fromtimestamp(f.stat().st_mtime).isoformat()
            })
        except:
            pass
    return jsonify(flows)


@app.route('/api/flows/<flow_id>', methods=['GET'])
def get_flow(flow_id):
    """Get a specific flow"""
    path = FLOWS_DIR / f'{flow_id}.json'
    if not path.exists():
        return jsonify({'error': 'Flow not found'}), 404
    
    with open(path) as f:
        data = json.load(f)
    return jsonify(data)


@app.route('/api/flows', methods=['POST'])
def create_flow():
    """Create a new flow"""
    data = request.json
    flow_id = data.get('id') or str(uuid.uuid4())[:8]
    
    data['id'] = flow_id
    data['created_at'] = datetime.now().isoformat()
    data['updated_at'] = datetime.now().isoformat()
    
    path = FLOWS_DIR / f'{flow_id}.json'
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)
    
    return jsonify({'id': flow_id, 'status': 'created'})


@app.route('/api/flows/<flow_id>', methods=['PUT'])
def update_flow(flow_id):
    """Update an existing flow"""
    data = request.json
    
    path = FLOWS_DIR / f'{flow_id}.json'
    data['id'] = flow_id
    data['updated_at'] = datetime.now().isoformat()
    
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)
    
    return jsonify({'id': flow_id, 'status': 'updated'})


@app.route('/api/flows/<flow_id>', methods=['DELETE'])
def delete_flow(flow_id):
    """Delete a flow"""
    path = FLOWS_DIR / f'{flow_id}.json'
    if path.exists():
        path.unlink()
        return jsonify({'status': 'deleted'})
    return jsonify({'error': 'Flow not found'}), 404


# ==================== Flow Execution ====================

# Global active runners
ACTIVE_RUNNERS = {}  # flow_id -> FlowRunner instance

@app.route('/api/flows/<flow_id>/run', methods=['POST'])
def run_flow(flow_id):
    """Execute a flow with streaming updates (supports batch mode with data_source)"""
    path = FLOWS_DIR / f'{flow_id}.json'
    if not path.exists():
        return jsonify({'error': 'Flow not found'}), 404
    
    data = request.json or {}
    session_prefix = data.get('session_id', flow_id)
    
    # Queue for execution events
    from queue import Queue, Empty
    event_queue = Queue()
    
    def on_progress(event):
        event_queue.put(event)
    
    def run_wrapper():
        try:
            runner = FlowRunner(get_portal())
            ACTIVE_RUNNERS[flow_id] = runner
            
            # Load flow data to check for graph mode
            with open(path) as f:
                flow_data = json.load(f)
            
            # Check if flow has _editor with connections (needed for condition branching)
            editor = flow_data.get("_editor", {})
            connections = editor.get("connections", [])
            
            # Check if any connection uses yes/no ports (condition branching)
            has_branching = any(
                conn.get("fromPort") in ["yes", "no"] 
                for conn in connections
            )
            
            # Check if flow has data_source (internal iterator)
            steps = flow_data.get("steps", [])
            has_data_source = any(s.get("action") == "data_source" for s in steps)

            if has_branching or has_data_source:
                # Use graph-based execution for conditional flows OR data source loops
                print("📊 Using graph mode (conditional branching or data source detected)")
                # If has data source, increase max iterations to allow loops
                max_iter = 10000 if has_data_source else 200
                ctx = runner.run_graph(flow_data, session_prefix, callback=on_progress, max_iterations=max_iter)
                results = [ctx]
            else:
                # Use regular batch mode for linear flows
                results = runner.run_file_batch(str(path), session_prefix, callback=on_progress)
            
            # Send final batch results
            total_success = sum(
                1 for ctx in results 
                if all(r["result"] == "success" for r in ctx.step_results)
            )
            
            event_queue.put({
                "type": "batch_completed",
                "total_rows": len(results),
                "successful_rows": total_success,
                "all_data": [ctx.data for ctx in results]
            })
        except Exception as e:
            import traceback
            traceback.print_exc()
            event_queue.put({"type": "error", "error": str(e)})
        finally:
            if flow_id in ACTIVE_RUNNERS:
                del ACTIVE_RUNNERS[flow_id]
            event_queue.put(None)  # Signal end
    
    # Start thread
    t = threading.Thread(target=run_wrapper, daemon=True)
    t.start()
    
    def generate():
        while True:
            try:
                # Wait for data
                item = event_queue.get(timeout=120)  # 2min timeout for OTP/long waits
                if item is None:
                    break
                yield json.dumps(item) + "\n"
                
            except Empty:
                # KEEPALIVE
                yield "{}\n"
            except Exception as e:
                yield json.dumps({"type": "error", "error": str(e)}) + "\n"
                break
    
    return app.response_class(generate(), mimetype='application/x-ndjson')


@app.route('/api/flows/<flow_id>/stop', methods=['POST'])
def stop_flow(flow_id):
    """Stop a running flow"""
    if flow_id in ACTIVE_RUNNERS:
        ACTIVE_RUNNERS[flow_id].stop()
        return jsonify({'status': 'stopping'})
    return jsonify({'status': 'not_running'})


@app.route('/api/run-step', methods=['POST'])
def run_single_step():
    """Execute a single step for testing purposes"""
    from core.flow_runner import FlowRunner, StepContext
    
    data = request.json
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    step_type = data.get('type')
    params = data.get('params', {})
    session_id = data.get('session_id', 'test')
    context_data = data.get('context_data', {})
    
    if not step_type:
        return jsonify({'error': 'Missing step type'}), 400
    
    try:
        runner = FlowRunner(get_portal())
        
        # Create single step config
        step = {
            'name': f'Test {step_type}',
            'action': step_type,
            'params': params,
            'retry_count': 1,  # Single try for test
            'wait_before': 0.2,
            'wait_after': 0.2
        }
        
        # Run single step
        ctx = runner.run([step], session_id, initial_data=context_data)
        
        # Get result
        if ctx.step_results:
            result = ctx.step_results[0]
            return jsonify({
                'status': 'ok',
                'result': result.get('result'),
                'step': result.get('step'),
                'captured_data': ctx.data
            })
        else:
            return jsonify({'error': 'No result returned'}), 500
            
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


# ==================== Device Interaction ====================

@app.route('/api/device/packages', methods=['GET'])
def get_packages():
    """Get list of installed packages on device"""
    import subprocess
    
    filter_type = request.args.get('filter', 'user')  # user, system, all
    search = request.args.get('search', '').lower()
    
    try:
        # Get packages
        if filter_type == 'user':
            # Third-party apps only
            cmd = ["adb", "shell", "pm", "list", "packages", "-3"]
        elif filter_type == 'system':
            # System apps only
            cmd = ["adb", "shell", "pm", "list", "packages", "-s"]
        else:
            # All packages
            cmd = ["adb", "shell", "pm", "list", "packages"]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        
        packages = []
        for line in result.stdout.strip().split('\n'):
            if line.startswith('package:'):
                pkg = line.replace('package:', '').strip()
                if search and search not in pkg.lower():
                    continue
                packages.append(pkg)
        
        packages.sort()
        
        return jsonify({
            'packages': packages,
            'count': len(packages),
            'filter': filter_type
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/device/elements', methods=['GET'])
def get_elements():
    """Get current screen elements"""
    try:
        p = get_portal()
        state = p.get_phone_state()
        elements = p.get_elements()
        
        # Flatten elements
        def flatten(elems, result=None):
            if result is None:
                result = []
            for e in elems:
                result.append({
                    'index': e.index,
                    'text': e.text,
                    'resource_id': e.resource_id,
                    'class_name': e.class_name,
                    'bounds': e.bounds,
                    'center': e.center
                })
                flatten(e.children, result)
            return result
        
        return jsonify({
            'package': state.get('packageName', ''),
            'activity': state.get('activityName', ''),
            'keyboard_visible': state.get('keyboardVisible', False),
            'elements': flatten(elements)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/device/screenshot', methods=['GET'])
def get_screenshot():
    """Get device screenshot as base64"""
    try:
        device = get_device()
        tmp_path = '/tmp/screenshot_web.png'
        device.screenshot(tmp_path)
        
        with open(tmp_path, 'rb') as f:
            img_data = base64.b64encode(f.read()).decode()
        
        return jsonify({'image': f'data:image/png;base64,{img_data}'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/device/tap', methods=['POST'])
def tap():
    """Execute a tap"""
    data = request.json
    try:
        p = get_portal()
        
        if 'x' in data and 'y' in data:
            p.tap(data['x'], data['y'])
        elif 'text' in data:
            p.tap_text(data['text'])
        elif 'resource_id' in data:
            p.tap_resource_id(data['resource_id'])
        elif 'index' in data:
            p.tap_index(data['index'])
        else:
            return jsonify({'error': 'Missing tap target'}), 400
        
        return jsonify({'status': 'ok'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/device/type', methods=['POST'])
def type_text():
    """Type text"""
    data = request.json
    try:
        p = get_portal()
        p.type_text(data.get('text', ''))
        return jsonify({'status': 'ok'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/device/key', methods=['POST'])
def press_key():
    """Press a key"""
    data = request.json
    key_codes = {
        'enter': 66, 'back': 4, 'home': 3, 'recent': 187,
        'backspace': 67, 'tab': 61, 'escape': 111
    }
    try:
        p = get_portal()
        key = data.get('key', '')
        code = key_codes.get(key.lower(), int(key) if key.isdigit() else 0)
        p.press_key(code)
        return jsonify({'status': 'ok'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ==================== OTP ====================

@app.route('/api/otp', methods=['POST'])
def receive_otp():
    """Receive OTP (proxy to otp_store)"""
    data = request.json
    session_id = data.get('session_id', 'default')
    otp = data.get('otp')
    
    if not otp:
        return jsonify({'error': 'Missing OTP'}), 400
    
    otp_store.set_otp(session_id, otp, data.get('metadata'))
    return jsonify({'status': 'ok', 'message': f'OTP stored for session: {session_id}'})


@app.route('/api/otp/<session_id>', methods=['GET'])
def get_otp(session_id):
    """Get stored OTP"""
    otp = otp_store.get_otp(session_id, mark_used=False)
    if otp:
        return jsonify({'otp': otp})
    return jsonify({'error': 'No OTP found'}), 404


# ==================== Main ====================

if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Flow Editor Web Server')
    parser.add_argument('-p', '--port', type=int, default=8081, help='Port')
    parser.add_argument('--host', default='0.0.0.0', help='Host')
    parser.add_argument('--no-debug', action='store_true', help='Disable debug mode')
    args = parser.parse_args()
    
    # Only start OTP server on main process (not reloader)
    if os.environ.get('WERKZEUG_RUN_MAIN') != 'true':
        try:
            start_otp_server(5000)
        except:
            print("[OTP Server] Already running or port in use")
    
    print(f"""
╔═══════════════════════════════════════════════════════════╗
║             🎨 Flow Editor Web Server                     ║
╠═══════════════════════════════════════════════════════════╣
║  Open: http://localhost:{args.port}                            ║
║  OTP Server: http://localhost:5000                        ║
╚═══════════════════════════════════════════════════════════╝
""")
    
    app.run(host=args.host, port=args.port, debug=not args.no_debug)

