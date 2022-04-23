from telegram import *
from telegram.ext import *
import http.server as http
import threading as thr
import os.path
import time
import hashlib
import sqlite3
import requests as reqs
import urllib
import hmac
from config import *

EXMO_API_URL = "https://api.exmo.com/v1{}"

# to acces QIWI payments
QIWI_PAYMENTS = ("https://edge.qiwi.com/payment-history/v2/persons/{}"
                 "/payments?rows=10&operation=IN").format(QIWI_PHONE)
QIWI_AUTHORIZATION = {"Authorization": "Bearer {}".format(QIWI_API_TOKEN)}

# orders(id[0], date[1], chat_id[2], method[3], currency[4], amount[5], wallet[6], price[7], is_paid[8])
def dict_order(order):
    return {
        "id":       order[0],
        "date":     order[1],
        "chat_id":  order[2],
        "method":   order[3],
        "currency": order[4],
        "amount":   order[5],       
        "wallet":   order[6],
        "price":    order[7],
        "is_paid":  order[8]
    }

def exec_sql_stmt(stmt, *args):
    cur = db_conn.cursor()
    cur.execute(stmt, args)
    rows = cur.fetchall()
    cur.close()
    return rows
"""
def get_json_response(method, urlstr, params="", hdrs={}):
    url = urllib.parse.urlsplit(urlstr)
    conn = http.client.HTTPSConnection(url.netloc)
    conn.request(method, url.path+"?"+url.query, params, hdrs)
    resp = conn.getresponse().read()
    conn.close()
    return json.loads(resp.decode("utf-8"))
"""
def sha512_sign(params):
    h = hmac.new(key=EXMO_SECRET_TOKEN, digestmod=hashlib.sha512)
    h.update(urllib.parse.urlencode(params).encode("utf-8"))
    return h.hexdigest()

def transfer_btc(amount, wallet):
    params = {
        "amount":   amount,
        "currency": "BTC",
        "address":  wallet
    }
    hdrs = {
        "Content-type": "application/x-www-form-urlencoded",
        "Key":          EXMO_PUBLIC_TOKEN,
        "Sign":         sha512_sign(params)
    }
    data = reqs.post(EXMO_API_URL.format("/withdraw_crypt"), params, headers=hdrs).json()
    if not data["result"]:
        return ""

    # get transaction id to track transfer
    params = {"task_id": data["task_id"]}
    hdrs["Sign"] = sha512_sign(params)
    data = reqs.post(EXMO_API_URL.format("/withdraw_get_txid"), params, headers=hdrs).json()
    return data["txid"]

# only for btc
def get_new_exmo_code(amount):
    params = {
        "currency": "BTC",
        "amount":   amount
    }
    hdrs = {
        "Content-type": "application/x-www-form-urlencoded",
        "Key":          EXMO_PUBLIC_TOKEN,
        "Sign":         sha512_sign(params)
    }
    data = reqs.post(EXMO_API_URL.format("/excode_create"), params, headers=hdrs).json()
    return data["code"]

def get_current_btc_balance():
    params = {"nonce": int(time.time() * 1000)}
    hdrs = {
        "Content-type": "application/x-www-form-urlencoded",
        "Key":          EXMO_PUBLIC_TOKEN,
        "Sign":         sha512_sign(params)
    }
    data = reqs.post(EXMO_API_URL.format("/user_info"), params, headers=hdrs).json()
    return float(data["balances"]["BTC"])

def get_current_btc_price():
    data = reqs.get(EXMO_API_URL.format("/trades"), params={"pair": "BTC_RUB"}).json()
    return float(data["BTC_RUB"][0]["price"])

def has_open_order(chat_id):
    res = exec_sql_stmt("SELECT * FROM orders WHERE chat_id=? AND is_paid=?", chat_id, False)
    return bool(res)

def accept_order(bot, update):
    # orders(id[0], date[1], chat_id[2], method[3], currency[4], amount[5], wallet[6], price[7], is_paid[8])
    exec_sql_stmt("INSERT INTO orders VALUES(NULL,?,?,?,?,?,?,?,?)", int(time.time()),
                  update.message.chat.id, '', '', 0.0, '', 0.0, False)
    
    show_payment_methods(bot, update)

