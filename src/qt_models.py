"""
PandasTableModel — bridge between a pandas DataFrame and PySide6 QTableView.

Subclass of QAbstractTableModel; handles pandas NaN/NaT safely.
"""

import pandas as pd
import numpy as np
from typing import Any, Callable, Optional

from PySide6 import QtCore
from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PySide6 import QtGui
from PySide6.QtGui import QUndoCommand, QUndoStack


def _coerce_edit_value_for_dataframe(value: Any, col_dtype: Any) -> Any:
    """
    Coerce a value from the Qt editor (often str) to a type compatible with the column dtype.
    """
    if value is None:
        if pd.api.types.is_extension_array_dtype(col_dtype):
            return pd.NA
        if pd.api.types.is_float_dtype(col_dtype) or pd.api.types.is_complex_dtype(
            col_dtype
        ):
            return np.nan
        if pd.api.types.is_integer_dtype(col_dtype):
            raise ValueError("null in non-nullable integer column")
        return ""

    if hasattr(value, "item") and callable(getattr(value, "item", None)):
        try:
            value = value.item()
        except (ValueError, AttributeError):
            pass

    if isinstance(value, (bool, np.bool_)):
        if pd.api.types.is_bool_dtype(col_dtype):
            return bool(value)
        if pd.api.types.is_numeric_dtype(col_dtype):
            return int(value)
        return str(value)

    if isinstance(value, (int, np.integer)) and not isinstance(value, (bool, np.bool_)):
        if pd.api.types.is_float_dtype(col_dtype) or pd.api.types.is_complex_dtype(
            col_dtype
        ):
            return float(value)
        if pd.api.types.is_integer_dtype(col_dtype):
            return int(value)
        if pd.api.types.is_bool_dtype(col_dtype):
            return bool(value)
        return int(value)

    if isinstance(value, (float, np.floating)) and not isinstance(value, bool):
        if pd.api.types.is_integer_dtype(col_dtype):
            x = float(value)
            if not np.isfinite(x):
                raise ValueError("non-finite")
            return int(round(x))
        return float(value)

    if isinstance(value, str):
        s = value.strip().replace("\u00a0", " ").replace(",", ".")
        if pd.api.types.is_bool_dtype(col_dtype):
            sl = s.lower()
            if sl in ("", "0", "no", "false", "n"):
                return False
            if sl in ("1", "yes", "true", "y"):
                return True
            raise ValueError(f"unrecognized bool: {value!r}")

        if pd.api.types.is_numeric_dtype(col_dtype):
            if s == "" or s.lower() in ("nan", "none", "nat"):
                if pd.api.types.is_extension_array_dtype(col_dtype):
                    return pd.NA
                if pd.api.types.is_float_dtype(
                    col_dtype
                ) or pd.api.types.is_complex_dtype(col_dtype):
                    return np.nan
                raise ValueError("empty numeric integer cell")

            parsed = float(s)
            if not np.isfinite(parsed):
                raise ValueError("non-finite")
            if pd.api.types.is_integer_dtype(col_dtype):
                return int(round(parsed))
            return parsed

        return value

    return value


def _cell_values_equal(a: Any, b: Any) -> bool:
    try:
        if pd.isna(a) and pd.isna(b):
            return True
    except TypeError:
        pass
    return a == b


class DataFrameCellEditCommand(QUndoCommand):
    """Undo one cell edit on a PandasTableModel."""

    def __init__(
        self,
        model: "PandasTableModel",
        row: int,
        col: int,
        old_val: Any,
        new_val: Any,
        description: str = "",
    ):
        super().__init__(description or "Edit cell")
        self._model = model
        self._row = row
        self._col = col
        self._old = old_val
        self._new = new_val

    def redo(self) -> None:
        self._model._write_cell(self._row, self._col, self._new, emit_change=True)

    def undo(self) -> None:
        self._model._write_cell(self._row, self._col, self._old, emit_change=True)


