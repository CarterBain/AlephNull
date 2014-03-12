import pandas as pd
from pandas import Series, DataFrame

from alephnull.protocol import BarData, SIDData


def roll(logic):
    def wrap(func):
        def modified_func(self, data):
            positions = self.portfolio.positions
            frames = {}
            for sym in data.keys():
                frames[sym] = DataFrame({k: Series(v.__dict__) for
                                         k, v in data[sym].iteritems()})

            all_ = pd.concat(frames, axis=1).T
            try:
                all_ = all_.groupby(axis=0, level=0).apply(logic).reset_index(
                    level=(0, 2), drop=True)
            except:
                all_ = all_.groupby(axis=0, level=0).apply(logic)


            #Todo: handle multiple contract returns
            all_ = all_.groupby(axis=0, level=0).agg(lambda x: x.max())

            #Todo: Data should be reconstructed into BarData object
            data = all_.T.to_dict()

            front_months = [(sym, all_.ix[sym]['contract']) for sym in all_.index]
            back_months = [sym for sym in self.perf_tracker.get_portfolio().positions
                           if sym not in front_months]

            offsets = {}
            for sym in back_months:
                offsets[sym] = 0
                for order_id in self.get_orders(sym):
                    order = self.blotter.orders[order_id]
                    if order.status != 3:
                        offsets[sym] += (order.amount - order.filled)
                stack = self.perf_tracker.get_portfolio().positions[sym].amount + offsets[sym]
                if stack != 0:
                    self.order(sym, -stack)
                    [self.order(exp, stack) for exp in front_months if exp[0] == sym[0]]

            bar_data = BarData()
            bar_data.__dict__['_data'].update({k: SIDData(v) for k, v in data.iteritems()})

            return func(self, bar_data)

        return modified_func

    return wrap


