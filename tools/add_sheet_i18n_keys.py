"""Add worksheet-picker i18n keys to every locale catalog (idempotent)."""

from __future__ import annotations

import json
from pathlib import Path

LANG_DIR = Path(__file__).resolve().parents[1] / "lang"

NEW = {
    "en": {
        "bom.sheet": "Sheet:",
        "bom.sheet_tip": (
            "Which worksheet to read from an Excel/ODS BOM. "
            "'(auto)' picks the first visible sheet; hidden sheets are marked '(hidden)'."
        ),
        "bom.sheet_rows": "{sheet} — {rows} rows",
        "pnp.sheet": "Sheet:",
        "pnp.sheet_tip": (
            "Which worksheet to read from an Excel/ODS placement file. "
            "'(auto)' picks the first visible sheet; hidden sheets are marked '(hidden)'."
        ),
        "pnp.sheet_rows": "{sheet} — {rows} rows",
    },
    "ru": {
        "bom.sheet": "Лист:",
        "bom.sheet_tip": (
            "Какой лист читать из Excel/ODS-файла BOM. "
            "'(auto)' берёт первый видимый лист; скрытые помечены '(hidden)'."
        ),
        "bom.sheet_rows": "{sheet} — строк: {rows}",
        "pnp.sheet": "Лист:",
        "pnp.sheet_tip": (
            "Какой лист читать из Excel/ODS-файла размещения. "
            "'(auto)' берёт первый видимый лист; скрытые помечены '(hidden)'."
        ),
        "pnp.sheet_rows": "{sheet} — строк: {rows}",
    },
    "de": {
        "bom.sheet": "Blatt:",
        "bom.sheet_tip": (
            "Welches Arbeitsblatt aus einer Excel/ODS-BOM gelesen wird. "
            "'(auto)' wählt das erste sichtbare Blatt; ausgeblendete sind mit '(hidden)' markiert."
        ),
        "bom.sheet_rows": "{sheet} — {rows} Zeilen",
        "pnp.sheet": "Blatt:",
        "pnp.sheet_tip": (
            "Welches Arbeitsblatt aus einer Excel/ODS-Bestückungsdatei gelesen wird. "
            "'(auto)' wählt das erste sichtbare Blatt; ausgeblendete sind mit '(hidden)' markiert."
        ),
        "pnp.sheet_rows": "{sheet} — {rows} Zeilen",
    },
    "pl": {
        "bom.sheet": "Arkusz:",
        "bom.sheet_tip": (
            "Który arkusz czytać z pliku Excel/ODS BOM. "
            "'(auto)' wybiera pierwszy widoczny arkusz; ukryte są oznaczone '(hidden)'."
        ),
        "bom.sheet_rows": "{sheet} — wierszy: {rows}",
        "pnp.sheet": "Arkusz:",
        "pnp.sheet_tip": (
            "Który arkusz czytać z pliku rozmieszczenia Excel/ODS. "
            "'(auto)' wybiera pierwszy widoczny arkusz; ukryte są oznaczone '(hidden)'."
        ),
        "pnp.sheet_rows": "{sheet} — wierszy: {rows}",
    },
    "pt": {
        "bom.sheet": "Planilha:",
        "bom.sheet_tip": (
            "Qual planilha ler de um BOM Excel/ODS. "
            "'(auto)' usa a primeira planilha visível; as ocultas estão marcadas '(hidden)'."
        ),
        "bom.sheet_rows": "{sheet} — {rows} linhas",
        "pnp.sheet": "Planilha:",
        "pnp.sheet_tip": (
            "Qual planilha ler de um arquivo de posicionamento Excel/ODS. "
            "'(auto)' usa a primeira planilha visível; as ocultas estão marcadas '(hidden)'."
        ),
        "pnp.sheet_rows": "{sheet} — {rows} linhas",
    },
    "zh": {
        "bom.sheet": "工作表：",
        "bom.sheet_tip": (
            "从 Excel/ODS BOM 文件读取哪个工作表。"
            "'(auto)' 使用第一个可见工作表；隐藏工作表标记为 '(hidden)'。"
        ),
        "bom.sheet_rows": "{sheet} — {rows} 行",
        "pnp.sheet": "工作表：",
        "pnp.sheet_tip": (
            "从 Excel/ODS 贴片文件读取哪个工作表。"
            "'(auto)' 使用第一个可见工作表；隐藏工作表标记为 '(hidden)'。"
        ),
        "pnp.sheet_rows": "{sheet} — {rows} 行",
    },
}


def main() -> None:
    for loc, additions in NEW.items():
        path = LANG_DIR / f"{loc}.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        added = [k for k in additions if k not in data]
        data.update(additions)
        path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(f"{loc}: added {len(added)} keys -> {path.name}")


if __name__ == "__main__":
    main()
