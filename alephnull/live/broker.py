__author__ = 'oglebrandon'

from logbook import Logger

from ib.ext.Contract import Contract
from ib.ext.ExecutionFilter import ExecutionFilter
from ib.ext.Order import Order as IBOrder
from alephnull.finance.blotter import Blotter
from alephnull.utils.protocol_utils import Enum
from alephnull.finance.slippage import Transaction
import alephnull.protocol as zp


# Medici fork of IbPy
# https://github.com/CarterBain/Medici
from ib.client.IBrokers import IBClient
import datetime as dt
import pytz

log = Logger('Blotter')

ORDER_STATUS = Enum(
    'OPEN',
    'FILLED',
    'CANCELLED'
)


def round_for_minimum_price_variation(x):
    #Todo: modify to round to minimum tick
    return x


class LiveBlotter(Blotter):
    id_map = {}

    def __init__(self):
        super(LiveBlotter, self).__init__()


    def order(self, sid, amount, limit_price, stop_price, order_id=None):
        id = super(LiveBlotter, self).order(sid, amount, limit_price, stop_price, order_id=None)
        order_obj = self.orders[id]

        ib_order = IBOrder()
        ib_order.m_transmit = True
        ib_order.m_orderRef = order_obj.id
        ib_order.m_totalQuantity = order_obj.amount
        ib_order.m_action = ['BUY' if ib_order.m_totalQuantity > 0 else 'SELL'][0]
        ib_order.m_tif = 'DAY'
        #Todo: make the FA params configurable
        ib_order.m_faGroup = 'ALL'
        ib_order.m_faMethod = 'AvailableEquity'

        # infer order type
        if order_obj.stop and not order_obj.limit:
            ib_order.m_orderType = 'STP'
            ib_order.m_auxPrice = float(order_obj.stop)

        elif order_obj.limit and not order_obj.stop:
            ib_order.m_orderType = 'LMT'
            ib_order.m_lmtPrice = float(order_obj.limit)

        elif order_obj.stop and order_obj.limit:
            ib_order.m_orderType = 'STPLMT'
            ib_order.m_auxPrice = float(order_obj.stop)
            ib_order.m_lmtPrice = float(order_obj.limit)

        else:
            ib_order.m_orderType = 'MKT'

        contract = Contract()
        contract.m_symbol = order_obj.sid
        contract.m_currency = 'USD'

        if hasattr(order_obj, 'contract'):
            # This is a futures contract
            contract.m_secType = 'FUT'
            contract.m_exchange = 'GLOBEX'
            contract.m_expiry = order_obj.contract

        else:
            # This is a stock
            contract.m_secType = 'STK'
            contract.m_exchange = 'SMART'

        ib_id = self.place_order(contract, ib_order)
        self.id_map[order_obj.id] = ib_id

        return order_obj.id

    def cancel(self, order_id):
        ib_id = self.id_map[order_id]
        self.cancel_order(ib_id)
        super(Blotter, self).order(order_id)

    def process_trade(self, trade_event):

        # checks if event is trade
        if trade_event.type != zp.DATASOURCE_TYPE.TRADE:
            return

        # checks if is future contract
        if hasattr(trade_event, 'contract'):
            sid = (trade_event.sid, trade_event.cotract)
        else:
            sid = trade_event.sid

        if sid in self.open_orders:
            orders = self.open_orders[sid]
            # sort orders by datetime, and filter out future dates
            # lambda x: sort([order.dt for order in orders])

        else:
            return

        for order, txn in self.get_transactions(trade_event, orders):
            # check that not commission
            order.filled += txn.amount
            if order.amount - order.filled == 0:
                order.status = ORDER_STATUS.FILLED
            order.dt = txn.dt
            print txn.__dict__
            yield txn, order

        self.open_orders[sid] = \
            [order for order
             in self.open_orders[sid]
             if order.open]


