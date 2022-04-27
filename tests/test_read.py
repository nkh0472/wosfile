import pytest
from io import StringIO

from wosfile.read import (
    PlainTextReader,
    ReadError,
    TabDelimitedReader,
    get_reader,
    read,
)

preamble_b = b"""FN Thomson Reuters Web of Science
VR 1.0
"""
preamble_s = preamble_b.decode("utf-8")


def assert_no_bom(record):
    # very basic way of asserting that we've successfully stripped the BOM
    assert u"PT" in record


def test_get_reader():
    f = StringIO(preamble_s)
    assert get_reader(f) == PlainTextReader

    f = StringIO("PT\tAF\tAU\tCU\tC1")
    assert get_reader(f) == TabDelimitedReader

    with pytest.raises(ReadError):
        get_reader(StringIO("XY Bla\nVR 1.0"))


def test_read(tmp_path):
    data = preamble_b + b"PT J\nAU John Doe\nER\nEF"
    expected = {"PT": "J", "AU": "John Doe"}

    filename = tmp_path / "test_read"
    with open(filename, "wb") as f:
        f.write(data)
    for res in (list(read(filename)), list(read(filename, using=PlainTextReader))):
        assert len(res) == 1
        assert res[0] == expected
        assert f.closed


def test_read_actual_data():
    for fname in (
        "wos_plaintext.txt",
        "wos_tab_delimited_win_utf8.txt",
        "wos_tab_delimited_win_utf16.txt",
    ):
        for rec in read("data/" + fname):
            assert_no_bom(rec)


def test_read_multiple_files(tmp_path):
    data = [
        preamble_b + b"PT J\nAU John Doe\nER\nEF",
        preamble_b + b"PT T\nAU Mary Stuart\nER\nEF",
    ]
    expected = [{"PT": "J", "AU": "John Doe"}, {"PT": "T", "AU": "Mary Stuart"}]

    files = []
    for i, d in enumerate(data):
        fname = tmp_path / f"test_read_multiple_files{i}"
        with open(fname, "wb") as f:
            f.write(d)
        files.append(fname)

    for rec, exp in zip(read(files), expected):
        assert rec == exp


class TestPlainTextReader:
    def test_wrong_format(self):
        f = StringIO("XY Bla\nVR 1.0")
        with pytest.raises(ReadError):
            PlainTextReader(f)

    def test_wrong_version(self):
        f = StringIO("FN Thomson Reuters Web of Science\nVR 1.1")
        with pytest.raises(ReadError):
            PlainTextReader(f)

    def test_forgotten_ER(self):
        f = StringIO(preamble_s + "PT abc\nAU xuz\nER\n\nPT abc2\nEF")
        r = PlainTextReader(f)
        with pytest.raises(ReadError):
            list(r)

    def test_forgotten_EF(self):
        f = StringIO(preamble_s + "PT abc\nAU xuz\nER\n\nPT abc2\nER")
        r = PlainTextReader(f)
        with pytest.raises(ReadError):
            list(r)

    def test_unknown_tag(self):
        f = StringIO(preamble_s + "PT abc\n\nQQ x\nER\nEF")
        r = PlainTextReader(f)
        with pytest.raises(NotImplementedError):
            list(r)

    def test_ignore_empty_lines(self):
        f = StringIO(preamble_s + "PT abc\n\nAU xyz\nER\nEF")
        r = PlainTextReader(f)

        expected = {"PT": "abc", "AU": "xyz"}
        assert next(r) == expected

    def test_multiple_records(self):
        f = StringIO(
            preamble_s + "PT abc\nAU xyz\nER\n\nPT abc2\n AU xyz2\n"
            "AB abstract\nER\nEF"
        )
        r = PlainTextReader(f)

        results = list(r)
        expected = [
            {"PT": "abc", "AU": "xyz"},
            {"PT": "abc2", "AU": "xyz2", "AB": "abstract"},
        ]

        assert len(results) == len(expected)
        for result, exp in zip(results, expected):
            assert result == exp

    def test_multiline_fields_split(self):
        f = StringIO(
            preamble_s + "PT abc\nSO J.Whatever\nAF Here\n   be\n" "   dragons\nER\nEF"
        )

        r = PlainTextReader(f)
        expected = {"PT": "abc", "SO": "J.Whatever", "AF": "Here; be; dragons"}
        assert next(r) == expected

    def test_multiline_fields_nosplit(self):
        f = StringIO(
            preamble_s + "PT abc\nSC Here; there\n  be dragons; Yes" "\nER\nEF"
        )

        r = PlainTextReader(f)
        expected = {"PT": "abc", "SC": "Here; there be dragons; Yes"}
        assert next(r) == expected

    def test_wos_plaintext(self):
        # utf-8-sig = UTF-8 with BOM
        with open("data/wos_plaintext.txt", encoding="utf-8-sig") as fh:
            r = PlainTextReader(fh)
            for _ in r:
                pass


class TestTabDelimitedReader:
    def test_one_record(self):
        f = StringIO("PT\tAF\tC1\nJ\tAa; Bb\tX; Y")

        r = TabDelimitedReader(f)
        expected = {"PT": "J", "AF": "Aa; Bb", "C1": "X; Y"}

        assert next(r) == expected

    def test_multiple_records(self):
        f = StringIO("PT\tAF\tC1\nJ\tAa; Bb\tX; Y\nJ\tBb; Cc\tY; Z")
        r = TabDelimitedReader(f)

        results = [result for result in r]
        expected = [
            {"PT": "J", "AF": "Aa; Bb", "C1": "X; Y"},
            {"PT": "J", "AF": "Bb; Cc", "C1": "Y; Z"},
        ]

        assert len(results) == len(expected)
        for result, exp in zip(results, expected):
            assert result == exp

    def test_spurious_tab_at_end(self):
        f = StringIO("PT\tAU\tC1\nJ\ta\tb\t")
        r = TabDelimitedReader(f)

        expected = {"PT": "J", "AU": "a", "C1": "b"}
        assert next(r) == expected

    def test_wos_tabdelimited_utf16(self):
        with open("data/wos_tab_delimited_win_utf16.txt", encoding="utf-16") as fh:
            r = TabDelimitedReader(fh)
            for record in r:
                assert_no_bom(record)

    def test_wos_tabdelimited_utf8(self):
        with open("data/wos_tab_delimited_win_utf8.txt", encoding="utf-8-sig") as fh:
            r = TabDelimitedReader(fh)
            for record in r:
                assert_no_bom(record)


# This fails because of small differences between content of fields in the two
# formats...
# def test_plaintext_tabdelimited_equivalent():
#    with open("data/wos_plaintext.txt") as plaintext,\
#            open("data/wos_tab_delimited_win_utf8.txt") as tabdelimited:
#        pt_reader = PlainTextReader(plaintext)
#        td_reader = TabDelimitedReader(tabdelimited)
#        for pt in pt_reader:
#            td = next(td_reader)
#            for k, v in pt.iteritems():
#                assert v == td[k]
