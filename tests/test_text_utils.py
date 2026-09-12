from services.text_utils import escape_markdown


def test_escapes_legacy_markdown_chars():
    assert escape_markdown('a_b*c[d]e(f)`g`') == r'a\_b\*c\[d\]e\(f\)\`g\`'


def test_empty_string():
    assert escape_markdown('') == ''


def test_short_name_full_fio():
    from services.text_utils import short_name
    assert short_name('Ищенко Ксения Александровна') == 'Ищенко К.А.'


def test_short_name_two_words_unchanged():
    from services.text_utils import short_name
    assert short_name('Иванов Пётр') == 'Иванов Пётр'


def test_short_name_truncated_fio_stays_visible():
    from services.text_utils import short_name
    # Обрезанное источником ФИО сокращается до инициалов — обрезка не видна
    assert short_name('Александрова Валентина Александровн') == 'Александрова В.А.'


def test_short_name_multiple_teachers():
    from services.text_utils import short_name
    assert short_name('Иванов Иван Иванович, Петров Пётр Петрович') == 'Иванов И.И., Петров П.П.'


def test_short_name_empty():
    from services.text_utils import short_name
    assert short_name('') == ''
