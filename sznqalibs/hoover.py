# coding=utf-8

import collections
import csv
import difflib
import hashlib
import inspect
import itertools
import json
import operator
import time
from copy import deepcopy


###############################################################################
## The Motor                                                                 ##
###############################################################################

def regression_test(argsrc, tests, driver_settings, cleanup_hack=None,
                    apply_hacks=None, on_next=None):
    """Perform regression test with argsets from `argsrc`.

    For each argset pulled from source, performs one comparison
    per driver pair in `tests`, which is list of tuples with
    comparison function and pair of test driver classes: `(operator,
    oracle_class, result_class)`.  (The classes are assumed to
    be sub-classes of `hoover.BaseTestDriver`.)

    `driver_settings` is a dictionary supposed to hold environmental
    values for all the drivers, the keys having form "DriverName.
    settingName".  Each driver is then instantiated with this
    dict, and gets a copy of the dict with settings only intended
    for itself (and the "DriverName" part stripped).

    If comparison fails, report is generated using `hoover.jsDiff()`,
    and along with affected arguments stored in `hoover.Tracker`
    instance, which is finally used as a return value.  This instance
    then contains method for basic stats as well as method to format
    the final report and a helper method to export argument sets
    as a CSV files.

    Supports hacks, which are a data transformations performed by
    `hoover.TinyCase` class and are intended to avoid known bugs
    and anomalies (`apply_hacks`) or clean up data structures of
    irrelevant data (`cleanup_hack`, performed only if the comparison
    function provided along with driver pair is not "equals").

    A function can be provided as `on_next` argument, that will be
    called after pulling each argument set, with last argument set
    (or `None`) as first argument and current one as second argument.
    """

    # TODO: do not parse driver_settings thousands of times (use a view class?)

    on_next = on_next if on_next else lambda a, b: None
    apply_hacks = apply_hacks if apply_hacks else []

    tracker = Tracker()
    last_argset = None

    all_classes = set(reduce(lambda a, b: a+b,
                             [triple[1:] for triple in tests]))

    counter = StatCounter()

    for argset in argsrc:

        on_start = time.time()
        on_next(argset, last_argset)
        counter.add('on_next', time.time() - on_start)

        ## load the data first, only once for each driver
        #
        data = {}
        for aclass in all_classes:
            try:
                aclass.check_values(argset)
            except NotImplementedError:         # let them bail out
                counter.count_for(aclass, 'bailouts')
                pass
            else:
                data[aclass], duration, overhead = get_data_and_stats(
                    aclass, argset, driver_settings)
                counter.count_for(aclass, 'calls')
                counter.add_for(aclass, 'duration', duration)
                counter.add_for(aclass, 'overhead', overhead)

        for match_op, oclass, rclass in tests:

            # skip test if one of classes bailed out on the argset
            if oclass not in data or rclass not in data:
                continue

            diff = None

            case = TinyCase({
                'argset': argset,
                'oracle': deepcopy(data[oclass]),
                'result': deepcopy(data[rclass]),
                'oname': oclass.__name__,
                'rname': rclass.__name__
            })

            hacks_done = sum([case.hack(h) for h in apply_hacks])
            counter.add_for(oclass, 'ohacks', hacks_done)
            counter.add_for(rclass, 'rhacks', hacks_done)
            counter.add('hacks', hacks_done)
            counter.add('hacked_cases', (1 if hacks_done else 0))

            if not match_op(case['oracle'], case['result']):

                # try to clean up so that normally ignored items
                # do not clutter up the report
                if not match_op == operator.eq:
                    case.hack(cleanup_hack)
                    if match_op(case['oracle'], case['result']):
                        raise RuntimeError("cleanup ate error")

                diff = jsDiff(dira=case['oracle'],
                              dirb=case['result'],
                              namea=case['oname'],
                              nameb=case['rname'])

            tracker.update(diff, argset)

            counter.count('cases')

        tracker.argsets_done += 1
        last_argset = argset

        counter.count('argsets')

    tracker.driver_stats = counter.all_stats()
    return tracker


def get_data_and_stats(driverClass, argset, driver_settings):
    """Run test with given driver"""
    start = time.time()
    d = driverClass()
    d.setup(driver_settings, only_own=True)
    d.run(argset)
    return (d.data, d.duration, time.time() - d.duration - start)


def get_data(driverClass, argset, driver_settings):
    """Run test with given driver"""
    d = driverClass()
    d.setup(driver_settings, only_own=True)
    d.run(argset)
    return d.data


###############################################################################
## The Pattern                                                               ##
###############################################################################

class _BaseRuleOp():

    def __init__(self, items, item_ok):
        self._items = items
        self._item_ok = item_ok

    def _eval(self, item):
        try:                                    # it's a pattern! (recurse)
            return RuleOp.Match(item, self._item_ok)
        except ValueError:                      # no, it's something else...
            return self._item_ok(item)

    def __nonzero__(self):
        try:
            return self._match()
        except TypeError:
            raise ValueError("items must be an iterable: %r" % self._items)


