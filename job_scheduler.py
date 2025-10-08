import tweepy
import time
import schedule
import logging
from datetime import datetime
from config import X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_SECRET
from backend.database.models import (
    get_all_schedule_for_niche,
    get_draft_posts_for_niche,
    update_post_schedule,
    get_due_posts,
    update_post_status,
)
from backend.services.ai_generator import generate_post_content

# ------------------- Logging Setup -------------------
logging.basicConfig(
    filename="scheduler.log",
    level=logging.INFO,
    format="%(asctime)s — %(levelname)s — %(message)s",
)


# ------------------- Time Slot Generator -------------------
def generate_time_slots(posts_per_day):
    today = datetime.today().date()
    start = datetime.combine(today, datetime.strptime("07:00", "%H:%M").time())
    end = datetime.combine(today, datetime.strptime("23:00", "%H:%M").time())

    if posts_per_day <= 0:
        return []

    duration = end - start
    interval = duration / posts_per_day
    slots = [(start + (interval * i)).strftime("%Y-%m-%d %H:%M:%S") for i in range(posts_per_day)]
    return slots


# ------------------- Assign Posts -------------------
def assign_posts_to_slot():
    schedule_data = get_all_schedule_for_niche(1)
    logging.info(f"schedule for niche: {schedule_data}")

    if not schedule_data:
        logging.warning("No schedule found.")
        return

    schedule_row = schedule_data[0]
    posts_per_day = schedule_row["posts_per_day"]
    needs_approval = schedule_row["needs_approval"]
    slots = generate_time_slots(posts_per_day)
    drafts = get_draft_posts_for_niche(1, posts_per_day)

    if not drafts:
        logging.warning("No draft posts found for scheduling.")
        return

    for slot, draft in zip(slots, drafts):
        niche_id = draft["niche_id"]
        ai_text = generate_post_content(niche_id)

        try:
            if needs_approval == 1:
                update_post_schedule(draft["id"], slot, status="draft", content=ai_text)
                logging.info(f"Draft post {draft['id']} scheduled with AI content.")
            else:
                update_post_schedule(draft["id"], slot, status="scheduled", content=ai_text)
                logging.info(f"Scheduled post {draft['id']} updated with AI content.")
        except Exception as e:
            logging.error(f"Error updating post {draft['id']}: {e}")


# ------------------- Process Due Posts -------------------
def process_due_posts():
    due_posts = get_due_posts()
    if not due_posts:
        logging.info("No due posts found.")
        return

    for due in due_posts:
        needs_approval = due["needs_approval"]
        post_id = due["id"]

        try:
            if needs_approval == 1 and due["status"] == "scheduled":
                update_post_status(post_id, "pending approval")
                logging.info(f"Post {post_id} set to pending approval.")
            elif due["status"] == "approved":
                publish_post(due)
            else:
                publish_post(due)
                update_post_status(post_id, "posted")
        except Exception as e:
            logging.error(f"Error processing post {post_id}: {e}")


# ------------------- Publish Post -------------------
def publish_post(post):
    post_id = post["id"]
    content = post["content"]

    client = tweepy.Client(
        consumer_key=X_API_KEY,
        consumer_secret=X_API_SECRET,
        access_token=X_ACCESS_TOKEN,
        access_token_secret=X_ACCESS_SECRET,
    )

    try:
        me = client.get_me()
        logging.info(f"Authenticated as: {me.data.username}")

        response = client.create_tweet(text=content)
        logging.info(f"Tweet successfully posted for post {post_id}: {response}")
        update_post_status(post_id, "posted")

    except tweepy.TooManyRequests:
        logging.warning("Rate limit reached. Retrying in 15 minutes...")
        time.sleep(900)
        publish_post(post)
    except Exception as e:
        logging.error(f"Error posting tweet {post_id}: {e}")


# ------------------- Run Scheduler -------------------
def run_scheduler():
    schedule.every().day.at("00:00").do(assign_posts_to_slot)
    schedule.every(1).minutes.do(process_due_posts)

    logging.info("Scheduler started... press CTRL+C to stop.")
    while True:
        schedule.run_pending()
        time.sleep(1)


if __name__ == "__main__":
    run_scheduler()
