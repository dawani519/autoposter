from flask import Flask, jsonify, send_from_directory
from backend.scheduler.job_scheduler import assign_posts_to_slot, process_due_posts, run_scheduler
import threading
import os

# ------------------- Flask App -------------------
app = Flask(__name__, static_folder='.')

# ------------------- Static Files Route -------------------
@app.route("/")
def index():
    """Serve the main index.html page."""
    return send_from_directory('.', 'index.html')

@app.route("/<path:path>")
def serve_static(path):
    """Serve static files (CSS, JS, etc.)."""
    if os.path.exists(path):
        return send_from_directory('.', path)
    return "File not found", 404

# ------------------- API Routes -------------------
@app.route("/run-assign-posts")
def run_assign_posts():
    """Manually trigger assigning AI posts to time slots."""
    try:
        assign_posts_to_slot()
        return jsonify({"status": "success", "message": "Posts assigned successfully"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})


@app.route("/run-due-posts")
def run_due_posts():
    """Manually trigger processing due posts."""
    try:
        process_due_posts()
        return jsonify({"status": "success", "message": "Due posts processed successfully"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})


@app.route("/start-scheduler")
def start_scheduler():
    """Start the scheduler in a background thread."""
    try:
        # Run the scheduler in a separate thread so Flask stays responsive
        threading.Thread(target=run_scheduler, daemon=True).start()
        return jsonify({"status": "success", "message": "Scheduler started in background"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})


# ------------------- Flask Entry Point -------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
