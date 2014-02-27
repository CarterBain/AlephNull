#
# Copyright 2013 Quantopian, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""

Performance Period
==================

Performance Periods are updated with every trade. When calling
code needs a portfolio object that fulfills the algorithm
protocol, use the PerformancePeriod.as_portfolio method. See that
method for comments on the specific fields provided (and
omitted).

    +---------------+------------------------------------------------------+
    | key           | value                                                |
    +===============+======================================================+
    | ending_value  | the total market value of the positions held at the  |
    |               | end of the period                                    |
    +---------------+------------------------------------------------------+
    | cash_flow     | the cash flow in the period (negative means spent)   |
    |               | from buying and selling securities in the period.    |
    |               | Includes dividend payments in the period as well.    |
    +---------------+------------------------------------------------------+
    | starting_value| the total market value of the positions held at the  |
    |               | start of the period                                  |
    +---------------+------------------------------------------------------+
    | starting_cash | cash on hand at the beginning of the period          |
    +---------------+------------------------------------------------------+
    | ending_cash   | cash on hand at the end of the period                |
    +---------------+------------------------------------------------------+
    | positions     | a list of dicts representing positions, see          |
    |               | :py:meth:`Position.to_dict()`                        |
    |               | for details on the contents of the dict              |
    +---------------+------------------------------------------------------+
    | pnl           | Dollar value profit and loss, for both realized and  |
    |               | unrealized gains.                                    |
    +---------------+------------------------------------------------------+
    | returns       | percentage returns for the entire portfolio over the |
    |               | period                                               |
    +---------------+------------------------------------------------------+
    | cumulative\   | The net capital used (positive is spent) during      |
    | _capital_used | the period                                           |
    +---------------+------------------------------------------------------+
    | max_capital\  | The maximum amount of capital deployed during the    |
    | _used         | period.                                              |
    +---------------+------------------------------------------------------+
    | max_leverage  | The maximum leverage used during the period.         |
    +---------------+------------------------------------------------------+
    | period_close  | The last close of the market in period. datetime in  |
    |               | pytz.utc timezone.                                   |
    +---------------+------------------------------------------------------+
    | period_open   | The first open of the market in period. datetime in  |
    |               | pytz.utc timezone.                                   |
    +---------------+------------------------------------------------------+
    | transactions  | all the transactions that were acrued during this    |
    |               | period. Unset/missing for cumulative periods.        |
    +---------------+------------------------------------------------------+


