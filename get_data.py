import json
import time
from datetime import datetime
import pytz
import pywebio.output
from requests import Session
from calendar import _monthlen
import pandas as pd
import numpy as np
import os

chrome107 = {
    'Accept': 'application/json, text/plain, */*', 'Accept-Encoding': 'gzip, deflate, br',
    'Accept-Language': 'en-US,en;q=0.9', 'Connection': 'keep-alive', 'Content-Length': '53',
    'Content-Type': 'application/json;charset=UTF-8', 'DNT': '1', 'Host': 'myaccount.warehousemobile.co.nz',
    'Origin': 'https://myaccount.warehousemobile.co.nz', 'Referer': 'https://myaccount.warehousemobile.co.nz/app/',
    'Sec-Fetch-Dest': 'empty', 'Sec-Fetch-Mode': 'cors', 'Sec-Fetch-Site': 'same-origin',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 '
                  'Safari/537.36',
    'sec-ch-ua': '"Google Chrome";v="107", "Chromium";v="107", "Not=A?Brand";v="24"'
}
session = Session()
session.trust_env = False
page_size = 20


def parse_response(response):
    if response.status_code != 200:
        raise Exception('Network error. Cannot connect to warehouse mobile website. '
                        f'HTTPS status code {response.status_code}. URL: {response.url}')
    response_text = json.loads(response.text)
    if response_text.get('errorcode'):
        raise Exception(f"Response error. Message: {response_text.get('errormessage')}")
    return response_text


@np.vectorize
def previous_month(year, month):
    if month == 1:
        return year - 1, 12
    else:
        return year, month - 1


@np.vectorize
def compare_month(year1, month1, year2, month2):
    if year1 < year2:
        return '<'
    elif year1 > year2:
        return '>'
    else:
        if month1 < month2:
            return '<'
        elif month1 > month2:
            return '>'
        else:
            return '='


def get_edr(year, month, page, login_token, username, day=None):
    if day is None:
        day = _monthlen(year, month)
    edr_payload = {
        # It is a mistake that, if one send a text message at 00:00:00, it will not be retrieved. However, this is the
        # behaviour of warehouse mobile website. I keep the same behavior to prevent being detected and considered as
        # abnormal request by warehouse mobile website.
        "token": login_token, "from": f"{year}/{month}/1 00:00:01", "to": f"{year}/{month}/{day} 23:59:59",
        "msisdn": username, "utypes": ["All"], "curpage": page, "pagesize": page_size
    }
    edr = session.post(
        url='https://myaccount.warehousemobile.co.nz/scp/me/edr',
        data=json.dumps(edr_payload),
        headers=chrome107
    )
    edr_response = parse_response(edr)
    n_ = edr_response.get('edramount')
    records_ = edr_response.get('edrs')
    return n_, pd.DataFrame(records_)


def get_data(username, password):
    login = session.post(
        url='https://myaccount.warehousemobile.co.nz/scp/login',
        data=json.dumps({'msisdn': username, 'password': password}),
        headers=chrome107
    )
    login_token = parse_response(login).get('token')
    pywebio.output.put_text('Logging in ...')
    time.sleep(np.random.uniform(low=0.7, high=1.3))

    cached_records_path = f'raw/{username}.pkl'
    if os.path.exists(cached_records_path):
        cached_records = pd.read_pickle(cached_records_path)
        last_sync = cached_records['date_and_time'].max()
        last_sync = (last_sync.year, last_sync.month)
    else:
        os.makedirs('raw/', exist_ok=True)
        cached_records = None
        last_sync = None

    records = []
    today = datetime.now(tz=pytz.timezone('Pacific/Auckland'))
    year_, month_ = today.year, today.month
    n, record = get_edr(year_, month_, 0, login_token, username, today.day)
    time.sleep(np.random.uniform(low=0.7, high=1.3))
    n_pages = np.ceil(n / page_size).astype(int)
    pywebio.output.put_text(f'Retrieved {year_}-{month_}, page {1} of {n_pages} ...')
    if n == 0:
        raise Exception('No data in this account.')
    record['date_and_time'] = pd.to_datetime(record['date_and_time'], unit='ms')
    records.append(record)
    for p in range(1, n_pages):
        _, record = get_edr(year_, month_, p, login_token, username, today.day)
        time.sleep(np.random.uniform(low=0.7, high=1.3))
        pywebio.output.put_text(f'Retrieved {year_}-{month_}, page {p + 1} of {n_pages} ...')
        record['date_and_time'] = pd.to_datetime(record['date_and_time'], unit='ms')
        records.append(record)
    while 1:
        year_, month_ = previous_month(year_, month_)
        if last_sync and compare_month(year_, month_, *last_sync) == '<':
            break
        n, record = get_edr(year_, month_, 0, login_token, username)
        time.sleep(np.random.uniform(low=0.7, high=1.3))
        n_pages = np.ceil(n / page_size).astype(int)
        pywebio.output.put_text(f'Retrieved {year_}-{month_}, page {1} of {n_pages} ...')
        if n == 0:
            break
        record['date_and_time'] = pd.to_datetime(record['date_and_time'], unit='ms')
        records.append(record)
        for p in range(1, n_pages):
            _, record = get_edr(year_, month_, p, login_token, username)
            time.sleep(np.random.uniform(low=0.7, high=1.3))
            pywebio.output.put_text(f'Retrieved {year_}-{month_}, page {p + 1} of {n_pages} ...')
            record['date_and_time'] = pd.to_datetime(record['date_and_time'], unit='ms')
            records.append(record)
    records = pd.concat(records, axis=0, ignore_index=True)
    if last_sync:
        cached_dt = cached_records['date_and_time'].dt
        records = pd.concat([
            records,
            cached_records.loc[np.bitwise_or(cached_dt.year != last_sync[0], cached_dt.month != last_sync[1]), :]
        ], axis=0, ignore_index=True)
    records.to_pickle(cached_records_path)
