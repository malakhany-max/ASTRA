from hypothesis import given, settings, strategies as st
import astra_security as sec

junk = st.dictionaries(
    st.text(max_size=20),
    st.one_of(st.none(), st.booleans(), st.integers(), st.floats(), st.text(max_size=40),
              st.lists(st.integers(), max_size=5)),
    max_size=12)


@settings(max_examples=200, deadline=None)
@given(junk)
def test_never_crashes_never_trusted(msg):
    assert sec.verify_and_classify(msg)["classification"] != "trusted"


@settings(max_examples=200, deadline=None)
@given(junk)
def test_canonicalize_order_independent(d):
    rev = dict(reversed(list(d.items())))
    assert sec.canonicalize(d) == sec.canonicalize(rev)
