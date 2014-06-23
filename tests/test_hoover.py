#!/usr/bin/python
# flake8: noqa

import unittest
from sznqalibs import hoover
import copy
import json
import unittest


class DictPathTest(unittest.TestCase):

    def setUp(self):
        super(DictPathTest, self).setUp()

        class PathyDict(dict, hoover.DictPath):
            pass

        testDict = {
            's': 11,
            'x': {
                'a': 55,
                'hello': {
                    'world': 1, 'sun': 3, 'blackhole': None
                },
                'b': 59
            },
        }

        self.pdict = PathyDict(testDict)

    def testDelSun(self):
        oracle = copy.deepcopy(self.pdict)
        result = copy.deepcopy(self.pdict)
        del oracle['x']['hello']['sun']
        result.delpath("/x/hello/sun")
        self.assertEqual(oracle, result)

    def testGetHello(self):
        oracle = copy.deepcopy(self.pdict['x']['hello'])
        result = self.pdict.getpath("/x/hello")
        self.assertEqual(oracle, result)

    def testSetHello(self):
        oracle = copy.deepcopy(self.pdict)
        result = copy.deepcopy(self.pdict)
        oracle['x']['hello']['sun'] = 'moon'
        result.setpath("/x/hello/sun", 'moon')
        self.assertEqual(oracle, result)

    def testSetNewItem(self):
        oracle = copy.deepcopy(self.pdict)
        result = copy.deepcopy(self.pdict)
        oracle['x']['hullo'] = 'NEW'
        result.setpath("/x/hullo", 'NEW')
        self.assertEqual(oracle, result)

    def testHelloExists(self):
        self.assertTrue(self.pdict.ispath('/x/hello'))

    def testWorldNotExists(self):
        self.assertFalse(self.pdict.ispath('/x/world'))

    def testDelBadPath(self):
        fn = lambda: self.pdict.delpath('/x/hullo')
        self.assertRaises(KeyError, fn)

    def testGetBadPath(self):
        fn = lambda: self.pdict.getpath('/x/hullo')
        self.assertRaises(KeyError, fn)

    def testSetBadPath(self):
        fn = lambda: self.pdict.setpath('/x/hullo/newthing', 1)
        self.assertRaises(KeyError, fn)

    # the scary None

    def testDelNone(self):
        oracle = copy.deepcopy(self.pdict)
        result = copy.deepcopy(self.pdict)
        del oracle['x']['hello']['blackhole']
        result.delpath("/x/hello/blackhole")
        self.assertEqual(oracle, result)

    def testSetNone(self):
        oracle = copy.deepcopy(self.pdict)
        result = copy.deepcopy(self.pdict)
        oracle['x']['hello']['sun'] = None
        result.setpath("/x/hello/sun", None)
        self.assertEqual(oracle, result)

    def testSetNewNone(self):
        oracle = copy.deepcopy(self.pdict)
        result = copy.deepcopy(self.pdict)
        oracle['x']['hullo'] = None
        result.setpath("/x/hullo", None)
        self.assertEqual(oracle, result)

    def testGetNone(self):
        oracle = copy.deepcopy(self.pdict['x']['hello']['blackhole'])
        result = self.pdict.getpath("/x/hello/blackhole")
        self.assertEqual(oracle, result)

    def testNoneExists(self):
        result = self.pdict.ispath('/x/hello/blackhole')
        self.assertTrue(result)