class RuleOp():

    class ALL(_BaseRuleOp):

        def _match(self):
            return all(self._eval(item) for item in self._items)

    class ANY(_BaseRuleOp):

        def _match(self):
            return any(self._eval(item) for item in self._items)

    @staticmethod
    def Match(pattern, item_ok):
        """Evaluate set of logically structured patterns using passed function.

        pattern has form of `(op, [item1, item2, ...])` where op can be any of
        pre-defined logical operators (`ALL`/`ANY`, I doubt you will ever need
        more) and item_ok is a function that will be used to evaluate each one
        in the list.  In case an itemN is actually pattern as well, it will be
        recursed into, passing the item_ok on and on.

        Note that there is no data to evaluate "against",  you can use closure
        if you need to do that.
        """

        try:
            op, items = pattern
        except TypeError:
            raise ValueError("pattern is not a tuple: %r" % pattern)
        try:
            assert issubclass(op, _BaseRuleOp)
        except TypeError:
            raise ValueError("invalid operator: %r" % op)
        except AssertionError:
            raise ValueError("invalid operator class: %s" % op.__name__)
        return bool(op(items, item_ok))


###############################################################################
## The Path                                                                  ##
###############################################################################

class DictPath():
    """Mixin that adds "path-like" behavior to the top dict of dicts.

    See TinyCase for description"""

    DIV = "/"

    class Path():

        def __init__(self, path, div):
            self.DIV = div
            self._path = path

        def _validate(self):
            try:
                assert self._path.startswith(self.DIV)
            except (AttributeError, AssertionError):
                raise ValueError("invalid path: %r" % self._path)

        def stripped(self):
            return self._path.lstrip(self.DIV)

    @classmethod
    def __s2path(cls, path):
        return cls.Path(path, cls.DIV)

    @classmethod
    def __err_path_not_found(cls, path):
        raise KeyError("path not found: %s" % path)

    @classmethod
    def __getitem(cls, dct, key):
        if cls.DIV in key:
            frag, rest = key.split(cls.DIV, 1)
            subdct = dct[frag]
            result = cls.__getitem(subdct, rest)
        else:
            result = dct[key]
        return result

    @classmethod
    def __setitem(cls, dct, key, value):
        if cls.DIV not in key:
            dct[key] = value
        else:
            frag, rest = key.split(cls.DIV, 1)
            subdct = dct[frag]
            cls.__setitem(subdct, rest, value)

    @classmethod
    def __delitem(cls, dct, key):
        if cls.DIV not in key:
            del dct[key]
        else:
            frag, rest = key.split(cls.DIV, 1)
            subdct = dct[frag]
            return cls.__delitem(subdct, rest)

    ## public methods
    #

    def getpath(self, path):
        try:
            return self.__getitem(self, self.__s2path(path).stripped())
        except (TypeError, KeyError):
            self.__err_path_not_found(path)

    def setpath(self, path, value):
        try:
            self.__setitem(self, self.__s2path(path).stripped(), value)
        except (TypeError, KeyError):
            self.__err_path_not_found(path)

    def delpath(self, path):
        try:
            self.__delitem(self, self.__s2path(path).stripped())
        except (TypeError, KeyError):
            self.__err_path_not_found(path)

    def ispath(self, path):
        try:
            self.getpath(path)
            return True
        except KeyError:
            return False


###############################################################################
## The Case                                                                  ##
###############################################################################

