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

SYMBOL = 'GS'

class BuyStock(TradingAlgorithm):  # inherit from TradingAlgorithm
    """This is the simplest possible algorithm that does nothing but
    buy 1 share of SYMBOL on each event.
    """
    def handle_data(self, data):  # overload handle_data() method
        self.order(SYMBOL, 1)  # order SID (=0) and amount (=1 shares)


if __name__ == '__main__':
    start = datetime(2008, 1, 1, 0, 0, 0, 0, pytz.utc)
    end = datetime(2013, 1, 1, 0, 0, 0, 0, pytz.utc)
    data = load_from_yahoo(stocks=[SYMBOL], indexes={}, start=start,
                           end=end)
    simple_algo = BuyStock()
    results = simple_algo.run(data)

    ax1 = plt.subplot(211)
    results.portfolio_value.plot(ax=ax1)
    ax2 = plt.subplot(212, sharex=ax1)
    stock_data = getattr(data, SYMBOL)
    stock_data.plot(ax=ax2)
    plt.gcf().set_size_inches(18, 8)