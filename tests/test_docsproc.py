import zlib

import pytest

from prelexy.docsproc import DocEntry, extract_glosses, parse_inventory

INVENTORY_LINES = "\n".join(
    [
        "itertools.chain py:function 1 library/itertools.html#$ -",
        "list.pop py:method 1 library/stdtypes.html#$ -",
        "itertools py:module 0 library/itertools.html#module-$ -",  # skipped role
        "some.js.thing js:function 1 other.html#$ -",  # skipped domain
        "collections.Counter py:class 1 library/collections.html#collections.Counter -",
    ]
)


def make_inventory(tmp_path):
    path = tmp_path / "objects.inv"
    header = (
        b"# Sphinx inventory version 2\n"
        b"# Project: Python\n"
        b"# Version: 3.12\n"
        b"# The remainder of this file is compressed using zlib.\n"
    )
    path.write_bytes(header + zlib.compress(INVENTORY_LINES.encode()))
    return path


def test_parse_inventory_keeps_learnable_python_objects(tmp_path):
    entries = parse_inventory(make_inventory(tmp_path))
    assert entries == [
        DocEntry("itertools.chain", "function", "library/itertools.html", "itertools.chain"),
        DocEntry("list.pop", "method", "library/stdtypes.html", "list.pop"),
        DocEntry("collections.Counter", "class", "library/collections.html", "collections.Counter"),
    ]
    assert entries[0].module == "itertools"
    assert entries[1].module == "list"


def test_parse_inventory_rejects_other_formats(tmp_path):
    bad = tmp_path / "objects.inv"
    bad.write_bytes(b"# Sphinx inventory version 1\nwhatever")
    with pytest.raises(ValueError):
        parse_inventory(bad)


SPHINX_PAGE = """
<html><body>
<dl class="py function">
<dt id="itertools.chain">
  <span class="pre">itertools.</span><span class="pre">chain</span>(*iterables)<a class="headerlink" href="#itertools.chain">¶</a>
</dt>
<dd><p>Make an iterator that returns elements from the first iterable
until it is exhausted. Then proceeds to the next iterable.</p>
<p>Second paragraph is ignored.</p></dd>
</dl>
<dl class="py function">
<dt id="itertools.count"><span class="pre">itertools.count</span>(start=0, step=1)</dt>
<dd><p>Make an iterator that returns evenly spaced values.</p></dd>
</dl>
<dl class="py function">
<dt id="itertools.unwanted"><span class="pre">nope</span>()</dt>
<dd><p>Should not be extracted.</p></dd>
</dl>
</body></html>
"""


def test_extract_glosses_signature_and_first_sentence():
    result = extract_glosses(SPHINX_PAGE, {"itertools.chain", "itertools.count"})
    signature, gloss = result["itertools.chain"]
    assert signature == "itertools.chain(*iterables)"
    assert gloss == (
        "Make an iterator that returns elements from the first iterable "
        "until it is exhausted."
    )
    assert result["itertools.count"][1] == "Make an iterator that returns evenly spaced values."
    assert "itertools.unwanted" not in result
