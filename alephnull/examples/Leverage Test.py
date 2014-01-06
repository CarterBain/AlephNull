#========================================================================
#                           Leverage Demo
#========================================================================
# This example allocates all of the cash equally among the symbols passed,
# after the order is filled or cancelled a offsetting order divests the
# capital. This is used to ensure that opening orders are tested for
# leverage whereas offsetting orders are not, so long as the net
# transaction results in a neutral position
#========================================================================

import datetime as dt

from pandas.io.data import DataReader
import matplotlib.pyplot as plt

from alephnull.algorithm import TradingAlgorithm


__author__ = 'Brandon Ogle'
#========================================================================
#                     brandon.ogle@carterbain.com
#========================================================================




database = DataReader(['XLF', 'XLB', 'XLP', 'XLK', 'XLE'], 'yahoo',
                      start=dt.datetime.utcnow() - dt.timedelta(days=5000
                      ))['Adj Close'].tz_localize('UTC')


class BuySell(TradingAlgorithm):
	def initialize(self):
		self.days_in_trade = 0
		self.id_ = None

	def handle_data(self, data):
		for sym in data.keys():
			if self.portfolio.positions[sym].amount == 0:
				order = (self.portfolio.cash / data[sym].price / len(data.keys()))
				order -= order % 10
				self.id_ = self.order(sym, order)
				self.days_in_trade = 0

			elif self.blotter.orders[self.id_].amount == self.blotter.orders[self.id_].filled or \
							self.blotter.orders[self.id_].status == 2:

				self.id_ = self.order(sym, -self.portfolio.positions[sym].amount)
				self.days_in_trade = 0
		self.days_in_trade += 1


trade = BuySell()
results = trade.run(database)

fig = plt.figure(figsize=(18, 6))
ax = fig.add_subplot(111)
results['portfolio_value'].plot(ax=ax)

fig.show()

#waits for user input before closing chart
raw_input()