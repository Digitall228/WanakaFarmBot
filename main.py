import datetime
import time

import requests
import json
import traceback

wallet_address = 'YOUR_EMAIL'
sign = 'YOUR_PASSWORD'

def log_add(text):
    print(f'{datetime.datetime.utcnow()}: {text}')

def auth(session: requests.Session):
    data = {"c":{},"d":{"wallet_address":wallet_address,"sign":sign}}
    js = send_request(session.post, 3, 'https://game-api.wanakafarm.com/api/v1/user/connect_wallet', data)
    if js is None:
        log_add("Couldn't auth")
        return
    if 'access_token' in js['d']:
        session.headers.update({'Authorization' : js['d']['access_token']})
        log_add('Successfully authed')
    else:
        log_add('Something gone wrong while authing')

def check_watering_time(item):
    if item['attributes'][9]['value'] is None:
        return True
    if int(item['attributes'][7]['value']) < int(item['attributes'][8]['value']):
        last_watering_time = datetime.datetime.strptime(item['attributes'][9]['value'], '%Y-%m-%dT%H:%M:%S.%f+00:00')
        watering_times = item['attributes'][6]['value'].split(',')
        for watering_time_str in watering_times:
            watering_time = datetime.datetime.strptime(watering_time_str, '%Y-%m-%dT%H:%M:%S+00:00')
            if watering_time < datetime.datetime.utcnow():
                if last_watering_time < watering_time:
                    return True
            else:
                return False
    else:
        return False

def water_item(session: requests.Session, item):
    data = {"c":{},"d":{"itemId":item["id"]}}
    js = send_request(session.post, 3, 'https://game-api.wanakafarm.com/api/v1/action/watering', data)

    log_add(f'[{item["id"]}] watered {item["name"]} {js["d"]["wateringInfo"]["wateringTimes"]}/'
            f'{js["d"]["wateringInfo"]["wateringMaximumTimes"]} times, code={js["c"]["code"]}')

def check_harvesting_time(item):
    harvesting_time = datetime.datetime.strptime(item['attributes'][10]['value'], '%Y-%m-%dT%H:%M:%S.%f+00:00')
    if datetime.datetime.utcnow() > harvesting_time:
        return True
    else:
        return False

def harvest_item(session: requests.Session, item, land_id):
    data = {"c":{},"d":{"itemId":item['id'],"landId":land_id,"posX":item['attributes'][14]['value'],"posY":item['attributes'][15]['value']}}
    js = send_request(session.post, 3, 'https://game-api.wanakafarm.com/api/v1/inventory/harvested_item', data)

    harvested_item = js['d']['itemInfo']
    log_add(f'[{harvested_item["id"]}] {harvested_item["name"]} ({harvested_item["attributes"][6]["value"]}) harvested '
            f'with weight={harvested_item["attributes"][4]["value"]}, quality={harvested_item["attributes"][5]["value"]}')
    return True

def plow_land(session: requests.Session, item, land_id):
    data = {"c":{},"d":{"landId":land_id,"posX":item['attributes'][14]['value'],"posY":item['attributes'][15]['value']}}
    js = send_request(session.post, 3, 'https://game-api.wanakafarm.com/api/v1/action/plowing', data)

    if js['c']['code'] == 'S000':
        log_add(f'[{item["id"]}] Successfully plowed')
    else:
        log_add(f'[{item["id"]}] Unexpected code while plowing, js={js}')

def check_item_availability(session: requests.Session, item):
    data = {"c":{},"d":{"type":item["attributes"][0]['value']}}
    js = send_request(session.post, 3, 'https://game-api.wanakafarm.com/api/v1/inventory/filter_item', data)

    for inventory_item in js['d']['datas']:
        if inventory_item['item_code'] == item['item_code'] and inventory_item['attributes'][2]['value'] == 'Seed':
            return True
    return False

def get_items_from_inventory(session: requests.Session, item, type='Harvested', count=2):
    items = []
    data = {"c": {}, "d": {"type": item["attributes"][0]['value']}}
    js = send_request(session.post, 3, 'https://game-api.wanakafarm.com/api/v1/inventory/filter_item', data)

    for inventory_item in js['d']['datas']:
        if len(items) >= count:
            break
        if inventory_item['item_code'] == item['item_code'] and inventory_item['attributes'][2]['value'] == type:
            items.append(inventory_item)
    return items

