import sqlite3
import json
import re
import requests as reqs
from flask import Flask, request
from vk_api import VkApi
from vk_api.keyboard import VkKeyboard
import config as cfg


def main():
    # establish connection to db
    db = sqlite3.connect(cfg.DB_NAME, isolation_level=None, check_same_thread=False)
    # universal sql statement executor
    def exec_sql_stmt(stmt, *args):
        cur = db.cursor()
        cur.execute(stmt, args)
        rows = cur.fetchall()
        cur.close()
        return rows
    
    # to store users data
    users = {}
    
    # vk api
    vkapi = VkApi(token=cfg.VK_TOKEN).get_api()
    
    # handlers
    def build_keyboard_from(data, i=0):
        size = len(data)
        kb = VkKeyboard()
        for j, _ in zip(range(i*28, size, 2), range(9)):
            for d in data[j:j+2]:
                kb.add_button(d)
            kb.add_line()
        if i > 0:
            kb.add_button('Назад')
        kb.add_button('На главную')
        if size-28*i > 28:
            kb.add_button('Вперед')
        return kb.get_keyboard()
    
    def add_to_basket(user_id, prod_id, count):
        price = exec_sql_stmt('SELECT price FROM products WHERE id=?', prod_id)[0][0]
        prod = exec_sql_stmt('SELECT * FROM basket WHERE prod_id=?', prod_id)
        if prod:
            exec_sql_stmt('UPDATE basket SET count=?, sum=? WHERE prod_id=?',
                      prod[0][3]+count, prod[0][4]+count*price, prod_id)
        else:
            exec_sql_stmt('INSERT INTO basket VALUES(NULL,?,?,?,?)', user_id, prod_id,
                                                                     count, count*price)
        vkapi.messages.send(peer_id=user_id, message='Продукт успешно добавлен в корзину')
        show_menu(user_id)

    def handle_count(user_id, msg):
        if msg == 'На главную':
            show_menu(user_id)
            return
        if not msg.isdigit():
            vkapi.messages.send(peer_id=user_id, message='Введите число!')
            users[user_id]['handler'] = handle_count
            return
        add_to_basket(user_id, users[user_id]['prod_id'], int(msg))

    def show_numeric_keypad(user_id):
        nums = tuple(range(1, 13))
        kb = VkKeyboard()
        for i in range(0, 12, 3):
            for x in nums[i:i+3]:
                kb.add_button(str(x))
            kb.add_line()
        kb.add_button('На главную')
        vkapi.messages.send(peer_id=user_id, message='Выберите количество',
                            keyboard=kb.get_keyboard())
        
    def handle_product(user_id, msg):
        if msg == 'Вперед':
            show_products(user_id, users[user_id]['cat_id'], i=users[user_id]['index']+1)
            return
        if msg == 'Назад':
            show_products(user_id, users[user_id]['cat_id'], i=users[user_id]['index']-1)
            return
        if msg == 'На главную':
            show_menu(user_id)
            return
        prod = None
        try:
            prod = exec_sql_stmt('SELECT * FROM products WHERE name=?', msg)[0]
        except IndexError:
            vkapi.messages.send(peer_id=user_id, message='Неверный продукт!')
            users[user_id]['handler'] = handle_product
            return
        reply = ('Продукт: {}\n'
                 'Цена:    {}\n'
                 'Вес:     {}\n').format(prod[1],
                                         prod[2],
                                         prod[3])
        vkapi.messages.send(peer_id=user_id, message=reply)
        users[user_id]['prod_id'] = prod[0]
        users[user_id]['handler'] = handle_count
        show_numeric_keypad(user_id)
        
    def handle_category(user_id, msg):
        if msg == 'Вперед':
            show_categories(user_id, i=users[user_id]['index']+1)
            return
        if msg == 'Назад':
            show_categories(user_id, i=users[user_id]['index']-1)
            return
        if msg == 'На главную':
            show_menu(user_id)
            return
        cat_id = ''
        try:
            cat_id = exec_sql_stmt('SELECT id FROM categories WHERE name=?', msg)[0][0]
        except IndexError:
            vkapi.messages.send(peer_id=user_id, message='Неверная категория!')
            users[user_id]['handler'] = handle_category
            return
        show_products(user_id, cat_id)

    def show_products(user_id, cat_id, i=0):
        prods = exec_sql_stmt('SELECT name FROM products WHERE cat_id=?', cat_id)   # add price!
        prods = [p[0] for p in prods]
        vkapi.messages.send(peer_id=user_id, message='Выберите продукт',
                            keyboard=build_keyboard_from(prods, i))
        users[user_id]['cat_id'] = cat_id
        users[user_id]['index'] = i
        users[user_id]['handler'] = handle_product
    
    def show_categories(user_id, i=0):
        cats = exec_sql_stmt('SELECT name FROM categories')
        cats = [c[0] for c in cats]
        vkapi.messages.send(peer_id=user_id, message='Выберите категорию',
                            keyboard=build_keyboard_from(cats, i))
        users[user_id]['index'] = i
        users[user_id]['handler'] = handle_category

    def close_order(user_id):
        basket = exec_sql_stmt('SELECT basket.prod_id,products.name,basket.count,basket.sum FROM basket '
                               'JOIN products ON basket.prod_id=products.id WHERE user_id=?', user_id)
        exec_sql_stmt('DELETE FROM basket WHERE user_id=?', user_id)
        items = []
        total = 0
        for p in basket:
            total += p[3]
            print(p[0])     # DEBUG
            items.append({
                'id':     p[0],
                'name':   p[1],
                'amount': p[2]
            })
        order = {
            'organization': cfg.IIKO_ORG,
            'customer': {
                'name':  users[user_id]['name'],
                'phone': users[user_id]['phone']
            },
            'order': {
                'date':    None,
                'items':   items,
                'phone':   users[user_id]['phone'],
                'address': {
                    'city':   'Осинники',                         # ЛИШЬ ПРИМЕР! СЛЕДУЕТ ИЗМЕНИТЬ!
                    'street': users[user_id]['addr']['street'],
                    'home':   users[user_id]['addr']['home']
                }
            },
            'fullSum': total
        }
        token = reqs.get('{}auth/access_token?user_id={}&user_secret={}'.format(cfg.IIKO_API_URL,
                                                                                cfg.IIKO_LOGIN,
                                                                                cfg.IIKO_PASSWD)).json()
        data = reqs.post('{}orders/add?access_token={}'.format(cfg.IIKO_API_URL,token),
                         json=order).json()
        print(data) # DEBUG
        vkapi.messages.send(peer_id=user_id,
                            message='Спасибо за заказ, менеджер свяжется с вами')
        show_menu(user_id)
    
    def handle_pers_data(user_id, msg):
        if msg == 'На главную':
            show_menu(user_id)
            return
        if not users[user_id].get('name'):
            users[user_id]['name'] = msg
            vkapi.messages.send(peer_id=user_id, message='Укажите свой номер телефона')
            return
        if not users[user_id].get('phone'):
            if not re.match('^(8|\+?\d{1,3})?[ -]?\(?(\d{3})\)?[ -]?(\d{3})[ -]?(\d{2})[ -]?(\d{2})$', msg):
                vkapi.messages.send(peer_id=user_id, message='Неверный номер телефона!')
                return
            users[user_id]['phone'] = msg
            vkapi.messages.send(peer_id=user_id, message='Укажите свой адрес')
            return
        if not users[user_id].get('addr'):
            addr = msg.split(' ')
            if len(addr) < 2:
                vkapi.messages.send(peer_id=user_id, message='Неверный адрес!')
                return
            users[user_id]['addr'] = {
                'street': addr[0],
                'home':   addr[1]
            }
        close_order(user_id)
    
    def handle_basket_op(user_id, msg):
        if msg == 'Очистить':
            exec_sql_stmt('DELETE FROM basket WHERE user_id=?', user_id)
            vkapi.messages.send(peer_id=user_id, message='Корзина успешно очищена')
            show_menu(user_id)
            return
        if msg == 'На главную':
            show_menu(user_id)
            return
        if '-1' in msg:
            name = msg.replace('-1 ', '')   # error can occur/check users input/try except
            prod_id = exec_sql_stmt('SELECT id FROM products WHERE name=?', name)[0][0]
            prod = exec_sql_stmt('SELECT count,sum FROM basket WHERE user_id=? AND prod_id=?',
                                 user_id, prod_id)[0]
            if prod[0] == 1:
                exec_sql_stmt('DELETE FROM basket WHERE user_id=? AND prod_id=?', user_id, prod_id)
                show_basket(user_id)
                return
            exec_sql_stmt('UPDATE basket SET count=?,sum=? WHERE user_id=? AND prod_id=?',
                          prod[0]-1, prod[1]-prod[1]/prod[0], user_id, prod_id)
            show_basket(user_id)
            return
        if msg == 'Оформить заказ':
            kb = VkKeyboard()
            kb.add_button('На главную')
            vkapi.messages.send(peer_id=user_id, message='Укажите свое имя', keyboard=kb.get_keyboard())
            users[user_id]['handler'] = handle_pers_data
            return
        vkapi.messages.send(peer_id=user_id, message='Неверная опция!')
        users[user_id]['handler'] = handle_basket_op

    def show_basket(user_id):
        basket = exec_sql_stmt('SELECT products.name,basket.count,basket.sum FROM basket '
                               'JOIN products ON basket.prod_id=products.id WHERE user_id=?', user_id)
        if not basket:
            vkapi.messages.send(peer_id=user_id, message='Ваша корзина пуста')
            show_menu(user_id)
            return
        reply = ''
        total = 0
        for p in basket:
            total += p[2]
            reply += ('Продукт:    {}\n'
                      'Количество: {}\n'
                      'Сумма:      {}\n\n').format(p[0],
                                                   p[1],
                                                   p[2])
        reply += 'Итого: {}'.format(total)
        kb = VkKeyboard()
        for i in range(0, len(basket), 2):
            for p in basket[i:i+2]:
                kb.add_button('-1 {}'.format(p[0]))
            kb.add_line()
        kb.add_button('Очистить')
        kb.add_button('На главную')
        kb.add_button('Оформить заказ')
        vkapi.messages.send(peer_id=user_id, message=reply, keyboard=kb.get_keyboard())
        users[user_id]['handler'] = handle_basket_op
    
    def handle_menu_op(user_id, msg):
        if msg == 'Категории':
            show_categories(user_id)
            return
        if msg == 'Корзина':
            show_basket(user_id)
            return
    
    def show_menu(user_id):
        kb = VkKeyboard()
        kb.add_button('Категории')
        kb.add_line()
        kb.add_button('Корзина')
        vkapi.messages.send(peer_id=user_id, message='Выберите желаемую опцию',
                            keyboard=kb.get_keyboard())
        users[user_id] = {}
        users[user_id]['handler'] = handle_menu_op
    
    # flask app
    app = Flask(__name__)
    # main handler
    @app.route('/', methods=['POST'])
    def handler_msg():
        upd = json.loads(request.data.decode('utf-8'))
        if upd.get('type') != 'message_new':
            return 'not ok'
        uid = upd['object']['user_id']
        msg = upd['object']['body']
        usr = users.get(uid)
        if usr:
            usr['handler'](uid, msg)
            return 'ok'
        if msg == 'start':
            vkapi.messages.send(peer_id=uid, message='Добро пожаловать в службу доставки TokioSushi!')
            show_menu(uid)
            return 'ok'
        vkapi.messages.send(peer_id=uid, message='Неверная опция!')
        return 'ok'
    
    # run flask app
    app.run(cfg.HOST, cfg.PORT)

main()
