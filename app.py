import os
import uuid
import json
import queue
import threading
from flask import Flask, render_template, request, jsonify, Response, send_file
from werkzeug.utils import safe_join
from exporter_engine import FramerExporter

app = Flask(__name__)
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
EXPORTS_DIR = os.path.join(BASE_DIR, "exports")
os.makedirs(EXPORTS_DIR, exist_ok=True)

# Store background export jobs
export_jobs = {}

class ExportJob:
    def __init__(self, export_id, target_url, options):
        self.export_id = export_id
        self.target_url = target_url
        self.options = options
        self.status = "queued"  # queued, running, completed, failed
        self.progress = 0
        self.logs = []
        self.discovered_routes = []
        self.exported_files = []
        self.zip_filepath = None
        self.error_message = None
        self.subscribers = []
        self.lock = threading.Lock()

    def log(self, message, level="info"):
        log_entry = {
            "message": message,
            "level": level,
        }
        with self.lock:
            self.logs.append(log_entry)
            for q in list(self.subscribers):
                try:
                    q.put_nowait(log_entry)
                except queue.Full:
                    pass

    def run(self):
        self.status = "running"
        self.log(f"Starting export task [{self.export_id}] for {self.target_url}")
        
        output_dir = os.path.join(EXPORTS_DIR, self.export_id)
        
        def engine_logger(msg, level="info"):
            self.log(msg, level)
            
        try:
            exporter = FramerExporter(self.target_url, options=self.options, log_callback=engine_logger)
            result = exporter.export_site(output_dir)
            
            with self.lock:
                self.status = "completed"
                self.progress = 100
                self.discovered_routes = sorted(list(exporter.discovered_routes))
                self.exported_files = result["exported_files"]
                self.zip_filepath = result["zip_filepath"]
                
            self.log(f"Export completed! {len(self.exported_files)} pages packaged into ZIP.")
        except Exception as e:
            with self.lock:
                self.status = "failed"
                self.error_message = str(e)
            self.log(f"Export failed: {e}", level="error")

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/export", methods=["POST"])
def start_export():
    data = request.json or {}
    url = data.get("url", "").strip()
    if not url:
        return jsonify({"error": "Please provide a valid Framer URL."}), 400

    options = {
        "strip_telemetry": data.get("strip_telemetry", True),
        "hide_badge": data.get("hide_badge", True),
        "rewrite_links": data.get("rewrite_links", True),
        "max_pages": int(data.get("max_pages", 100)),
    }

    export_id = str(uuid.uuid4())[:8]
    job = ExportJob(export_id, url, options)
    export_jobs[export_id] = job

    # Start thread
    thread = threading.Thread(target=job.run, daemon=True)
    thread.start()

    return jsonify({
        "export_id": export_id,
        "status": "started",
    })

@app.route("/api/stream/<export_id>")
def stream_logs(export_id):
    job = export_jobs.get(export_id)
    if not job:
        return jsonify({"error": "Export job not found."}), 404

    q = queue.Queue(maxsize=200)
    
    with job.lock:
        # Catch up existing logs
        for log_entry in job.logs:
            q.put_nowait(log_entry)
        job.subscribers.append(q)

    def event_stream():
        try:
            while True:
                try:
                    log_entry = q.get(timeout=20)
                    yield f"data: {json.dumps(log_entry)}\n\n"
                    if job.status in ("completed", "failed") and q.empty():
                        yield f"event: status\ndata: {json.dumps({'status': job.status, 'files': job.exported_files, 'routes': job.discovered_routes})}\n\n"
                        break
                except queue.Empty:
                    # Heartbeat
                    yield "event: ping\ndata: {}\n\n"

                    if job.status in ("completed", "failed") and q.empty():
                        yield f"event: status\ndata: {json.dumps({'status': job.status, 'files': job.exported_files, 'routes': job.discovered_routes})}\n\n"
                        break
        finally:
            with job.lock:
                if q in job.subscribers:
                    job.subscribers.remove(q)

    return Response(event_stream(), mimetype="text/event-stream")

@app.route("/api/status/<export_id>")
def get_status(export_id):
    job = export_jobs.get(export_id)
    if not job:
        return jsonify({"error": "Export job not found."}), 404

    with job.lock:
        return jsonify({
            "export_id": job.export_id,
            "status": job.status,
            "target_url": job.target_url,
            "discovered_routes": job.discovered_routes,
            "exported_files": job.exported_files,
            "total_pages": len(job.exported_files),
            "error_message": job.error_message,
        })

@app.route("/api/download/<export_id>")
def download_export(export_id):
    job = export_jobs.get(export_id)
    zip_path = os.path.join(EXPORTS_DIR, export_id, "website_export.zip")
    
    if not os.path.exists(zip_path):
        return jsonify({"error": "Export ZIP file not found."}), 404
        
    return send_file(zip_path, as_attachment=True, download_name=f"framer_export_{export_id}.zip")

@app.route("/api/tree/<export_id>")
def get_tree(export_id):
    export_dir = os.path.join(EXPORTS_DIR, export_id)
    if not os.path.exists(export_dir):
        return jsonify({"error": "Export folder not found."}), 404

    tree = []
    for root, dirs, files in os.walk(export_dir):
        rel_root = os.path.relpath(root, export_dir)
        if rel_root == ".":
            rel_root = ""
        for file in files:
            if file != "website_export.zip":
                file_rel_path = os.path.join(rel_root, file).replace("\\", "/")
                tree.append({
                    "path": file_rel_path,
                    "name": file,
                    "folder": rel_root,
                    "size": os.path.getsize(os.path.join(root, file))
                })
                
    return jsonify({"tree": sorted(tree, key=lambda x: x["path"])})

@app.route("/api/file/<export_id>")
def get_file_content(export_id):
    filepath = request.args.get("path", "")
    if not filepath:
        return jsonify({"error": "Path parameter required."}), 400

    export_dir = os.path.join(EXPORTS_DIR, export_id)
    abs_path = safe_join(export_dir, filepath)
    
    if not abs_path or not os.path.exists(abs_path):
        return jsonify({"error": "File not found."}), 404

    try:
        with open(abs_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        return jsonify({"path": filepath, "content": content})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "false").lower() in ("1", "true")
    app.run(host="0.0.0.0", port=port, debug=debug)

