from db import get_connection
from datetime import datetime
from backend.database.models import get_all_posts
from backend.database.models import get_scheduled_posts
from backend.database.models import get_all_schedule_for_niche

def get_all_schedule():
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM schedule")
    schedule = cursor.fetchall()
    cursor.close()
    conn.close()
    return schedule


schedule = get_all_schedule()
for s in schedule:
    posts_per_day = s["posts_per_day"]
    print(posts_per_day)
posts = get_all_posts()
for post in posts:
    niche_id = post["niche_id"]
    scheduled_time = post["scheduled_time"]
    print(niche_id, scheduled_time)

