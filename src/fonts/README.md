# Bundled fonts (`src/fonts/`)

## UI vs tables vs console

- **Main UI (chrome, combos, line edits):** `QSettings` `ui/font_family` (`inter` or `system`), `ui/font_point_size`, `ui/font_style` (`regular` / `bold` / `italic` / `bolditalic`). Defaults: Inter when TTFs are present, else system sans.
- **Data tables (BOM/PnP grids, tree views, headers):** `ui/table_font_family` (`jetbrains` / `inter` / `system`), `ui/table_font_point_size`, `ui/table_font_style`. Default table face is **JetBrains Mono** when bundled.
- **Project tab console log:** always monospace — JetBrains Mono when bundled, else Consolas / DejaVu Sans Mono / similar. Uses `ui/font_point_size` (clamped for the log).

PyInstaller copies `*.ttf` from this directory into the bundle under `fonts/` (see `boomer.spec`).

## Inter (SIL OFL 1.1)

[Inter](https://github.com/rsms/inter) — [SIL Open Font License 1.1](https://github.com/rsms/inter/blob/master/LICENSE.txt).

### Obtain the files

**Script (from repo `boomer/` root, network required):**

```bash
source venv/bin/activate
python tools/fetch_inter.py
```

**Manual:** from an [Inter release ZIP](https://github.com/rsms/inter/releases), copy from `extras/ttf/`:

- `Inter-Regular.ttf`
- `Inter-Bold.ttf`
- `Inter-Italic.ttf`
- `Inter-BoldItalic.ttf`

If none are present, the UI falls back to the system sans stack.

## JetBrains Mono (SIL OFL 1.1)

[JetBrains Mono](https://github.com/JetBrains/JetBrainsMono) — [SIL Open Font License 1.1](https://github.com/JetBrains/JetBrainsMono/blob/master/OFL.txt).

### Obtain the files

**Script (from repo `boomer/` root, network required):**

```bash
source venv/bin/activate
python tools/fetch_jetbrains_mono.py
```

**Manual:** from a [release ZIP](https://github.com/JetBrains/JetBrainsMono/releases), copy from `fonts/ttf/`:

- `JetBrainsMono-Regular.ttf`
- `JetBrainsMono-Bold.ttf`
- `JetBrainsMono-Italic.ttf`
- `JetBrainsMono-BoldItalic.ttf`

If none are present, the console still works with a system monospace fallback.