class TinyCase(dict, DictPath):
    """Abstraction of the smallest unit of testing.

    This class is intended to hold relevant data after the actual test
    and apply transformations (hacks) as defined by rules.

    The data form (self) is:

        {
            'argset': {},   # argset as fed into `BaseTestDriver.run`
            'oracle': {},   # data as returned from oracle driver's `run()`
            'result': {},   # data as returned from result driver's `run()`
            'oname': "",    # name of oracle driver's class
            'rname': ""     # name of result driver's class
        }

    The transformation is done using the `TinyCase.hack()` method to which
    a list of rules is passed.  Each rule is applied, and rules are expected
    to be in a following form:

        {
            'drivers': [{}],        # list of structures to match against self
            'argsets': [{}],        # -ditto-
            'action_name': <Arg>    # an action name with argument
        }

    For each of patterns ('drivers', argsets') present, match against self
    is done using function `hoover.dataMatch`, which is basically a recursive
    test if the pattern is a subset of the case.  If none of results is
    negative (i.e. both patterns missing results in match), any known actions
    included in the rule are called.  Along with action name a list or a dict
    providing necessary parameters is expected: this is simply passed as only
    parameter to corresponding method.

    Actions use specific way how to address elements in the structures
    saved in the oracle and result keys provided by `DictPath`, which makes
    it easy to define rules for arbitrarily complex dictionary structures.
    The format resembles to Unix path, where "directories" are dict
    keys and "root" is the `self` of the `TinyCase` instance:

        /oracle/temperature
        /result/stats/word_count

    Refer to each action's docstring for descriprion of their function
    as well as expected format of argument.  The name of action as used
    in the reule is the name of method without leading 'a_'.

    Warning: All actions will silently ignore any paths that are invalid
             or leading to non-existent data!
             (This does not apply to a path leading to `None`.)
    """

    def a_exchange(self, action):
        """Exchange value A for value B.

        Expects a dict, where key is a tuple of two values `(a, b)` and
        value is a list of paths.  For each key, it goes through the
        paths and if the value equals `a` it is set to `b`.
        """
        for (oldv, newv), paths in action.iteritems():
            for path in paths:
                try:
                    curv = self.getpath(path)
                except KeyError:
                    continue
                else:
                    if curv == oldv:
                        self.setpath(path, newv)

    def a_format_str(self, action):
        """Convert value to a string using format string.

        Expects a dict, where key is a format string, and value is a list
        of paths.  For each record, the paths are traversed, and value is
        converted to string using the format string and the `%` operator.

        This is especially useful for floats which you may want to trim
        before comparison, since direct comparison of floats is unreliable
        on some architectures.
        """
        for fmt, paths in action.iteritems():
            for path in paths:
                if self.ispath(path):
                    new = fmt % self.getpath(path)
                    self.setpath(path, new)

    def a_even_up(self, action):
        """Even up structure of both dictionaries.

        Expects a list of two-element tuples `('/dict/a', '/dict/b')`
        containing pairs of path do simple dictionaries.

        Then the two dicts are altered to have same structure: if a key
        in dict "a" is missing in dict "b", it is set to `None` in "b" and
        vice-versa,
        """
        for patha, pathb in action:
            try:
                a = self.getpath(patha)
                b = self.getpath(pathb)
            except KeyError:
                continue
            else:
                for key in set(a.keys()) | set(b.keys()):
                    if key in a and key in b:
                        pass    # nothing to do here
                    elif key in a and a[key] is None:
                        b[key] = None
                    elif key in b and b[key] is None:
                        a[key] = None
                    else:
                        pass    # bailout: odd key but value is *not* None

    def a_remove(self, action):
        """Remove elements from structure.

        Expects a simple list of paths that are simply deleted fro, the
        structure.
        """
        for path in action:
            if self.ispath(path):
                self.delpath(path)

    def a_round(self, action):
        """Round a (presumably) float using tha `float()` built-in.

        Expects dict with precision (ndigits, after the dot) as a key and
        list of paths as value.
        """
        for ndigits, paths in action.iteritems():
            for path in paths:
                try:
                    f = self.getpath(path)
                except KeyError:
                    pass
                else:
                    self.setpath(path, round(f, ndigits))

    known_actions = {'remove': a_remove,
                     'even_up': a_even_up,
                     'format_str': a_format_str,
                     'exchange': a_exchange,
                     'round': a_round}

    def hack(self, ruleset):
        """Apply action from each rule, if patterns match."""

        def driver_matches():
            if 'drivers' not in rule:
                return True
            else:
                return any(dataMatch(p, self)
                           for p in rule['drivers'])

        def argset_matches():
            if 'argsets' not in rule:
                return True
            else:
                return any(dataMatch(p, self)
                           for p in rule['argsets'])

        matched = False
        cls = self.__class__
        for rule in ruleset:
            if driver_matches() and argset_matches():
                matched = True
                for action_name in cls.known_actions:
                    if action_name in rule:
                        cls.known_actions[action_name](self, rule[action_name])
        return matched


###############################################################################
## Drivers                                                                   ##
###############################################################################

class DriverError(Exception):
    """Error encountered when obtaining driver data"""

    def __init__(self, message, driver):
        self.message = message
        self.driver = driver

    def __str__(self):

        result = ("\n\n"
                  "  type: %s\n"
                  "  message: %s\n"
                  "  driver: %s\n"
                  "  args: %s\n"
                  "  settings: %s\n"
                  % (self.message.__class__.__name__,
                     self.message,
                     self.driver.__class__.__name__,
                     self.driver._args,
                     self.driver._settings))

        return result


class DriverDataError(Exception):
    """Error encountered when decoding or normalizing driver data"""

    def __init__(self, exception, driver):
        self.exception = exception
        self.driver = driver

    def __str__(self):

        result = ("%s: %s\n"
                  "  class: %s\n"
                  "  args: %s\n"
                  "  data: %s\n"
                  % (self.exception.__class__.__name__, self.exception,
                     self.driver.__class__.__name__,
                     json.dumps(self.driver._args, sort_keys=True, indent=4),
                     json.dumps(self.driver.data, sort_keys=True, indent=4)))
        return result


