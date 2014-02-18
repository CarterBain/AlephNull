import pandas as pd

from alephnull.gens.utils import hash_args

from alephnull.sources.data_source import DataSource


class FuturesDataFrameSource(DataSource):
    """
    Yields all events in event_list that match the given sid_filter.
    If no event_list is specified, generates an internal stream of events
    to filter.  Returns all events if filter is None.

    Configuration options:

    sids   : list of values representing simulated internal sids
    start  : start date
    delta  : timedelta between internal events
    filter : filter to remove the sids
    """

    def __init__(self, data, **kwargs):
        """
        Data must be a DataFrame formatted like this:

        #################################################################################################
        #                     # GS                                # TW                                  #
        #                     # N10             # H10             # G14              # H14              #
        #                     # Price  # Volume # Price  # Volume # Price  # Metric3 # Price  # Metric3 #
        # 2013-12-20 00:09:15 # 101.00 # 1000   # 60.34  # 2500   # 400.00 # -0.0034 # Price # -5.0     #
        # 2013-12-20 00:09:17 # 201.00 # 2000   # 20.34  # 2500   # 200.00 # -2.0034 # Price # -2.0     #
        # etc...                                                                                        #
        #################################################################################################

        """
        assert isinstance(data.index, pd.tseries.index.DatetimeIndex)

        self.data = data
        # Unpack config dictionary with default values.
        self.sids = kwargs.get('sids', list(set(['.'.join(tup[:2]) for tup in data.columns])))
        self.start = kwargs.get('start', data.index[0])
        self.end = kwargs.get('end', data.index[-1])

        # Hash_value for downstream sorting.
        self.arg_string = hash_args(data, **kwargs)

        self._raw_data = None

    @property
    def mapping(self):
        return {
            'dt': (lambda x: x, 'dt'),
            'sid': (lambda x: x[:x.find(".")], 'sid'),
            'contract': (lambda x: x[x.find(".") + 1:], 'sid'),
            'price': (float, 'price'),
            'volume': (int, 'volume'),
            'open_interest': (int, 'open_interest'),
        }

    @property
    def instance_hash(self):
        return self.arg_string

    def raw_data_gen(self):
        for dt, series in self.data.iterrows():
            events = {}
            for (underlying, exp, metric), value in series.iterkv():
                sid = '.'.join([underlying, exp])
                if sid in self.sids:
                    if sid not in events:
                        events[sid] = {'dt': dt, 'sid': sid}
                    events[sid][metric] = value
            for event in events.itervalues():
                yield event

    @property
    def raw_data(self):
        if not self._raw_data:
            self._raw_data = self.raw_data_gen()
        return self._raw_data