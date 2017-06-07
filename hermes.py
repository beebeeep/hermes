#!/usr/bin/env python

import threading
import copy
import sys
import logging
import random
import math
import traceback
import argparse

logging.basicConfig(level=logging.ERROR, format="%(asctime)s [%(levelname)-4.4s] %(name)s: %(message)s")

# goods from A to Z with price from 1 to 26
PRICES = dict( (chr(x), x-64) for x in range(65, 91))
# 10% of whole cash

class Agent(object):
    def __init__(self, name, money, goods, daily_limit):
        self.name = name
        self.money = money
        self.goods = copy.copy(goods)
        self.daily_limit = daily_limit
        self.lock = threading.Lock()
        self._reserved_goods = dict( (g,0) for g in PRICES.keys())
        self._today_sells = 0
        self._today_buys = 0

    def _goods_cost(self):
        return sum(PRICES[good]*amount for good, amount in self.goods.items())

    def finish_day(self):
        """ drop all reserves and counters """
        self._today_buys = 0
        self._today_sells = 0
        self._reserved_goods = dict( (g,0) for g in PRICES.keys())

    def gen_sell_order(self, stock):
        """ Generate sell order for random amount of random good we can sell today """
        max_cost = self.daily_limit*self._goods_cost() - self._today_sells

        possible_goods = [good for good, amount in self.goods.items()
                if amount - self._reserved_goods.get(good, 0) > 0 and PRICES[good] <= max_cost]
        if not possible_goods:
            return 0
        good = random.sample(possible_goods, 1)[0]
        max_amount = min(self.goods[good] - self._reserved_goods.get(good,0), int(math.floor(max_cost/PRICES[good])))
        amount = random.sample(range(1, max_amount+1), 1)[0]
        self._reserved_goods[good] += amount

        cost = PRICES[good]*amount
        logging.debug("Agent %s puts sell order for %s of %s, total cost is %s, reserved %s out of %s",
                self.name, amount, good, cost, self._reserved_goods[good], self.goods[good])
        stock.sell(self, good, amount)
        self._today_sells += cost
        return cost

    def gen_buy_order(self, stock):
        """ Generate buy order for random amount of random good we can buy today """
        available_money = self.daily_limit*self.money - self._today_buys
        possible_goods = [good for good, price in PRICES.items() if PRICES[good] <= available_money]
        if not possible_goods:
            return 0
        good = random.sample(possible_goods, 1)[0]
        max_amount = int(math.floor(available_money/PRICES[good]))

        amount = random.sample(range(1, max_amount+1), 1)[0]

        cost = PRICES[good]*amount
        logging.debug("Agent %s puts buy order for %s of %s, total cost is %s", self.name, amount, good, cost)
        stock.buy(self, good, amount)
        self._today_buys += cost
        return cost


class Order(object):
    def __init__(self, agent, good, amount):
        self.agent = agent
        self.good = good
        self.amount = amount
        self.cost = PRICES[good]*amount
        self.filled = False


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

    def buy(self, buyer, good, amount):
        with self.lock:
            order = Order(buyer, good, amount)
            if good in self.buys:
                self.buys[good].append(order)
            else:
                self.buys[good] = [order]

    def process_orders(self):
        deals = 0
        for good, sell_orders in self.sells.items():
            random.shuffle(sell_orders)     # just in case
            for sell_order in sell_orders:
                buy_orders = self.buys.get(good, [])
                for buy_order in random.sample(buy_orders, len(buy_orders)):
                    if sell_order.filled or buy_order.filled:
                        continue
                    if buy_order.amount == sell_order.amount and buy_order.agent != sell_order.agent:
                        try:
                            self.do_deal(seller=sell_order.agent, buyer=buy_order.agent, good=good, amount=sell_order.amount)
                        except Exception as e:
                            logging.error("Cannot process order: %s, %s", e, traceback.format_exc(e))
                            sys.exit(-1)
                        else:
                            logging.info("transaction ok")
                            deals += 1
                            sell_order.filled = True
                            buy_order.filled = True
        return deals

    @staticmethod
    def do_deal(seller, buyer, good, amount):
        cost = PRICES[good]*amount
        if seller.goods[good] < amount:
            raise Exception("Seller {} doesn't have enough good {} ({} requested, {} in stock)".format(seller.name, good, amount, seller.goods[good]))
        if buyer.money < cost:
            raise Exception("Buyer {} doesn't have enough money ({} needed, {} available)".format(buyer.name, cost, buyer.money))

        logging.info("Agent %s buys %s of %s from %s, cost is %s", buyer.name, amount, good, seller.name, cost)
        with seller.lock:
            with buyer.lock:
                seller.goods[good] -= amount
                seller.money += cost
                buyer.goods[good] += amount
                buyer.money -= cost

def model(max_agents, daily_limit, days):
    # random set of goods for all agents
    starting_goods = dict( (chr(x), random.randint(0,10)) for x in range(65, 91))
    starting_money = 100
    agents = []
    logging.debug("Starting goods: %s", starting_goods)
    for x in xrange(max_agents):
        agents.append(Agent(str(x), starting_money, starting_goods, daily_limit))

    for day in xrange(days):
        stock = Stock()
        logging.info("====== DAY %s ======", day)
        for agent in agents:
            while True:
                if agent.gen_buy_order(stock) == 0:
                    break
            while True:
                if agent.gen_sell_order(stock) == 0:
                    break
        transactions = buys = stock.process_orders()

        for agent in agents:
            agent.finish_day()

        sys.stdout.write("\rDay {} finished, {} transactions.                      ".format(day, transactions))
        sys.stdout.flush()

    return agents

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='hermes')
    parser.add_argument('-n', '--max-agents', type=int, default=1000)
    parser.add_argument('-l', '--daily-limit', type=float, default=0.1)
    parser.add_argument('-d', '--days', type=int, default=1)
    args = parser.parse_args()

    agents = model(args.max_agents, args.daily_limit, args.days)
    for agent in sorted(agents, key=lambda x: x.money):
        print "Agent {}, money {}".format(agent.name, agent.money)


