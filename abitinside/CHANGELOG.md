# Changelog

## 1.0.0

Layout safe zones. New videos are scene DSL placed by `abitinside/layout` and published only with a certificate. The 2026-10-13 episode is unchanged and is rejected by the gate.

Zones, type floors, and gaps live in `layout/layout_spec.yaml`. `pipeline/export.py` and `2026-10-13/src/stamp_metadata.py` refuse to write upload metadata for a file that is not certified. That is the only episode wiring, and it does not change the episode's pictures.
