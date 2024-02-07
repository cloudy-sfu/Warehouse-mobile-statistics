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

chrome121 = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Encoding": "gzip, deflate, br",
    "Accept-Language": "en,zh-CN;q=0.9,zh;q=0.8",
    "Connection": "keep-alive",
    "Content-Length": "59",
    "Content-Type": "application/json;charset=UTF-8",
    "Dnt": "1",
    "Host": "myaccount.warehousemobile.co.nz",
    "Origin": "https://myaccount.warehousemobile.co.nz",
    "Referer": "https://myaccount.warehousemobile.co.nz/app/",
    "Sec-Ch-Ua": "\"Not A(Brand\";v=\"99\", \"Google Chrome\";v=\"121\", "
                 "\"Chromium\";v=\"121\"",
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": "\"Windows\"",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, "
                  "like Gecko) Chrome/121.0.0.0 Safari/537.36"
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
    put_text('Logging in.')
    login = session.post(
        url='https://myaccount.warehousemobile.co.nz/scp/login',
        data=json.dumps({'msisdn': username, 'password': password}),
        headers=chrome121, verify=False
    )
    sleep(round(uniform(0.5, 1), 2))
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
    put_text(f"Retrieving usage history from {start_date.strftime('%Y-%m-%d')} to "
             f"{end_date.strftime('%Y-%m-%d')}, page {page + 1}.")
    edr_payload = {
        # It is a mistake that, if one send a text message at 00:00:00, it will not be
        # retrieved. However, this is the behaviour of warehouse mobile website. I keep
        # the same behavior to prevent being detected and considered as abnormal
        # request by warehouse mobile website.
        "token": token, "from": start_date.strftime('%Y/%m/%d 00:00:01'),
        "to": end_date.strftime('%Y/%m/%d 23:59:59'),
        "msisdn": username, "utypes": ["All"], "curpage": page, "pagesize": page_size
    }
    edr = session.post(
        url='https://myaccount.warehousemobile.co.nz/scp/me/edr',
        data=json.dumps(edr_payload),
        headers=chrome121, verify=False,
    )
    sleep(round(uniform(0.5, 1), 2))
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
    r.execute('select password from tokens where username = ?',
              (username,))
    password_db = r.fetchone()
    if password_db:
        password_db = password_db[0]
    r.close()
    c.close()
    return password_db


def save_password(username, password):
    c = sqlite3.connect(database_path)
    r = c.cursor()
    r.execute('select password from tokens where username = ?',
              (username,))
    password_db = r.fetchone()
    if password_db:
        password_db = password_db[0]
        r.execute('delete from tokens where username = ?',
                  (username,))
        c.commit()
    r.execute('insert into tokens (username, password) values (?, ?)',
              (username, password))
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


def get_edr_full_history(username, token, recover_mode=False):
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
            n_items = get_edr(start_date, end_date, 0, username, token)
            n_pages = ceil(n_items / page_size)
            for p in range(1, n_pages):
                get_edr(start_date, end_date, p, username, token)
            end_date = start_date - timedelta(days=1)
            start_date = max(last_sync, end_date - timedelta(days=28))
    else:
        for shift in range(6):
            end_date = yesterday - timedelta(days=28 * shift)
            start_date = end_date - timedelta(days=28)
            n_items = get_edr(start_date, end_date, 0, username, token)
            n_pages = ceil(n_items / page_size)
            for p in range(1, n_pages):
                get_edr(start_date, end_date, p, username, token)


def get_data_balance(username, token):
    put_text("Retrieving statistics of remaining data package.")
    payload = {"msisdn": username, "token": token}
    request = session.post(
        url='https://myaccount.warehousemobile.co.nz/scp/vp/balance',
        data=json.dumps(payload),
        headers=chrome121, verify=False,
    )
    response_text = parse_response(request)
    put_text("Warehouse mobile only shows the earliest expiry date of data packages. "
             "Some other data may expire after that date.")
    for i, balance in enumerate(response_text.get("balances", [])):
        put_text(f"[Data package {i+1}]")
        put_text(f"Total balance is {balance.get('totalBalance')} MB.")
        bucket_expiry = balance.get('expirationDateDataPack')
        if bucket_expiry:
            bucket_expiry = datetime.strptime(
                str(bucket_expiry), "%Y%m%d%H%M%S").strftime("%Y-%m-%d %H:%M:%S")
            put_text(f"{balance.get('closesEpiryBucketBalance')} MB will expire at "
                     f"{bucket_expiry}. Buy a package before the expiry date, these data "
                     f"will be extended to 28 days after your purchase.")
        rollover_expiry = balance.get('earliestExpiringRolloverDate')
        if rollover_expiry:
            rollover_expiry = datetime.strptime(
                str(rollover_expiry), "%Y%m%d%H%M%S").strftime("%Y-%m-%d %H:%M:%S")
            put_text(f"{balance.get('earliestExpiringRolloverAmount')} MB will expire at "
                     f"{rollover_expiry}. Rollover policy is not applicable to this.")
