"""Generates fairly plausible random dummy universe data

Naming conventions:

symbol - a high level symbol (i.e. a "contract constructor" in functional terms) like YG
contract - a low level symbol that represents a specific contract like ZLF17
"""

from pandas.tslib import Timestamp
from pandas.core.frame import DataFrame
from collections import OrderedDict
import datetime
import random
import pytz
import pandas as pd

# Presets

MORE_ACCEPTABLE_SYMBOLS = {
    "GC": "GHMQVZ",
    "SI": "HKNUZ",
    "HG": "HKNUZ",
    "PL": "FJNV",
    "PA": "HMUZ",
    "CT": "HKNVZ",
    "OJ": "FHKNUX",
    "KC": "HKNUZ",
    "ES": "HMUZ",
    "LE": "GJMQVZ",
    "ZL": "FHKNQUVZ",
}

LESS_ACCEPTABLE_SYMBOLS = {
    "GC": "GHV",
    "HG": "HUZ",
}

MORE_BAR_RANGE = (Timestamp('2013-05-13 13:30:00+0000', tz='UTC'), Timestamp('2013-09-11 20:30:00+0000', tz='UTC'))
LESS_BAR_RANGE = (Timestamp('2013-05-13 13:30:00+0000', tz='UTC'), Timestamp('2013-05-15 20:30:00+0000', tz='UTC'))

MORE_CONTRACT_OUT_LIMIT = 2020
LESS_CONTRACT_OUT_LIMIT = 2014

MORE_STEP = datetime.timedelta(minutes=30)
LESS_STEP = datetime.timedelta(days=1)

# Configuration

ACCEPTABLE_SYMBOLS = LESS_ACCEPTABLE_SYMBOLS
BAR_RANGE = LESS_BAR_RANGE
CONTRACT_OUT_LIMIT = LESS_CONTRACT_OUT_LIMIT
STEP = LESS_STEP

CONTRACT_COUNT = sum([sum([1 for m in month_list]) for month_list in [x for x in ACCEPTABLE_SYMBOLS.itervalues()]])




class PrevIterator(object):
    """Iterator with the capability to fetch the previous element
    (though history does not go back any farther).
    """
    def __init__(self, iterator):
        self.iterator = iterator
        self.current_element = None
        self.last_element = None
    
    def __iter__(self):
        return self
    
    def next(self):
        self.last_element = self.current_element
        self.current_element = next(self.iterator)
        return self.current_element
        
    def last(self):
        return self.last_element


def lazy_contracts():
    for symbol, months in ACCEPTABLE_SYMBOLS.iteritems():
        for month in list(months):
            for year in range(datetime.date.today().year, CONTRACT_OUT_LIMIT + 1):
                short_year = year - 2000
                yield (symbol, month, str(short_year))


def lazy_timestamps():
    start = BAR_RANGE[0]
    end = BAR_RANGE[1]
    exchange_opens = datetime.time(hour=13, minute=30)  # UTC
    exchange_closes = datetime.time(hour=20, minute=0)  # UTC
    step = STEP
    
    running_timestamp = start
    while running_timestamp <= end:
        yield running_timestamp
        if exchange_opens <= running_timestamp.time() <= exchange_closes:
            running_timestamp += step
        elif running_timestamp.time() < exchange_opens:
            d = running_timestamp.date()
            z = running_timestamp.tz
            running_timestamp = Timestamp(d, exchange_opens, z)
        elif running_timestamp.time() > exchange_closes:
            d = running_timestamp.date()
            z = running_timestamp.tz
            running_timestamp = datetime.datetime.combine(d + datetime.timedelta(days=1), exchange_opens)
            running_timestamp = running_timestamp.replace(tzinfo=pytz.UTC)
            running_timestamp = Timestamp(running_timestamp)


def create_dummy_universe_dict():
    """
    WARNING: Because the underlying data structure has to be highly nested, the logic in here
    will be highly nested.
    """
    universe_dict = OrderedDict()
    timestamps = PrevIterator(lazy_timestamps())
    for timestamp in timestamps:
        universe_dict[timestamp] = {}
        for symbol, month, short_year in lazy_contracts():
            if symbol not in universe_dict[timestamp]:
                universe_dict[timestamp][symbol] = {}
            expiry = month + str(short_year)
            universe_dict[timestamp][symbol][expiry] = {}
            
            if timestamps.last() in universe_dict:
                old_price = universe_dict[timestamps.last()][symbol][expiry]["Price"]
                price_percent_change = 0.1
                new_price = random.gauss(mu=old_price, sigma=old_price * price_percent_change)
                
                old_open_interest = universe_dict[timestamps.last()][symbol][expiry]["Open Interest"]
                open_interest_percent_change = 0.1
                new_open_interest = random.gauss(mu=old_open_interest,
                                                 sigma=old_open_interest * open_interest_percent_change)

                # For now, assume all margin requirements stay static.
                # In the future: read the SPAN Margining handout for an algorithm
                old_margin_requirements = universe_dict[timestamps.last()][symbol][expiry]["Margin Requirements"]
                new_margin_requirements = old_margin_requirements
            else:
                # First price
                new_price = random.random() * 100
                new_open_interest = random.random() * 2000
                new_margin_requirements = 100.00
                
            new_price = round(new_price, 2)
            universe_dict[timestamp][symbol][expiry]["Price"] = new_price
            
            new_open_interest = int(round(new_open_interest, 0))
            universe_dict[timestamp][symbol][expiry]["Open Interest"] = new_open_interest

            new_margin_requirements = round(new_margin_requirements, 2)
            universe_dict[timestamp][symbol][expiry]["Margin Requirements"] = new_margin_requirements
        
    return universe_dict


def dataframe_from_universe_dict(universe_dict):
    timestamps = []
    outer_frames = []
    for timestamp, hl_ticker_dict in universe_dict.iteritems():
        timestamps.append(timestamp)
        
        inner_frames = []
        hl_tickers = []
        for hl_ticker, low_level_ticker_dict in hl_ticker_dict.iteritems():
            hl_tickers.append(hl_ticker)
            inner_frames.append(DataFrame.from_dict(low_level_ticker_dict, orient='index'))
        hl_ticker_frame = pd.concat(inner_frames, keys=hl_tickers)
        outer_frames.append(hl_ticker_frame)
        
    universe_df = pd.concat(outer_frames, keys=timestamps)
    return universe_df
    
"""
A small set of dummy futures data will have this structure:

{Timestamp('2013-05-13 07:45:49+0000', tz='UTC'): 
    {'YG':
        {'F15': 
            {'Price': 180.00, 
             'Open Index': 1000,
            },
         'N16': 
            {'Price': 250.75, 
             'Open Index': 2000,
            },
        },
     'XSN':
         {'F15': 
            {'Price': 360.00, 
             'Open Index': 4682,
            },
         'N16': 
            {'Price': 405.75, 
             'Open Index': 4001,
            },
        },
    },
 Timestamp('2013-05-13 08:45:49+0000', tz='UTC'): 
    {'YG':
        {'F15': 
            {'Price': 195.66, 
             'Open Index': 996,
            },
         'N16': 
            {'Price': 266.75, 
             'Open Index': 2003,
            },
        },
     'XSN':
        {'F15': 
            {'Price': 358.08, 
             'Open Index': 5000,
            },
         'N16': 
            {'Price': 402.75, 
             'Open Index': 4002,
            },
        },
    },
}
"""