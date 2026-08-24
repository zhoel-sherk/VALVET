def prefs_profile_bool(val: object, default: bool = False) -> bool:
    """
    Coerce JSON / profile / string values to bool.

    ``bool("false")`` is True in Python, so plain ``bool(c.get(...))`` breaks
    checkboxes when a profile stores string flags.
    """
    if isinstance(val, bool):
        return val
    if isinstance(val, (int, float)) and not isinstance(val, bool):
        return bool(val)
    if isinstance(val, str):
        v = val.strip().lower()
        if v in ("0", "false", "no", "off", ""):
            return False
        if v in ("1", "true", "yes", "on"):
            return True
    return default


_prefs_profile_bool = prefs_profile_bool