class BaseTestDriver(object):
    """Base class for test drivers used by `hoover.regression_test` and others.

    This class is used to create a test driver, which is an abstraction
    and encapsulation of the system being tested.  Or, the driver in fact
    can be just a "mock" driver that provides data for comparison with
    a "real" driver.

    The minimum you need to create a working driver is to implement a working
    `self._get_data` method that sets `self.data`.  Any exception from this
    method will be re-raised as DriverError with additional information.

    Also, you can set self.duration (in fractional seconds, as returned by
    standard time module) in the _get_data method, but if you don't, it is
    measured for you as time the method call took.  This is useful if you
    need to fetch the data from some other driver or a gateway, and you
    have better mechanism to determine how long the action would take "in
    real life".

    For example, if we are testing a Java library using a Py4J gateway,
    we need to do some more conversions outside our testing code just to
    be able to use the data in our Python test.  We don't want to include
    this in the "duration", since we are measuring the Java library, not the
    Py4J GW (or our ability to perform the conversions optimally).  So we
    do our measurement within the Java machine and pass the result to the
    Python driver.

    Optionally, you can:

    *   Make an __init__ and after calling base __init__, set

        *   `self._mandatory_args`, a list of keys that need to be present
            in `args` argument to `run()`

        *   and `self._mandatory_settings`, a list of keys that need to be
            present in the `settings` argument to `__init__`

    *   implement methods

        *   `_decode_data` and `_normalize_data`, which are intended to decode
             the data from any raw format it is received, and to prepare it
             for comparison in test,

        *   and `_check_data`, to allow for early detection of failure,

        from which any exception is re-raised as a DriverDataError with
        some additional info

    *   set "bailouts", a list of functions which, when passed "args"
        argument, return true to indicate that driver is not able to
        process these values (see below for explanation).  If any of
        these functions returns true, NotImplementedError is raised.

    The expected workflow when using the driver is:

        # 1. sub-class hoover.BaseTestDriver
        # 2. prepare settings and args
        MyDriver.check_values(args)     # optional, to force bailouts ASAP
        d = MyDriver()
        d.setup(settings)
        d.run(args)
        assert d.data, "no data"        # evaluate the result...
        assert d.duration < 1           # duration of _get_data in seconds

    Note on bailouts:  Typical strategy for which the driver is intended is
    that each possible combination of `args` is exhausted, and results from
    multiple drivers are compared to evaluate if driver, i.e. system in
    question is O.K.

    The bailouts mechanism is useful in cases, where for a certain system,
    a valid combination of arguments would bring the same result as another,
    so there is basically no value in testing both of them.

    Example might be a system that does not support a binary flag and
    behaves as if it was "on": you can simply make the test driver
    accept the option but "bail out" any time it is "off", therefore
    skipping the time-and-resource-consuming test.
    """

    bailouts = []

    ##
    #  internal methods
    #

    def __init__(self):
        self.data = {}
        self.duration = None
        self._args = {}
        self._mandatory_args = []
        self._mandatory_settings = []
        self._settings = {}
        self._setup_ok = False

    def __check_mandatory(self):
        """validate before run()"""
        for key in self._mandatory_args:
            assert key in self._args, "missing arg: '%s'" % key
        for key in self._mandatory_settings:
            assert key in self._settings, "missing setting: '%s'" % key

    def __cleanup_data(self):
        """remove hidden data; e.g. what was only there for _check_data"""
        for key in self.data.keys():
            if key.startswith("_"):
                del self.data[key]

    ##
    #  virtual methods
    #

    def _check_data(self):
        """Early check for failure"""
        pass

    def _decode_data(self):
        """Decode from raw data as brought by _get_data"""
        pass

    def _normalize_data(self):
        """Preare data for comparison (e.g. sort, split, trim...)"""
        pass

    ##
    #  public methods
    #

    @classmethod
    def check_values(cls, args=None):
        """check args in advance before running or setting up anything"""
        for fn in cls.bailouts:
            if fn(args):
                raise NotImplementedError(inspect.getsource(fn))

    def setup(self, settings, only_own=False):
        """Load settings. only_own means that only settings that belong to us
        are loaded ("DriverClass.settingName", the first discriminating part
        is removed)"""
        if only_own:
            for ckey in settings.keys():
                driver_class_name, setting_name = ckey.split(".", 2)
                if self.__class__.__name__ == driver_class_name:
                    self._settings[setting_name] = settings[ckey]
        else:
            self._settings = settings
        self._setup_ok = True

    def run(self, args):
        """validate, run and store data"""

        self._args = args
        assert self._setup_ok, "run() before setup()?"
        self.__class__.check_values(self._args)
        self.__check_mandatory()
        start = time.time()
        try:
            self._get_data()        # run the test, i.e. obtain raw data
        except StandardError as e:
            raise DriverError(e, self)
        self.duration = (time.time() - start if self.duration is None
                         else self.duration)
        try:
            self._decode_data()     # decode raw data
            self._normalize_data()  # normalize decoded data
            self._check_data()      # perform arbitrarty checking
        except StandardError, e:
            raise DriverDataError(e, self)
        self.__cleanup_data()   # cleanup (remove data['_*'])


