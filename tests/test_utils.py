from musicbot.utils import format_duration


def test_format_duration_seconds_only():
    assert format_duration(45) == "0:45"


def test_format_duration_minutes_and_seconds():
    assert format_duration(225) == "3:45"


def test_format_duration_hours():
    assert format_duration(3725) == "1:02:05"


def test_format_duration_zero():
    assert format_duration(0) == "0:00"


def test_format_duration_none_is_live():
    assert format_duration(None) == "En vivo"


def test_format_duration_float_truncates():
    assert format_duration(90.9) == "1:30"