def cancel_order(bot, update):
    exec_sql_stmt("DELETE FROM orders WHERE chat_id=? AND is_paid=?",
                  update.message.chat.id, False)
    show_options(bot, update)

def show_options(bot, update):
    kb = [["Обмен"],
          ["Информация о последнем заказе"],
          ["Перейти на канал"]]        
    update.message.reply_text("Пожалуйста выберите желаемую опцию.",
                              reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard = True))

def show_payment_methods(bot, update):
    kb = [["QIWI"],
          ["Яндекс.Деньги"],
          ["Отмена"]]    
    update.message.reply_text("Выберите способ оплаты.",
                              reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard = True))

def show_currency(bot, update):
    kb = [["EXMO-Код"],
          ["BTC-Кошелек"],
          ["Отмена"]]
    update.message.reply_text("Выберите желаемую валюту.",
                              reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard = True))

def ask_for_amount(bot, update):
    update.message.reply_text("Сколько биткоинов вы хотите иметь?")

def show_last_order(bot, update):
    order = exec_sql_stmt("SELECT * FROM orders WHERE chat_id=? AND is_paid=? ORDER BY date DESC LIMIT 1",
                        update.message.chat.id, True)
    if not order:
        update.message.reply_text("Вы пока что не делали заказы.")
        return
        
    order = dict_order(order)
    update.message.reply_text("Дата: {}\n"
                              "Способ оплаты: {}\n"
                              "Валюта: {}\n"
                              "Количество: {}\n"
                              "Цена: {}".format(time.strftime("%a, %d %b %Y %H:%M:%S", time.gmtime(order["date"])),
                                                order["method"], order["currency"], order["amount"], order["price"]))
    
def invite_to_channel(bot, update):
    update.message.reply_text("Наш канал: {}".format(CHANNEL))

def calculate(bot, update):
    order = exec_sql_stmt("SELECT * FROM orders WHERE chat_id=? AND is_paid=?",
                          update.message.chat.id, False)[-1]
    order = dict_order(order)
    
    # check if enough btc available
    if order["amount"] > get_current_btc_balance():
        update.message.reply_text("Извините, такого количества биткоинов у нас нет.")
        cancel_order(bot, update)
        return

    # calculate price
    price = get_current_btc_price()
    # der Grundpreis
    price = order["amount"]/(1/price)
    # substract commission
    price = price - price*(COMMISION/100)
    # round 4
    price = round(price, 4)

    exec_sql_stmt("UPDATE orders SET price=? WHERE chat_id=? AND is_paid=?",
                  price, order["chat_id"], False)

    # choose wallet
    wallet = QIWI_PHONE if order["method"] == "QIWI" else YANDEX_PHONE
    
    # beg to pay
    # id is unique and increments automatically!
    update.message.reply_text("Конечная сумма составляет: {} руб.\n"
                              "В качестве способа оплаты вы выбрали {}.\n"
                              "Переведите сумму на следующий номер: {}.\n"
                              "В качестве комментария укажите следующую строку: {}.\n"
                              "ВНИМАНИЕ: оплата с банкомата не принимается!".format(price,
                                                                                    order["method"],
                                                                                    wallet,
                                                                                    order["id"]))

def handle_choice(bot, update):
    choice = update.message.text
    chat_id = update.message.chat.id

    # return improves readability
    # check if option
    if choice == "Обмен":
        # check whether has order which was not paid
        if has_open_order(chat_id):
            update.message.reply_text("Сначала оплатите/отмените предыдущий заказ.")
            return
        accept_order(bot, update)
        return
    if choice == "Информация о последнем заказе":
        show_last_order(bot, update)
        return
    if choice == "Перейти на канал":
        invite_to_channel(bot, update)
        return
    if choice == "Отмена":
        cancel_order(bot, update)
        return

    # if nothing was bought, return
    if not has_open_order(chat_id):
        return
    
    # payment method?
    if choice in ("QIWI", "Яндекс.Деньги"):
        exec_sql_stmt("UPDATE orders SET method=? WHERE chat_id=? AND is_paid=?",
                      choice, chat_id, False)
        show_currency(bot, update)
        return
        
    # currency?    
    if choice in ("EXMO-Код", "BTC-Кошелек"):
        exec_sql_stmt("UPDATE orders SET currency=? WHERE chat_id=? AND is_paid=?",
                      choice, chat_id, False)
        if choice == "BTC-Кошелек":
            update.message.reply_text("Введите адрес своего биткоин кошелька.")
            return
        ask_for_amount(bot, update)
        return
        
    # bitcoin amount?
    if choice.replace('.', '').isdigit():
        exec_sql_stmt("UPDATE orders SET amount=? WHERE chat_id=? AND is_paid=?",
                      float(choice), chat_id, False)        
        calculate(bot, update)
        return
        
    # bitcoin address?
    if len(choice) >= 25:
        exec_sql_stmt("UPDATE orders SET wallet=? WHERE chat_id=? AND is_paid=?",
                      choice, chat_id, False)
        ask_for_amount(bot, update)
        return

    update.message.reply_text("Неверная опция.")

