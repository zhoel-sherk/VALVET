# VALVET — ALPHA v0.2.0

[English](README.md) | **Русский**

<p align="center">
  <img src="img/readme.svg" alt="VALVET — Validator And Line-Verified Export Tool" width="880"/>
</p>

Десктоп (PySide6) для подготовки SMT: открыть **BOM** и **pick-and-place**, почистить имена, сверить, слить, выгрузить на линию.

Репозиторий: [zhoel-sherk/VALVET](https://github.com/zhoel-sherk/VALVET). Свой проект (не GitHub-форк [marmidr/boomer](https://github.com/marmidr/boomer)). **ALPHA** — правка Hanwha MDB, PCB Preview и Step 3D ещё сырые.

## Скриншоты

<table>
<tr>
<td width="50%" valign="top">
<img src="img/data_bom.png" alt="DATA BOM" width="100%"/>
<p><em>DATA — BOM</em></p>
</td>
<td width="50%" valign="top">
<img src="img/data_pnp.png" alt="DATA PnP" width="100%"/>
<p><em>DATA — PnP</em></p>
</td>
</tr>
<tr>
<td width="50%" valign="top">
<img src="img/transform_clean.png" alt="TRANSFORM Clean BOM" width="100%"/>
<p><em>TRANSFORM — Clean BOM</em></p>
</td>
<td width="50%" valign="top">
<img src="img/transform_merge.png" alt="TRANSFORM Merge" width="100%"/>
<p><em>TRANSFORM — Merge / Export</em></p>
</td>
</tr>
<tr>
<td width="50%" valign="top">
<img src="img/output_report.png" alt="OUTPUT Report" width="100%"/>
<p><em>OUTPUT — Report</em></p>
</td>
<td width="50%" valign="top">
<img src="img/view_machine.png" alt="VIEW Machine lib" width="100%"/>
<p><em>VIEW — Machine lib</em></p>
</td>
</tr>
</table>

## Установка: Windows zip (без Python)

1. Скачай [VALVET-0.2.0-windows-x64.zip](https://github.com/zhoel-sherk/VALVET/releases/download/v0.2.0/VALVET-0.2.0-windows-x64.zip) с [релиза v0.2.0](https://github.com/zhoel-sherk/VALVET/releases/tag/v0.2.0).
2. Распакуй. Запусти `VALVET\VALVET.exe` (папка `_internal` должна лежать рядом с exe).
3. На флешку копируй **всю** папку.

В WinGet заявлен id **ZhoelSherk.VALVET**; пока PR не принят — бери zip. В zip **нет** `examples/`, нет ACE ODBC и pythonocc.

## Установка: из этого репозитория (разработка)

Нужен Python **3.10+**. В корне клона (там же `requirements.txt`):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
$env:PYTHONPATH = "src"
python src/main.py
```

Linux / macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
PYTHONPATH=src python src/main.py
```

`--debug` пишет логи, как галочка «Debug logs» на вкладке Project. Шрифты по желанию: `python tools/fetch_inter.py` и `python tools/fetch_jetbrains_mono.py`. Тесты: [doc/info/TESTING.md](doc/info/TESTING.md).

## Пример: первая плата (из репо)

Файлы в `examples/example1/`.

1. **DATA — BOM** → `Kaseta_2v1 BOM_results.txt`. В шапке: **REF** и **Comment** (имя компонента). **PnJoin** — только если вторую колонку надо приклеить к имени после Clean.
2. **DATA — PnP** → `Pick Place for Kaseta2v1(Standard).csv`. **REF**, **X**, **Y**, **Rotation**, **Layer** (плюс Comment / footprint, если есть).
3. **TRANSFORM — Clean BOM** → при необходимости Parser Settings → Convert. Вернуть чистые имена в BOM.
4. **OUTPUT — Report** → сверка (нет рефа, другой comment, одинаковые XY).
5. **TRANSFORM — Merge / Export** → Merge → CSV/XLSX или **Export Top** / **Export Bot**.

Другие образцы:

| Папка | Что |
| --- | --- |
| `examples/example2/` | BOM `.csv` + PnP `.txt` |
| `examples/example3/` | PnP `.csv` |
| `examples/mmd/` | эталоны экспорта `.mmd` |
| `examples/gerber_example3/` | Gerber для **VIEW — PCB Preview** |
| `examples/UPD.MDB` | библиотека Hanwha для **VIEW — Machine lib** (на Windows in-place save нужен ACE ODBC) |

`components.txt` в корне — образец списка компонентов (другой файл: переменная `BOOMER_COMPONENTS_TXT`).

## Вкладки (кратко)

| Группа | Вкладка | Зачем |
| --- | --- | --- |
| DATA | Project | Профиль, язык (`lang/`), сессия |
| DATA | BOM / PnP | `.xls` `.xlsx` `.csv` `.ods` `.txt` `.tab`, маппинг, правка, автосейв |
| TRANSFORM | Clean BOM | декод R/C/L + regex; вендорные PN (Yageo, Murata, …) |
| TRANSFORM | Merge / Export | слить BOM в PnP; Top/Bot / `.mmd` |
| OUTPUT | Report | сверка BOM и PnP |
| VIEW | PCB Preview | Gerber + наложение PnP (WIP) |
| VIEW | Step 3D | `.stp` / `.step` — доп. пакеты ниже |
| VIEW | Machine lib | Hanwha `.mdb` (WIP); Yamaha позже |

Настройки: организация **VALVET**. Профиль помнит маппинг и опции, не пути к файлам. Размер окна и последняя папка Browse — отдельно.

Step 3D по желанию: `pip install -r requirements-step3d.txt`, тесселяция `requirements-step3d-occ.txt` (на Windows удобнее conda-forge `pythonocc-core`). Или внешняя команда STEP→OBJ в Debug.

CLI без Qt: `pip install -r requirements-cli.txt`, затем `PYTHONPATH=src python -m cli --help`.

## Ещё

Дорожная карта: [doc/TODO.md](doc/TODO.md). Сборка Windows: [doc/info/PACKAGING_WINDOWS.md](doc/info/PACKAGING_WINDOWS.md). Лицензия: [MIT](LICENSE).

<p align="center">
  <img src="img/icon-512.png" alt="VALVET logo" width="120"/>
</p>
