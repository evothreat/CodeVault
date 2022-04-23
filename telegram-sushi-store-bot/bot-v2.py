import telebot as tb
import logging as lg
import flask as fsk
import config as cfg
import sqlite3 as sql
import csv
import time
from telebot import types
from os import path

# date[0], user_id[1], product[2], price[3], count[4], sum[5], phone[6], address[7], dtype[8]
def order_to_dict(order):
    return {
        'date':     order[0],
        'user_id':  order[1],
        'product':  order[2],
        'price':    order[3],
        'count':    order[4],
        'sum':      order[5],
        'phone':    order[6],
        'address':  order[7],
        'dtype':    order[8]
    }

def main():
    # base setup
    bot = tb.TeleBot(cfg.API_TOKEN)
    app = fsk.Flask(__name__)

    # setup db if not exists
    if not path.exists(cfg.DB_NAME):
        import db
        db.setup()
    db_conn = sql.connect(cfg.DB_NAME, isolation_level=None, check_same_thread=False)

    # webhook set/remove
    bot.remove_webhook()
    with open(cfg.CERTIFICATE) as crt:
        bot.set_webhook(url='https://{}:{}/{}/'.format(cfg.HOST, cfg.PORT, cfg.API_TOKEN),
                        certificate=crt)

    # sql
    def exec_sql_stmt(stmt, *args):
        cur = db_conn.cursor()
        cur.execute(stmt, args)
        rows = cur.fetchall()
        cur.close()
        return rows

    # csv
    def get_product_by_name(file, name):
        with open(file, encoding='cp1251') as f:
            r = csv.DictReader(f, delimiter=';')
            for row in r:
                if row['name'] == name:
                    return row

    def send_products_keyboard(msg, file):
        mup = types.ReplyKeyboardMarkup(True, row_width=2)
        mup.add('Подробный список')
        with open(file, encoding='cp1251') as f:
            r = csv.DictReader(f, delimiter=';')
            mup.add(*['{} ({} руб.)'.format(row['name'], row['price']) for row in r])
        mup.add('Назад', 'Корзина')
        sent = bot.send_message(msg.chat.id, 'Выберите продукт', reply_markup=mup)
        bot.register_next_step_handler(sent, lambda msg: handle_product(msg, file))
    
    def send_products_info(msg, file):
        sent = None
        with open(file, encoding='cp1251') as f:
            r = csv.DictReader(f, delimiter=';')
            for row in r:
                try:
                    sent = bot.send_photo(msg.chat.id, row['ref'],
                                          caption='{} ({} руб.)'.format(row['name'], row['price']))
                except tb.apihelper.ApiException:
                    continue
        bot.register_next_step_handler(sent, lambda msg: handle_product(msg, file))

    # flask
    @app.route('/{}/'.format(cfg.API_TOKEN), methods=['POST'])
    def webhook():
        if fsk.request.headers.get('content-type') == 'application/json':
            data = fsk.request.data.decode('utf-8')
            upd = types.Update.de_json(data)
            bot.process_new_updates([upd])
            return ''
        fsk.abort(403)

    # helpers
    def merge_product_dupes(rows):
        keys = []
        new = []
        for r in rows:
            if r[0] in keys:
                continue
            keys.append(r[0])
            new.append([r[0], 0, 0])
            for r2 in rows:
                if r2[0] == r[0]:
                    new[-1][1] += r2[1]
                    new[-1][2] += r2[2]
        return new
    
    def notify_manager(msg):
        rows = exec_sql_stmt('SELECT * FROM orders WHERE user_id=? AND NOT phone=? '
                             'AND dtype=? OR NOT address=?',
                             msg.from_user.id, '', 'На вынос', '')
        rows = merge_product_dupes(rows)
        total = 0
        reply = 'Поступил новый заказ от пользователя {}: \n'.format(msg.from_user.first_name)
        for r in rows:
            total += r[5]
            reply += ('Продукт: *{}*\n'
                      'Количество: *{}*\n'
                      'Сумма: *{}*\n'
                      'Номер: *{}*\n'
                      'Адрес: *{}*\n'
                      'Тип доставки: *{}*\n\n').format(r[2], r[4], r[5], r[6], r[7], r[8])
        reply += 'Итого: *{} руб.*'.format(total)
        bot.send_message(cfg.MANAGER_CHAT_ID, reply, parse_mode='Markdown')
        bot.send_message(msg.chat.id, 'Благодарим за покупку\n'
                                      'Менеджер свяжется с вами в течении 5 минут')
        begin(msg)
    
    # handlers (telebot)
    @bot.message_handler(commands=['start'])
    def welcome(msg):
        sent = bot.send_message(msg.chat.id, 'Привет {}!\n'
                                             'Я бот службы доставки Ramirez Sushi\n'
                                             'Отдел доставки работает ежедневно c 10:00 '
                                             'до 23:00'.format(msg.from_user.first_name))
        begin(sent)
    
    def begin(msg):
        mup = types.ReplyKeyboardMarkup(True)
        mup.add('Суши', 'Роллы')
        mup.add('Сеты', 'Пицца')
        mup.add('Wok', 'Акции')
        mup.add('Дополнительно', 'Корзина')
        sent = bot.send_message(msg.chat.id, 'Что пожелаете?', reply_markup=mup)
        bot.register_next_step_handler(sent, handle_category)
    
    def show_basket(msg):
        rows = exec_sql_stmt('SELECT * FROM orders WHERE user_id=?', msg.from_user.id)
        rows = merge_product_dupes(rows)
        if not rows:
            bot.send_message(msg.chat.id, 'Вы пока что не делали заказы')
            begin(msg)
            return
        total = 0
        reply = ''
        for r in rows:
            total += r[2]
            reply += ('Продукт: *{}*\n'
                      'Количество: *{}*\n'
                      'Сумма: *{}*\n\n').format(r[0], r[1], r[2])
        reply += 'Итого: *{} руб.*'.format(total)
        # kb
        mup = types.ReplyKeyboardMarkup(True, row_width=2)
        mup.add(*['Убрать {} ({})'.format(r[0], r[1]) for r in rows])
        mup.add('Назад', 'Очистить')
        mup.add('Оформить заказ')
        sent = bot.send_message(msg.chat.id, reply, reply_markup=mup, parse_mode='Markdown')
        bot.register_next_step_handler(sent, handle_basket_op)

    def handle_product_count(msg, product): # CHECKED
        if '/' in msg.text[:1]:
            return
        if msg.text == 'Назад':
            begin(msg)
            return
        if msg.text == 'Корзина':
            show_basket(msg)
            return
        if not msg.text.isdigit():
            sent = bot.send_message(msg.chat.id, 'Введите число')
            bot.register_next_step_handler(sent, lambda msg: handle_product_count(msg, product))
            return
        count = int(msg.text)
        exec_sql_stmt('INSERT INTO orders VALUES(?,?,?,?,?)', int(time.time()),
                      msg.from_user.id, product['name'], product['price']*count)
        bot.send_message(msg.chat.id, 'Продукт успешно добавлен в корзину')
        begin(msg)
        
    def handle_product(msg, file):  # CHECKED
        if '/' in msg.text[:1]:
            return
        if msg.text == 'Назад':
            begin(msg)
            return
        if msg.text == 'Корзина':
            show_basket(msg)
            return
        if msg.text == 'Подробный список':
            send_products_info(msg, file)
            return
        name = msg.text[:msg.text.find('(')-1]
        product = get_product_by_name(file, name)
        if not product:
            sent = bot.send_message(msg.chat.id, 'Такого продукта у нас нет')
            bot.register_next_step_handler(sent, lambda msg: handle_product(msg, file))
            return
        try:
            bot.send_photo(msg.chat.id, product['ref'], caption=msg.text)
        except ApiException:
            # "picture now not available"
            pass
        mup = types.ReplyKeyboardMarkup(True)
        mup.add('1', '2', '3')
        mup.add('4', '5', '6')
        mup.add('7', '8', '9')
        mup.add('Назад', 'Корзина')
        sent = bot.send_message(msg.chat.id, 'Выберите количество продукта',
                                reply_markup=mup)
        bot.register_next_step_handler(sent, lambda msg: handle_product_count(msg, product))

    def handle_subcategory(msg):    # CHECKED
        if '/' in msg.text[:1]:
            return
        if msg.text == 'Назад':
            begin(msg)
            return
        if msg.text == 'Корзина':
            show_basket(msg)
            return
        file = './csv/роллы/{}.csv'.format(msg.text)
        if path.exists(file):
            send_products_keyboard(msg, file)
            return
        sent = bot.send_message(msg.chat.id, 'Неверная подкатегория')
        bot.register_next_step(sent, handle_subcategory)

    def handle_personal_data(msg):
        if '/' in msg.text[:1]:
            return
        if msg.text == 'Назад':
            begin(msg)
            return
        if msg.text.isdigit():
            exec_sql_stmt('UPDATE orders SET phone=? WHERE user_id=?',
                          msg.text, msg.from_user.id)
            dtype = exec_sql_stmt('SELECT dtype FROM orders WHERE user_id=? LIMIT 1',
                                  msg.from_user.id)[0][0]
            if dtype == 'Доставка':
                sent = bot.send_message(msg.chat.id, 'Укажите свой адрес\n'
                                                     'Чтобы вернуться нажмите "Назад"')
                bot.register_next_step_handler(sent, handle_personal_data)
                return
        exec_sql_stmt('UPDATE orders SET address=? WHERE user_id=?',
                      msg.text, msg.from_user.id)
        notify_manager(msg)

    def handle_type(msg):
        if '/' in msg.text[:1]:
            return
        if msg.text == 'Назад':
            begin(msg)
            return
        if msg.text in ('На вынос', 'Доставка'):
            exec_sql_stmt('UPDATE orders SET dtype=? WHERE user_id=?',
                          msg.text, msg.from_user.id)
            sent = bot.send_message(msg.chat.id, 'Укажите свой номер\n'
                                                 'Чтобы вернуться нажмите "Назад"')
            bot.register_next_step_handler(sent, handle_personal_data)
            return
        sent = bot.send_message(msg.chat.id, 'Неверный тип доставки')
        bot.register_next_step_handler(sent, handle_type)

    def handle_basket_op(msg):
        if '/' in msg.text[:1]:
            return
        if msg.text == 'Назад':
            begin(msg)
            return
        if msg.text == 'Очистить':
            exec_sql_stmt('DELETE FROM orders WHERE user_id=?', msg.from_user.id)
            bot.send_message(msg.chat.id, 'Корзина успешно очищена')
            begin(msg)
            return
        if 'Убрать' in msg.text:
            name = msg.text[:msg.text.find('(')-1].replace('Убрать ', '')
            date, price, count = exec_sql_stmt('SELECT date,price,count FROM orders '
                                               'WHERE user_id=? AND product=? ORDER BY '
                                               'date DESC LIMIT 1', msg.from_user.id, name)[0]
            if count == 1:
                exec_sql_stmt('DELETE FROM orders WHERE date=?', date)
                show_basket(msg)
                return
            count -= 1
            exec_sql_stmt('UPDATE orders SET count=?, sum=? WHERE date=?',
                          count, count * price, date)
            show_basket(msg)
            return
        if msg.text == 'Оформить заказ':
            mup = types.ReplyKeyboardMarkup(True)
            mup.add('На вынос', 'Доставка')
            mup.add('Назад')
            sent = bot.send_message(msg.chat.id, 'Выберите тип доставки', reply_markup=mup)
            bot.register_next_step_handler(sent, handle_type)
            return
        sent = bot.send_message(msg.chat.id, 'Неверная опция')
        bot.register_next_step_handler(sent, handle_basket_op)
        
    def handle_category(msg):   # CHECKED
        if '/' in msg.text[:1]:
            return
        if msg.text == 'Корзина':
            show_basket(msg)
            return
        if msg.text == 'Роллы':
            mup = types.ReplyKeyboardMarkup(True)
            mup.add('Классические', 'Темпурные')
            mup.add('Острые', 'Фирменные')
            mup.add('Назад', 'Корзина')
            sent = bot.send_message(msg.chat.id, 'Выберите подкатегорию', reply_markup=mup)
            bot.register_next_step_handler(sent, handle_subcategory)
            return
        file = './csv/{}.csv'.format(msg.text)
        if path.exists(file):
            send_products_keyboard(msg, file)
            return
        sent = bot.send_message(msg.chat.id, 'Неверная опция')
        bot.register_next_step_handler(sent, handle_category)
        
    app.run(host=cfg.HOST, port=cfg.PORT, ssl_context=(cfg.CERTIFICATE, cfg.PRIVATE_KEY))

main()
            
