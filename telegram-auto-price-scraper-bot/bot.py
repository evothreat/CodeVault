import requests
import logging
import json
from json.decoder import JSONDecodeError
from requests.auth import HTTPProxyAuth
from urllib.parse import urlparse, urljoin
from bs4 import BeautifulSoup
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters
from telegram.ext.dispatcher import run_async
from telegram import ReplyKeyboardMarkup
from time import sleep
import random

# ANTI-BAN
USER_AGENTS = (
    'Mozilla/5.0 (Windows NT 10.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/83.0.4103.97 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/83.0.4103.97 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:77.0) Gecko/20100101 Firefox/77.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:77.0) Gecko/20100101 Firefox/77.0',
    'Mozilla/5.0 (Linux x86_64; rv:77.0) Gecko/20100101 Firefox/77.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/83.0.4103.97 Safari/537.36'
)
PROXIES = (
    'http://46.161.21.45:8000',
    'http://46.161.21.196:8000',
    'http://46.161.21.137:8000',
    'http://46.161.20.30:8000',
    'http://46.161.20.59:8000'
)
PROXY_AUTH = HTTPProxyAuth('', '')			# here login and password

# BOT
#BOT_TOKEN = ''   									# test bot token
BOT_TOKEN = '1165735816:AAHth_RPZY-mU5m3awhG64nkTzR0myL2RDg'				# main bot token

# ADMIN
ADMINS = (1286988767, 165745246)

COMMANDS = ('set', 'get', 'list')

# TARIFFS
REGIONS = ('Тюмень', 'Другие', 'Новосибирск-Красноярск', 'Омск')
REGION_TARIFFS = {
    'Тюмень':                 (453, 772, 1410, 2135, 2570),
    'Другие':                 (225, 283, 370, 428, 515),
    'Новосибирск-Красноярск': (295, 440, 585, 672, 730),
    'Омск':                   (265, 323, 410, 468, 555)
}

# contains region for each user
user_region = {}

def to_number(s):    
    strn = ''.join(['' if ord(x) < 48 or ord(x) > 57 else x for x in s])
    return int(strn) if strn else 0

def build_link(url):
    link = url.scheme + '://' + url.netloc
    link = urljoin(link, url.path)
    link = urljoin(link, 'page{}/') + ('?' + url.query if url.query else '')
    return link

def calculate(prices, tariff):
    res = 0
    for p in prices:
        if p < 300000:
            res += tariff[0]
        elif p < 500000:
            res += tariff[1]
        elif p < 800000:
            res += tariff[2]
        elif p < 1500000:
            res += tariff[3]
        else:
            res += tariff[4]
    return res
        
def start(update, ctx):
    keyboard = ReplyKeyboardMarkup([['Тюмень', 'Омск'],
                                    ['Новосибирск-Красноярск', 'Другие']], resize_keyboard=True)
    update.message.reply_text('Выберите регион:', reply_markup=keyboard)

def handle_link(update):
    url = urlparse(update.message.text)
    # verify link
    if url.scheme != 'https' or url.netloc != 'auto.drom.ru':
        update.message.reply_text('Неверная ссылка')
        return
    link = build_link(url)
    # iterate and collect prices
    prices = []
    for i in range(1, 100):
        headers = {'Accept':          'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                   'Accept-Encoding': 'gzip,deflate',
                   'Accept-Language': 'ru,en;q=0.9,uk;q=0.8',
                   'User-Agent':      random.choice(USER_AGENTS)}
        resp = requests.get(link.format(i), headers=headers, params={'unsold': '1'},
                            proxies={'http': random.choice(PROXIES)}, auth=PROXY_AUTH)
        if resp.status_code != 200:
            update.message.reply_text('Неверный путь/параметр ссылки')
            return
        bs = BeautifulSoup(resp.text, 'lxml')
        spans = bs.find_all('span', {'data-ftid': 'bull_price'})
        # stop here
        if not spans:
            break
        for sp in spans:
            # get first child
            price = to_number(next(sp.children))
            prices.append(price)
        sleep(0.2)
    # calculate price addicted to region
    user_id = update.message.from_user.id
    res = calculate(prices, REGION_TARIFFS[user_region[user_id]])
    update.message.reply_text('Цена размещения: ' + str(res))    

def set_tariffs(tafs):
    for k, v in tafs.items():
        if k in REGION_TARIFFS:
            REGION_TARIFFS[k] = tuple(v)            # convert to tuple?

def get_fmt_tariffs():
    res = ''
    for k, v in REGION_TARIFFS.items():
        res += '{}: {}\n'.format(k, v)
    return res

def notify_users(bot):
    for u in user_region:
        bot.send_message(chat_id=u, text='Тарифы обновлены.')

def get_fmt_users(bot):
    res = ''
    for u in user_region:
        user = bot.get_chat(u)
        ln = user.last_name if user.last_name else ''
        un = '@' + user.username if user.username else ''
        res += '{} {} ({})\n'.format(user.first_name, ln, un)
    return res if res else 'Пользователей нет.'

@run_async                                          # does it work?
def handle_cmd(cmd, update, bot):
    args = cmd.split(None, 2)[1:]                                           # split ignoring multiple spaces
    if len(args) < 1 or not (args[0] in COMMANDS):
        update.message.reply_text('Неверный формат команды.')
        return
    if args[0] == 'set':
        try:
            if len(args) < 2:
                update.message.reply_text('Неверный формат команды.')
                return
            tafs = json.loads(args[1]) 
        except JSONDecodeError:
            update.message.reply_text('Неверный формат тарифов.')
            return
        set_tariffs(tafs)
        notify_users(bot)
        return
    if args[0] == 'get':
        update.message.reply_text(get_fmt_tariffs())
        return
    if args[0] == 'list':
        update.message.reply_text(get_fmt_users(bot))
        return
    
def handle_text_msg(update, ctx):
    text = update.message.text
    user_id = update.message.from_user.id
    if text.startswith('do') and user_id in ADMINS:
        handle_cmd(text, update, ctx.bot)
        return
    if text in REGIONS:
        user_region[user_id] = text
        update.message.reply_text('Выбранный регион: ' + text)
        return
    if user_id in user_region:
        handle_link(update)
        return
    update.message.reply_text('Укажите город')

def run():
    logging.basicConfig(level=logging.ERROR)
    updater = Updater(BOT_TOKEN, use_context=True)
    updater.dispatcher.add_handler(CommandHandler('start', start))
    updater.dispatcher.add_handler(MessageHandler(Filters.text, handle_text_msg))
    updater.start_polling()
    updater.idle()

run()

