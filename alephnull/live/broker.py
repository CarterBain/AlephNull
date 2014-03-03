__author__ = 'oglebrandon'

from logbook import Logger

from ib.ext.Contract import Contract
from ib.ext.Order import Order as IBOrder
from alephnull.finance.blotter import Blotter
from alephnull.utils.protocol_utils import Enum


# Medici fork of IbPy
# https://github.com/CarterBain/Medici
from ib.client.IBrokers import IBClient
import alephnull.protocol as zp
import datetime as dt

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
        contract.m_exchange = 'USD'

        if hasattr(order_obj, 'contract'):
            # This is a futures contract
            contract.m_secType = 'FUT'
            contract.m_exchange = 'GLOBEX'
            contract.m_expiry = order_obj.contract

        else:
            # This is a stock
            contract.m_secType = 'STK'
            contract.m_exchange = 'SMART'

        return self.place_order(contract, ib_order)


class LiveExecution(IBClient):
    """Client connection to the Interactive Brokers API
       inherits from IBClient in the Medici fork of IbPy
    """

    def __init__(self, call_msg):
        super(LiveExecution, self).__init__(call_msg=call_msg)
        self._blotter = LiveBlotter()
        self._blotter.place_order = self.place_order

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