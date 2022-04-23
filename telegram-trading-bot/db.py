import sqlite3
from config import DB_NAME

def setup():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    cur.execute("""CREATE TABLE orders (
        id INTEGER PRIMARY KEY,
        date INTEGER,
        chat_id TEXT,
        method TEXT,
        currency TEXT,
        amount REAL,
        wallet TEXT,
        price REAL,
        is_paid INTEGER
    )""")

    conn.commit()
    conn.close()
