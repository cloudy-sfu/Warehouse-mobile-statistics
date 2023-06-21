import re
from requests import Session
import json
import pandas as pd
import sqlite3
from random import uniform
from time import sleep
from datetime import datetime, timedelta
import pytz
from math import ceil
from pywebio.output import put_text

chrome113 = {
    'Accept': 'application/json, text/plain, */*', 'Accept-Encoding': 'gzip, deflate, br',
    'Accept-Language': 'en-US,en;q=0.9', 'Connection': 'keep-alive', 'Content-Length': '53',
    'Content-Type': 'application/json;charset=UTF-8', 'DNT': '1', 'Host': 'myaccount.warehousemobile.co.nz',
    'Origin': 'https://myaccount.warehousemobile.co.nz', 'Referer': 'https://myaccount.warehousemobile.co.nz/app/',
    'Sec-Fetch-Dest': 'empty', 'Sec-Fetch-Mode': 'cors', 'Sec-Fetch-Site': 'same-origin',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 '
                  'Safari/537.36',
    'sec-ch-ua': '"Google Chrome";v="107", "Chromium";v="107", "Not=A?Brand";v="24"'
}
session = Session()
session.trust_env = False
page_size = 20
with open('sql/create_user_table.sql', 'r') as f:
    sql_create_user_table = f.read()
auckland = pytz.timezone('Pacific/Auckland')
database_path = 'warehouse_mobile.db'


def init_database():
    with open('sql/create_token_table.sql', 'r') as f:
        sql_create_tokens_table = f.read()
    c = sqlite3.connect(database_path)
    r = c.cursor()
    r.execute(sql_create_tokens_table)
    r.close()
    c.commit()
    c.close()


def get_login_token(username, password):
    login = session.post(
        url='https://myaccount.warehousemobile.co.nz/scp/login',
        data=json.dumps({'msisdn': username, 'password': password}),
        headers=chrome113
    )
    sleep(round(uniform(0.7, 1.3), 3))
    return parse_response(login).get('token')


def parse_response(response):
    if response.status_code != 200:
        put_text('Network error. Cannot connect to warehouse mobile website. '
                 f'HTTPS status code {response.status_code}. URL: {response.url}')
        return
    response_text = json.loads(response.text)
    if response_text.get('errorcode'):
        put_text(f"Response error. Message: {response_text.get('errormessage')}")
        return
    else:
        return response_text


def get_edr(start_date, end_date, page, username, token):
    put_text(f"Retrieving data from {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}, "
             f"page {page + 1}.")
    edr_payload = {
        # It is a mistake that, if one send a text message at 00:00:00, it will not be retrieved. However, this is the
        # behaviour of warehouse mobile website. I keep the same behavior to prevent being detected and considered as
        # abnormal request by warehouse mobile website.
        "token": token, "from": start_date.strftime('%Y/%m/%d 00:00:01'),
        "to": end_date.strftime('%Y/%m/%d 23:59:59'),
        "msisdn": username, "utypes": ["All"], "curpage": page, "pagesize": page_size
    }
    edr = session.post(
        url='https://myaccount.warehousemobile.co.nz/scp/me/edr',
        data=json.dumps(edr_payload),
        headers=chrome113
    )
    sleep(round(uniform(0.7, 1.3), 3))
    edr_response = parse_response(edr)
    n = edr_response.get('edramount')
    record = edr_response.get('edrs')
    record = pd.DataFrame(record)
    if 'date_and_time' in record.columns:
        record['date_and_time'] = pd.to_datetime(record['date_and_time'], unit='ms')
    c = sqlite3.connect(database_path)
    record.to_sql(name=username, con=c, if_exists='append', index=False)
    c.close()
    return n


def get_password_from_db(username):
    c = sqlite3.connect(database_path)
    r = c.cursor()
    # check if the password exists
    r.execute('select password from tokens where username = ?', (username,))
    password_db = r.fetchone()
    if password_db:
        password_db = password_db[0]
    r.close()
    c.close()
    return password_db


def save_password(username, password):
    c = sqlite3.connect(database_path)
    r = c.cursor()
    r.execute('select password from tokens where username = ?', (username,))
    password_db = r.fetchone()
    if password_db:
        password_db = password_db[0]
        r.execute('delete from tokens where username = ?', (username,))
        c.commit()
    r.execute('insert into tokens (username, password) values (?, ?)', (username, password))
    c.commit()
    r.close()
    c.close()


def delete_password(username):
    c = sqlite3.connect(database_path)
    r = c.cursor()
    r.execute('delete from tokens where username = ?', (username,))
    c.commit()
    r.close()
    c.close()


def retrieve(username, token, recover_mode=False):
    c = sqlite3.connect(database_path)
    r = c.cursor()
    # create the user table if not exists
    r.execute(sql_create_user_table % username)
    c.commit()
    # get last sync datetime text
    username_safe = ''.join(re.findall(r"\d+", username))
    r.execute(f'select max(date_and_time) from "{username_safe}"')
    last_sync = r.fetchone()[0]
    r.close()
    c.close()

    yesterday = datetime.now(tz=auckland) - timedelta(days=1)
    yesterday = yesterday.replace(hour=0, minute=0, second=0, microsecond=0)
    if last_sync and (not recover_mode):
        last_sync = datetime.strptime(last_sync, '%Y-%m-%d %H:%M:%S')
        last_sync = auckland.localize(last_sync)
        last_sync = last_sync.replace(hour=0, minute=0, second=0, microsecond=0)

        end_date = yesterday
        start_date = max(last_sync, end_date - timedelta(days=28))
        while end_date > last_sync:
            n = get_edr(start_date, end_date, 0, username, token)
            n_pages = ceil(n / page_size)
            for p in range(1, n_pages):
                get_edr(start_date, end_date, p, username, token)
            end_date = start_date - timedelta(days=1)
            start_date = max(last_sync, end_date - timedelta(days=28))
    else:
        n = 1
        end_date = yesterday
        start_date = end_date - timedelta(days=28)
        while n > 0:
            n = get_edr(start_date, end_date, 0, username, token)
            n_pages = ceil(n / page_size)
            for p in range(1, n_pages):
                get_edr(start_date, end_date, p, username, token)
            end_date = start_date - timedelta(days=1)
            start_date = end_date - timedelta(days=28)
