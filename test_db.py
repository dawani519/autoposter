from db import get_connection

try:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SHOW TABLES;")
    print("Tables in database:")
    for table in cursor.fetchall():
        print(table)
    conn.close()
except Exception as e:
    print("Connection failed:", e)
