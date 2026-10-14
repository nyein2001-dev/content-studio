# Layout safe zones

The zone map, the R01–R16 table, the content limits, and the component catalog are in [LAYOUT_RULES.md](LAYOUT_RULES.md).

Scene files name components and text. They do not contain coordinates. `python -m layout validate` checks geometry. `python -m layout qa` adds the pixel pass. `python -m layout publish` refuses a video that has an error, a missing font, or a report older than the file.