def close_order(order):
    bot.send_message(order["chat_id"], "Платеж усешно получен.")
    
    # exmo-code
    if order["currency"] == "EXMO-Код":
        code = get_new_exmo_code(order["amount"])
        bot.send_message(order["chat_id"], "Ваш EXMO-Код: {}".format(code))
        
    # send to wallet
    elif order["currency"] == "BTC-Кошелек":
        code = transfer_btc(order["amount"], order["wallet"])
        bot.send_message(order["chat_id"], "Ваш транзакционный код: {}".format(code))
        
    # set as paid
    exec_sql_stmt("UPDATE orders SET is_paid=? WHERE chat_id=? AND is_paid=?",
                  True, order["chat_id"], False)
    # show main page
    show_options(bot, update)

# set in yandex wallet settings this ip address!        
class NotificationHandler(http.BaseHTTPRequestHandler):
    def do_POST(self):
        size = int(self.headers["Content-Length"])
        lines = self.rfile.read(size).decode("utf-8").split("\n")
        if len(lines) < 9:
            return
        opid = lines[0].replace("operation_id = ", '')
        # associate data with retrieved id
        yandex_payments[opid] = {
            "currency": int(lines[5].replace("currency = ", '')),
            "amount":   float(lines[6].replace("amount = ", '')),
            "comment":  lines[8].replace("label = ", '')
        }
        self.wfile.write("DONE!".encode("utf-8"))                   # DEBUG

# start both in thread
def listen_notifications():
    server = http.HTTPServer(('', 80), NotificationHandler)
    server.serve_forever()

def check_payments():
    # for yandex notifications
    global yandex_payments
    yandex_payments = {}
    # run checker
    while True:
        # orders(id[0], date[1], chat_id[2], method[3], currency[4], amount[5], wallet[6], price[7], is_paid[8])
        # convert first to dictionary?
        orders = exec_sql_stmt("SELECT * FROM orders WHERE is_paid=?", False)
        for order in orders:
            order = dict_order(order)
            paid = False
            # check bot wallets
            if order["method"] == "Яндекс.Деньги":
                for opid, pm in yandex_payments.copy().items():
                    if pm["comment"] == order["id"] and pm["amount"] == order["price"] and pm["currency"] == 643:
                        close_order(order)
                        del yandex_payments[opid]
                        paid = True
                        break
            if paid:
                continue
            for pm in reqs.get(QIWI_PAYMENTS, headers=QIWI_AUTHORIZATION).json()["data"]:
                if pm["comment"] == order["id"] and pm["sum"]["amount"] == order["price"] and pm["currency"] == 643:
                    close_order(order)
                    break
        time.sleep(RECONN_TIME)

def handle_error(bot, update, error):
    print("Error occured:", error)

def main():
    # check whether database exists and build if not
    if not os.path.exists(DB_NAME):
        import db
        db.setup()
        
    # open global connection
    # autocommit is enabled
    global db_conn
    db_conn = sqlite3.connect(DB_NAME, isolation_level=None, check_same_thread=False)

    # run threads
    thr.Thread(target=check_payments).start()
    thr.Thread(target=listen_notifications).start()
    
    up = Updater(BOT_API_TOKEN)
    dp = up.dispatcher
    dp.add_handler(CommandHandler("start", show_options))
    # accept only text not commands
    dp.add_handler(MessageHandler((Filters.text & ~ Filters.command), handle_choice))
    dp.add_error_handler(handle_error)
    up.start_polling()
    up.idle()

    # dont forget to close database!
    db_conn.close()

main()
