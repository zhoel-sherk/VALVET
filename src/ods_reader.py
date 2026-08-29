#
# 2025-11-28
#

from pathlib import Path

from odf import opendocument, table

import logger

# local copy of odf:
# import os
# import sys
# sys.path.append(os.path.join(os.path.dirname(__file__), "odfpy"))
# from odfpy.odf import opendocument, table
from text_grid import TextGrid

# -----------------------------------------------------------------------------


def _require_existing_file(path: str) -> Path:
    assert path is not None
    if not str(path).strip():
        logger.error("Empty file path")
        raise FileNotFoundError("Empty file path")
    p = Path(path)
    if not p.is_file():
        logger.error("File not found: %s", path)
        raise FileNotFoundError(f"File not found: {path}")
    return p


def __check_row_valid(row_cells: list[str]) -> bool:
    # ignore rows with empty cells 'A,B,C' or cell 'A' with a long horizontal line
    row_valid = (len(row_cells) > 3) and (row_cells[0] or row_cells[1] or row_cells[2])
    row_valid = row_valid and not row_cells[0].startswith("___")
    return row_valid


def read_ods_sheet(path: str) -> TextGrid:
    """
    Reads ODS/spreadsheet document, returning the first sheet
    """
    p = _require_existing_file(path)
    logger.info(f"Reading file '{path}'")
    try:
        doc = opendocument.load(str(p))
    except Exception as e:
        logger.error("Cannot read ODS file %s: %s", path, e)
        raise
    tg = TextGrid()

    # with open(path + "-dump.xml", "w") as f:
    #     f.write(str(doc.xml()))

    if "opendocument.spreadsheet" in doc.getMediaType():
        for tab in doc.getElementsByType(table.Table):
            name = tab.getAttrNS(table.TABLENS, "name")
            logger.info(f"Reading sheet: {name}")
            max_cols = 0
            REPEATS_ATTR = "number-columns-repeated".replace("-", "")

            for tablerow in tab.getElementsByType(table.TableRow):
                tablecells = tablerow.getElementsByType(table.TableCell)
                row_cells = []

                # when iterating through the row cells, take the "repeat" attribute into account
                for cell in tablecells:
                    rep_attr = cell.getAttribute(REPEATS_ATTR) or 1
                    repeated = int(rep_attr)
                    if repeated > 25:
                        logger.warning(
                            "Cell {ridx}:{cidx} repeated {rep} times".format(
                                ridx=len(tg.rows_raw()) + 1,
                                cidx=len(row_cells) + 1,
                                rep=repeated,
                            )
                        )
                        repeated = 25
                    cell = str(cell).strip()

                    for _ in range(repeated):
                        row_cells.append(cell)

                if __check_row_valid(row_cells):
                    max_cols = max(max_cols, len(row_cells))
                    tg.rows_raw().append(row_cells)

            tg.nrows = len(tg.rows_raw())
            tg.ncols = max_cols

            # dont read any other sheets
            break
    else:
        logger.error("File does not contain a spreadsheet document")

    tg.align_number_of_columns()
    return tg
