# Corrupt#5352

import requests
from bs4 import BeautifulSoup
import json
import time
import re
import sys
import os
import random
import urllib3
import threading


# Disable the unsecure request warning
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


# VARIABLES ( IMPORTANT TO REVIEW THESE BEFORE RUNNING )
delist_mode = True
new_listing_mode = False
api_mode = False
html_mode = True
proxy_mode = False
time_between_requests = 5
debug_mode = True

if delist_mode == False and new_listing_mode == False:
    print("Please choose a mode. delist_mode or new_listing_mode")
    sys.exit()


# CONSTANTS
URL = "https://www.binance.com/bapi/composite/v1/public/cms/article/list/query?type=1&pageSize=20&pageNo=1" if api_mode else (
    "https://www.binance.com/en/support/announcement/new-cryptocurrency-listing?c=48&navId=48" if new_listing_mode else "https://www.binance.com/en/support/announcement/delisting?c=161&navId=161")
OUTPUT_FILE_NAME = "Binance Adds.txt" if new_listing_mode else "Binance Removes.txt"


PROXIES = list(dict.fromkeys(
    [x for x in open("proxies.txt", "r").read().split("\n") if x != '']))

if len(PROXIES) == 0:
    print('No proxies in proxies.txt')
    sys.exit()

print(f"Loaded {len(PROXIES)} proxies and removed duplicates")
print(
    f"Starting Binance List/Delist Tracker\nRequest mode: { 'API' if api_mode else 'HTML' }\nUse Proxies: {proxy_mode}\n")


def select_proxy():
    return random.choice(PROXIES) if PROXIES else None


def format_proxy(px):
    if '@' not in px:
        sp = px.split(':')
        if len(sp) == 4:
            px = f'{sp[2]}:{sp[3]}@{sp[0]}:{sp[1]}'
        elif len(sp) == 2:
            px = f'{sp[0]}:{sp[1]}'
    return {"http": f"http://{px}/", 'https': f'http://{px}/'}


def timeout_proxy(proxy):
    if proxy in PROXIES:
        PROXIES.remove(proxy)

    def add_to_proxies():
        if proxy not in PROXIES:
            PROXIES.append(proxy)

    threading.Timer(180, add_to_proxies).start()


def get_articles(response):
    try:
        if html_mode:
            html_text = response.text
            soup = BeautifulSoup(html_text, 'html.parser')
            data_in_html = soup.find(id="__APP_DATA")
            if data_in_html == None:
                raise Exception("__APP_DATA is None")
            json_data = json.loads(data_in_html.text)
            articles = next(
                obj['articles'] for obj in json_data["routeProps"]["ce50"]["catalogs"] if obj['catalogName'] == ("New Cryptocurrency Listing" if new_listing_mode else "Delisting")
            )
        elif api_mode:
            json_data = response.json()
            articles = next(
                obj['articles'] for obj in json_data["data"]['catalogs'] if obj['catalogName'] == ("New Cryptocurrency Listing" if new_listing_mode else "Delisting")
            )
        return articles
    except Exception as e:
        print("Error: " + str(e))
        return None


def get_coin_names(article_titles):
    coin_names = []
    for title in article_titles:
        if delist_mode and re.match(r'^Binance (?:Margin )?Will Delist', title) or new_listing_mode and re.match(r'^Binance Adds', title):
            matches = re.findall(r'[A-Z0-9]{2,}(?=\b)(?<!\d)', title)
            for match in matches:
                coin_names.append(match)

    coin_names = sorted(list(set(coin_names)))
    return coin_names or None


def main():
    while True:
        if proxy_mode:
            while True:
                proxy = select_proxy()
                if proxy == None:
                    print("No proxies work, os exiting...")
                    os._exit(1)

                formatted_proxy = format_proxy(proxy)
                try:
                    response = requests.get(
                        URL, proxies=formatted_proxy, verify=False, timeout=3)
                    response.raise_for_status()
                    break
                except Exception as err:
                    if debug_mode:
                        print(f'Proxy error ({proxy}): {err}\n')
                    timeout_proxy(proxy)
                    pass
        else:
            while True:
                try:
                    response = requests.get(URL)
                    response.raise_for_status()
                    break
                except requests.exceptions.HTTPError as err:
                    if debug_mode:
                        print(
                            f'Request error ({proxy}): {err}\nWaiting 3 mins')
                    time.sleep(60*3)
                    pass

        articles = get_articles(response)

        if articles is None:
            print("Could not fetch delist articles")
            return

        article_titles = [obj["title"] for obj in articles]

        coin_names = get_coin_names(article_titles)

        if coin_names is None:
            print("Could not parse any coin names")
            return

        with open(OUTPUT_FILE_NAME, "a+", encoding="utf-8") as output_file:
            output_file.seek(0)
            existing_output_text = output_file.read()

            filtered_list = [
                item for item in coin_names if item not in existing_output_text]

            if len(filtered_list) != 0:
                output_text = '\n'.join(filtered_list)
                output_file.write(output_text + '\n')

        time.sleep(time_between_requests)


if __name__ == "__main__":
    main()
