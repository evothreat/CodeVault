import telebot as tb
import logging as lg
import flask as fsk
import config as cfg
import sqlite3 as sql
import csv
import time
from telebot import types
from os import path

# change if you want
FMT_TIME = "%a, %d %b %Y %H:%M:%S"

def build_product_keyboard(file):
    mup = types.ReplyKeyboardMarkup(True, row_width=2)
    mup.add('Подробный список')
    with open(file, encoding='cp1251') as f:
        r = csv.DictReader(f, delimiter=';')
        mup.add(*['{} ({} руб.)'.format(row['name'], row['price']) for row in r])
    mup.add('Назад', 'Корзина')
    return mup

def get_products(file):
    with open(file, encoding='cp1251') as f:
        r = csv.DictReader(f, delimiter=';')
        return list(r)

def get_product_by_name(file, name):
    with open(file, encoding='cp1251') as f:
        r = csv.DictReader(f, delimiter=';')
        for row in r:
            if row['name'] == name:
                return row
            
def main():
    bot = tb.TeleBot(cfg.API_TOKEN)
    app = fsk.Flask(__name__)

    # check whether database already exists, setup if not
    if not path.exists(cfg.DB_NAME):
        import db
        db.setup()
    db_conn = sql.connect(cfg.DB_NAME, isolation_level=None, check_same_thread=False)

    # remove old webhook
    bot.remove_webhook()
    # set new webhook
    with open(cfg.CERTIFICATE) as crt:
        bot.set_webhook(url='https://{}:{}/{}/'.format(cfg.HOST, cfg.PORT, cfg.API_TOKEN),
                        certificate=crt)

    # universal sql executions
    def exec_sql_stmt(stmt, *args):
        cur = db_conn.cursor()
        cur.execute(stmt, args)
        rows = cur.fetchall()
        cur.close()
        return rows
    
    # process webhook calls
    @app.route('/{}/'.format(cfg.API_TOKEN), methods=['POST'])
    def webhook():
        if fsk.request.headers.get('content-type') == 'application/json':
            data = fsk.request.data.decode('utf-8')
            upd = types.Update.de_json(data)
            bot.process_new_updates([upd])
            return ''
        fsk.abort(403)

    @bot.message_handler(commands=['start'])
    def welcome(msg): # CHECKED
        sent = bot.send_message(msg.chat.id, 'Привет {}!\n'
                                             'Я бот службы доставки Ramirez Sushi\n'
                                             'Отдел доставки работает ежедневно c 10:00 '
                                             'до 23:00'.format(msg.from_user.first_name))
        begin(sent)
        
    def begin(msg): # CHECKED
        mup = types.ReplyKeyboardMarkup(True)
        mup.add('Суши', 'Роллы')
        mup.add('Сеты', 'Пицца')
        mup.add('Wok', 'Акции')
        mup.add('Дополнительно', 'Корзина')
        sent = bot.send_message(msg.chat.id, 'Что пожелаете?', reply_markup=mup)
        bot.register_next_step_handler(sent, handle_choice)
    
    def show_basket(msg): # CHECKED
        # date[0], user_id[1], product[2], price[3], count[4], sum[5], phone[6], address[7], type[8]
        rows = exec_sql_stmt('SELECT * FROM orders WHERE user_id=?', msg.from_user.id)
        if not rows:
            bot.send_message(msg.chat.id, 'Вы пока что не делали заказы')
            begin(msg)
            return
        total = 0
        reply = ''
        for row in rows:
            total += row[5]
            reply += ('Дата: *{}*\n'
                      'Продукт: *{}*\n'
                      'Количество: *{}*\n'
                      'Сумма: *{}*\n\n').format(time.strftime(FMT_TIME, time.gmtime(row[0])),
                                                row[2], row[4], row[5])
        reply += 'Итого: *{} руб.*'.format(total)
        # basket options
        mup = types.ReplyKeyboardMarkup(True, row_width=2)
        mup.add(*['Убрать {} ({})'.format(row[2], row[4]) for row in rows])
        mup.add('Назад', 'Очистить')
        mup.add('Оформить заказ')
        sent = bot.send_message(msg.chat.id, reply, reply_markup=mup, parse_mode='Markdown')
        bot.register_next_step_handler(sent, handle_operation_choice)
                            
    def handle_product_count(msg): # CHECKED
        if msg.text.startswith('/'):
            return
        if msg.text == 'Назад':
            exec_sql_stmt('DELETE FROM orders WHERE user_id=? '
                          'AND date=(SELECT MAX(date) FROM orders WHERE user_id=?)',
                          msg.from_user.id, msg.from_user.id)
            begin(msg)
            return
        if msg.text == 'Корзина':
            show_basket(msg)
            return
        if not msg.text.isdigit():
            sent = bot.send_message(msg.chat.id, 'Введите число')
            bot.register_next_step_handler(sent, handle_product_count)
            return
        count = int(msg.text)
        # get last order of user
        price, date = exec_sql_stmt('SELECT price,date FROM orders '
                                    'WHERE user_id=? ORDER BY date DESC LIMIT 1',
                                    msg.from_user.id)[0]
        # multiplicate count with start price
        exec_sql_stmt('UPDATE orders SET count=?, sum=? WHERE date=?',
                      count, count * price, date)
        # report and redirect to main
        bot.send_message(msg.chat.id, 'Продукт успешно добавлен в корзину')
        begin(msg)
    
    def handle_product_choice(msg, file): # CHECKED
        if msg.text.startswith('/'):
            return
        if msg.text == 'Назад':
            begin(msg)
            return
        if msg.text == 'Корзина':
            show_basket(msg)
            return
        if msg.text == 'Подробный список':
            sent = None
            for p in get_products(file):
                try:
                    sent = bot.send_photo(msg.chat.id, p['ref'],
                                          caption='{} ({} руб.)'.format(p['name'], p['price']))
                except ApiException:
                    continue
            bot.register_next_step_handler(sent, lambda msg: handle_product_choice(msg, file))
            return            
        # store user/product details
        name = msg.text[:msg.text.find('(')-1]
        product = get_product_by_name(file, name)
        # if product does not exist
        if not product:
            sent = bot.send_message(msg.chat.id, 'Такого продукта у нас нет')
            bot.register_next_step_handler(sent, lambda msg: handle_product_choice(msg, file))
            return
        price = int(product['price'])
        exec_sql_stmt('INSERT INTO orders VALUES(?,?,?,?,?,?,?,?,?)',
                      int(time.time()), msg.from_user.id, product['name'],
                      price, 1, price, '', '', '')
        # send image with chosen product as description
        try:
            bot.send_photo(msg.chat.id, product['ref'], caption=msg.text)
        except ApiException:
            pass
        mup = types.ReplyKeyboardMarkup(True)
        mup.add('1', '2', '3')
        mup.add('4', '5', '6')
        mup.add('7', '8', '9')
        mup.add('Назад', 'Корзина')
        sent = bot.send_message(msg.chat.id, 'Выберите количество продукта',
                                reply_markup=mup)
        bot.register_next_step_handler(sent, handle_product_count)

    def handle_category_choice(msg): # CHECKED
        if msg.text.startswith('/'):
            return
        if msg.text == 'Назад':
            begin(msg)
            return
        if msg.text == 'Корзина':
            show_basket(msg)
            return
        file = './csv/роллы/{}.csv'.format(msg.text)
        if path.exists(file):
            sent = bot.send_message(msg.chat.id, 'Выберите продукт',
                                    reply_markup=build_product_keyboard(file))
            bot.register_next_step_handler(sent, lambda msg: handle_product_choice(msg, file))
            return
        sent = bot.send_message(msg.chat.id, 'Неверная подкатегория')
        bot.register_next_step(sent, handle_category_choice)

    def handle_personal_data(msg): # CHECKED
        if msg.text.startswith('/'):
            return
        if msg.text == 'Назад':
            begin(msg)
            return
        # does not check if number is valid
        if msg.text.isdigit():
            exec_sql_stmt('UPDATE orders SET phone=? WHERE user_id=?',
                          msg.from_user.id)
            dtype = exec_sql_stmt('SELECT type FROM orders WHERE user_id=? LIMIT 1',
                                 msg.from_user.id)[0][0]
            if dtype == 'Доставка':
                sent = bot.send_message(msg.chat.id, 'Укажите свой адрес\n'
                                                     'Чтобы вернуться нажмите "Назад"')
                bot.register_next_step_handler(sent, handle_personal_data)
                return
        # does not check if address exists
        exec_sql_stmt('UPDATE orders SET address=? WHERE user_id=?',
                      msg.text, msg.from_user.id)
        bot.send_message(msg.chat.id, 'Благодарим за покупку\n'
                                      'Менеджер свяжется с вами в течении 5 минут')
        begin(msg)

    def handle_type_choice(msg): # CHECKED
        if msg.text.startswith('/'):
            return
        if msg.text == 'Назад':
            begin(msg)
            return
        if msg.text in ('На вынос', 'Доставка'):
            exec_sql_stmt('UPDATE orders SET type=? WHERE user_id=?',
                          msg.text, msg.from_user.id)
            sent = bot.send_message(msg.chat.id, 'Укажите свой номер\n'
                                                 'Чтобы вернуться нажмите "Назад"')
            bot.register_next_step_handler(sent, handle_personal_data)
            return
        sent = bot.send_message(msg.chat.id, 'Неверный тип доставки')
        bot.register_next_step_handler(sent, handle_type_choice)
    
    def handle_operation_choice(msg): # CHECKED
        if msg.text.startswith('/'):
            return
        if msg.text == 'Назад':
            begin(msg)
            return
        if msg.text == 'Очистить':
            exec_sql_stmt('DELETE FROM orders WHERE user_id=?', msg.from_user.id)
            bot.send_message(msg.chat.id, 'Корзина успешно очищена')
            begin(msg)
            return
        if msg.text.startswith('Убрать'):   # if something else, will fail
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
            bot.register_next_step_handler(sent, handle_type_choice)
            return
        sent = bot.send_message(msg.chat.id, 'Неверная опция')
        bot.register_next_step_handler(sent, handle_operation_choice)
        
    def handle_choice(msg): # CHECKED
        if msg.text.startswith('/'):
            return
        if msg.text == 'Корзина':
            show_basket(msg)
            return
        if msg.text == 'Роллы':
            mup = types.ReplyKeyboardMarkup(True)
            mup.add('Классические', 'Темпурные')
            mup.add('Острые', 'Фирменные')
            mup.add('Назад', 'Корзина')
            sent = bot.send_message(msg.chat.id, 'Выберите подкатегорию',
                                    reply_markup=mup)
            bot.register_next_step_handler(sent, handle_category_choice)
            return
        file = './csv/{}.csv'.format(msg.text)
        if path.exists(file):
            sent = bot.send_message(msg.chat.id, 'Выберите продукт',
                                    reply_markup=build_product_keyboard(file))
            bot.register_next_step_handler(sent, lambda msg: handle_product_choice(msg, file))
            return
        sent = bot.send_message(msg.chat.id, 'Неверная опция')
        bot.register_next_step_handler(sent, handle_choice)
        
    app.run(host=cfg.HOST, port=cfg.PORT, ssl_context=(cfg.CERTIFICATE, cfg.PRIVATE_KEY))

main()
            
