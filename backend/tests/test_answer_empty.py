"""Contract for review / flags: empty detection matches PATCH validation."""

from app.services.answers import answer_value_is_effectively_empty


def test_empty_strings_and_insufficient():
    assert answer_value_is_effectively_empty(None, "textarea") is True
    assert answer_value_is_effectively_empty("", "textarea") is True
    assert answer_value_is_effectively_empty("   ", "textarea") is True
    assert answer_value_is_effectively_empty("INSUFFICIENT_INFO", "textarea") is True
    assert answer_value_is_effectively_empty("insufficient_info", "textarea") is True


def test_nonempty_text():
    assert answer_value_is_effectively_empty("Hello", "textarea") is False


def test_number_zero_is_nonempty():
    assert answer_value_is_effectively_empty(0, "number") is False


def test_empty_list_multi():
    assert answer_value_is_effectively_empty([], "multi_choice") is True