class CartmanTest(unittest.TestCase):

    def sdiff(self, a, b):
        sa = [json.dumps(i) for i in a]
        sb = [json.dumps(i) for i in b]
        diff = set(sa) - set(sb)
        return [json.loads(i) for i in diff]

    def chkoracle(self, o):
        def dups(self):
            so = [json.dumps(i) for i in o]
            return len(o) != len(set(so))
        if dups(o):
            self.logger.warn("duplicates in oracle!")

    def setUp(self):
        super(CartmanTest, self).setUp()

    def compare(self, source, scheme, oracle):
        self.chkoracle(oracle)

        def fmtdiff(diff, word):
            strn = ""
            if diff:
                strn = ("\n----------------------"
                        "\n  %s elements (%s):\n%s"
                        % (word, len(diff), pretty(diff)))
            return strn

        pretty = hoover.jsDump

        cm = hoover.Cartman(source, scheme)
        result = [i for i in cm]

        xtra = self.sdiff(result, oracle)
        miss = self.sdiff(oracle, result)

        err = ""
        err += fmtdiff(miss, 'missing')
        err += fmtdiff(xtra, 'extra')
        return err

    def test_Flat_2of3(self):

        scheme = {
            'a': hoover.Cartman.Iterable,
            'b': hoover.Cartman.Iterable,
        }
        source = {
            'a': [1, 2, 3],
            'b': ['i', 'ii', 'iii'],
            'c': ['I', 'II', 'III'],
        }
        oracle = [
            {'a': 1, 'b': 'i'},
            {'a': 1, 'b': 'ii'},
            {'a': 1, 'b': 'iii'},
            {'a': 2, 'b': 'i'},
            {'a': 2, 'b': 'ii'},
            {'a': 2, 'b': 'iii'},
            {'a': 3, 'b': 'i'},
            {'a': 3, 'b': 'ii'},
            {'a': 3, 'b': 'iii'},
        ]

        err = self.compare(source, scheme, oracle)
        self.assertFalse(err, "errors found: %s\n" % err)

    def test_Deep1(self):

        scheme = {
            'a': hoover.Cartman.Iterable,
            'b': hoover.Cartman.Iterable,
            'x': {
                'h1': hoover.Cartman.Iterable,
                'h2': hoover.Cartman.Iterable,
            }
        }
        source = {
            'a': [1, 2, 3],
            'b': ['i', 'ii', 'iii'],
            'x': {'h1': [101, 102], 'h2': [201, 202]}
        }
        oracle = [

            {'a': 1, 'b': 'i', 'x': {'h1': 101, 'h2': 201}},
            {'a': 1, 'b': 'i', 'x': {'h1': 101, 'h2': 202}},
            {'a': 1, 'b': 'i', 'x': {'h1': 102, 'h2': 201}},
            {'a': 1, 'b': 'i', 'x': {'h1': 102, 'h2': 202}},
            {'a': 1, 'b': 'ii', 'x': {'h1': 101, 'h2': 201}},
            {'a': 1, 'b': 'ii', 'x': {'h1': 101, 'h2': 202}},
            {'a': 1, 'b': 'ii', 'x': {'h1': 102, 'h2': 201}},
            {'a': 1, 'b': 'ii', 'x': {'h1': 102, 'h2': 202}},
            {'a': 1, 'b': 'iii', 'x': {'h1': 101, 'h2': 201}},
            {'a': 1, 'b': 'iii', 'x': {'h1': 101, 'h2': 202}},
            {'a': 1, 'b': 'iii', 'x': {'h1': 102, 'h2': 201}},
            {'a': 1, 'b': 'iii', 'x': {'h1': 102, 'h2': 202}},

            {'a': 2, 'b': 'i', 'x': {'h1': 101, 'h2': 201}},
            {'a': 2, 'b': 'i', 'x': {'h1': 101, 'h2': 202}},
            {'a': 2, 'b': 'i', 'x': {'h1': 102, 'h2': 201}},
            {'a': 2, 'b': 'i', 'x': {'h1': 102, 'h2': 202}},
            {'a': 2, 'b': 'ii', 'x': {'h1': 101, 'h2': 201}},
            {'a': 2, 'b': 'ii', 'x': {'h1': 101, 'h2': 202}},
            {'a': 2, 'b': 'ii', 'x': {'h1': 102, 'h2': 201}},
            {'a': 2, 'b': 'ii', 'x': {'h1': 102, 'h2': 202}},
            {'a': 2, 'b': 'iii', 'x': {'h1': 101, 'h2': 201}},
            {'a': 2, 'b': 'iii', 'x': {'h1': 101, 'h2': 202}},
            {'a': 2, 'b': 'iii', 'x': {'h1': 102, 'h2': 201}},
            {'a': 2, 'b': 'iii', 'x': {'h1': 102, 'h2': 202}},

            {'a': 3, 'b': 'i', 'x': {'h1': 101, 'h2': 201}},
            {'a': 3, 'b': 'i', 'x': {'h1': 101, 'h2': 202}},
            {'a': 3, 'b': 'i', 'x': {'h1': 102, 'h2': 201}},
            {'a': 3, 'b': 'i', 'x': {'h1': 102, 'h2': 202}},
            {'a': 3, 'b': 'ii', 'x': {'h1': 101, 'h2': 201}},
            {'a': 3, 'b': 'ii', 'x': {'h1': 101, 'h2': 202}},
            {'a': 3, 'b': 'ii', 'x': {'h1': 102, 'h2': 201}},
            {'a': 3, 'b': 'ii', 'x': {'h1': 102, 'h2': 202}},
            {'a': 3, 'b': 'iii', 'x': {'h1': 101, 'h2': 201}},
            {'a': 3, 'b': 'iii', 'x': {'h1': 101, 'h2': 202}},
            {'a': 3, 'b': 'iii', 'x': {'h1': 102, 'h2': 201}},
            {'a': 3, 'b': 'iii', 'x': {'h1': 102, 'h2': 202}},
        ]

        err = self.compare(source, scheme, oracle)
        self.assertFalse(err, "errors found: %s\n" % err)

    def test_Scalar(self):

        scheme = {
            'a': hoover.Cartman.Iterable,
            'b': hoover.Cartman.Iterable,
            'il': hoover.Cartman.Scalar,
            'id': hoover.Cartman.Scalar,
            'ii': hoover.Cartman.Scalar,
        }
        source = {
            'a': [1, 2, 3],
            'b': ['i', 'ii', 'iii'],
            'il': [2, 7],
            'id': {'a': 1},
            'ii': 42
        }
        invars = {
            'il': [2, 7], 'id': {'a': 1}, 'ii': 42
        }
        oracle = [
            {'a': 1, 'b': 'i'},
            {'a': 1, 'b': 'ii'},
            {'a': 1, 'b': 'iii'},
            {'a': 2, 'b': 'i'},
            {'a': 2, 'b': 'ii'},
            {'a': 2, 'b': 'iii'},
            {'a': 3, 'b': 'i'},
            {'a': 3, 'b': 'ii'},
            {'a': 3, 'b': 'iii'},
        ]
        for o in oracle:
            o.update(invars)

        err = self.compare(source, scheme, oracle)
        self.assertFalse(err, "errors found: %s\n" % err)

    def test_dataDangling(self):

        scheme = {
            'a': hoover.Cartman.Iterable,
            'b': hoover.Cartman.Iterable,
        }
        source = {
            'a': [1, 2, 3],
            'b': ['i', 'ii', 'iii'],
            'dangling_str': "tr",
            'dangling_dict': {'a': 1},
            'dangling_list': []
        }
        oracle = [
            {'a': 1, 'b': 'i'},
            {'a': 1, 'b': 'ii'},
            {'a': 1, 'b': 'iii'},
            {'a': 2, 'b': 'i'},
            {'a': 2, 'b': 'ii'},
            {'a': 2, 'b': 'iii'},
            {'a': 3, 'b': 'i'},
            {'a': 3, 'b': 'ii'},
            {'a': 3, 'b': 'iii'},
        ]

        err = self.compare(source, scheme, oracle)
        self.assertFalse(err, "errors found: %s\n" % err)

    def test_dataMissing(self):

        scheme = {
            'a': hoover.Cartman.Iterable,
            'b': hoover.Cartman.Iterable,
            'MIA': hoover.Cartman.Iterable,
        }
        source = {
            'a': [1, 2, 3],
            'b': ['i', 'ii', 'iii'],
        }
        oracle = [
            {'a': 1, 'b': 'i'},
            {'a': 1, 'b': 'ii'},
            {'a': 1, 'b': 'iii'},
            {'a': 2, 'b': 'i'},
            {'a': 2, 'b': 'ii'},
            {'a': 2, 'b': 'iii'},
            {'a': 3, 'b': 'i'},
            {'a': 3, 'b': 'ii'},
            {'a': 3, 'b': 'iii'},
        ]

        err = self.compare(source, scheme, oracle)
        self.assertFalse(err, "errors found: %s\n" % err)

    def test_withListIterator(self):

        scheme = {
            'a': hoover.Cartman.Iterable,
            'b': hoover.Cartman.Iterable,
            'ITER': hoover.Cartman.Iterable,
        }
        source = {
            'a': [1, 2, 3],
            'b': ['i', 'ii', 'iii'],
            'ITER': iter(['iterate', 'over', 'me'])
        }
        oracle = [
            {'a': 1, 'b': 'i', 'ITER': 'iterate'},
            {'a': 1, 'b': 'ii', 'ITER': 'iterate'},
            {'a': 1, 'b': 'iii', 'ITER': 'iterate'},
            {'a': 2, 'b': 'i', 'ITER': 'iterate'},
            {'a': 2, 'b': 'ii', 'ITER': 'iterate'},
            {'a': 2, 'b': 'iii', 'ITER': 'iterate'},
            {'a': 3, 'b': 'i', 'ITER': 'iterate'},
            {'a': 3, 'b': 'ii', 'ITER': 'iterate'},
            {'a': 3, 'b': 'iii', 'ITER': 'iterate'},
            {'a': 1, 'b': 'i', 'ITER': 'over'},
            {'a': 1, 'b': 'ii', 'ITER': 'over'},
            {'a': 1, 'b': 'iii', 'ITER': 'over'},
            {'a': 2, 'b': 'i', 'ITER': 'over'},
            {'a': 2, 'b': 'ii', 'ITER': 'over'},
            {'a': 2, 'b': 'iii', 'ITER': 'over'},
            {'a': 3, 'b': 'i', 'ITER': 'over'},
            {'a': 3, 'b': 'ii', 'ITER': 'over'},
            {'a': 3, 'b': 'iii', 'ITER': 'over'},
            {'a': 1, 'b': 'i', 'ITER': 'me'},
            {'a': 1, 'b': 'ii', 'ITER': 'me'},
            {'a': 1, 'b': 'iii', 'ITER': 'me'},
            {'a': 2, 'b': 'i', 'ITER': 'me'},
            {'a': 2, 'b': 'ii', 'ITER': 'me'},
            {'a': 2, 'b': 'iii', 'ITER': 'me'},
            {'a': 3, 'b': 'i', 'ITER': 'me'},
            {'a': 3, 'b': 'ii', 'ITER': 'me'},
            {'a': 3, 'b': 'iii', 'ITER': 'me'},
        ]

        err = self.compare(source, scheme, oracle)
        self.assertFalse(err, "errors found: %s\n" % err)

    def test_withCustomIterator_TypeA(self):

        class ITER_A(object):

            def __init__(self, items):
                self.items = items
                self.n = 0

            def __iter__(self):
                return self

            def next(self):
                try:
                    item = self.items[self.n]
                except IndexError:
                    raise StopIteration
                else:
                    self.n += 1
                    return item

        scheme = {
            'd': {
                'a': hoover.Cartman.Iterable,
                'b': hoover.Cartman.Iterable,
                'ITER_A': hoover.Cartman.Iterable
            }
        }
        source = {
            'd': {
                'a': [1, 2, 3],
                'b': ['i', 'ii', 'iii'],
                'ITER_A': ITER_A(['iterate', 'over', 'him'])
            }
        }
        oracle = [
            {'d': {'a': 1, 'b': 'i', 'ITER_A': 'iterate'}},
            {'d': {'a': 1, 'b': 'ii', 'ITER_A': 'iterate'}},
            {'d': {'a': 1, 'b': 'iii', 'ITER_A': 'iterate'}},
            {'d': {'a': 2, 'b': 'i', 'ITER_A': 'iterate'}},
            {'d': {'a': 2, 'b': 'ii', 'ITER_A': 'iterate'}},
            {'d': {'a': 2, 'b': 'iii', 'ITER_A': 'iterate'}},
            {'d': {'a': 3, 'b': 'i', 'ITER_A': 'iterate'}},
            {'d': {'a': 3, 'b': 'ii', 'ITER_A': 'iterate'}},
            {'d': {'a': 3, 'b': 'iii', 'ITER_A': 'iterate'}},
            {'d': {'a': 1, 'b': 'i', 'ITER_A': 'over'}},
            {'d': {'a': 1, 'b': 'ii', 'ITER_A': 'over'}},
            {'d': {'a': 1, 'b': 'iii', 'ITER_A': 'over'}},
            {'d': {'a': 2, 'b': 'i', 'ITER_A': 'over'}},
            {'d': {'a': 2, 'b': 'ii', 'ITER_A': 'over'}},
            {'d': {'a': 2, 'b': 'iii', 'ITER_A': 'over'}},
            {'d': {'a': 3, 'b': 'i', 'ITER_A': 'over'}},
            {'d': {'a': 3, 'b': 'ii', 'ITER_A': 'over'}},
            {'d': {'a': 3, 'b': 'iii', 'ITER_A': 'over'}},
            {'d': {'a': 1, 'b': 'i', 'ITER_A': 'him'}},
            {'d': {'a': 1, 'b': 'ii', 'ITER_A': 'him'}},
            {'d': {'a': 1, 'b': 'iii', 'ITER_A': 'him'}},
            {'d': {'a': 2, 'b': 'i', 'ITER_A': 'him'}},
            {'d': {'a': 2, 'b': 'ii', 'ITER_A': 'him'}},
            {'d': {'a': 2, 'b': 'iii', 'ITER_A': 'him'}},
            {'d': {'a': 3, 'b': 'i', 'ITER_A': 'him'}},
            {'d': {'a': 3, 'b': 'ii', 'ITER_A': 'him'}},
            {'d': {'a': 3, 'b': 'iii', 'ITER_A': 'him'}},
        ]

        err = self.compare(source, scheme, oracle)
        self.assertFalse(err, "errors found: %s\n" % err)

    def test_withCustomIterator_TypeB(self):

        class ITER_B(object):

            def __init__(self, items):
                self.items = items

            def __getitem__(self, n):
                return self.items[n]

        scheme = {
            'd': {
                'a': hoover.Cartman.Iterable,
                'b': hoover.Cartman.Iterable,
                'ITER_B': hoover.Cartman.Iterable
            }
        }
        source = {
            'd': {
                'a': [1, 2, 3],
                'b': ['i', 'ii', 'iii'],
                'ITER_B': ITER_B(['iterate', 'by', 'him'])
            }
        }
        oracle = [
            {'d': {'a': 1, 'b': 'i', 'ITER_B': 'iterate'}},
            {'d': {'a': 1, 'b': 'ii', 'ITER_B': 'iterate'}},
            {'d': {'a': 1, 'b': 'iii', 'ITER_B': 'iterate'}},
            {'d': {'a': 2, 'b': 'i', 'ITER_B': 'iterate'}},
            {'d': {'a': 2, 'b': 'ii', 'ITER_B': 'iterate'}},
            {'d': {'a': 2, 'b': 'iii', 'ITER_B': 'iterate'}},
            {'d': {'a': 3, 'b': 'i', 'ITER_B': 'iterate'}},
            {'d': {'a': 3, 'b': 'ii', 'ITER_B': 'iterate'}},
            {'d': {'a': 3, 'b': 'iii', 'ITER_B': 'iterate'}},
            {'d': {'a': 1, 'b': 'i', 'ITER_B': 'by'}},
            {'d': {'a': 1, 'b': 'ii', 'ITER_B': 'by'}},
            {'d': {'a': 1, 'b': 'iii', 'ITER_B': 'by'}},
            {'d': {'a': 2, 'b': 'i', 'ITER_B': 'by'}},
            {'d': {'a': 2, 'b': 'ii', 'ITER_B': 'by'}},
            {'d': {'a': 2, 'b': 'iii', 'ITER_B': 'by'}},
            {'d': {'a': 3, 'b': 'i', 'ITER_B': 'by'}},
            {'d': {'a': 3, 'b': 'ii', 'ITER_B': 'by'}},
            {'d': {'a': 3, 'b': 'iii', 'ITER_B': 'by'}},
            {'d': {'a': 1, 'b': 'i', 'ITER_B': 'him'}},
            {'d': {'a': 1, 'b': 'ii', 'ITER_B': 'him'}},
            {'d': {'a': 1, 'b': 'iii', 'ITER_B': 'him'}},
            {'d': {'a': 2, 'b': 'i', 'ITER_B': 'him'}},
            {'d': {'a': 2, 'b': 'ii', 'ITER_B': 'him'}},
            {'d': {'a': 2, 'b': 'iii', 'ITER_B': 'him'}},
            {'d': {'a': 3, 'b': 'i', 'ITER_B': 'him'}},
            {'d': {'a': 3, 'b': 'ii', 'ITER_B': 'him'}},
            {'d': {'a': 3, 'b': 'iii', 'ITER_B': 'him'}},
        ]

        err = self.compare(source, scheme, oracle)
        self.assertFalse(err, "errors found: %s\n" % err)

    def test_BadSchemeBelow(self):

        def fn():

            scheme = {
                'h': 1,
                'p': hoover.Cartman.Iterable,
                'd': hoover.Cartman.Iterable
            }
            source = {
                'h': {
                    'ua': ['ua1', 'ua2']
                },
                'p': ['a', 'b'],
                'd': [False, True]
            }
            iter(hoover.Cartman(source, scheme)).next()

        self.assertRaises(ValueError, fn)

    def test_BadSourceBelow(self):

        def fn():

            scheme = {
                'h': {
                    'ua': hoover.Cartman.Iterable,
                },
                'p': hoover.Cartman.Iterable,
                'd': hoover.Cartman.Iterable
            }
            source = {
                'h': 'NOT A CORRESPONDING OBJECT',
                'p': ['a', 'b'],
                'd': [False, True]
            }
            iter(hoover.Cartman(source, scheme)).next()

        self.assertRaises(ValueError, fn)

    def test_BadMark(self):

        def fn():
            class a_mark(hoover.Cartman._BaseMark):
                pass
            scheme = {
                'a': hoover.Cartman.Iterable,
                'b': hoover.Cartman.Iterable,
                'c': a_mark
            }
            source = dict.fromkeys(scheme.keys(), [])
            iter(hoover.Cartman(source, scheme)).next()

        self.assertRaises(ValueError, fn)


