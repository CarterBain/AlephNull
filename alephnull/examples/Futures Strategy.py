from alephnull.algorithm import TradingAlgorithm
from alephnull.sources.futures_data_frame_source import FuturesDataFrameSource
import matplotlib.pylab as plt
import numpy as np
import pandas as pd
from pandas import DataFrame
import datetime as dt
import string


source = DataFrame(np.random.uniform(100, 200, [60,30]))
cols = ['price', 'volume', 'open_interest']
scale = (len(source.columns) / len(cols))
source.columns = [scale  * cols]
sym = lambda x: np.random.choice([abc for abc in x],
                                 np.random.choice([2,3]))
month = lambda x: np.random.choice([abc for abc in x],
                                 np.random.choice([1]))

contracts = np.ravel([[(''.join(month(string.letters[:26])) +
             str(np.random.choice([14,15,16])))] * len(cols)
             for x in xrange(len(source.columns) / len(cols)/ 2)])

level_1 = len(source.columns) / len(contracts) * list(contracts)

numsyms = len(source.columns) / (len(set(level_1)) * len(cols))
underlyings = [''.join(sym(string.letters[:26])) for x in xrange(numsyms)]
level_0 = np.ravel([[sym] * len(set(level_1)) * len(cols) for sym in underlyings])

source.columns = pd.MultiIndex.from_tuples(zip(level_0, level_1, source.columns))
source.index = pd.date_range(start= dt.datetime.utcnow() - dt.timedelta(hours=len(source.index)-1),
                             end = dt.datetime.utcnow(), freq='H')

futdata = FuturesDataFrameSource(source.tz_localize('UTC'))

class Trader(TradingAlgorithm):
    def handle_data(self, data):
        for sym in data.keys():
            for exp in data[sym].keys():
               self.order((sym, exp), 1)

x = Trader()
res = x.run(futdata)

print x.perf_tracker.get_portfolio()
res['portfolio_value'].plot()

plt.show()

raw_input()