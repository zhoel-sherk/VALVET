import sys
import os

# adding src path to search list
tests_path = os.path.dirname(os.path.realpath(__file__))
sys.path.append(os.path.join(os.path.dirname(tests_path), "src"))

# tested module
from text_grid import TextGrid

# -----------------------------------------------------------------------------


def test_default():
    tg = TextGrid()
    assert tg.nrows == 0
    assert tg.ncols == 0
    assert type(tg.rows_raw()) is list
    assert len(tg.rows_raw()) == 0


def test_full_features():
    expected_lines = (
        "002 | ID     | Val            | Comment  | ",
        "003 | #      |                |          | ",
        "004 | R1     | 15k            | resistor | ",
        "005 | R3     | 1.2            |          | ",
        "006 | Jumper |                |          | ",
        "007 | U1     | STM32F12345678 | 4321     | ",
    )

    tg = TextGrid()
    tg.rows_raw().append(["List of materials"])
    tg.rows_raw().append(["ID", "Val", "Comment"])
    tg.rows_raw().append(["#", None, ""])
    tg.rows_raw().append(["R1", "15k", "resistor"])
    tg.rows_raw().append(["R3", 1.2, None])
    tg.rows_raw().append(["Jumper", ""])
    tg.rows_raw().append(["U1", "STM32F12345678", 4321])
    tg.nrows = len(tg.rows_raw())
    tg.ncols = 3
    tg.align_number_of_columns()
    assert tg.rows_raw()[0][1] == ""
    assert tg.rows_raw()[0][2] == ""
    formatted = tg.format_grid(1)
    # print()
    # print(txt)
    actual_lines = formatted.splitlines()
    for act, exp in zip(actual_lines, expected_lines):
        assert act == exp