class MockDriverTrue(BaseTestDriver):
    """A simple mock driver, always returning True"""

    def _get_data(self, args):
        self.data = True


###############################################################################
## Helpers                                                                   ##
###############################################################################

class StatCounter(object):
    """A simple counter with formulas support."""

    def __init__(self):
        self.generic_stats = {}
        self.driver_stats = {}
        self.formulas = {}
        self._born = time.time()

    def _register(self, dname):
        self.driver_stats[dname] = {
            'calls': 0,
            'rhacks': 0,
            'ohacks': 0,
            'duration': 0,
            'overhead': 0
        }

        ##
        ## Formulas.  A lot of them.
        ##

        ## cumulative duration/overhead; just round to ms
        #
        self.add_formula(dname + '_overhead',
                         lambda g, d: int(1000 * d[dname]['overhead']))
        self.add_formula(dname + '_duration',
                         lambda g, d: int(1000 * d[dname]['duration']))

        ## average (per driver call) overhead/duration
        #
        self.add_formula(
            dname + '_overhead_per_call',
            lambda g, d: int(1000 * d[dname]['overhead'] / d[dname]['calls'])
        )
        self.add_formula(
            dname + '_duration_per_call',
            lambda g, d: int(1000 * d[dname]['duration'] / d[dname]['calls'])
        )

        ## grand totals in times: driver time, loop overhead
        #
        def gtotal_drivertime(g, d):
            driver_time = (sum(s['overhead'] for s in d.values())
                           + sum(s['duration'] for s in d.values()))
            return int(1000 * driver_time)

        def gtotal_loop_overhead(g, d):
            driver_time = gtotal_drivertime(g, d)
            onnext_time = int(1000 * g['on_next'])
            age = int(1000 * (time.time() - self._born))
            return age - driver_time - onnext_time

        self.add_formula('gtotal_drivertime', gtotal_drivertime)
        self.add_formula('gtotal_loop_overhead', gtotal_loop_overhead)
        self.add_formula('gtotal_loop_onnext',
                         lambda g, d: int(1000 * g['on_next']))

        ## average (per driver call) overhead/duration
        #
        self.add_formula(
            'cases_hacked',
            lambda g, d: round(100 * float(g['hacked_cases']) / g['cases'], 2)
        )

    def _computed_stats(self):
        computed = dict.fromkeys(self.formulas.keys())
        for fname, fml in self.formulas.iteritems():
            try:
                v = fml(self.generic_stats, self.driver_stats)
            except ZeroDivisionError:
                v = None
            computed[fname] = v
        return computed

    def add_formula(self, vname, formula):
        """Add a function to work with generic_stats, driver_stats."""
        self.formulas[vname] = formula

    def add(self, vname, value):
        """Add a value to generic stat counter."""
        if vname in self.generic_stats:
            self.generic_stats[vname] += value
        else:
            self.generic_stats[vname] = value

    def add_for(self, dclass, vname, value):
        """Add a value to driver stat counter."""
        dname = dclass.__name__
        if dname not in self.driver_stats:
            self._register(dname)
        if vname in self.driver_stats[dname]:
            self.driver_stats[dname][vname] += value
        else:
            self.driver_stats[dname][vname] = value

    def count(self, vname):
        """Alias to add(vname, 1)"""
        self.add(vname, 1)

    def count_for(self, dclass, vname):
        """Alias to add_for(vname, 1)"""
        self.add_for(dclass, vname, 1)

    def all_stats(self):
        """Compute stats from formulas and add them to colledted data."""
        stats = self.generic_stats
        for dname, dstats in self.driver_stats.iteritems():
            for key, value in dstats.iteritems():
                stats[dname + "_" + key] = value
        stats.update(self._computed_stats())
        return stats


