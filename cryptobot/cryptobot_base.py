'''
Description
----------
This script contains the crypto coin trading bot base class.
All the needed functions for performing automated coin trading
are in here and the only thing one needs to do to adopt this
on various coin pairs is to call the class upon a proper
coin pair from Kraken. Note that you also need a verified
account on Kraken and keys for the REST API in order for the
bot to be able to access your account.

Functions
---------
(1) get_kraken_signature: Authentication and signature.
(2) kraken_request: Attaches auth headers and returns results
of a POST request.
(3) get_coin_price: get the price of the coin at current time.
(4) get_coin_balance: get the number of coins we currently possess.
(5) get_median_of_last_x_min: Get the median price of the coin for
the last x minutes (select x).
(6) place_order: place a 'market' order (either buy or sell).
(7) get_order_info: get the result of the order in order to use the
price as the last_trade_price for the next trade.
(8) get_account_balance: Check the balance of our account to make sure
we have enough available resources for the next trade.
(9) auto_trade: Executes the trading bot.

Example Usage:
--------------
from cryptobot_base_v1 import cryptobot

eth_bot = cryptobot('XXRPZEUR')
eth_bot.auto_trade(last_trade_price = 0.9542)
'''

import requests
import urllib.parse
import hashlib
import hmac
import json
import base64
from datetime import datetime, timedelta
from time import time, sleep
import numpy as np
import logging

