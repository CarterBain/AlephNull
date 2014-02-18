from __future__ import division
import math
from collections import OrderedDict, defaultdict

import logbook
import numpy as np
import pandas as pd

import alephnull.protocol as zp
from .position import positiondict


try:
    from alephtools.connection import get_multiplier
except:
    #Replace this with source to multiplier
    get_multiplier = lambda x: 25

log = logbook.Logger('Performance')


class FuturesPerformancePeriod(object):
    def __init__(
            self,
            starting_cash,
            period_open=None,
            period_close=None,
            keep_transactions=True,
            keep_orders=False,
            serialize_positions=True):

        # * #
        self.starting_mav = starting_cash
        self.ending_mav = starting_cash
        self.cash_adjustment = 0
        self.ending_total_value = 0.0
        self.pnl = 0.0
        # ** #

        self.period_open = period_open
        self.period_close = period_close

        # sid => position object
        self.positions = positiondict()
        # rollover initializes a number of self's attributes:
        self.rollover()
        self.keep_transactions = keep_transactions
        self.keep_orders = keep_orders

        # Arrays for quick calculations of positions value
        self._position_amounts = pd.Series()
        self._position_last_sale_prices = pd.Series()

        self.calculate_performance()

        # An object to recycle via assigning new values
        # when returning portfolio information.
        # So as not to avoid creating a new object for each event
        self._portfolio_store = zp.Portfolio()
        self._positions_store = zp.Positions()
        self.serialize_positions = serialize_positions

    def rollover(self):
        # * #
        self.starting_mav = self.ending_mav
        self.cash_adjustment = 0
        self.pnl = 0.0
        # ** #

        self.processed_transactions = defaultdict(list)
        self.orders_by_modified = defaultdict(OrderedDict)
        self.orders_by_id = OrderedDict()
        self.cumulative_capital_used = 0.0
        self.max_capital_used = 0.0
        self.max_leverage = 0.0

    def ensure_position_index(self, sid):
        try:
            _ = self._position_amounts[sid]
            _ = self._position_last_sale_prices[sid]
        except (KeyError, IndexError):
            self._position_amounts = \
                self._position_amounts.append(pd.Series({sid: 0.0}))
            self._position_last_sale_prices = \
                self._position_last_sale_prices.append(pd.Series({sid: 0.0}))

    def add_dividend(self, div):
        pass

    def handle_split(self, split):
        pass

    def update_dividends(self, todays_date):
        """
        Check the payment date and ex date against today's date
        to determine if we are owed a dividend payment or if the
        payment has been disbursed.
        """
        cash_payments = 0.0
        for sid, pos in self.positions.iteritems():
            cash_payments += pos.update_dividends(todays_date)

        # credit our cash balance with the dividend payments, or
        # if we are short, debit our cash balance with the
        # payments.
        # debit our cumulative cash spent with the dividend
        # payments, or credit our cumulative cash spent if we are
        # short the stock.
        self.handle_cash_payment(cash_payments)

        # recalculate performance, including the dividend
        # payments
        self.calculate_performance()

    def handle_cash_payment(self, payment_amount):
        self.adjust_cash(payment_amount)

    def handle_commission(self, commission):
        # Deduct from our total cash pool.
        self.adjust_cash(-commission.cost)
        # Adjust the cost basis of the stock if we own it
        if commission.sid in self.positions:
            self.positions[commission.sid]. \
                adjust_commission_cost_basis(commission)

    def adjust_cash(self, amount):
        # * #
        self.cash_adjustment += amount
        # ** #
        self.cumulative_capital_used -= amount

    def calculate_performance(self):
        old_total_value = self.ending_total_value
        old_mav = self.ending_mav
        self.ending_total_value = self.calculate_positions_value()
        total_value_difference = self.ending_total_value - old_total_value
        self.ending_mav = old_mav + total_value_difference + self.cash_adjustment
        self.cash_adjustment = 0

        self.pnl = self.ending_mav - self.starting_mav

        if self.starting_mav != 0:
            self.returns = self.pnl / self.starting_mav
        else:
            self.returns = 0.0

    def record_order(self, order):
        if self.keep_orders:
            dt_orders = self.orders_by_modified[order.dt]
            if order.id in dt_orders:
                del dt_orders[order.id]
            dt_orders[order.id] = order
            # to preserve the order of the orders by modified date
            # we delete and add back. (ordered dictionary is sorted by
            # first insertion date).
            if order.id in self.orders_by_id:
                del self.orders_by_id[order.id]
            self.orders_by_id[order.id] = order

    def execute_transaction(self, txn):
        # Update Position
        # ----------------
        if 'contract' in txn.__dict__:
            sid = (txn.sid, txn.contract)
        else:
            sid = txn.sid

        position = self.positions[sid]

        position.update(txn)
        self.ensure_position_index(sid)
        self._position_amounts[sid] = position.amount

        # Max Leverage
        # ---------------
        # Calculate the maximum capital used and maximum leverage
        transaction_cost = txn.price * txn.amount
        self.cumulative_capital_used += transaction_cost

        # * #
        # now we update ending_mav and ending_total_value such that the performance tracker doesn't think we
        # profited when in fact we just entered another position.
        # how? just put a negative balance into cash_adjustment equal to the value of the position entered
        self.cash_adjustment -= txn.price * txn.amount * get_multiplier(sid)

        if math.fabs(self.cumulative_capital_used) > self.max_capital_used:
            self.max_capital_used = math.fabs(self.cumulative_capital_used)

            # We want to conveye a level, rather than a precise figure.
            # round to the nearest 5,000 to keep the number easy on the eyes
            self.max_capital_used = self.round_to_nearest(
                self.max_capital_used,
                base=5000
            )

            # we're adding a 10% cushion to the capital used.
            self.max_leverage = 1.1 * \
                                self.max_capital_used / self.starting_mav

        # add transaction to the list of processed transactions
        if self.keep_transactions:
            self.processed_transactions[txn.dt].append(txn)


    def round_to_nearest(self, x, base=5):
        return int(base * round(float(x) / base))

    def calculate_positions_value(self):
        multipliers = [get_multiplier(symbol) for symbol in self._position_amounts.keys()]
        result = 0
        for amount, price, multiplier in zip(self._position_amounts, self._position_last_sale_prices, multipliers):
            result += amount * price * multiplier
        return result

    def update_last_sale(self, event):
        if 'contract' in event:
            sid = (event.sid, event.contract)
        else:
            sid = event.sid

        is_trade = event.type == zp.DATASOURCE_TYPE.TRADE
        has_price = not np.isnan(event.price)
        # isnan check will keep the last price if its not present

        if sid in self.positions and is_trade and has_price:
            self.positions[sid].last_sale_price = event.price
            self.ensure_position_index(sid)
            self._position_last_sale_prices[sid] = event.price
            self.positions[sid].last_sale_date = event.dt

    def __core_dict(self):
        rval = {
            'ending_value': self.ending_total_value,
            # this field is renamed to capital_used for backward
            # compatibility.
            'capital_used': self.starting_mav,
            'starting_cash': self.starting_mav,
            'ending_cash': self.ending_mav,
            'portfolio_value': self.ending_mav,
            'cumulative_capital_used': self.cumulative_capital_used,
            'max_capital_used': self.max_capital_used,
            'max_leverage': self.max_leverage,
            'pnl': self.pnl,
            'returns': self.returns,
            'period_open': self.period_open,
            'period_close': self.period_close,
        }

        return rval

    def to_dict(self, dt=None):
        """
        Creates a dictionary representing the state of this performance
        period. See header comments for a detailed description.

        Kwargs:
            dt (datetime): If present, only return transactions for the dt.
        """
        rval = self.__core_dict()

        if self.serialize_positions:
            positions = self.get_positions_list()
            rval['positions'] = positions

        # we want the key to be absent, not just empty
        if self.keep_transactions:
            if dt:
                # Only include transactions for given dt
                transactions = [x.to_dict()
                                for x in self.processed_transactions[dt]]
            else:
                transactions = \
                    [y.to_dict()
                     for x in self.processed_transactions.itervalues()
                     for y in x]
            rval['transactions'] = transactions

        if self.keep_orders:
            if dt:
                # only include orders modified as of the given dt.
                orders = [x.to_dict()
                          for x in self.orders_by_modified[dt].itervalues()]
            else:
                orders = [x.to_dict() for x in self.orders_by_id.itervalues()]
            rval['orders'] = orders

        return rval

    def as_portfolio(self):
        """
        The purpose of this method is to provide a portfolio
        object to algorithms running inside the same trading
        client. The data needed is captured raw in a
        PerformancePeriod, and in this method we rename some
        fields for usability and remove extraneous fields.
        """
        # Recycles containing objects' Portfolio object
        # which is used for returning values.
        # as_portfolio is called in an inner loop,
        # so repeated object creation becomes too expensive
        portfolio = self._portfolio_store
        # maintaining the old name for the portfolio field for
        # backward compatibility
        portfolio.capital_used = self.starting_mav
        portfolio.starting_cash = self.starting_mav
        portfolio.portfolio_value = self.ending_mav
        portfolio.pnl = self.pnl
        portfolio.returns = self.returns
        portfolio.cash = self.ending_mav
        portfolio.start_date = self.period_open
        portfolio.positions = self.get_positions()
        portfolio.positions_value = self.ending_total_value
        return portfolio

    def get_positions(self):
        positions = self._positions_store

        for sid, pos in self.positions.iteritems():

            if sid not in positions:
                if type(sid) is tuple:
                    positions[sid] = zp.Position(sid[0], contract=sid[1])
                else:
                    positions[sid] = zp.Position(sid)
            position = positions[sid]
            position.amount = pos.amount
            position.cost_basis = pos.cost_basis
            position.last_sale_price = pos.last_sale_price

        return positions

    def get_positions_list(self):
        positions = []
        for sid, pos in self.positions.iteritems():
            if pos.amount != 0:
                positions.append(pos.to_dict())
        return positions