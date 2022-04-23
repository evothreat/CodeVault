import sqlite3
import os
import requests as reqs
import config as cfg

def get_iiko_token():
    return reqs.get('{}auth/access_token?user_id={}&user_secret={}'\
                    .format(cfg.IIKO_API_URL, cfg.IIKO_LOGIN, cfg.IIKO_PASSWD)).json()

# create indexes!
def create_tables(db):
    cur = db.cursor()
    cur.execute('''CREATE TABLE categories(
            id TEXT PRIMARY KEY,
            name TEXT
        )''')
    cur.execute('''CREATE TABLE products(
            id TEXT PRIMARY KEY,
            name TEXT,
            price INTEGER,
            weight INTEGER,
            cat_id TEXT,
            photo TEXT,
            FOREIGN KEY(cat_id) REFERENCES categories(id)
        )''')
    cur.execute('''CREATE TABLE basket(
            id INTEGER PRIMARY KEY,
            user_id INTEGER,
            prod_id TEXT,
            count INTEGER,
            sum INTEGER,
            FOREIGN KEY(prod_id) REFERENCES products(id)
        )''')
    db.commit()

def fill_tables(db):
    cur = db.cursor()
    token = get_iiko_token()
    data = reqs.get('{}nomenclature/{}?access_token={}'\
                    .format(cfg.IIKO_API_URL, cfg.IIKO_ORG, token)).json()
    for c in data['productCategories']:
        cur.execute('INSERT INTO categories VALUES(?,?)', (c['id'], c['name']))
    for p in data['products']:
        cur.execute('INSERT INTO products VALUES(?,?,?,?,?,?)', (p['id'], p['name'],
                                                                 p['price'], p['weight'],
                                                                 p['productCategoryId'],
                                                                 ''))   # NO PHOTO!
    db.commit()

def main():
    if os.path.exists(cfg.DB_NAME):
        os.remove(cfg.DB_NAME)
    db = sqlite3.connect(cfg.DB_NAME)
    create_tables(db)
    fill_tables(db)
    db.close()

main()
