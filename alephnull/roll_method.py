import pandas as pd
from pandas import Series, DataFrame


def roll(logic):
    def wrap(func):
        def modified_func(self, data):
            positions = self.portfolio.positions
            frames = {}
            for sym in data.keys():
                frames[sym] = DataFrame({k: Series(v.__dict__) for
                                         k, v in data[sym].iteritems()})

            all_ = pd.concat(frames, axis=1).T
            all_ = all_.groupby(axis=0, level=0).apply(logic).reset_index(level=(0, 2), drop=True)

            #Todo: handle multiple contract returns
            all_ = all_.groupby(axis=0, level=0).agg(lambda x: x.max())

            #Todo: Data should be reconstructed into BarData object
            data = all_.T.to_dict()
            front_months = [(sym, all_.ix[sym]['contract']) for sym in all_.index]
            outdated = [exp for exp in positions.keys() if exp not in front_months]

            offsets = {}
            #Todo: get amount from blotter to catch outstanding orders
            #Todo: cancel those orders to prevent fill after offset
            for pos in outdated:
                amount = positions[pos].amount
                if pos[0] in offsets:
                    offsets[pos[0]] += amount
                else:
                    offsets[pos[0]] = amount
                if amount != 0:
                    self.order(pos, -amount)

            if offsets:
                for pos in front_months:
                    if pos[0] in offsets and offsets[pos[0]] != 0:
                        self.order(pos, -offsets[pos[0]])

            return func(self, data)

        return modified_func

    return wrap


