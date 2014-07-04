#!/usr/bin/python

import httplib
import operator
import subprocess
import unittest
import urlparse

from sznqalibs import hoover


class BaseCalcDriver(hoover.BaseTestDriver):

    def __init__(self):
        super(BaseCalcDriver, self).__init__()
        self._mandatory_args = ['op', 'a', 'b']

        def bailout_on_zerodiv(argset):
            if argset['op'] == 'div':
                return argset['b'] == 0
            return False

        self.bailouts = [bailout_on_zerodiv]


class PyCalcDriver(BaseCalcDriver):

    def _get_data(self):
        ops = {
            'add': lambda a, b: float(a) + b,
            'sub': lambda a, b: float(a) - b,
            'mul': lambda a, b: float(a) * b,
            'div': lambda a, b: float(a) / b,
        }
        a = self._args['a']
        b = self._args['b']
        op = self._args['op']
        self.data['result'] = ops[op](a, b)


class CgiCalcDriver(BaseCalcDriver):

    def __init__(self):
        super(CgiCalcDriver, self).__init__()
        self._mandatory_settings = ['uri']

    def _get_data(self):
        pq = "op=%(op)s&a=%(a)s&b=%(b)s" % self._args
        parsed_url = urlparse.urlparse(self._settings['uri'])
        conn = httplib.HTTPConnection(parsed_url.hostname)
        conn.request("GET", "%s?%s" % (parsed_url.path, pq))
        resp = conn.getresponse()
        assert resp.status == 200
        self.data['result'] = float(resp.read().strip())


class CliCalcDriver(BaseCalcDriver):

    def __init__(self):
        super(CliCalcDriver, self).__init__()
        self._mandatory_settings = ['cmd']

    def _get_data(self):
        cmd = [
            self._settings['cmd'],
            self._args['op'],
            str(self._args['a']),
            str(self._args['b']),
        ]
        out = subprocess.check_output(cmd)
        self.data['result'] = float(out.strip())


class TestCase(unittest.TestCase):

    def setUp(self):
        self.driver_settings = {
            'uri': "http://myserver/cgi-bin/calc.cgi",
            'cmd': "./calc.sh"
        }
        self.scheme = dict.fromkeys(['op', 'a', 'b'], hoover.Cartman.Iterable)

    def test_using_rt(self):
        argsrc = hoover.Cartman({
            'op': ['add', 'sub', 'mul', 'div'],
            'a': [-10, -1, 1, 10, 1000],
            'b': [-10, -1, 1, 10, 1000],
            }, self.scheme
        )
        tests = [
            (operator.eq, PyCalcDriver, CliCalcDriver),
            (operator.eq, PyCalcDriver, CliCalcDriver),
        ]
        tracker = hoover.regression_test(argsrc, tests, self.driver_settings)
        print hoover.jsDump(tracker.getstats())
        if tracker.errors_found():
            self.fail(tracker.format_report())


if __name__ == '__main__':
    unittest.main()