class RuleOpTest(unittest.TestCase):

    # basic cases

    def testAllEmpty(self):
        oracle = True
        result = hoover.RuleOp.Match((hoover.RuleOp.ALL, []), bool)
        self.assertEqual(oracle, result)

    def testAllTrue(self):
        oracle = True
        result = hoover.RuleOp.Match((hoover.RuleOp.ALL, [1, 1, 1]), bool)
        self.assertEqual(oracle, result)

    def testAllMixed(self):
        oracle = False
        result = hoover.RuleOp.Match((hoover.RuleOp.ALL, [1, 0, 1]), bool)
        self.assertEqual(oracle, result)

    def testAllFalse(self):
        oracle = False
        result = hoover.RuleOp.Match((hoover.RuleOp.ALL, [0, 0, 0]), bool)
        self.assertEqual(oracle, result)

    def testAnyEmpty(self):
        oracle = False
        result = hoover.RuleOp.Match((hoover.RuleOp.ANY, []), bool)
        self.assertEqual(oracle, result)

    def testAnyTrue(self):
        oracle = True
        result = hoover.RuleOp.Match((hoover.RuleOp.ANY, [1, 1, 1]), bool)
        self.assertEqual(oracle, result)

    def testAnyMixed(self):
        oracle = True
        result = hoover.RuleOp.Match((hoover.RuleOp.ANY, [1, 0, 1]), bool)
        self.assertEqual(oracle, result)

    def testAnyFalse(self):
        oracle = False
        result = hoover.RuleOp.Match((hoover.RuleOp.ANY, [0, 0, 0]), bool)
        self.assertEqual(oracle, result)

    # nesting

    def testAnyAllTrue(self):
        patt = (hoover.RuleOp.ANY, [(hoover.RuleOp.ALL, [1, 1]), 0, 0])
        oracle = True
        result = hoover.RuleOp.Match(patt, bool)
        self.assertEqual(oracle, result)

    def testAllAnyFalse(self):
        patt = (hoover.RuleOp.ALL, [1, (hoover.RuleOp.ANY, [0, 0]), 1, 1])
        oracle = False
        result = hoover.RuleOp.Match(patt, bool)
        self.assertEqual(oracle, result)

    # error handling

    def testBadOpClass(self):
        class bad_op(object):
            def _match(self):
                return True
        fn = lambda: hoover.RuleOp.Match(((bad_op, [])), bool)
        self.assertRaises(ValueError, fn)

    def testBadOpNonClass(self):
        fn = lambda: hoover.RuleOp.Match((("bad_op", [])), bool)
        self.assertRaises(ValueError, fn)

    def testBadPatternScalar(self):
        fn = lambda: hoover.RuleOp.Match(43, bool)
        self.assertRaises(ValueError, fn)

    def testBadPatternShort(self):
        fn = lambda: hoover.RuleOp.Match((43,), bool)
        self.assertRaises(ValueError, fn)

    def testBadPatternLong(self):
        fn = lambda: hoover.RuleOp.Match((43, 41, 42), bool)
        self.assertRaises(ValueError, fn)

    def testBadItems(self):
        fn = lambda: hoover.RuleOp.Match(((hoover.RuleOp.ALL, 1)), bool)
        self.assertRaises(ValueError, fn)

    # own operator

    def testOwnOp(self):
        class MYOP(hoover._BaseRuleOp):
            def _match(self):
                return True
        oracle = True
        result = hoover.RuleOp.Match((MYOP, [0, 1, 2]), bool)
        self.assertEqual(oracle, result)


