#!/usr/bin/env python
#
# Copyright 2012 Quantopian, Inc.
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

import matplotlib.pyplot as plt
import pandas as pd
from datetime import datetime
import pytz

from alephnull.algorithm import TradingAlgorithm
from alephnull.utils.factory import load_from_yahoo


class BuyStratasys(TradingAlgorithm):  # inherit from TradingAlgorithm
	"""This is the simplest possible algorithm that does nothing but
	buy 1 apple share on each event.
	"""

	def handle_data(self, data):  # overload handle_data() method
		self.order('SSYS', 100)


if __name__ == '__main__':
	start = datetime(2013, 10, 1, 0, 0, 0, 0, pytz.utc)
	end = datetime(2013, 12, 31, 0, 0, 0, 0, pytz.utc)
	data = load_from_yahoo(stocks=['SSYS'], start=start, end=end)

	simple_algo = BuyStratasys(leverage_restrictions=[200, 1])
	results = simple_algo.run(data)
	fig = plt.figure()
	ax1 = fig.add_subplot(111)
	results.portfolio_value.plot(ax=ax1)
	fig.show()

