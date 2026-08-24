# Parser encoding rules

Tables below are the **coding rules** VALVET tests against (extracted from `src/pn_original/` and regex parsers). Official PDFs belong in `pdf/` (gitignored).

Each file has a `## samples` table:

| mpn_or_bom | ctype | expected | path |
| --- | --- | --- | --- |
| RC0402FR-0710KL | RES | 0402_10K_1% | vendor |

`path` is `vendor` (MPN codecs on, regex later) or `regex` (vendor+hanwha disabled).

Retrieved: 2026-08-24
