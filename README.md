AlephNull
=======
AlephNull is a python module for the development
and execution of algorithmic trading strategies.
The library is being developed under commission
by [Carter Bain](carterbain.com). 

The module is built on top of the Zipline library, 
the backbone of the web-based backtesting
platform [Quantopian](https://www.quantopian.com) 

The aim of the module is to extend the features
of Zipline, for use within an institutional framework. 
We hope to use the module to standardize research across 
our trade desk and support live execution across all 
asset classes for our clients.

Dependencies (zipline)
------------

* Python (>= 2.7.2)
* numpy (>= 1.6.0)
* pandas (>= 0.9.0)
* pytz
* msgpack-python
* Logbook
* blist
* requests
* delorean
* iso8601
* [python-dateutil](https://pypi.python.org/pypi/python-dateutil) (>= 2.1)

Style Guide
------------

To ensure that changes and patches are focused on behavior changes,
the zipline codebase adheres to both PEP-8,
<http://www.python.org/dev/peps/pep-0008/>, and pyflakes,
<https://launchpad.net/pyflakes/>.

The maintainers check the code using the flake8 script,
<https://github.com/bmcustodio/flake8>, which is included in the
requirements_dev.txt.

Before submitting patches or pull requests, please ensure that your
changes pass ```flake8 zipline tests``` and ```nosetests```

Build Status
============

[![Build Status](https://travis-ci.org/quantopian/zipline.png)](https://travis-ci.org/quantopian/zipline)

Contact
=======
brandon.ogle@carterbain.com
For questions about zipline, please contact <opensource@quantopian.com>.