class PandasTableModel(QAbstractTableModel):
    """
    Generic Qt model backed by a pandas DataFrame.

    Usage:
        model = PandasTableModel(df)
        table_view.setModel(model)

        model.update_dataframe(new_df)
    """

    def __init__(
        self,
        dataframe: Optional[pd.DataFrame] = None,
        parent: Optional[QtCore.QObject] = None,
        editable: bool = False,
    ):
        super().__init__(parent)
        self._df = dataframe if dataframe is not None else pd.DataFrame()
        self._editable = editable
        self._active_row_range: tuple[int, int] | None = None
        self._column_display_names: dict[str, str] = {}
        self._column_tooltips: dict[str, str] = {}
        self._undo_stack: Optional[QUndoStack] = None
        self._audit_table_id: str = ""
        self._audit_callback: Optional[Callable[[dict[str, Any]], None]] = None
        self._read_only_guard: bool = False

    # =========================================================================
    # Required Abstract Methods
    # =========================================================================

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return len(self._df)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return len(self._df.columns)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid():
            return None

        row = index.row()
        col = index.column()

        if row >= len(self._df) or col >= len(self._df.columns):
            return None

        value = self._df.iloc[row, col]

        if role == Qt.ItemDataRole.DisplayRole:
            return self._format_value(value)

        elif role == Qt.ItemDataRole.EditRole:
            return self._format_value(value, for_edit=True)

        elif role == Qt.ItemDataRole.TextAlignmentRole:
            return Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter

        elif role == Qt.ItemDataRole.ToolTipRole:
            return self._format_value(value, for_edit=True)

        elif role == Qt.ItemDataRole.BackgroundRole:
            return self._get_background(row, col, value)

        elif role == Qt.ItemDataRole.ForegroundRole:
            return self._get_foreground(row, col, value)

        return None

    def headerData(
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> Any:
        if orientation == Qt.Orientation.Horizontal:
            if section >= len(self._df.columns):
                return None
            col_name = str(self._df.columns[section])
            if role == Qt.ItemDataRole.DisplayRole:
                return self._column_display_names.get(col_name, col_name)
            if role == Qt.ItemDataRole.ToolTipRole:
                return self._column_tooltips.get(col_name) or col_name
            return None

        elif orientation == Qt.Orientation.Vertical:
            if role == Qt.ItemDataRole.DisplayRole:
                return str(section + 1)
            if (
                role == Qt.ItemDataRole.BackgroundRole
                and self._active_row_range is not None
            ):
                first, last = self._active_row_range
                row_number = section + 1
                if first <= row_number <= last:
                    return QtGui.QBrush(QtGui.QColor(66, 133, 244))
            if (
                role == Qt.ItemDataRole.ForegroundRole
                and self._active_row_range is not None
            ):
                first, last = self._active_row_range
                row_number = section + 1
                if first <= row_number <= last:
                    return QtGui.QBrush(QtGui.QColor(255, 255, 255))
            if role == Qt.ItemDataRole.FontRole and self._active_row_range is not None:
                first, last = self._active_row_range
                row_number = section + 1
                if first <= row_number <= last:
                    font = QtGui.QFont()
                    font.setBold(True)
                    return font

        return None

    # =========================================================================
    # Optional: Flags
    # =========================================================================

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        flags = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
        if self._editable:
            flags |= Qt.ItemFlag.ItemIsEditable
        return flags

    def set_undo_stack(
        self,
        stack: Optional[QUndoStack],
        *,
        table_id: str = "",
        audit_callback: Optional[Callable[[dict[str, Any]], None]] = None,
    ) -> None:
        self._undo_stack = stack
        self._audit_table_id = table_id
        self._audit_callback = audit_callback

    def set_read_only_guard(self, on: bool) -> None:
        """When True, reject all edits via setData (audit / protection)."""
        self._read_only_guard = bool(on)

    def clear_undo_stack(self) -> None:
        if self._undo_stack is not None:
            self._undo_stack.clear()

    def _emit_cell_changed(self, row: int, col: int) -> None:
        idx = self.index(row, col)
        self.dataChanged.emit(
            idx, idx, [Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole]
        )

    def _write_cell(self, row: int, col: int, value: Any, *, emit_change: bool) -> None:
        self._df.iat[row, col] = value
        if emit_change:
            self._emit_cell_changed(row, col)

    def _audit(self, payload: dict[str, Any]) -> None:
        if self._audit_callback is None:
            return
        payload = dict(payload)
        payload.setdefault("table", self._audit_table_id)
        self._audit_callback(payload)

    def setData(
        self, index: QModelIndex, value: Any, role: int = Qt.ItemDataRole.EditRole
    ) -> bool:
        if (
            not self._editable
            or role != Qt.ItemDataRole.EditRole
            or not index.isValid()
        ):
            return False
        if self._read_only_guard:
            return False
        row = index.row()
        col = index.column()
        if row >= len(self._df) or col >= len(self._df.columns):
            return False
        col_dtype = self._df.dtypes.iloc[col]
        try:
            coerced = _coerce_edit_value_for_dataframe(value, col_dtype)
        except (ValueError, TypeError, OverflowError):
            return False
        old_val = self._df.iat[row, col]
        if _cell_values_equal(old_val, coerced):
            return True
        if self._undo_stack is not None:
            cmd = DataFrameCellEditCommand(self, row, col, old_val, coerced)
            self._undo_stack.push(cmd)
            self._audit(
                {
                    "event": "cell_edit",
                    "row": row,
                    "col": col,
                    "column": str(self._df.columns[col]),
                    "old": old_val,
                    "new": coerced,
                }
            )
            return True
        self._df.iat[row, col] = coerced
        self._audit(
            {
                "event": "cell_edit",
                "row": row,
                "col": col,
                "column": str(self._df.columns[col]),
                "old": old_val,
                "new": coerced,
            }
        )
        self.dataChanged.emit(
            index, index, [Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole]
        )
        return True

    # =========================================================================
    # Update Methods
    # =========================================================================

    def update_dataframe(self, new_df: Optional[pd.DataFrame]) -> None:
        if new_df is None:
            new_df = pd.DataFrame()

        old_rows = len(self._df)
        old_cols = len(self._df.columns)

        self.clear_undo_stack()
        self.beginResetModel()
        self._df = new_df
        self.endResetModel()

        if old_rows != len(new_df) or old_cols != len(new_df.columns):
            pass

    def get_dataframe(self) -> pd.DataFrame:
        return self._df

    def set_column_header_metadata(
        self, display: dict[str, str], tooltips: dict[str, str]
    ) -> None:
        self._column_display_names = dict(display)
        self._column_tooltips = dict(tooltips)
        if len(self._df.columns):
            self.headerDataChanged.emit(
                Qt.Orientation.Horizontal, 0, len(self._df.columns) - 1
            )

    def apply_row_patch(self, row: int, patch: dict[str, Any]) -> bool:
        """Apply string/coerced values to one row; emits dataChanged for touched columns."""
        if row < 0 or row >= len(self._df):
            return False
        cols = list(self._df.columns)
        changed_j: list[int] = []
        commands: list[DataFrameCellEditCommand] = []
        for key, value in patch.items():
            if key not in cols:
                continue
            j = cols.index(key)
            col_dtype = self._df.dtypes.iloc[j]
            try:
                coerced = _coerce_edit_value_for_dataframe(value, col_dtype)
            except (ValueError, TypeError, OverflowError):
                return False
            old_v = self._df.iat[row, j]
            if _cell_values_equal(old_v, coerced):
                continue
            if self._undo_stack is not None:
                commands.append(
                    DataFrameCellEditCommand(self, row, j, old_v, coerced, "Row patch")
                )
            else:
                self._df.iat[row, j] = coerced
                changed_j.append(j)
        if self._undo_stack is not None and commands:
            self._undo_stack.beginMacro("Row patch")
            for c in commands:
                self._undo_stack.push(c)
            self._undo_stack.endMacro()
            return True
        if not changed_j:
            return True
        lo, hi = min(changed_j), max(changed_j)
        tl = self.index(row, lo)
        br = self.index(row, hi)
        self.dataChanged.emit(
            tl, br, [Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole]
        )
        return True

    def set_active_row_range(self, first: int | None, last: int | None) -> None:
        if first is None or last is None or first < 1 or last < first:
            self._active_row_range = None
        else:
            self._active_row_range = (first, last)
        if self.rowCount() > 0:
            self.headerDataChanged.emit(Qt.Orientation.Vertical, 0, self.rowCount() - 1)

    def get_column_value(self, column_name: str) -> pd.Series:
        if column_name in self._df.columns:
            return self._df[column_name]
        return pd.Series()

    def get_row_values(self, row: int) -> dict:
        if row < len(self._df):
            return self._df.iloc[row].to_dict()
        return {}

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _format_value(self, value: Any, for_edit: bool = False) -> str:
        if value is None or pd.isna(value):
            return ""

        if isinstance(value, (bool, np.bool_)):
            return "Yes" if value else "No"

        if isinstance(value, (int, float, np.integer, np.floating)):
            if for_edit:
                return str(value)
            if isinstance(value, float):
                return f"{value:g}"
            return str(value)

        try:
            if isinstance(value, pd.Timestamp):
                return value.strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            pass

        return str(value).strip()

    def _get_background(self, row: int, col: int, value: Any) -> Optional[QtGui.QBrush]:
        """Let the view / stylesheet paint alternate rows (dark theme); no hardcoded light stripes."""
        return None

    def _get_foreground(self, row: int, col: int, value: Any) -> Optional[QtGui.QBrush]:
        return None


class ReadOnlyTableModel(PandasTableModel):
    """Read-only table model (no in-place cell edits)."""

    pass


class SortableTableModel(PandasTableModel):
    """Sortable model (click header to sort; optional sort arrow in header text)."""

    def __init__(
        self,
        dataframe: Optional[pd.DataFrame] = None,
        parent: Optional[QtCore.QObject] = None,
        editable: bool = False,
    ):
        super().__init__(dataframe, parent, editable=editable)
        self._sort_column = -1
        self._sort_order = Qt.SortOrder.AscendingOrder

    def sort(
        self, column: int, order: Qt.SortOrder = Qt.SortOrder.AscendingOrder
    ) -> None:
        if column < 0 or column >= len(self._df.columns):
            return

        self.beginResetModel()
        self._sort_column = column
        self._sort_order = order

        col_name = self._df.columns[column]
        ascending = order == Qt.SortOrder.AscendingOrder

        self.clear_undo_stack()
        try:
            self._df = self._df.sort_values(by=col_name, ascending=ascending)
        except Exception:
            pass

        self.endResetModel()

    def headerData(
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> Any:
        result = super().headerData(section, orientation, role)

        if (
            role == Qt.ItemDataRole.DisplayRole
            and orientation == Qt.Orientation.Horizontal
        ):
            if section == self._sort_column:
                arrow = "▲" if self._sort_order == Qt.SortOrder.AscendingOrder else "▼"
                return f"{result} {arrow}"

        return result


def create_table_model(
    df: Optional[pd.DataFrame] = None, sortable: bool = False, readonly: bool = True
) -> PandasTableModel:
    if sortable:
        return SortableTableModel(df, editable=not readonly)
    elif readonly:
        return ReadOnlyTableModel(df)
    else:
        return PandasTableModel(df)


class CleanPreviewTableModel(SortableTableModel):
    """Clean BOM preview: optional green tint on Cleaned from Win%% column."""

    def __init__(
        self,
        dataframe: pd.DataFrame | None = None,
        parent: QtCore.QObject | None = None,
        *,
        arbiter_score_highlight: bool = False,
    ) -> None:
        super().__init__(dataframe, parent, editable=False)
        self._arbiter_score_highlight = bool(arbiter_score_highlight)

    def set_arbiter_score_highlight(self, on: bool) -> None:
        self._arbiter_score_highlight = bool(on)
        if self.rowCount() > 0 and self.columnCount() > 0:
            tl = self.index(0, 0)
            br = self.index(self.rowCount() - 1, self.columnCount() - 1)
            self.dataChanged.emit(
                tl,
                br,
                [QtCore.Qt.ItemDataRole.BackgroundRole],
            )

    def _get_background(self, row: int, col: int, value: Any) -> Any:
        base = super()._get_background(row, col, value)
        if not self._arbiter_score_highlight:
            return base
        if row >= len(self._df) or col >= len(self._df.columns):
            return base
        if str(self._df.columns[col]) != "Cleaned" or "Win%" not in self._df.columns:
            return base
        wcell = self._df.iloc[row]["Win%"]
        try:
            if wcell is None or (isinstance(wcell, float) and pd.isna(wcell)):
                return base
            s = str(wcell).strip()
            if not s:
                return base
            pct = float(s)
        except (TypeError, ValueError):
            return base
        pct = max(0.0, min(100.0, pct))
        intensity = int(210 + (pct / 100.0) * 40)
        alt = row % 2 == 1
        if alt:
            mix = int(230 - (pct / 100.0) * 35)
            return QtGui.QBrush(QtGui.QColor(mix, intensity, mix))
        return QtGui.QBrush(QtGui.QColor(235, intensity + 8, 235))

    def _get_foreground(self, row: int, col: int, value: Any) -> Optional[QtGui.QBrush]:
        if row < len(self._df) and col < len(self._df.columns):
            col_name = str(self._df.columns[col])
            if col_name == "Source":
                if value is None or (isinstance(value, float) and pd.isna(value)):
                    pass
                else:
                    sv = str(value)
                    if "PARTIAL" in sv.upper():
                        return QtGui.QBrush(QtGui.QColor(220, 85, 0))
        return super()._get_foreground(row, col, value)