class JsDiff(unittest.TestCase):

    def setUp(self):
        self.a = {
            'joe': 31,
            'johnny': 55,
            'twins': {
                'al': 1,
                'bo': 1,
                'ww': 1
            },
            'annie': 1,
            'todo': [
                'buy milk',
                'visit aunt Emma',
                {'buy presents': [
                    'for daddy',
                    'for mommy',
                    'for sister',
                    'for brother'
                ]},
                'stop smoking',
                'make less promises'
            ],
            'stones': [
                'red stone',
                'stone',
                'get stoned'
            ]
        }

        self.b = {
            'joe': 31,
            'johnny': 55,
            'twins': {
                'al': 1,
                'bo': 1,
                'ww': 1
            },
            'annie': 3,
            'todo': [
                'buy milk',
                {'buy presents': [
                    'for sister',
                    'for brother'
                ]},
                'stop smoking',
                'take over the world',
                'make less promises'
            ],
            'tamara': 110,
            'stones': [
                'red stone',
                'moonstone',
                'stone',
                'get stoned'
            ]
        }

    def testDense(self):
        oracle = (
            'aaa ~/A\n'
            ' {\n'
            'a    "annie": 1,\n'
            '     "stones": [\n'
            '     "todo": [\n'
            'a        "visit aunt Emma",\n'
            '             "buy presents": [\n'
            'a                "for daddy",\n'
            'a                "for mommy",\n'
            'bbb ~/B\n'
            ' {\n'
            'b    "annie": 3,\n'
            '     "stones": [\n'
            'b        "moonstone",\n'
            'b    "tamara": 110,\n'
            '     "todo": [\n'
            '             "buy presents": [\n'
            'b        "take over the world",'
        )
        result = hoover.jsDiff(self.a, self.b)
        self.assertEqual(oracle, result)


