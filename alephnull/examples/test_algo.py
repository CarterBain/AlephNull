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
import string

import numpy as np
import pandas as pd
from pandas import DataFrame

from alephnull.algorithm import TradingAlgorithm
from alephnull.sources.futures_data_frame_source import FuturesDataFrameSource
from alephnull.roll_method import roll


source = DataFrame(np.random.uniform(100, 200, [60, 30]))
cols = ['price', 'volume', 'open_interest']
scale = (len(source.columns) / len(cols))
source.columns = [scale * cols]
sym = lambda x: np.random.choice([abc for abc in x],
                                 np.random.choice([2, 3]))
month = lambda x: np.random.choice([abc for abc in x],
                                   np.random.choice([1]))

contracts = np.ravel([[(''.join(month(string.letters[:26])) +
                        str(np.random.choice([14, 15, 16])))] * len(cols)
                      for x in xrange(len(source.columns) / len(cols) / 2)])

level_1 = len(source.columns) / len(contracts) * list(contracts)

numsyms = len(source.columns) / (len(set(level_1)) * len(cols))
underlyings = [''.join(sym(string.letters[:26])) for x in xrange(numsyms)]
level_0 = np.ravel([[sym] * len(set(level_1)) * len(cols) for sym in underlyings])

source.columns = pd.MultiIndex.from_tuples(zip(level_0, level_1, source.columns))
source.index = pd.date_range(start=dt.datetime.utcnow() - dt.timedelta(days=len(source.index) - 1),
                             end=dt.datetime.utcnow(), freq='D')

futdata = FuturesDataFrameSource(source.tz_localize('UTC'))


class FrontTrader(TradingAlgorithm):
    @roll(lambda x: x[x['open_interest'] == x['open_interest'].max()])
    def handle_data(self, data):
        for sym in data.keys():
            self.order((sym, data[sym]['contract']), 2)
        return data


bot = FrontTrader()
stats = bot.run(futdata)
