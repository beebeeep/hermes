#!/usr/bin/env python

import threading
import copy
import logging
import random
import math

logging.basicConfig(level=logging.DEBUG, format="%(asctime)s [%(levelname)-4.4s] %(name)s: %(message)s")

# goods from A to Z with price from 1 to 26
PRICES = dict( (chr(x), x-64) for x in range(65, 91))
# 10% of whole cash
DAILY_LIMIT = 0.1
NUM_AGENTS=10000

class Agent(object):
    def __init__(self, name, money, goods):
        self.name = name
        self.money = money
        self.goods = copy.copy(goods)
        self.lock = threading.Lock()
        self._today_sells = 0
        self._today_buys = 0

    def _goods_cost(self):
        return sum(prices[good]*amount for good, amount in self.goods.keys())

    def gen_sell_order(self, stock):
        """ Generate sell order for random amount of random good we can sell today """
        max_cost = DAILY_LIMIT*self._goods_cost() - self._today_sells

        possible_goods = [good for good, amount in self.goods.items() if amount > 0 and PRICES[good] <= max_cost]
        if not possible_goods:
            return 0
        good = random.sample(possible_goods, 1)[0]
        max_amount = int(math.floor(max_cost/PRICES[good]))
        amount = random.sample(range(1, max_amount+1), 1)[0]

        cost = PRICES[good]*amount
        logging.debug("Agent %s puts sell order for %s of %s, total cost is %s", self.name, amount, good, cost)
        stock.sell(self, good, amount)
        self._today_sells += cost
        return cost

    def gen_buy_order(self):
        """ Generate buy order for random amount of random good we can buy today """
        available_money = DAILY_LIMIT*self.money - self._today_buys
        possible_goods = [good for good, price in PRICES.items() if PRICES[good] <= available_money]
        good = random.sample(possible_goods, 1)[0]
        if not possible_goods:
            return 0
        max_amount = int(math.floor(available_money/PRICES[good]))

        amount = random.sample(range(1, max_amount+1), 1)[0]

        cost = PRICES[good]*amount
        logging.debug("Agent %s puts buy order for %s of %s, total cost is %s", self.name, amount, good, cost)
        stock.buy(self, good, amount)
        self._today_sells += cost
        return cost


class Order(object):
    def __init__(self, agent, good, amount):
        self.agent = agent
        self.good = good
        self.amount = amount
        self.cost = PRICES[good]*amount


class Stock(object):
    def __init__(self):
        self.sells = {}
        self.buys = {}
        self.lock = threading.Lock()

    def sell(self, seller, good, amount):
        with self.lock:
            order = Order(seller, good, amount)
            if good in self.sells:
                self.sells[good].append(order)
            else:
                self.sells[good] = [order]

            self.sells.append()

    def buy(self, buyer, good, amount):
        with self.lock:
            order = Order(buyer, good, amount)
            if good in self.buys:
                self.buys[good].append(order)
            else:
                self.buys[good] = [order]

    def process_orders(self):
        for good, sell_order in self.sells.items():
            if good in self.buys:
                for buy_order in self.buys[good]:
                    if buy_order.amount == sell_order.amount:
                        try:
                            self.do_deal(seller=sell_order.agent, buyer=buy_order.agent, good=good, amount=sell_order.amount)
                        except Exception as e:
                            logging.error("Cannot process order: %s", e)
                        else:
                            self.sells[good].remove(sell_order)
                            self.buys[good].remove(buy_order)

    def do_deal(seller, buyer, good, amount):
        cost = PRICES[good]*amount
        if seller.goods[good] < amount:
            raise Exception("Seller doesn't have enough good")
        if buyer.money < cost:
            raise Exception("Buyer doesn't have enough money")

        logging.info("Agent %s buys %s of %s from %s, cost is %s", buyer.name, amount, good, seller.name, cost)
        with seller.lock:
            with buyer.lock:
                seller.goods[good] -= amount
                seller.money += cost
                buyer.goods[good] += amount
                buyer.money -= cost

if __name__ == '__main__':
    # random set of goods for all agents
    starting_goods = dict( (chr(x), random.randint(0,10)) for x in range(65, 91))
    starting_money = 100
    agents = []
    for x in xrange(NUM_AGENTS):
        agents.append(Agent(str(x), starting_money, starting_goods))


    for day in xrange(1):
        stock = Stock()
        logging.info("====== DAY %s ======", day)
        for agent in agents:
            while True:
                if agent.gen_buy_order() == 0:
                    break
            while True:
                if agent.gen_sell_order() == 0:
                    break
        stock.process_orders()