class Tracker(dict):
    """Error tracker to allow for usable reports from huge regression tests.

    Best used as a result bearer from `regression_test`, this class keeps
    a simple in-memory "database" of errors seen during the regression
    test, and implements few methods to access the data.

    The basic usage is:

         1. Instantiate (no parameters)

         2. Each time you have a result of a test, you pass it to `update()`
            method along with the argument set (as a single object, typically
            a dict) that caused the error.

            If boolean value of the result is False, the object is thrown away
            and nothing happen.  Otherwise, its string value is used as a key
            under which the argument set is saved.

            As you can see, the string is supposed to be ''as deterministic
            as possible'', i.e. it should provide as little information
            about the error as is necessary.  Do not include any timestamps
            or "volatile" values.

         3. At final stage, you can retrieve statistics as how many (distinct)
            errors have been recorded, what was the duration of the whole test,
            how many times `update()` was called, etc.

         4. Optionally, you can also call `format_report()` to get a nicely
            formatted report with list of arguments for each error string.

         5. Since in bigger tests, argument lists can grow really large,
            complete lists are not normally printed.  Instead, you can use
            `write_stats_csv()`, which will create one CSV per each error,
            named as first 7 chars of its SHA1 (inspired by Git).

            Note that you need to pass an existing writable folder path.
    """

    ##
    #  internal methods
    #

    def __init__(self):
        self._start = time.time()
        self._db = {}
        self.tests_done = 0
        self.tests_passed = 0
        self.argsets_done = 0
        self.driver_stats = {}

    def _csv_fname(self, errstr, prefix):
        """Format name of file for this error string"""
        return '%s/%s.csv' % (prefix, self._eid(errstr))

    def _eid(self, errstr):
        """Return EID for the error string (first 7 chars of SHA1)."""
        return hashlib.sha1(errstr).hexdigest()[:7]

    def _insert(self, errstr, argset):
        """Insert the argset into DB."""
        if not errstr in self._db:
            self._db[errstr] = []
        self._db[errstr].append(argset)

    def _format_error(self, errstr, max_aa=0):
        """Format single error for output."""
        argsets_affected = self._db[errstr]
        num_aa = len(argsets_affected)

        # trim if list is too long for Jenkins
        argsets_shown = argsets_affected
        if max_aa and (num_aa > max_aa):
            div = ["[...] not showing %s cases, see %s.csv for full list"
                   % (num_aa - max_aa, self._eid(errstr))]
            argsets_shown = argsets_affected[0:max_aa] + div

        # format error
        formatted_aa = "\n".join([str(arg) for arg in argsets_shown])
        return ("~~~ ERROR FOUND (%s) ~~~~~~~~~~~~~~~~~~~~~~~~~\n"
                "--- error string: -----------------------------------\n%s\n"
                "--- argsets affected (%d) ---------------------------\n%s\n"
                % (self._eid(errstr), errstr, num_aa, formatted_aa))

    ##
    #  public methods
    #

    def errors_found(self):
        """Return number of non-distinct errors in db."""
        return bool(self._db)

    def format_report(self, max_aa=0):
        """Return complete report formatted as string."""
        error_list = "\n".join([self._format_error(e, max_aa=max_aa)
                                for e in self._db])
        return ("Found %(total_errors)s (%(distinct_errors)s distinct) errors"
                " in %(tests_done)s tests with %(argsets)s argsets"
                " (duration: %(time)ss):"
                % self.getstats()
                + "\n\n" + error_list)

    def getstats(self):
        """Return basic and driver stats

            argsets_done - this should must be raised by outer code,
                           once per each unique argset
            tests_done   - how many times Tracker.update() was called
            distinct_errors - how many distinct errors (same `str(error)`)
                           were seen by Tracker.update()
            total_errors - how many times `Tracker.update()` saw an
                           error, i.e. how many argsets are in DB
            time         - how long since init (seconds)
        """

        def total_errors():
            return reduce(lambda x, y: x + len(y), self._db.values(), 0)

        stats = {
            "argsets": self.argsets_done,
            "tests_done": self.tests_done,
            "distinct_errors": len(self._db),
            "total_errors": total_errors(),
            "time": int(time.time() - self._start)
        }
        stats.update(self.driver_stats)
        return stats

    def update(self, error, argset):
        """Update tracker with test result.

        If `bool(error)` is true, it is considered error and argset
        is inserted to DB with `str(error)` as key.  This allows for later
        sorting and analysis.
        """
        self.tests_done += 1
        if error:
            errstr = str(error)
            self._insert(errstr, argset)

    def write_stats_csv(self, fname):
        """Write stats to a simple one row (plus header) CSV."""
        stats = self.getstats()
        colnames = sorted(stats.keys())
        with open(fname, 'a') as fh:
            cw = csv.DictWriter(fh, colnames)
            cw.writerow(dict(zip(colnames, colnames)))  # header
            cw.writerow(stats)

    def write_args_csv(self, prefix=''):
        """Write out a set of CSV files, one per distinctive error.

        Each CSV is named with error EID (first 7 chars of SHA1) and lists
        all argument sets affected by this error.  This is supposed to make
        easier to further analyse impact and trigerring values of errors,
        perhaps using a table processor software."""

        def get_all_colnames():
            cn = {}
            for errstr, affected in self._db.iteritems():
                for argset in affected:
                    cn.update(dict.fromkeys(argset.keys()))
                return sorted(cn.keys())

        all_colnames = get_all_colnames()

        for errstr in self._db:
            with open(self._csv_fname(errstr, prefix), 'a') as fh:
                cw = csv.DictWriter(fh, all_colnames)
                cw.writerow(dict(zip(all_colnames, all_colnames)))  # header
                for argset in self._db[errstr]:
                    cw.writerow(argset)


## ............................................................................
## dataMatch -- a data structure matcher
##
#

