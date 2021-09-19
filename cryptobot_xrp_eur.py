'''
Simple script to call the cryptobot_base class
on the currency pair of our choice. Just create
a class using the currency pair you decide and
then call the 'auto_trade function. The only
parameter needed is the price at which the coin
was bought.
'''
from cryptobot_base_v2 import cryptobot

eth_bot = cryptobot('XXRPZEUR')
eth_bot.auto_trade(last_trade_price = 1.07598)