class DataMatch(unittest.TestCase):

    class sdict(dict):
        pass

    class slist(list):
        pass

    def setUp(self):
        super(DataMatch, self).setUp()

    # dict

    def test_Dict_Ok(self):
        p = { 1: 2 }
        r = { 1: 2, 3: 4 }
        self.assertTrue(hoover.dataMatch(p, r))

    def test_Dict_Nok(self):
        p = { 1: 2 }
        r = { 1: 3, 3: 4 }
        self.assertFalse(hoover.dataMatch(p, r))

    def test_DictDict_Ok(self):
        p = {       'a': { 'A': 'B' } }
        r = { 1: 2, 'a': { 'A': 'B' } }
        self.assertTrue(hoover.dataMatch(p, r))

    def test_DictDict_Nok(self):
        p = {       'a': { 'A': 'B' } }
        r = { 1: 2, 'a': { 'C': 'D' } }
        self.assertFalse(hoover.dataMatch(p, r))

    def test_DictList_Ok(self):
        p = {       3: [ 11, 12 ] }
        r = { 1: 2, 3: [ 10, 11, 12, 13 ] }
        self.assertTrue(hoover.dataMatch(p, r))

    def test_DictList_Nok(self):
        p = {       3: [ 11, 12 ] }
        r = { 1: 2, 3: [ 10, 11, 13 ] }
        self.assertFalse(hoover.dataMatch(p, r))

    # list

    def test_List_Ok(self):
        p = [ 101, 102 ]
        r = [ 101, 103, 102 ]
        self.assertTrue(hoover.dataMatch(p, r))

    def test_List_Nok(self):
        p = [ 101, 102 ]
        r = [ 101, 103 ]
        self.assertFalse(hoover.dataMatch(p, r))

    def test_ListList_Ok(self):
        p = [ 101, ['a', 'b'], 102 ]
        r = [ 101, [1, 'a', 2, 'b'], 103, 102 ]
        self.assertTrue(hoover.dataMatch(p, r))

    def test_ListDict_Ok(self):
        p = [ 101, {'a': 'A'}, 102 ]
        r = [ 101, {'a': 'A', 'b': 'B'}, 103, 102 ]
        self.assertTrue(hoover.dataMatch(p, r))

    def test_ListDict_Nok(self):
        p = [ 101, {'a': 'A'}, 102 ]
        r = [ 101, {'a': 'X', 'b': 'B'}, 103, 102 ]
        self.assertFalse(hoover.dataMatch(p, r))

    # dict/list subclass

    def test_DictPSub_Ok(self):
        p = self.sdict({ 1: 2 })
        r = { 1: 2, 3: 4 }
        self.assertTrue(hoover.dataMatch(p, r))

    def test_DictPSub_Nok(self):
        p = self.sdict({ 1: 2 })
        r = { 1: 3, 3: 4 }
        self.assertFalse(hoover.dataMatch(p, r))

    def test_DictRSub_Ok(self):
        p = { 1: 2 }
        r = self.sdict({ 1: 2, 3: 4 })
        self.assertTrue(hoover.dataMatch(p, r))

    def test_DictRSub_Nok(self):
        p = { 1: 2 }
        r = self.sdict({ 1: 3, 3: 4 })
        self.assertFalse(hoover.dataMatch(p, r))

    def test_DictPRSub_Ok(self):
        p = self.sdict({ 1: 2 })
        r = self.sdict({ 1: 2, 3: 4 })
        self.assertTrue(hoover.dataMatch(p, r))

    def test_DictPRSub_Nok(self):
        p = self.sdict({ 1: 2 })
        r = self.sdict({ 1: 3, 3: 4 })
        self.assertFalse(hoover.dataMatch(p, r))

    def test_ListPSub_Ok(self):
        p = self.slist([ 101, 102 ])
        r = [ 101, 103, 102 ]
        self.assertTrue(hoover.dataMatch(p, r))

    def test_ListPSub_Nok(self):
        p = self.slist([ 101, 102 ])
        r = [ 101, 103 ]
        self.assertFalse(hoover.dataMatch(p, r))

    def test_ListRSub_Ok(self):
        p = [ 101, 102 ]
        r = self.slist([ 101, 103, 102 ])
        self.assertTrue(hoover.dataMatch(p, r))

    def test_ListRSub_Nok(self):
        p = [ 101, 102 ]
        r = self.slist([ 101, 103 ])
        self.assertFalse(hoover.dataMatch(p, r))

    def test_ListPRSub_Ok(self):
        p = self.slist([ 101, 102 ])
        r = self.slist([ 101, 103, 102 ])
        self.assertTrue(hoover.dataMatch(p, r))

    def test_ListPRSub_Nok(self):
        p = self.slist([ 101, 102 ])
        r = self.slist([ 101, 103 ])
        self.assertFalse(hoover.dataMatch(p, r))


if __name__ == "__main__":
    unittest.main()
