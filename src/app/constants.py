APP_NAME = "VALVET"
APP_EXPANSION = "Validator And Line-Verified Export Tool"
APP_VERSION = "0.1.3"
VERSION_DISPLAY = "ALPHA v0.1.3"

SETTINGS_ORG = "VALVET"
SETTINGS_APP = "VALVET"

PROFILE_STATE_VERSION = 1
PROFILE_NAMES_KEY = "profiles/names"
PROFILE_LAST_ACTIVE_KEY = "profiles/last_active"

# Hidden from UI: False = treat loaded grids as «no dedicated header row» for core mapping (matches
# full-row preview: «spaces» loader does not promote a row into column names).
HIDDEN_TABLE_HAS_HEADER_ROW = False

# Mapping combos live in the horizontal header (one QComboBox per section).
_PREVIEW_TABLE_HDR_HEIGHT = 26
_MAPPING_COMBO_MAX_HEIGHT = 26

# Cap table column auto-width so BOM/PnP load does not force a multi-screen-wide window.
_TABLE_COL_MAX_WIDTH = 400

_BOM_MAPPING_ROLES = ("-", "REF", "Comment")
_PNP_MAPPING_ROLES = (
    "-",
    "REF",
    "Comment",
    "Value",
    "Footprint",
    "X",
    "Y",
    "Rotation",
    "Layer",
)
_MAPPING_I18N_KEY = {
    "-": "mapping.none",
    "REF": "mapping.ref",
    "Comment": "mapping.pn_name",
    "Value": "mapping.value",
    "Footprint": "mapping.footprint",
    "X": "mapping.x",
    "Y": "mapping.y",
    "Rotation": "mapping.rotation",
    "Layer": "mapping.layer",
}
_DANGER_CLEAR_BTN_STYLE = (
    "QPushButton#dangerClearBtn { color: #ffcdd2; background-color: #5c1a1a; "
    "border: 1px solid #c62828; padding: 4px 10px; }"
    "QPushButton#dangerClearBtn:hover { background-color: #7f1d1d; }"
    "QPushButton#dangerClearBtn:disabled { color: #888; background-color: #333; }"
)
_RCL_ROW_DISABLED_STYLE = (
    'QFrame#cleanRclRow[rclDisabled="true"] { background-color: rgba(96, 96, 96, 0.18); }'
    'QFrame#cleanRclRow[rclDisabled="true"] QLabel, '
    'QFrame#cleanRclRow[rclDisabled="true"] QComboBox, '
    'QFrame#cleanRclRow[rclDisabled="true"] QLineEdit, '
    'QFrame#cleanRclRow[rclDisabled="true"] QCheckBox { color: #888; }'
)
_MAPPING_COMBO_HIGHLIGHT_STYLE = (
    "QComboBox#valvetMappingCombo { border: 2px solid #42a5f5; }"
)