class cryptobot():
    '''
    Crypto coin trading bot class. Contains all the needed
    functions for querying the account and for performing
    automated trades based on some specified strategy.
    '''
    def __init__(self,pair):
        '''
        init function: reads the files needed for the bot
        to work. The parameters _pair_name, _coin and
        _currency pertain to the coin-currency pair and the
        next are the api keys needed to communicate with the
        Kraken Rest API.

        :param pair: the coin pair symbol. Can be a pair of two
        cryptos or crypto to fiat currency. The available ones
        can be found in the 'pair_dictionary.json' file or we can
        use the create_pair_metadata.py file to add new ones.
        '''
        with open('../resources/pair_dictionary.json') as jsonFile:
            jsonObject = json.load(jsonFile)
            jsonFile.close()

        self._pair_name = jsonObject[pair]['pair_name']
        self._coin = jsonObject[pair]['coin']
        self._currency = jsonObject[pair]['currency']

        with open('../resources/api_keys/api_url.txt', "r") as txt_file:
            self.__api_url = txt_file.readline()
        with open('../resources/api_keys/api_key.txt', "r") as txt_file:
            self.__api_key = txt_file.readline()
        with open('../resources/api_keys/api_sec.txt', "r") as txt_file:
            self.__api_sec = txt_file.readline()

    def get_kraken_signature(self,urlpath, data, secret):
        '''
        Function (1): Authentication and signature.

        :param urlpath: read from the api_keys directory.
        :param data: standardized according to query - no need
        to set manually.
        :param secret: read from the api_keys directory.
        :return:
        '''
        postdata = urllib.parse.urlencode(data)
        encoded = (str(data['nonce']) + postdata).encode()
        message = urlpath.encode() + hashlib.sha256(encoded).digest()

        mac = hmac.new(base64.b64decode(secret), message, hashlib.sha512)
        sigdigest = base64.b64encode(mac.digest())

        return sigdigest.decode()

    # Attaches auth headers and returns results of a POST request
    def kraken_request(self, api_url, uri_path, data, api_key, api_sec):
        '''
        Function (2): Attaches auth headers and returns results
        of a POST request.

        :param api_url: read from the api_keys directory.
        :param uri_path: standard parameter according to the query - no
        need to set manually.
        :param data: also standardized according to query - no need
        to set manually.
        :param api_key: read from the api_keys directory.
        :param api_sec: read from the api_keys directory.
        :return:
        '''
        headers = {}
        headers['API-Key'] = api_key
        headers['API-Sign'] = self.get_kraken_signature(uri_path, data, api_sec)
        req = requests.post((api_url + uri_path), headers=headers, data=data)

        return req

    def get_coin_price(self):
        '''
        Function (3): get the price of the coin at current time.

        :return: the current price of the coin.
        '''
        pair = self._pair_name
        pair_url = 'https://api.kraken.com/0/public/Ticker?pair=' + pair
        resp = requests.get(pair_url)
        res = resp.json()

        last_trade_price = float(res['result'][pair]['a'][0])

        return last_trade_price

    # get coin balance
    def get_coin_balance(self):
        '''
        Function (4): get the number of coins we currently possess

        :return: number of coins in our Kraken account
        '''
        coin = self._coin
        resp = self.kraken_request(self.__api_url,
                              '/0/private/Balance',
                              {"nonce": str(int(1000*time()))},
                              self.__api_key, self.__api_sec)

        res = resp.json()
        number_of_coins = res['result'][coin]

        return number_of_coins

    def get_median_of_last_x_min(self, n_minutes = 120):
        '''
        Function (5): Get the median price of the coin for the last x minutes.

        :param n_minutes: select the number of recent minutes upon which the
        median price of the coin will be calculated.
        :return: median price of the token in these last x minutes.
        '''
        pair = self._pair_name
        pair_url = 'https://api.kraken.com/0/public/OHLC?pair=' + pair + \
                   '&interval=1'
        resp = requests.get(pair_url)
        res = resp.json()

        last_x_minutes_prices = []
        for i in range(n_minutes, len(res['result'][pair])):
            last_x_minutes_prices.append(float(res['result'][pair][i][1]))

        return np.median(last_x_minutes_prices)

    def place_order(self, volume, ordertype = 'market', type = 'buy', price = 0):
        '''
        Function (6): Place a buy or sell volume according to the last
        action. If last action was 'buy' we perform 'sell'. If last
        action was 'sell' we perform 'buy'.

        :param volume: number of coins to buy.
        :param ordertype: can be either 'market' (for spot) or 'limit'
        (for future trades at specified price). Currently only 'market'
        has been tested for the bot.
        :param type: can be either 'buy' or 'sell'.
        :return: returns the response of the server to check if the
        trade was successful.
        '''
        pair = self._pair_name
        if ordertype == 'market':
            resp = self.kraken_request(self.__api_url,
                                  '/0/private/AddOrder',
                                  {"nonce": str(int(1000*time())),
                                    "ordertype": ordertype,
                                    "type": type,
                                    "volume": volume,
                                    "pair": pair,
                                    # "price": 27500
                                   },
                                  self.__api_key, self.__api_sec)
        elif ordertype == 'limit':
            resp = self.kraken_request(self.__api_url,
                                  '/0/private/AddOrder',
                                  {"nonce": str(int(1000*time())),
                                    "ordertype": ordertype,
                                    "type": type,
                                    "volume": volume,
                                    "pair": pair,
                                    "price": price
                                   },
                                  self.__api_key, self.__api_sec)
        res = resp.json()

        return res

    def get_order_info(self, trade_ledger):
        '''
        Function (7): get the result of the order in order to use the
        price as the last_trade_price for the next trade.

        :param trade_ledger: the ledger of the trade for which we want
        to return the result. It is automatically fetched from the
        'place_order' function so no need to manually set.
        :return: the price at which the trade was performed.
        '''
        resp = self.kraken_request(self.__api_url,
                              '/0/private/QueryOrders',
                              {"nonce": str(int(1000*time())),
                               "txid": trade_ledger,
                               "trades": True
                              },
                              self.__api_key, self.__api_sec)

        res = resp.json()

        return res

    def get_account_balance(self):
        '''
        Function (8): Check the balance of our account to make sure
        we have enough available resources (in the selected currency)
        for the next trade.

        :return: balance available in the selected fiat currency.
        '''
        currency = self._currency
        # Construct the request and print the result
        resp = self.kraken_request(self.__api_url,
                              '/0/private/Balance',
                              {"nonce": str(int(1000*time()))},
                              self.__api_key, self.__api_sec)

        res = resp.json()
        res = float(res['result'][currency])

        return res

    def auto_trade(self, last_trade_action = 'buy', trade_strategy_pct = 0.02,
                   patience = 3600*6, last_trade_price = None):
        '''
        Function (9): Executes the trading bot.

        :param last_trade_action: either "sell" or "buy". If "buy" we should have
        some coins in our wallet, if "sell" we should have some money.
        :param trade_strategy_pct: the percentage threshold over which (or below
        which) a sell (or buy) order will be placed.
        :param patience: time period to wait before re-adjusting last_trade_timestamp
        (in seconds).
        :return: the function returns for each time instance t, the total money, the
        number of coins, the last trade flag, the last trade price and whether the
        price has been adjusted.

        Scenario:
        --------
        According to the current scenario, we have an given amount of money to spend
        and some coins in our possession. The last action has been 'buy' (manually)
        before starting the bot.

        Instructions:
        ------------
        There are two main checks happening every 60 sec: if the previous order was 'buy',
        we are looking to sell. This will only happen if the time goes up by more than x
        percent from previous order. If if the previous oreder was 'sell' then we seek to
        buy. This will only happen if the price drops by more than x percent of the
        previous 'sell' order. We also perform a drift check (only in the case of an
        upward trend). If we sold and wait to buy again but the price keeps increasing,
        we readjust the price after 6 hours. If we bought and the price keeps dropping we
        do nothing, we only wait for the price to re-surge (or lose all our money - there
        is no fail-safe :)).
        '''

        #  Logger initialization
        # Remove all handlers associated with the root logger object.
        for handler in logging.root.handlers[:]:
            logging.root.removeHandler(handler)

        logging.basicConfig(filename='logfile.log', level=logging.DEBUG,
                            format='%(asctime)s %(message)s')

        # Variable initializations
        last_trade_timestamp = datetime.now()

        # Run for ever (until we become rich or lose all our money)
        while last_trade_price!=None:
            # Execute every 1 minute
            sleep(60)
            # Get new price at time t
            new_trade_price = self.get_coin_price()
            current_time = datetime.now()
            time_since_last_trade = (current_time -
                                     last_trade_timestamp).total_seconds()
            print('Time since last trade: {} seconds'.format(
                time_since_last_trade))
            logging.info('Time since last trade: {} seconds'.format(
                time_since_last_trade))
            if last_trade_action == 'buy':
                if new_trade_price>=(1+trade_strategy_pct)*last_trade_price:
                    print('Price is {}. We got a new high (vs {})'.format(
                        new_trade_price,last_trade_price))
                    logging.info('Price is {}. We got a new high (vs {})'.format(
                        new_trade_price,last_trade_price))
                    # New high was found so its time to sell.
                    try:
                        volume_to_sell = float(self.get_coin_balance())

                        print('Volume to sell is: {}'.format(volume_to_sell))
                        logging.info('Volume to sell is: {}'.format(volume_to_sell))

                        res = self.place_order(volume_to_sell, ordertype='market',
                                               type='sell')

                        # Get order information
                        sleep(10)
                        order_ledger_sell = res['result']['txid'][0]
                        print('order_ledger_sell: {}'.format(order_ledger_sell))
                        res_order_sell = self.get_order_info(order_ledger_sell)
                        last_trade_action = 'sell'
                        last_trade_price = float(res_order_sell['result']\
                                                 [order_ledger_sell]['price'])
                        last_trade_timestamp = current_time
                        logging.info('Last trade action is {}'.format(last_trade_action))
                        logging.info('Last trade price is {}'.format(last_trade_price))
                        logging.info('Last trade timestamp is {}'.format(last_trade_timestamp))
                    except Exception as e:
                        print(e)
                        pass

                else:
                    print('Datetime is {}. Last trade action was {} with price {}.'.format(
                                                    datetime.now(),
                                                    last_trade_action,
                                                    last_trade_price))
                    logging.info('Last trade action was {} with price {}.'.format(
                                                    last_trade_action,
                                                    last_trade_price))
                    print('Price now is {}. Still not more than {}% from previous (target is {})'.format(
                        new_trade_price,
                        100*trade_strategy_pct,
                        (1+trade_strategy_pct)*\
                        last_trade_price))
                    logging.info('Price now is {}. Still not more than {}% from previous (target is {})'.format(
                        new_trade_price,
                        100*trade_strategy_pct,
                        (1+trade_strategy_pct)*\
                        last_trade_price))
                    pass
            elif last_trade_action == 'sell':
                '''If more than x minutes have passed without a 'buy' order adjust 
                the price to be the median of these last x minutes'''
                if time_since_last_trade >= patience:
                    print('##############')
                    print('Reached maximum waiting time.Resetting timestamp and last' +
                          ' trading price')
                    print('##############')
                    logging.info('Reached maximum waiting time.Resetting timestamp and last' +
                          ' trading price')

                    try:
                        # Get amount of euros available
                        money_balance = self.get_account_balance()
                        # Turn amount of euros into coins at current price
                        # (spend max 50 euros)
                        coins_to_buy = min(money_balance,50)/new_trade_price
                        print('Coins to buy" {}'.format(coins_to_buy))
                        logging.info('Coins to buy" {}'.format(coins_to_buy))
                        res = self.place_order(coins_to_buy, ordertype='market',
                                               type='buy')

                        # Get order information
                        sleep(10)
                        order_ledger_buy = res['result']['txid'][0]
                        res_order_buy = self.get_order_info(order_ledger_buy)
                        print('order_ledger_buy: {}'.format(order_ledger_sell))
                        last_trade_action = 'buy'
                        last_trade_price = float(res_order_buy['result']\
                                                     [order_ledger_buy]['price'])
                        last_trade_timestamp = current_time
                        logging.info('Last trade action is {}'.format(last_trade_action))
                        logging.info('Last trade price is {}'.format(last_trade_price))
                        logging.info('Last trade timestamp is {}'.format(last_trade_timestamp))

                    except Exception as e:
                        print(e)
                        pass

                elif new_trade_price<=(1-trade_strategy_pct)*last_trade_price:
                    print('Price is {}. We got a new low (vs {})'.format(
                        new_trade_price,last_trade_price))
                    logging.info('Price is {}. We got a new low (vs {})'.format(
                        new_trade_price,last_trade_price))
                    # New low was found so its time to buy.
                    try:
                        # Get amount of euros available
                        money_balance = self.get_account_balance()
                        # Turn amount of euros into coins at current price
                        # (spend max 50 euros)
                        coins_to_buy = min(money_balance,50)/new_trade_price
                        print('Coins to buy" {}'.format(coins_to_buy))

                        res = self.place_order(coins_to_buy, ordertype='market',
                                               type='buy')

                        # Get order information
                        sleep(10)
                        order_ledger_buy = res['result']['txid'][0]
                        res_order_buy = self.get_order_info(order_ledger_buy)
                        print('order_ledger_buy: {}'.format(order_ledger_sell))
                        last_trade_action = 'buy'
                        last_trade_price = float(res_order_buy['result']\
                                                     [order_ledger_buy]['price'])
                        last_trade_timestamp = current_time
                        logging.info('Last trade action is {}'.format(last_trade_action))
                        logging.info('Last trade price is {}'.format(last_trade_price))
                        logging.info('Last trade timestamp is {}'.format(last_trade_timestamp))

                    except Exception as e:
                        print(e)
                        pass

                else:
                    print('Datetime is {}. Last trade action was {} with price {}.'.format(
                        datetime.now(),
                        last_trade_action,
                        last_trade_price))
                    logging.info('Last trade action was {} with price {}.'.format(
                        last_trade_action,
                        last_trade_price))
                    print('Price now is {}. Still not less than {}% from previous (target is {})'.format(
                        new_trade_price,
                        100*trade_strategy_pct,
                        (1-trade_strategy_pct)*\
                        last_trade_price))
                    logging.info('Price now is {}. Still not less than {}% from previous (target is {})'.format(
                        new_trade_price,
                        100*trade_strategy_pct,
                        (1-trade_strategy_pct)*\
                        last_trade_price))
                    pass