class LiveExecution(IBClient):
    """Client connection to the Interactive Brokers API
       inherits from IBClient in the Medici fork of IbPy
    """

    def __init__(self, call_msg):
        super(LiveExecution, self).__init__(call_msg=call_msg)
        self._blotter = LiveBlotter()
        self._blotter.place_order = self.place_order
        self._blotter.get_transactions = self.get_transactions
        self._blotter.cancel_order = self.cancel_order
        super(LiveExecution, self).__track_orders__()

    @property
    def blotter(self):
        return self._blotter


    def __ib_to_aleph_sym_map__(self, contract):
        decade = dt.date.today().strftime('%y')[0]
        sym = contract.m_symbol
        exp = contract.m_localSymbol.split(sym)[1]
        exp = exp[0] + decade[0] + exp[1]

        return (sym, exp)


    def total_cash(self):
        cash = 0
        for acct in self.account.child_accounts:
            try:
                cash += float([x.value for x in self.account_details(acct)
                               if x.key == 'TotalCashValue'][0])
            except:
                return self.total_cash()

        return cash

    def ib_portfolio(self):

        portfolio_store = zp.Portfolio()
        positions_store = zp.Positions()

        for acct in self.account.child_accounts:
            positions = self.portfolio(acct)
            for pos in positions:
                # Skip empty requests
                if hasattr(pos, 'contract'):
                    contract = pos.contract

                    # determine position sid
                    if contract.m_secType == 'STK':
                        sid = contract.m_localSymbol
                    if contract.m_secType == 'FUT':
                        sid = self.__ib_to_aleph_sym_map__(contract)

                    # if sid not in positions create a new position object
                    if sid not in positions_store:
                        if type(sid) is tuple:
                            positions_store[sid] = zp.Position(sid[0], contract=sid[1])
                        else:
                            positions_store[sid] = zp.Position(sid)

                        positions_store[sid].amount = pos.position_size
                        positions_store[sid].last_sale_price = pos.market_price
                        positions_store[sid].cost_basis = pos.avg_cost
                    else:
                        current_size = positions_store[sid].amount
                        # adjust cost basis:
                        # this should never result in a different value unless
                        # IB doesn't enforce best execution
                        positions_store[sid].amount += pos.position_size
                        if positions_store[sid].amount != 0:
                            mkt_value = positions_store[sid].cost_basis * current_size
                            added_value = pos.avg_cost * pos.position_size
                            positions_store[sid].cost_basis = (mkt_value + added_value) / \
                                                              positions_store[sid].amount

                    portfolio_store.positions_value += pos.market_value
                    portfolio_store.pnl = pos.realized_pnl + pos.unrealized_pnl
                    portfolio_store.positions = positions_store

        return portfolio_store

    def get_transactions(self, event, orders):
        import time

        time.sleep(1)
        efilter = ExecutionFilter()
        efilter.m_symbol = event.sid

        for order in orders:

            # Todo: I need to refactor how executions are summoned, this is currently a huge bottleneck
            # cycle through all executions matching the event sid
            for execution in self.executions(efilter):
                prior_execution = None

                # further filter out any executions not matching the order.id
                if execution.m_orderRef == order.id:

                    # prevent processing of duplicate executions
                    if execution != prior_execution:
                        order_status_vals = (0, 0)

                        # cycle through the order status messages to get transaction details
                        for status in self.order_status(execution.m_orderId):

                            # filter out duplicate transaction messages
                            if (status['remaining'], status['filled']) != order_status_vals:

                                # get execution date
                                date = dt.datetime.strptime(execution.m_time,
                                                            '%Y%m%d %H:%M:%S').replace(tzinfo=pytz.utc)
                                amount = status['filled'] - order_status_vals[1]

                                txn = {'sid': event.sid,
                                       'amount': int(amount),
                                       'dt': date,
                                       'price': status['lastFillPrice'],
                                       'order_id': order.id}

                                transaction = Transaction(**txn)
                                order_status_vals = (status['remaining'], status['filled'])
                                #TODO: pretty sure there is still transactions are being duplicated still
                                if order.status == ORDER_STATUS.OPEN:
                                    yield order, transaction

                    prior_execution = execution