def dataMatch(pattern, data, rmax=10, _r=0):
    """Check if data structure matches a pattern data structure.

    Supports lists, dictionaries and scalars (int, float, string).

    For scalars, simple `==` is used.  Lists are converted to sets and
    "to match" means "to have a matching subset (e.g. `[1, 2, 3, 4]`
    matches `[3, 2]`).  Both lists and dictionaries are matched recursively.
    """

    def listMatch(pattern, data):
        """Match list-like objects"""
        assert all([hasattr(o, 'append') for o in [pattern, data]])
        results = []
        for pv in pattern:
            if any([dataMatch(pv, dv, _r=_r+1) for dv in data]):
                results.append(True)
            else:
                results.append(False)
        return all(results)

    def dictMatch(pattern, data):
        """Match dict-like objects"""
        assert all([hasattr(o, 'iteritems') for o in [pattern, data]])
        results = []
        try:
            for pk, pv in pattern.iteritems():
                results.append(dataMatch(pv, data[pk], _r=_r+1))
        except KeyError:
            results.append(False)
        return all(results)

    if _r == rmax:
        raise RuntimeError("recursion limit hit")

    result = None
    if pattern == data:
        result = True
    else:
        for handler in [dictMatch, listMatch]:
            try:
                result = handler(pattern, data)
            except AssertionError:
                continue
    return result


def jsDump(data):
    """A human-readable JSON dump."""
    return json.dumps(data, sort_keys=True, indent=4,
                      separators=(',', ': '))


def jsDiff(dira, dirb, namea="A", nameb="B", chara="a", charb="b"):
    """JSON-based human-readable diff of two data structures.

    '''BETA''' version.

    jsDiff is based on unified diff of two human-readable JSON dumps except
    that instead of showing line numbers and context based on proximity to
    the changed lines, it prints only context important from the data
    structure point.

    The goal is to be able to quickly tell the story of what has changed
    where in the structure, no matter size and complexity of the data set.

    For example:

        a = {
            'w': {1: 2, 3: 4},
            'x': [1, 2, 3],
            'y': [3, 1, 2]
        }
        b = {
            'w': {1: 2, 3: 4},
            'x': [1, 1, 3],
            'y': [3, 1, 3]
        }
        print jsDiff(a, b)

    will output:

        aaa ~/A
             "x": [
        a        2,
             "y": [
        a        2
        bbb ~/B
             "x": [
        b        1,
             "y": [
        b        3

    Notice that the final output somehow resembles the traditional unified
    diff, so to avoid confusion, +/- is changed to a/b (the characters can
    be provided as well as the names A/B).
    """

    def compress(lines):

        def is_body(line):
            return line.startswith(("-", "+", " "))

        def is_diff(line):
            return line.startswith(("-", "+"))

        def is_diffA(line):
            return line.startswith("-")

        def is_diffB(line):
            return line.startswith("+")

        def is_context(line):
            return line.startswith(" ")

        def is_hdr(line):
            return line.startswith(("@@", "---", "+++"))

        def is_hdr_hunk(line):
            return line.startswith("@@")

        def is_hdr_A(line):
            return line.startswith("---")

        def is_hdr_B(line):
            return line.startswith("+++")

        class Level(object):

            def __init__(self, hint):
                self.hint = hint
                self.hinted = False

            def __str__(self):
                return str(self.hint)

            def get_hint(self):
                if not self.hinted:
                    self.hinted = True
                    return self.hint

        class ContextTracker(object):

            def __init__(self):
                self.trace = []
                self.last_line = None
                self.last_indent = -1

            def indent_of(self, line):
                meat = line[1:].lstrip(" ")
                ind = len(line) - len(meat) - 1
                return ind

            def check(self, line):
                indent = self.indent_of(line)
                if indent > self.last_indent:
                    self.trace.append(Level(self.last_line))
                elif indent < self.last_indent:
                    self.trace.pop()
                self.last_line = line
                self.last_indent = indent

            def get_hint(self):
                return self.trace[-1].get_hint()

        buffa = []
        buffb = []
        ct = ContextTracker()

        for line in lines:

            if is_hdr_hunk(line):
                continue
            elif is_hdr_A(line):
                line = line.replace("---", chara * 3, 1)
                buffa.insert(0, line)
            elif is_hdr_B(line):
                line = line.replace("+++", charb * 3, 1)
                buffb.insert(0, line)

            elif is_body(line):

                ct.check(line)

                if is_diff(line):
                    hint = ct.get_hint()
                    if hint:
                        buffa.append(hint)
                        buffb.append(hint)

                if is_diffA(line):
                    line = line.replace("-", chara, 1)
                    buffa.append(line)

                elif is_diffB(line):
                    line = line.replace("+", charb, 1)
                    buffb.append(line)

            else:
                raise AssertionError("difflib.unified_diff emited"
                                     " unknown format (%s chars):\n%s"
                                     % (len(line), line))

        return buffa + buffb

    dumpa = jsDump(dira)
    dumpb = jsDump(dirb)
    udiff = difflib.unified_diff(dumpa.split("\n"), dumpb.split("\n"),
                                 "~/" + namea, "~/" + nameb,
                                 n=10000, lineterm='')

    return "\n".join(compress([line for line in udiff]))


