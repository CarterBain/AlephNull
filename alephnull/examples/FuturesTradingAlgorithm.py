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

from alephnull.algorithm import TradingAlgorithm
from alephnull.utils.factory import load_from_yahoo

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
        self.margin_account_log = TimeSeries()
        self.margin_account_value = 100000
        self.last_prices = {}
        self.initialize_futures(*args, **kwargs)

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

        self.margin_account_log = self.margin_account_log.set_value(timestamp, self.margin_account_value)

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
            timestamp = next(data[0].iteritems() if type(data) is list else data.iteritems())[1]['datetime']
            print("You can't handle the truth! " + timestamp)
            pass

    def handle_futures_data(self):
        """Up to subclasses to implement"""
        pass

    def initialize_futures(self, *args, **kwargs):
        """Up to subclasses to implement"""
        pass

    def _handle_margin_call(self, data):
        """Up to subclasses to implement, though this class does provide a few premade procedures
        like _liquidate_excess_on_margin_call"""
        pass

    def _liquidate_excess_on_margin_call(self, data):
        """ A sample procedure for what to do on a margin call.
        This gets the first position among the ones owned and liquidates
        enough (putting the proceeds into the margin account) to put you back
        above initial margin for all your contracts.

        TODO: Distribute over all positions
        """
        symbol, measures = next(data.iteritems())
        position = self.perf_tracker.cumulative_performance.positions[symbol]
        maintenance_margin = measures['maintenance_margin']
        quantity_owned = position.amount
        margin = position.margin
        initial_margin = measures['initial_margin']
        if maintenance_margin * quantity_owned > margin:
            # sell enough so that your margin account is back above initial margin for every contract
            quantity_to_sell = int(initial_margin * quantity_owned ** 2 / margin - quantity_owned) + 1
            TradingAlgorithm.order(self, symbol, -1 * quantity_to_sell)


class BuyGoogleAsFuture(FuturesTradingAlgorithm):

    def initialize_futures(self, *args, **kwargs):
        pass

    def handle_futures_data(self, data):
        self.order("GOOG", 1, initial_margin=data['GOOG']['initial_margin'])

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

    plt.gcf().set_size_inches(18, 8)