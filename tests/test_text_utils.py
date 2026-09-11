from services.text_utils import escape_markdown


def test_escapes_legacy_markdown_chars():
    assert escape_markdown('a_b*c[d]e(f)`g`') == r'a\_b\*c\[d\]e\(f\)\`g\`'


def test_empty_string():
    assert escape_markdown('') == ''