#
## Cartman - create dict arguments from dicts of available values (iterables)
#            and a defined scheme
#

class Cartman(object):
    """Create argument sets from ranges (or ay iterators) of values.

    This class is to enable easy definition and generation of dictionary
    argument  sets using Cartesian product.  You only need to define:

     *  structure of argument set (can be more than just flat dict)

     *  ranges, or arbitrary iterators of values on each "leaf" of the
        argument set

    Since there is expectation that any argument can have any kind of values
    even another iterables, the pure logic "iterate it if you can"
    is insufficient.  Instead, definition is divided in two parts:

     *  scheme, which is a "prototype" of a final argument set, except
        that for each value that will change, a `Cartman.Iterable`
        sentinel is used.  For each leaf that is constant, `Cartman.Scalar`
        is used

     *  source, which has the same structure, except that where in scheme
        is `Iterable`, an iterable object is expected, whereas in places
        where `Scalar` is used, a value is assigned that does not change
        during iteration.

    Finally, when such instance is used in loop, argument sets are generated
    uising Cartesian product of each iterable found.  This allows for
    relatively easy definition of complex scenarios.

    Consider this example:

        You have a system (wrapped up in test driver) that takes ''size''
        argument, that is supposed to be ''width'', ''height'' and ''depth'',
        each an integer ranging from 1 to 100, and ''color'' that can
        be "white", "black" or "yellow".

        For a test using all-combinations strategy, you will need to generate
        100 * 100 * 100 * 3 argument sets, i.e. 3M tests.

        All you need to do is:

            scheme = {
                'size': {
                    'width': Cartman.Iterable,
                    'height': Cartman.Iterable,
                    'depth': Cartman.Iterable,
                }
                'color': Cartman.Iterable,
            }

            source = {
                'size': {
                    'width': range(1, 100),
                    'height': range(1, 100),
                    'depth': range(1, 100),
                }
                'color': ['white', 'black', 'yellow'],
            }

            c = Cartman(source, scheme)

            for argset in c:
                result = my_test(argset)
                # assert ...

    The main advantage is that you can separate the definition from
    the code, and you can keep yor iterators as big or as small as
    needed, and add / remove values.

    Also in case your parameters vary in structure over time, or from
    one test to another, it gets much easier to keep up with changes
    without much jumping through hoops.

    Note: `Cartman.Scalar` is provided mainly to make your definitions
    more readable.  Following constructions are functionally equal:

        c = Cartman({'a': 1}, {'a': Cartman.Scalar})
        c = Cartman({'a': [1]}, {'a': Cartman.Iterable})

    In future, however, this might change, though, mainly in case
    optimization became possible based on what was used.
    """


    # TODO: support for arbitrary ordering (profile / nginx)
    # TODO: implement getstats and fmtstats
    # TODO: N-wise

    class _BaseMark(object):
        pass

    class Scalar(_BaseMark):
        pass

    class Iterable(_BaseMark):
        pass

    def __init__(self, source, scheme, recursion_limit=10, _r=0):
        self.source = source
        self.scheme = scheme
        self.recursion_limit = recursion_limit
        self._r = _r
        if self._r > self.recursion_limit:
            raise RuntimeError("recursion limit exceeded")

        # validate scheme + source and throw useful error
        scheme_ok = isinstance(self.scheme, collections.Mapping)
        source_ok = isinstance(self.source, collections.Mapping)
        if not scheme_ok:
            raise ValueError("scheme must be a mapping (e.g. dict)")
        elif scheme_ok and not source_ok:
            raise ValueError("scheme vs. source mismatch")

    def __deepcopy__(self, memo):
        return Cartman(deepcopy(self.source, memo),
                       deepcopy(self.scheme, memo))

    def _is_mark(self, subscheme):
        try:
            return issubclass(subscheme, Cartman._BaseMark)
        except TypeError:
            return False

    def _means_scalar(self, subscheme):
        if self._is_mark(subscheme):
            return issubclass(subscheme, Cartman.Scalar)

    def _means_iterable(self, subscheme):
        if self._is_mark(subscheme):
            return issubclass(subscheme, Cartman.Iterable)

    def _get_iterable_for(self, key):
        subscheme = self.scheme[key]
        subsource = self.source[key]
        if self._means_scalar(subscheme):
            return [subsource]
        elif self._means_iterable(subscheme):
            return subsource
        else:   # try to use it as scheme
            return iter(Cartman(subsource, subscheme, _r=self._r+1))

    def __iter__(self):

        names = []
        iterables = []

        keys = self.scheme.keys()

        for key in keys:
            try:
                iterables.append(self._get_iterable_for(key))
            except KeyError:
                pass    # ignore that subsource mentioned by scheme is missing
            else:
                names.append(key)

        for values in itertools.product(*iterables):
            yield dict(zip(names, values))

    def getstats(self):
        return {}

    def fmtstats(self):
        return ""
