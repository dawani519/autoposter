from db import get_connection
import psycopg2.extras

#function to create niches
def create_niche(name, description, primary_statement):
    conn = get_connection()
    cursor = conn.cursor()
    sql = """ INSERT INTO niches (name, description, primary_statement)
            VALUES (%s, %s, %s)
            """ 
    values = (name, description, primary_statement)
    cursor.execute(sql, values)
    conn.commit()
    cursor.close()
    conn.close()
    print("niche created successfully")

#function to fetch niches
def get_all_niches():
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cursor.execute(" SELECT * FROM niches ")
    niches = cursor.fetchall()
    cursor.close()
    conn.close()
    return niches

#function to create hashtags
def create_hashtags(niche_id, tag):
    conn = get_connection()
    cursor = conn.cursor()
    sql = """ INSERT INTO  hashtags (niche_id, tag)
            VALUES (%s, %s) 
            """
    values = (niche_id, tag)
    cursor.execute(sql, values)
    conn.commit()
    cursor.close()
    conn.close()
    print("hashtags added successfully")

#function to fetch hashtags
def get_all_hashtags(niche_id):
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    value = (niche_id,)
    cursor.execute("SELECT * FROM hashtags WHERE niche_id = %s", (value))
    niches = cursor.fetchall()
    cursor.close()
    conn.close()
    return niches

#function to create accounts
def create_account(platform, api_key, api_secret, access_token, access_secret):
    conn = get_connection()
    cursor = conn.cursor()
    sql = """ INSERT INTO platform_accounts (platform, api_key, api_secret, access_token, access_secret)
            VALUES (%s, %s, %s, %s, %s) 
            """
    values = (platform, api_key, api_secret, access_token, access_secret)
    cursor.execute(sql, values)
    conn.commit()
    cursor.close()
    conn.close()
    print("account created successfully")

#function to fetch all accounts
def get_all_accounts():
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cursor.execute("SELECT * FROM platform_accounts")
    accounts = cursor.fetchone()
    cursor.close()
    conn.close()
    return accounts

#function to create posts
def create_post(niche_id, account_id, content, media_url=None, scheduled_time=None, status="draft"):
    conn = get_connection()
    cursor = conn.cursor()
    sql = """ INSERT INTO posts (niche_id, account_id, content, media_url, scheduled_time, status)
            VALUES (%s, %s, %s, %s, %s, %s)
       """
    values = (niche_id, account_id, content, media_url, scheduled_time, status)
    cursor.execute(sql, values)
    conn.commit()
    cursor.close()
    conn.close()
    print("post created successfully")

#function to fetch posts
def get_all_posts():
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cursor.execute("SELECT * FROM posts")
    posts = cursor.fetchall()
    cursor.close()
    conn.close()
    return posts

#function to fetch scheduled posts
def get_scheduled_posts():
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    sql = """ SELECT * FROM posts
            WHERE scheduled_time IS NOT NULL
            AND scheduled_time > CURRENT_TIMESTAMP;
            """
    cursor.execute(sql)
    posts = cursor.fetchall()
    cursor.close()
    conn.close()
    return posts

#function to create schedule
def create_schedule(niche_id, posts_per_day, needs_approval):
    conn = get_connection() 
    cursor = conn.cursor()
    sql = """ INSERT INTO schedule (niche_id, posts_per_day, needs_approval) 
        VALUES (%s, %s, %s) """
    value = (niche_id, posts_per_day, needs_approval)
    cursor.execute(sql, value)
    conn.commit()
    cursor.close()
    conn.close()
    print("scheduled posts inserted") 


#function to fetch schedule for niche
def get_all_schedule_for_niche(niche_id):
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cursor.execute("SELECT * FROM schedule WHERE niche_id = %s", (niche_id,))
    niche = cursor.fetchall()
    cursor.close()
    conn.close()
    return niche

#fetch schedule from the schedule table

def get_all_schedule():
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cursor.execute("SELECT * FROM schedule")
    schedule = cursor.fetchall()
    cursor.close()
    conn.close()
    return schedule

#count scheduled posts for a niche 

def count_scheduled_posts_for_niche_today(niche_id):
    conn = get_connection()
    cursor = conn.cursor()
    sql = "SELECT COUNT(*) FROM posts WHERE niche_id = %s AND DATE(scheduled_time) = CURRENT_DATE;"
    cursor.execute(sql, (niche_id,))
    count = cursor.fetchone()
    result = count[0]
    cursor.close()
    conn.close()
    return result    

#fetch draft posts
def get_draft_posts_for_niche(niche_id, limit):
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    sql = "SELECT * FROM posts WHERE niche_id = %s AND status = 'draft' ORDER BY created_at ASC LIMIT %s;"
    cursor.execute(sql, (niche_id, limit))
    status = cursor.fetchall()
    cursor.close() 
    conn.close()
    return status

#update scheduled time
def update_post_schedule(post_id, scheduled_time, status, content):
    conn = get_connection()
    cursor = conn.cursor()
    sql = """ UPDATE posts
            SET scheduled_time = %s, status = %s, content = %s
            WHERE id = %s;
    """
    cursor.execute(sql, (scheduled_time, status, content, post_id))
    conn.commit()
    cursor.close()
    conn.close()
    print("schedule updtated successfully")


#fetch specific posts where status = schedule
def get_due_posts():
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    sql = """ SELECT p.*, s.needs_approval
            FROM posts p
            JOIN schedule s ON p.niche_id = s.niche_id
            WHERE p.status = 'scheduled'
            AND p.scheduled_time <= CURRENT_TIMESTAMP;
        """
    cursor.execute(sql)
    status = cursor.fetchall()
    cursor.close()
    conn.close()
    return status


#update post status
def update_post_status(post_id, status):
    conn = get_connection()
    cursor = conn.cursor()
    sql = """
            UPDATE posts
            SET status = %s
            WHERE id = %s;
            """
    cursor.execute(sql, (status, post_id))
    conn.commit()
    cursor.close()
    conn.close()
    print("status updated successfully")


#approve posts
def approve_post(post_id):
    conn = get_connection()
    cursor = conn.cursor()
    sql = "UPDATE posts SET status = 'scheduled' WHERE id = %s"
    cursor.execute(sql, (post_id,))
    conn.commit()
    cursor.close()
    conn.close()




# id, niche_id, content, approved, posted, created_at, account_id, media_url, status, scheduled_time
# id, platform, api_key, api_secret, access_token, access_secret
