sznqalibs
=========

Collection of python libs developed for testing purposes.


hoover
------

hoover is a testing framework built with following principles
in mind:

 *  data-driven testing,
 *  easy test data definition (even with huge sets),
 *  helpful reporting.

Typical use case is that you have a tested system, another
"reference" system and knowledge about testing input.  You then
create drivers for both systems that will parse and prepare
output in a way that it can be compared to eaach other.


### Examples ###

An example is worth 1000 words:

    from sznqalibs import hoover


    class BaloonDriver(hoover.TestDriver):
        """
        Object enclosing SUT or one of its typical use patterns
        """

        _get_data(self):
            # now do something to obtain results from the SUT
            # using self._argset dictionary
            self.data['sentence'] = subprocess.check_output(
                ['sut', self.args['count'], self.args['color']]
            )

    class OracleDriver(hoover.TestDriver):
        """
        Object providing Oracle (expected output) for test arguments
        """

        _get_data(self):
            # obtain expected results, for example by asking
            # reference implementation (or by reimplementing
            # fraction of the SUT, e.g. only for the expected
            # data)
            self.data['sentence'] = ("%(count)s %(color)s baloons"
                                     % self._args)

    class MyTest(unittest.TestCase):

        def test_valid(self):
            # as alternative to defining each _args separately,
            # Cartman lets you define just the ranges
            argsrc = hoover.Cartman({
                # for each parameter define iterator with
                # values you want to combine in this test
                'count': xrange(100),
                'color': ['red', 'blue']
            })
            # regression_test will call both drivers once with
            # each argument set, compare results and store results
            # along with some statistics
            tracker = hoover.regression_test(
                argsrc=argsrc,
                tests=[(operator.eq, OracleDriver, BaloonDriver)]
            )
            if tracker.errors_found():
                print tracker.format_report()

But that's just to get the idea.  For a (hopefully) working
example, look at doc/examples subfolder, there's a "calculator"
implemented in Bash and Perl/CGI, and a *hoover* test that
compares these two implementations to a Python implementation
defined inside the test.


### pFAQ (Potentially FAQ) ###

The truth is that nobody asked any questions so far, so I can't
honestly write FAQ (or even AQ, for that matter) ;).  So at
least I'll try to answer what I feel like people would ask:

 *  **Q:** What do you mean by implementing "reference", or
    "oracle" driver?  Am I supposed to re-implement the system?
    Are you serious?

    **A:** Yes, I am serious.  But consider this:

    First, not all systems are necessarily complicated.  Take
    GNU *cat*.  All  it does is print data.  Open, write,
    close.  The added value is that it's insanely good at it.
    However, your oracle driver does not need to be *that*
    good.  Even if it only was able to check the length or
    MD5 of data, it would be more than nothing.

    Also if you are creative enough, you can select the data
    in a clever way so that you can develop tricks that can
    help your driver on the way.   For example you could
    "inject" the data with hints on how the result should be.

    Next, you don't need to actually re-implement the driver.
    As
    the most "brute" strategy, instead of using hoover to
    generate the data, you might want to just go and generate
    the data somehow manually (as you might have done it so
    far), verify it and feed it to your drivers. including
    expected results.  This might not be the most viable option
    for a huge set, but at least what *hoover* will give you is
    the running and reporting engine.

    Then there might be cases when the system actually *is*
    trivial and you *can* re-implement it, but for some reason
    you don't have a testing framework on the native platform.
    For example, embedded system, or a library that needs to
    be in specific language like bash.  In case it has trivial
    parts, you can test them in *hoover* and save yourself
    some headache with maintenance.

    Last, but not least--this was actually the story behind
    *hoover* being born--there are cases whan you already
    *have* reference implementation and new implementation, you
    just need to verify that behavior is the same.  So you just
    wrap both systems in drivers, tweak them so that they can
    return the same data (if they already don't) or at least
    data you can write a comparison function for, squeeze them
    all into `hoover.regression_test` and hit the big button.
    Note that you can even have 1 reference driver and N SUT
    drivers, which can save you kajillions of machine seconds
    if your old library is slow or resource-hungry but you have
    more ports of the new one.

    As a bonus, note that *hoover* can also provide you with
    some performance stats.  Well, there's absolutely no intent
    to say that this is a proper performance measurement tool
    (it's actually been designed to assess performance of the
    drivers), but on the other hand, it comes with the package,
    so it might be useful for you.

 *  **Q:** Is it mature?

    **A:** No and a tiny yes.

    Yes, because it has already been used in real environment
    and it succeeded.  But then again, it has been deployed by
    author, and he has no idea if that's actually doable for
    any sane person.  You are more than welcome to try it and
    provide me with feedback and I can't provide any kind of
    guarranteees whatsoever.

    No, because there are parts that are still far from being
    polished, easy to use  or even possible to understand.
    (Heck, at this moment even I don't understand what `RuleOp`
    is or was for :D).  And there are probably limitations that
    could be removed.

    That said, the code is not a complete utter holy mess,
    though.

    But the API **will** change.  Things will be re-designed
    and some even removed or split to other modules.

    My current "strategy", however, is to do this on the run,
    probably based on real  experience when trying to use it in
    real testing scenarios.

