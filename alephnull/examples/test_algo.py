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

import datetime as dt

from pandas import DataFrame
from pandas.io.data import DataReader

from alephnull.algorithm import TradingAlgorithm


stocks = ['AAPL', 'GOOG', 'YHOO', 'SBUX']
stock_data = DataReader(stocks, 'yahoo',
                        start=dt.datetime.utcnow() -
                              dt.timedelta(days=10),
                        end=dt.datetime.utcnow())

stock_data = DataFrame(stock_data['Adj Close']).tz_localize('UTC')


class Trade(TradingAlgorithm):
    def initialize(self, *args, **kwargs):
        self.invested = False

    def handle_data(self, data):
        # if not self.invested:
        for sym in data:
            self.order(sym, 100)
            # self.invested = True


bot = Trade(live_execution=True)
stats = bot.run(stock_data)

bot.live_execution.disconnect()
