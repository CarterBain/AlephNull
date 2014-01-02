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

SYMBOL = 'GS'
TRACK = []
DAT = [None]
DIFFS = []
SHORTFALL_STRATEGY = "sell"


class BuyStock(TradingAlgorithm):
    """This is the simplest possible algorithm that does nothing but
    buy 1 share of SYMBOL on each event.
    """

    def add_margin(self, data):
        # Uses some strategy to get the price at some bar and calculate appropriate
        # initial and maintenance margins for that bar.
        # Ideally we would use SPAN margining; however, based on some naive data analysis,
        # the max a stock changes in a several day period (up to 30 days) is about 42%.
        # Change this when you have a better strategy!
        initial_margin = data[SYMBOL]['price'] * 0.42
        maintenance_margin = data[SYMBOL]['price'] * 0.32
        data[SYMBOL].__dict__.update({'initial_margin': initial_margin})
        data[SYMBOL].__dict__.update({'maintenance_margin': maintenance_margin})

    def initialize(self, *args, **kwargs):
        self._first_pass = True
        self.futures_results

    def handle_data(self, data):  # overload handle_data() method
        DAT[0] = data
        self.add_margin(data)
        position = self.perf_tracker.cumulative_performance.positions[SYMBOL]
        maintenance_margin = data[SYMBOL]['maintenance_margin']
        initial_margin = data[SYMBOL]['initial_margin']
        price = data[SYMBOL].price

        if self._first_pass:
            initial_quantity = 50
            self.order(SYMBOL, initial_quantity)
            position.margin += initial_margin * initial_quantity
            print(position.margin)
            self._first_pass = False
            self.last_price = price
            return
        else:
            DIFFS.append((self.last_price - price) / price)


        quantity_owned = position.amount
        margin = position.margin
        # don't ask...
        timestamp = next(data[0].iteritems() if type(data) is list else data.iteritems())[1]['datetime']

        TRACK.append((margin, quantity_owned, timestamp))
        if maintenance_margin * quantity_owned > margin:
            if SHORTFALL_STRATEGY == "sell":
                TRACK.append("SELL")
                # sell enough so that your margin account is back above initial margin for every contract
                quantity_to_sell = int(initial_margin * quantity_owned ** 2 / margin - quantity_owned) + 1
                self.order(SYMBOL, -1*quantity_to_sell)
                if quantity_to_sell == 0:
                    TRACK.append(str(timestamp) + " had a 0-sell!")
            elif SHORTFALL_STRATEGY == "buffer":
                # put some more money from elsewhere into the account
                pass
            elif margin > 1.5*(maintenance_margin * quantity_owned):
                # we've got too much in margin - we need to make our money work for us!
                # buy as many contracts as we can until buying another would put us under
                # 1.25 * required margin
                TRACK.append("BUY")
                max_funds_available = margin - 1.25*(maintenance_margin * quantity_owned)
                quantity_to_buy = int(max_funds_available / initial_margin)


                # we don't have to update the margin because the same amount of cash is still in the margin account,
                # it is just distributed over a larger number of contracts
                if quantity_to_buy == 0:
                    TRACK.append("0 to buy, what a shame")
                else:
                    self.order(SYMBOL, quantity_to_buy)  # order SID (=0) and amount (=1 shares)

                if quantity_to_buy == 0:
                    TRACK.append(str(timestamp) + " had a 0-sell!")

        self.last_price = price


if __name__ == '__main__':
    start = datetime(2008, 1, 1, 0, 0, 0, 0, pytz.utc)
    end = datetime(2013, 1, 1, 0, 0, 0, 0, pytz.utc)
    data = load_from_yahoo(stocks=[SYMBOL], indexes={}, start=start,
                           end=end, adjusted=True)
    simple_algo = BuyStock()
    results = simple_algo.run(data)

    ax1 = plt.subplot(211)
    ax2 = plt.subplot(212)
    TRACK_STRIPPED = [x for x in TRACK if type(x) == tuple]
    futures_indexes = [timestamp for (_, _, timestamp) in TRACK_STRIPPED]
    futures_quantity_data = [quantity_owned for (_, quantity_owned, _) in TRACK_STRIPPED]
    futures_margin_data = [margin for (margin, _, _) in TRACK_STRIPPED]

    futures_margin_series = TimeSeries(index=futures_indexes, data=futures_margin_data)
    futures_margin_series.plot(ax=ax1)
    futures_quantity_series = TimeSeries(index=futures_indexes, data=futures_quantity_data)
    futures_quantity_series.plot(ax=ax2)

    plt.gcf().set_size_inches(18, 8)