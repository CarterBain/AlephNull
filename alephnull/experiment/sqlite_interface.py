import sqlite3
from pandas.tslib import Timestamp

class FuturesDB(object):
    
    def __init__(self, file_path):
        self.conn = sqlite3.connect(file_path)
        self.cursor = self.conn.cursor()
        
    def _dummy_entry(self):
        myts_as_int = int(Timestamp('2013-05-13 07:45:49+0000', tz='UTC').value / 1000000000)
        c.execute("INSERT INTO timestamps VALUES (NULL, ?)", (myts_as_int,))
        c.execute("INSERT INTO symbols VALUES (NULL, ?, ?)", ("YG", 1))
        c.execute("INSERT INTO contracts VALUES (NULL, ?, ?, ?, ?)", ("F15", 105.51, 1000, 1))
        
    def initialize_tables(self):
        self.cursor.execute('''CREATE TABLE timestamps
                     (t_id INTEGER PRIMARY KEY, timestamp integer)''')
        self.cursor.execute('''CREATE TABLE symbols
                     (s_id INTEGER PRIMARY KEY, symbol TEXT, t_parent INTEGER)''')
        self.cursor.execute('''CREATE TABLE contracts
                     (c_id INTEGER PRIMARY KEY, contract_month TEXT, price REAL, open_interest INTEGER, s_parent INTEGER)''')
                     
    def insert_dict(self, universe_dict):
        for timestamp, symbol_dict in universe_dict.iteritems():
            timestamp_as_int = self._int_from_timestamp(timestamp)
            self.cursor.execute("INSERT INTO timestamps VALUES (NULL, ?)", (timestamp_as_int,))
            t_id = self.cursor.lastrowid
            
            for symbol, contract_dict in symbol_dict.iteritems():
                self.cursor.execute("INSERT INTO symbols VALUES (NULL, ?, ?)", (symbol, t_id))
                s_id = self.cursor.lastrowid
                
                for contract_month, details_dict in contract_dict.iteritems():
                    self.cursor.execute("INSERT INTO contracts VALUES (NULL, ?, ?, ?, ?)",
                                        (contract_month, details_dict['Price'], details_dict['Open Interest'], s_id))
                    
        
    def get_prices(self, timestamp, symbol=None, month=None):
        """Get a dict of prices that is wider or narrower depending on what parameters
        are specified.
        
        If you call fdb.get_prices(some_timestamp), you will get a dict that looks like:
           {YG: {F15: 100.00, N14: 340.12}, CT: {F16: 53.23, Z12: 56.98}}
        If you call fdb.get_prices(some_timestamp, some_symbol), you will get a dict that looks like:
            {F15: 100.00, N14: 340.12}
        If you call fdb.get_prices(some_timestamp, some_symbol, some_month), you will get a double
            that represents a single price, like 134.57
        
        Args:
            timestamp (Timestamp): a Timestamp instance
            symbol (string): a top-level futures symbol representing some commodity (i.e. YG)
            month (string): a month letter plus a year that represents, along with the symbol,
                a specific contract (i.e. F15)
        """
        timestamp_as_int = self._int_from_timestamp(timestamp)
        self.cursor.execute("SELECT * FROM timestamps WHERE timestamp=?", (timestamp_as_int,))
        t_row = self.cursor.fetchone()
        t_record = {'t_id': t_row[0], 'timestamp': t_row[1]}
        
        if symbol is not None:
            self.cursor.execute("SELECT s_id, symbol FROM symbols WHERE t_parent=? AND symbol=?", (t_record['t_id'], symbol))
            s_row = self.cursor.fetchone()
            s_record = {'s_id': s_row[0], 'symbol': s_row[1]}
            
            if month is not None:
                self.cursor.execute("SELECT c_id, price FROM contracts WHERE s_parent=? AND contract_month=?", (s_record['s_id'], month))
                c_row = self.cursor.fetchone()
                c_record = {'c_id': c_row[0], 'price': c_row[1]}
                
                return c_record['price']
                
            else:
                result_dict = {}
                self.cursor.execute("SELECT c_id, contract_month, price FROM contracts WHERE s_parent=?", (s_record['s_id'],))
                for _, contract_month, price in self.cursor:
                    result_dict[contract_month] = price
                return result_dict
        else:
            symbol_dict = {}
            result_dict = {}
            self.cursor.execute("SELECT s_id, symbol FROM symbols WHERE t_parent=?", (t_record['t_id'],))
            for s_id, symbol in self.cursor:
                symbol_dict[symbol] = s_id
            
            for symbol, s_id in symbol_dict.iteritems():
                result_dict[symbol] = {}
                self.cursor.execute("SELECT contract_month, price FROM contracts WHERE s_parent=?", (s_id,))
                for contract_month, price in self.cursor:
                    result_dict[symbol][contract_month] = {"Price": price}
            
            return result_dict
                    
    def get_price(self, timestamp, symbol, month):
        return self.get_prices(timestamp, symbol, month)
        
    def get_all_timestamps(self):
        self.cursor.execute("SELECT timestamp FROM timestamps")
        return [self._timestamp_from_int(ts_as_int) for (ts_as_int,) in self.cursor]
        
    def __getitem__(self, timestamp):
        query1 = "SELECT * FROM timestamps WHERE timestamp=?"
        query2 = "SELECT * FROM symbols WHERE t_parent=? AND symbol=?"
        query3 = "SELECT * FROM contracts WHERE  s_parent=? AND contract_month=?"
        
    def _kw_row(self, row, table):
        if table=='timestamps':
            t_record = {'t_id': t_row[0], 'timestamp': t_row[1]}
        if table=='symbols':
            pass
            
    def _int_from_timestamp(self, timestamp):
        return int(timestamp.value / 10**9)
    def _timestamp_from_int(self, timestamp_as_int):
        return Timestamp(timestamp_as_int * 10**9)
        
    def close(self):
        self.conn.close()
        
class _PartialResult:
    def __init__(self, cursor, query_queue, **kwargs):
        self.query_queue = query_queue
        self.cursor = cursor
    def __getitem__():
        next_query = self.query_queue[0]
        del(self.query_queue[0])
        