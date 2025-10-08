
from backend.scheduler.job_scheduler import assign_posts_to_slot
from backend.database.models import get_draft_posts_for_niche, get_due_posts
from backend.scheduler.job_scheduler import process_due_posts
from backend.services.ai_generator import generate_post_content

#create_niche("tech", "all about tech", "strictly about tech")

# get_all_niches()

#create_hashtags(1, "remove tinubu")

#niches = get_all_hashtags("1")
#print(niches)

#create_account("x", "aljf98woeijsfkjew9834weojaf", "lasjflkjsldkffa", "lsfkjslafksfj", "sakjflasfie")

#accounts = get_all_accounts()
#print(accounts)



#post = get_all_accounts()
#print(post)

#post = get_scheduled_posts()
#print(post)

#create_schedule("1", "3", "1")

#niche = get_all_schedule_for_niche(1)
#print(niche)

#schedule = get_all_schedule()
#print(schedule)
#create_post(niche_id = 1, account_id = 1, content = "i want to be extremely rich", media_url=None, scheduled_time = "2025-09-21", status="draft" )


#posts = get_all_posts()
#print(posts)

#count = count_scheduled_posts_for_niche_today(1)
#print(count)

#print(generate_time_slots(5))
#print(generate_time_slots(4))
#print(generate_time_slots(4))

#print(get_draft_posts_for_niche(1, 5))


print(assign_posts_to_slot())

#status = get_due_posts()
#print(status)



#status = process_due_posts()
#print(status)
#niche_id, account_id, content, media_url=None, scheduled_time=None, status="draft"

#generate_post_content("technology")