"""

from __future__ import division
import math
from collections import OrderedDict, defaultdict

import logbook
import numpy as np
import pandas as pd

import alephnull.protocol as zp
from . position import positiondict


log = logbook.Logger('Performance')


class PerformancePeriod(object):

    def __init__(
            self,
            starting_cash,
            period_open=None,
            period_close=None,
            keep_transactions=True,
            keep_orders=False,
            serialize_positions=True):

        self.period_open = period_open
        self.period_close = period_close

        self.ending_value = 0.0
        self.period_cash_flow = 0.0
        self.pnl = 0.0
        # sid => position object
        self.positions = positiondict()
        self.ending_cash = starting_cash
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
        self.starting_value = self.ending_value
        self.starting_cash = self.ending_cash
        self.period_cash_flow = 0.0
        self.pnl = 0.0
        self.processed_transactions = defaultdict(list)
        self.orders_by_modified = defaultdict(OrderedDict)
        self.orders_by_id = OrderedDict()
        self.cumulative_capital_used = 0.0
        self.max_capital_used = 0.0
        self.max_leverage = 0.0

    def ensure_position_index(self, sid):
        try:
            self._position_amounts[sid]
            self._position_last_sale_prices[sid]
        except (KeyError, IndexError):
            self._position_amounts = \
                self._position_amounts.append(pd.Series({sid: 0.0}))
            self._position_last_sale_prices = \
                self._position_last_sale_prices.append(pd.Series({sid: 0.0}))

    def add_dividend(self, div):
        # The dividend is received on midnight of the dividend
        # declared date. We calculate the dividends based on the amount of
        # stock owned on midnight of the ex dividend date. However, the cash
        # is not dispersed until the payment date, which is
        # included in the event.
        self.positions[div.sid].add_dividend(div)

    def handle_split(self, split):
        if split.sid in self.positions:
            # Make the position object handle the split. It returns the
            # leftover cash from a fractional share, if there is any.
            leftover_cash = self.positions[split.sid].handle_split(split)

            if leftover_cash > 0:
                self.handle_cash_payment(leftover_cash)

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
            self.positions[commission.sid].\
                adjust_commission_cost_basis(commission)

    def adjust_cash(self, amount):
        self.period_cash_flow += amount
        self.cumulative_capital_used -= amount

    def calculate_performance(self):
        self.ending_value = self.calculate_positions_value()

        total_at_start = self.starting_cash + self.starting_value
        self.ending_cash = self.starting_cash + self.period_cash_flow
        total_at_end = self.ending_cash + self.ending_value

        self.pnl = total_at_end - total_at_start
        if total_at_start != 0:
            self.returns = self.pnl / total_at_start
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

    def update_position(self, sid, contract=None, amount=None, last_sale_price=None,
                        last_sale_date=None, cost_basis=None):
        pos = self.positions[sid]
        self.ensure_position_index(sid)

        if contract is not None:
            pos.contract = contract
        if amount is not None:
            pos.amount = amount
            self._position_amounts[sid] = amount
        if last_sale_price is not None:
            pos.last_sale_price = last_sale_price
            self._position_last_sale_prices[sid] = last_sale_price
        if last_sale_date is not None:
            pos.last_sale_date = last_sale_date
        if cost_basis is not None:
            pos.cost_basis = cost_basis

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

        self.period_cash_flow -= txn.price * txn.amount

        # Max Leverage
        # ---------------
        # Calculate the maximum capital used and maximum leverage
        transaction_cost = txn.price * txn.amount
        self.cumulative_capital_used += transaction_cost

        if math.fabs(self.cumulative_capital_used) > self.max_capital_used:
            self.max_capital_used = math.fabs(self.cumulative_capital_used)

            # We want to convey a level, rather than a precise figure.
            # round to the nearest 5,000 to keep the number easy on the eyes
            self.max_capital_used = self.round_to_nearest(
                self.max_capital_used,
                base=5000
            )

            # we're adding a 10% cushion to the capital used.
            self.max_leverage = 1.1 * \
                self.max_capital_used / self.starting_cash

        # add transaction to the list of processed transactions
        if self.keep_transactions:
            self.processed_transactions[txn.dt].append(txn)

    def round_to_nearest(self, x, base=5):
        return int(base * round(float(x) / base))

    def calculate_positions_value(self):
        return np.dot(self._position_amounts, self._position_last_sale_prices)

    def update_last_sale(self, event):
        if 'contract' in event:
            sid = (event.sid, event.contract)
        else:
            sid = event.sid

        is_trade = event.type == zp.DATASOURCE_TYPE.TRADE
        has_price = not np.isnan(event.price)
        # isnan check will keep the last price if its not present

        is_contract_tracked = sid in self.positions

        if is_contract_tracked and is_trade and has_price:
            self.positions[sid].last_sale_price = event.price
            self.ensure_position_index(sid)
            self._position_last_sale_prices[sid] = event.price
            self.positions[sid].last_sale_date = event.dt

    def __core_dict(self):
        rval = {
            'ending_value': self.ending_value,
            # this field is renamed to capital_used for backward
            # compatibility.
            'capital_used': self.period_cash_flow,
            'starting_value': self.starting_value,
            'starting_cash': self.starting_cash,
            'ending_cash': self.ending_cash,
            'portfolio_value': self.ending_cash + self.ending_value,
            'cumulative_capital_used': self.cumulative_capital_used,
            'max_capital_used': self.max_capital_used,
            'max_leverage': self.max_leverage,
            'pnl': self.pnl,
            'returns': self.returns,
            'period_open': self.period_open,
            'period_close': self.period_close
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
        portfolio.capital_used = self.period_cash_flow
        portfolio.starting_cash = self.starting_cash
        portfolio.portfolio_value = self.ending_cash + self.ending_value
        portfolio.pnl = self.pnl
        portfolio.returns = self.returns
        portfolio.cash = self.ending_cash
        portfolio.start_date = self.period_open
        portfolio.positions = self.get_positions()
        portfolio.positions_value = self.ending_value
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


"""class FuturesPerformancePeriod(object):
    "We need to replicate:
    * calculate_performance
    * execute_transaction
    * record_order
    * update_last_sale
    "
    def __init__(
            self,
            starting_cash,
            period_open=None,
            period_close=None,
            keep_transactions=True,
            keep_orders=False,
            serialize_positions=True):
        self.backing_period = PerformancePeriod(starting_cash, period_open, period_close, keep_transactions,
                                                keep_orders, serialize_positions)

        self.margin_account_value = starting_cash
        self.owned_positions = {}  # will have a format like {("GS", "N10"): {amount: 100, last_price: 0.25}
        self.margin_history = {}  # format like {Timestamp(...): 400.30}

        self.contract_multiplier = 100
        self.maintenance_margin_rate = 0.20
        self.initial_margin_rate = 0.30

        self.contract_details = {}  # set externally if at all
        self.margin_data = {}  # set externally if at all
        self.margin_call = self.scale_back_positions  # can be set to another function externally
        self.gameover = False

        self.algo = None

    def get_initial_margin(self, sid, timestamp, contract_value):
        return self.get_margin("initial", sid, timestamp, contract_value)

    def get_maintenance_margin(self, sid, timestamp, contract_value):
        return self.get_margin("maintenance", sid, timestamp, contract_value)

    def get_margin(self, margin_type, sid, timestamp, contract_value):
        # provides initial margin for a sid, basing it on the latest_price if there is no data available.
        multiplier = {"initial": 0.25, "maintenance": 0.2}[margin_type]

        # the structure of self.margin_data is like so:
        # self.margin_data["initial"]["GS"]["N14"][Timestamp] == 300.03
        # where the final dict in the nesting is a TimeSeries
        if (margin_type in self.margin_data and
                sid[0] in self.margin_data[margin_type] and
                sid[1] in self.margin_data[margin_type][sid[0]]):
            series = self.margin_data[margin_type][sid[0]][sid[1]]
            previous_data = series[:timestamp]
            if previous_data:
                return previous_data[-1]
        return contract_value * multiplier


    def unit_multiplier(self, currency):
        "Returns a number C such that given_price / C = value of item in dollars.
        Another way of figuring is that 1 USD = C other currencies
        Exchange rates are estimated based on the time this is programmed and are thus in no way accurate.
        We're not really dealing with currencies so I don't much mind.
        The ones that matter are mainly dollars and cents (C's of 1 and 100 of course)

        Defaults to 1 if we don't know what to do."

        return {'$': 1,
                '$/GAL': 1,
                '$/GRAM': 1,
                '$/MBTU': 1,
                '$/MWH': 1,
                '$/TON': 1,
                'AU$': 1.12,
                'CD$': 1.07,
                'CHF': 0.91,
                'CZK': 20.18,
                'HUF': 220.32,
                'NOK': 6.17,
                'NZD': 1.21,
                'SEK': 6.51,
                'TRY': 2.17,
                u'\xa3': 0.61,  # Pound
                u'\xa5': 104.49,  # Yen
                u'\xf3': 100,  # Cents
                u'\u20ac': 0.73, # Euro
                }.get(currency, 1)

    def dollars_from_currency(self, price, unit):
        return price / self.unit_multiplier(unit)

    def get_multiplier(self, sid):
        # multiplier = contract_size * quoted_unit / $
        # i.e. what do I multiply price by to get the value of a single contract

        fallback = 1000

        contract_size = self.contract_details.get(sid[0], {}).get('contract_size', str(fallback) + " UNITS")
        quoted_unit = self.contract_details.get(sid[0], {}).get('quoted_unit', "$")

        def matches(pattern, text):
            result = re.match(pattern, text)
            if result is not None:
                return result.group() == text
            else:
                return False

        # case 1: some number with units like "1,000 TONS" or "42,000 GAL" and a quoted unit that is simply "$"
        # what "$" means is "$/UNIT", whether UNIT be GAL or LITERS or whatever.

        straight_currencies = {'$', 'AU$', 'CD$', 'CHF', 'CZK', 'HUF', 'NOK', 'NZD', 'SEK', 'TRY',
                                   u'\xa3',    # Pound
                                   u'\xa5',    # Yen
                                   u'\xf3',    # Cents
                                   u'\u20ac',  # Euro
                              }

        is_standard_quoted_unit = quoted_unit in straight_currencies or matches("\$\/.+", quoted_unit)
        is_standard_contract_size = matches("[0-9,\\.]+ [A-Za-z\\. \$]+", contract_size)

        is_standard_pointwise_contract_size = matches("\$?[\\.0-9,]+[ ]+(X[ ]+INDEX|TIMES INDEX VALUE)", contract_size)

        if quoted_unit == 'PTS.' and is_standard_pointwise_contract_size:
            result = ""
            # remove currency
            for n, ch in enumerate(contract_size):
                if ch in '0123456789':
                    result = contract_size[n:]
                    break
            result = result.replace(" ", "").replace("XINDEX", "").replace("TIMESINDEXVALUE", "")
            return result
        elif is_standard_quoted_unit and is_standard_contract_size:
            chunks = [x for x in contract_size.split(" ") if x]
            quantity = self.dollars_from_currency(
                float(chunks[0].replace(",", "")),
                quoted_unit)
            return quantity
        else:
            return fallback

    def get_first_notice(self, sid):
        # returns a Timestamp representing midnight at the day of first delivery
        expiration = self.contract_details.get(sid[0], {}).get('contracts', {}).get(sid[1], {}).get('expiration_date')
        if expiration is not None:
            return Timestamp(expiration, tz='UTC') - timedelta(days=5)
        else:
            delivery_months = "FGHJKMNQUVXZ"
            contract_delivery_month = delivery_months.find(sid[1][0]) + 1
            contract_delivery_year = int("20" + str(sid[1][1:]))
            return Timestamp(contract_delivery_year + "-" + contract_delivery_month + "-01") - timedelta(days=3)


    def record_order(self, order):
        # self.owned_positions[order.sid] = order.amount

        self.backing_period.record_order(order)

    def execute_transaction(self, txn):
        if self.gameover:
            self.margin_history[txn.dt] = self.margin_account_value
            return

        margin_for_new_txn = self.get_initial_margin(txn.sid, txn.dt,
            txn.price * self.get_multiplier(txn.sid)) * txn.amount

        if txn.sid in self.owned_positions:
            self.recalculate_margin_from_price_change(txn.sid, txn.price - txn.commission)

            if margin_for_new_txn <= self.margin_account_value - self.calculate_maintenance_margin(txn.dt):
                self.owned_positions[txn.sid]['amount'] += txn.amount
                self.margin_account_value -= txn.commission * txn.amount
        else:  # buying the first units of a contract
            if margin_for_new_txn <= self.margin_account_value - self.calculate_maintenance_margin(txn.dt):
                self.owned_positions[txn.sid] = {'amount': txn.amount, 'last_price': txn.price}

    def calculate_maintenance_margin(self, timestamp):
        "Uses the owned_positions dictionary to calculate the minimum a margin account must meet in order for
        new transactions to take place."

        maintenance_margin = 0
        for sid, position in self.owned_positions.iteritems():
            maintenance_margin += self.get_maintenance_margin(sid, timestamp,
                self.get_multiplier(sid) * position['last_price']) * position['amount']
        return maintenance_margin

    def update_last_sale(self, event):
        if self.gameover:
            self.margin_history[event.dt] = self.margin_account_value
            return

        if event.sid in self.owned_positions:
            self.recalculate_margin_from_price_change(event.sid, event.price)
            if self.calculate_maintenance_margin(event.dt) > self.margin_account_value:
                self.margin_call(event.dt)

        self.margin_history[event.dt] = self.margin_account_value

    def recalculate_margin_from_price_change(self, sid, new_price):
        "Adjusts the margin account value to compensate with a change in price of an already-owned contract"
        last_price = self.owned_positions[sid]['last_price']
        amount = self.owned_positions[sid]['amount']

        delta = self.get_multiplier(sid) * (new_price - last_price) * amount
        self.margin_account_value += delta
        self.owned_positions[sid]['last_price'] = new_price

        # margin call logic
        if self.margin_account_value <= 0:
            self.gameover = True

    def scale_back_positions(self, timestamp):
        # A default option for margin calls where it goes through positions alphabetically exits those positions until
        # the maintenance margin is below the margin account value

        # we know that
        #  self.calculate_maintenance_margin() > self.margin_account_value

        positions = list(reversed(sorted(self.owned_positions.items())))
        while self.calculate_maintenance_margin(timestamp) > self.margin_account_value:
            shortfall = self.calculate_maintenance_margin(timestamp) - self.margin_account_value
            position = positions.pop()
            sid = position[0]
            details = position[1]

            contract_value = self.get_multiplier(sid) * details['last_price']
            margin_per_contract = self.get_maintenance_margin(sid, timestamp, contract_value)
            contracts_to_exit_amount = int(shortfall / margin_per_contract) + 1
            if contracts_to_exit_amount >= details['amount']:
                del self.owned_positions[sid]
            else:
                self.owned_positions[sid] -= contracts_to_exit_amount


    def __getattr__(self, name):
        return getattr(self.backing_period, name)"""