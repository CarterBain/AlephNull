#!/usr/bin/env python
#
# Copyright 2013 Carter Bain Wealth Management
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

import matplotlib.pyplot as plt
from datetime import datetime
import pytz
import random

from alephnull.algorithm import TradingAlgorithm
from alephnull.utils.factory import load_from_yahoo

from collections import OrderedDict
from pandas.core.series import TimeSeries


class FuturesTradingAlgorithm(TradingAlgorithm):
    """A wrapper around TradingAlgorithm that adds calculations for futures contracts.

    In order to have everything work in subclasses, you have to do several things:

    Create a method "_handle_margin_call(self, data) that is executed if you go below maintenance margin.
    Instead of handle_data(), create handle_futures_data()
    Instead of initialize(), create initialize_futures()

    """

    def add_margin_to_bars(self, data):
        # Uses some strategy to get the price at some bar and calculate appropriate
        # initial and maintenance margins for that bar.
        # Ideally we would use SPAN margining; however, based on some naive data analysis,
        # the max a stock changes in a several day period (up to 30 days) is about 42%.
        # Change this when you have a better strategy!
        for symbol, measures in data.iteritems():
            initial_margin = measures['price'] * 0.42
            maintenance_margin = measures['price'] * 0.32
            measures.__dict__.update({'initial_margin': initial_margin})
            measures.__dict__.update({'maintenance_margin': maintenance_margin})

    def initialize(self, *args, **kwargs):
        self._margin_account_log = OrderedDict()
        self.margin_account_value = 100000
        self.last_prices = {}
        self.initialize_futures(*args, **kwargs)
        # self.max_leverage = 1.5

    def handle_data(self, data):

        self.add_margin_to_bars(data)
        self.total_maintenance_margin = 0

        # update margin account
        for symbol, measures in data.iteritems():
            position = self.perf_tracker.cumulative_performance.positions[symbol]
            last_price = self.last_prices.get(symbol)
            price = measures['price']
            if last_price is not None:
                self.margin_account_value += (price - last_price) * position.amount
            self.last_prices[symbol] = price
            self.total_maintenance_margin += measures['maintenance_margin']

        timestamp = next(data[0].iteritems() if type(data) is list else data.iteritems())[1]['datetime']

        self._margin_account_log[timestamp] = self.margin_account_value

        if self.margin_account_value < self.total_maintenance_margin:
            self._handle_margin_call()
        self.handle_futures_data(data)

    def order(self, sid, amount, initial_margin, limit_price=None, stop_price=None):
        # TODO: get rid of the initial_margin parameter when we can figure that out from inside this method
        # Check if there's enough in the margin account to cover initial margin
        if self.margin_account_value > self.total_maintenance_margin + initial_margin * amount:
            TradingAlgorithm.order(self, sid, amount, limit_price, stop_price)
        else:
            # there shouldn't be an exception here, right?
            # TODO: log once you figure out how zipline's logging works
            pass

    def handle_futures_data(self):
        """Up to subclasses to implement"""
        pass

    def initialize_futures(self, *args, **kwargs):
        """Up to subclasses to implement"""
        pass

    def _handle_margin_call(self):
        """Up to subclasses to implement, though this class does provide a few premade procedures
        like _liquidate_random_positions"""
        pass

    def _liquidate_random_positions(self):
        """Liquidate an entire position (the position in particular is chosen at random) until we are back above
        maintenance margin."""
        while self.margin_account_value < self.total_maintenance_margin:
            positions_as_list = self.perf_tracker.cumulative_performance.positions.items()[:]
            chosen_symbol, chosen_position = positions_as_list[random.randint(0, len(positions_as_list) - 1)]
            TradingAlgorithm.order(self, chosen_symbol, chosen_position.amount)
            positions_as_list.remove((chosen_symbol, chosen_position))

            self.total_maintenance_margin = sum(
                [position.last_sale_price * 0.32 * position.amount for symbol, position in positions_as_list])

    @property
    def margin_account_log(self):
        return TimeSeries(self._margin_account_log)


class BuyGoogleAsFuture(FuturesTradingAlgorithm):

    def initialize_futures(self, *args, **kwargs):
        pass

    def handle_futures_data(self, data):
        self.order("GOOG", 1, initial_margin=data['GOOG']['initial_margin'])

    def _handle_margin_call(self):
        self._liquidate_random_positions()

if __name__ == '__main__':
    start = datetime(2008, 1, 1, 0, 0, 0, 0, pytz.utc)
    end = datetime(2013, 1, 1, 0, 0, 0, 0, pytz.utc)
    data = load_from_yahoo(stocks=["GOOG"], indexes={}, start=start,
                           end=end, adjusted=True)
    simple_algo = BuyGoogleAsFuture()
    results = simple_algo.run(data)

    ax1 = plt.subplot(211)
    futures_indexes = list(simple_algo.margin_account_log.keys())
    futures_margin_data = list(simple_algo.margin_account_log.values)

    futures_margin_series = TimeSeries(index=futures_indexes, data=futures_margin_data)
    futures_margin_series.plot(ax=ax1)

    ax2 = plt.subplot(212, sharex=ax1)
    data.GOOG.plot(ax=ax2)

    plt.gcf().set_size_inches(18, 8)