import psycopg2
import psycopg2.extras
from dotenv import load_dotenv
import os

load_dotenv()  # loads .env file

def get_connection():
    # Use DATABASE_URL if available, otherwise construct from individual env vars
    database_url = os.getenv("DATABASE_URL")
    
    if database_url:
        return psycopg2.connect(database_url)
    else:
        return psycopg2.connect(
            host=os.getenv("PGHOST", "localhost"),
            user=os.getenv("PGUSER", "postgres"),
            password=os.getenv("PGPASSWORD", "password"),
            database=os.getenv("PGDATABASE", "postgres")
        )
