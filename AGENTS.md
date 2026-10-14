# A Bit Inside layout

Never place elements with raw coordinates in scene files.
Never call text drawing outside `abitinside/layout/text.py`.
Never edit numbers in `layout_spec.yaml` without updating the tests.
Never bypass or weaken a validator, and never lower a threshold to make a build pass.
Every scene change is followed by `python -m layout validate` and `python -m layout qa`.
If a violation occurs, shorten the content or change the template. Do not change the rules.
