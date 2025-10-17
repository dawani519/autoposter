from flask import Flask, jsonify, send_from_directory, request
from backend.scheduler.job_scheduler import assign_posts_to_slot, process_due_posts, run_scheduler
from backend.database.models import (
    create_niche, get_all_niches,
    create_post, get_all_posts, get_scheduled_posts,
    create_schedule, get_all_schedule,
    create_account, get_all_accounts
)
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

# ------------------- API Routes - Niches -------------------
@app.route("/api/niches", methods=["GET"])
def get_niches():
    """Get all niches."""
    try:
        niches = get_all_niches()
        return jsonify(niches)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/niches", methods=["POST"])
def add_niche():
    """Create a new niche."""
    try:
        data = request.get_json()
        create_niche(data['name'], data['description'], data['primary_statement'])
        return jsonify({"status": "success", "message": "Niche created successfully"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# ------------------- API Routes - Posts -------------------
@app.route("/api/posts", methods=["GET"])
def get_posts():
    """Get all posts."""
    try:
        posts = get_all_posts()
        return jsonify(posts)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/posts/scheduled", methods=["GET"])
def get_posts_scheduled():
    """Get scheduled posts."""
    try:
        posts = get_scheduled_posts()
        return jsonify(posts)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/posts", methods=["POST"])
def add_post():
    """Create a new post."""
    try:
        data = request.get_json()
        create_post(
            niche_id=data['niche_id'],
            account_id=data['account_id'],
            content=data['content'],
            media_url=data.get('media_url'),
            scheduled_time=data.get('scheduled_time'),
            status=data.get('status', 'draft')
        )
        return jsonify({"status": "success", "message": "Post created successfully"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# ------------------- API Routes - Schedules -------------------
@app.route("/api/schedules", methods=["GET"])
def get_schedules():
    """Get all schedules."""
    try:
        schedules = get_all_schedule()
        return jsonify(schedules)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/schedules", methods=["POST"])
def add_schedule():
    """Create a new schedule."""
    try:
        data = request.get_json()
        create_schedule(
            niche_id=data['niche_id'],
            posts_per_day=data['posts_per_day'],
            needs_approval=data['needs_approval']
        )
        return jsonify({"status": "success", "message": "Schedule created successfully"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# ------------------- API Routes - Accounts -------------------
@app.route("/api/accounts", methods=["GET"])
def get_accounts():
    """Get platform accounts."""
    try:
        account = get_all_accounts()
        return jsonify(account)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/accounts", methods=["POST"])
def add_account():
    """Create a new platform account."""
    try:
        data = request.get_json()
        create_account(
            platform=data['platform'],
            api_key=data['api_key'],
            api_secret=data['api_secret'],
            access_token=data['access_token'],
            access_secret=data['access_secret']
        )
        return jsonify({"status": "success", "message": "Account created successfully"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# ------------------- Scheduler Control Routes -------------------
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
