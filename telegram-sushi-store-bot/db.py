import sqlite3
from config import DB_NAME

def setup():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute('''CREATE TABLE orders (
        date INTEGER PRIMARY KEY,
        user_id INTEGER,
        product TEXT,
        price INTEGER,
        count INTEGER,
        sum INTEGER,
        phone TEXT,
        address TEXT,
        dtype TEXT
    )''')
    conn.commit()
    conn.close()
