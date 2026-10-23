# Parser encoding rules

Tables below are the **coding rules** VALVET tests against (extracted from `src/pn_original/` and regex parsers). Official PDFs belong in `pdf/` (gitignored).

Each file has a `## samples` table:

| mpn_or_bom | ctype | expected | path |
| --- | --- | --- | --- |
| RC0402FR-0710KL | RES | 0402_10K_1% | vendor |

`path` is `vendor` (MPN codecs on, regex later) or `regex` (vendor+hanwha disabled).

Retrieved: 2026-08-24

## Local PDF library

`datasheet/pdf/` is gitignored (`.gitignore`: `*.pdf`, `*.PDF`, `datasheet/pdf/`),
so manufacturer documents never enter the repository. Keep the local copies in
one shape so tables and docstrings can cite them unambiguously:

```
<vendor>_<family-or-document>_<kind>.pdf
```

- lowercase ASCII, `_` separators, no spaces, no `(1)` copies;
- `kind` is one of `catalog`, `datasheet`, `spec`, `approval_sheet`,
  `partnumber`, `guide`, `catalog_excerpt`;
- one file per document: exact duplicates are deleted, different revisions or
  documents from the same family get a distinguishing suffix (`_2016` /
  `_2017`, `_new`, `_power`, `_v`).

Cite the file name in tables and docstrings, e.g.
`samsung_mlcc_catalog_commercial_2025.pdf` p.6. PDFs are reference material:
a new parser or decoder must be justified against them, never invented from a
sample BOM alone.