def breed_item(session: requests.Session, item):
    items = get_items_from_inventory(session, item, 'Harvested', 2)
    if len(items) < 2:
        return False
    data = {"c":{},"d":{"first_item_id":items[0]['id'],"second_item_id":items[1]['id']}}
    js = send_request(session.post, 3, 'https://game-api.wanakafarm.com/api/v1/breed/processing', data)

    log_add(f'[{item["item_code"]}] breaded {len(js["d"]["list_breeds"])} {item["attributes"][1]["value"]}')
    return True

def grow_item(session: requests.Session, item, land_id):
    new_item = get_items_from_inventory(session, item, 'Seed', 1)
    data = {"c":{},"d":{"itemId":new_item[0]['id'],"landId":land_id,"posX":item['attributes'][14]['value'],"posY":item['attributes'][15]['value']}}
    js = send_request(session.post, 3, 'https://game-api.wanakafarm.com/api/v1/inventory/growing_item',  data)

    if js['c']['code'] == 'S000':
        log_add(f'[{item["attributes"][1]["value"]}] Successfully growing')
        return js['d']['item_info']
    else:
        log_add(f'[{item["attributes"][1]["value"]}] Unexpected code while growing, js={js}')

def check_nft_flag(item):
    if item['attributes'][3]['value']:
        return True
    else:
        return False

def check_land(session: requests.Session):
    pass

def check_items(session: requests.Session):
    global wai_balance, wana_balance
    data = {"c":{},"d":{}}
    js = send_request(session.post, 3, 'https://game-api.wanakafarm.com/api/v1/user/user_info', data)
    if js["c"]["code"] == "W001":
        time.sleep(600)
        return

    wai_balance = js['d']['user_info']['wai_balance']
    wana_balance = js['d']['user_info']['wana_balance']

    harvested_items = []

    for land in js['d']['list_lands']:
        for item in land['list_items']:
            if check_watering_time(item):
                log_add(f'[{item["id"]}] Watering {item["name"]}')
                water_item(session, item)
            if check_harvesting_time(item):
                log_add(f'[{item["id"]}] Harvesting {item["name"]}')
                if harvest_item(session, item, land['id']):
                    harvested_items.append([item, land['id']])
            if check_nft_flag(item):
                log_add(f'[{item["id"]}] Found {item["name"]} NFT!')

    for harvested_item in harvested_items:
        try:
            if harvested_item[0]['item_code'] == 'G01_0001':
                plow_land(session, harvested_item[0], harvested_item[1])
            if not check_item_availability(session, harvested_item[0]):
                if breed_item(session, harvested_item[0]):
                    new_item = grow_item(session, harvested_item[0], harvested_item[1])
                    water_item(session, new_item)
            else:
                new_item = grow_item(session, harvested_item[0], harvested_item[1])
                water_item(session, new_item)
        except:
            log_add(f'ERROR (continue): {traceback.format_exc()}')

def send_request(action, max_times, *args):
    times = 0
    try:
        if len(args) <= 1:
            r = action(args[0])
        elif len(args) == 2:
            r = action(args[0], json=args[1])
        js = json.loads(r.text)
        return js
    except Exception as ex:
        times += 1
        if times >= max_times:
            return None
        time.sleep(3)

wana_balance = 0
wai_balance = 0
session = requests.Session()
session.headers.update({'Host': 'game-api.wanakafarm.com',
                        'User-Agent': 'UnityPlayer/2020.3.12f1 (UnityWebRequest/1.0, libcurl/7.75.0-DEV)',
                        'Accept': '*/*',
                        'Content-Type': 'application/json',
                        'X-Unity-Version': '2020.3.12f1',
                        'Accept-Encoding': 'gzip, deflate'})
auth(session)
while True:
    try:
        check_items(session)
        time.sleep(240)
    except:
        log_add(f'Error: {traceback.format_exc()}')
        auth(session)

