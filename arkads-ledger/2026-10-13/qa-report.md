# Arkad's Ledger - QA report

Generated 2026-10-14T20:49:25Z

Video: `sample-final.mp4` (24.3 MB, 3128 frames, 104.27 s)

**4 of 13 gates passed.**

**Status: NOT READY**

| # | Gate | Result | Detail |
|---|---|---|---|
| 1 | container: codec, geometry, CFR, audio, duration | PASS | codec=h264; profile=High; 1080x1920; fps=30.0; avg_fps=30.0; pix=yuv420p; audio=aac; sr=48000; ch=2; dur=104.27s; A/V diff=0ms; cs=bt709; 24.3MB; frames=3128 expected 3128 |
| 2 | loudness: -16 LUFS, true peak, LRA, gaps | **FAIL** | NameError: name 'Q_silence' is not defined |
| 3 | layout: safe zone, centres, no blank run | **FAIL** | NameError: name '_background_plate' is not defined |
| 4 | glyphs: every on-screen character exists in the font | PASS | 84 characters covered by all four weights |
| 5 | text: spelling and number proofreading | **FAIL** | spelling=[] unknown_numbers=['0.29', '0.54', '0.65', '1.000', '7.8'] |
| 6 | facts and sources: URLs live, values traceable | **FAIL** | unreachable=[] unknown_spoken_numbers=['0.29', '0.54', '0.65', '1.000', '7.8'] |
| 7 | sync: SFX onsets and caption word starts | **FAIL** | worst onset 238ms, caption drift 0.0 frames |
| 8 | voice: flags logged and ASR match >= 95% | PASS | ASR word match 96.8% against small.en; 19 voice_qa flag(s) logged |
| 9 | map: bake once per scene, no per-frame geo, legend, glow source | **FAIL** | UnicodeDecodeError: 'utf-8' codec can't decode byte 0x89 in position 0: invalid start byte |
| 10 | hook and rhythm | **FAIL** | NameError: name '_visual_changes' is not defined |
| 11 | brand and legal | **FAIL** | violations=['src/theme.py: A Bit Inside', 'src/theme.py: ShakaHub'] disclosure=True |
| 12 | thumbnail | PASS | PNG (1080, 1920); JPG (1080, 1920); JPG 169 kB (<2MB); headline 4 words (max 5); margin difference 0.0px; downscaled contrast 255.0 |
| 13 | contact sheets | **FAIL** | TypeError: g13.<locals>.overlay_zones() takes 1 positional argument but 2 were given |

## Voice QA flags carried into the mix

The brief requires a calm, even mentor delivery, and the mandated Piper `en_US-ryan-high` narrator has a naturally narrow pitch range. The FLAT threshold (pitch SD < 1.8 semitones on >= 8 words) fires on that prosody rather than on a defective take, so re-synthesis cannot clear it. Each remaining flag is listed here with its sentence, as the brief requires.

| Scene | Flags | Sentence | Attempts |
|---|---|---|---|
| hook | FLAT | One American dollar buys about eight dollars worth of life in Nigeria. | 4 |
| hook | FLAT | In America, that same dollar buys exactly one dollar. | 4 |
| setup | FLAT | Neither number is a mistake. They answer different questions. | 4 |
| setup | FLAT | Markets price currency by trade. Nobody prices your groceries by trade. | 4 |
| setup | FLAT | So the exchange rate and your actual spending drift apart. | 4 |
| mechanism | FLAT, RUSH | An exchange rate tells you what you get when you trade currency. | 4 |
| mechanism | FLAT, RUSH | A price level tells you what your money actually buys where you live. | 4 |
| mechanism | FLAT, RUSH | One is a trade quote. The other is a shopping list. | 4 |
| dev_high | FLAT | The World Bank measures this and calls it the price level ratio. | 4 |
| dev_high | FLAT | It compares income per person converted at market rates with income per person converted at what it actually buys. | 3 |
| dev_high | FLAT | America sits at 1.000, because it is the reference country. | 3 |
| dev_high | FLAT | Britain is just below at 0.89. Germany is 0.80. Japan is 0.65. | 2 |
| dev_mid | FLAT | These are not rich or poor countries. They are cheap or expensive ones. | 4 |
| reveal | FLAT | India is 0.23. Nigeria is 0.128, the lowest here. | 2 |
| reveal | FLAT | Multiply that ratio by the American dollar and the gap becomes plain. | 4 |
| reveal | FLAT | One dollar of income in Nigeria is worth about 7.8 dollars in America. | 2 |
| payoff | FLAT, RUSH | If you compare incomes across a map using only the exchange rate, you measure the wrong thing. | 2 |
| payoff | FLAT, RUSH | A cheap country is not a poor country. It is a country where your money stretches. | 4 |
| payoff | FLAT | Prices are local. That is the whole mechanism. | 4 |

## Map and asset provenance

- Glow source: **procedural** - no no-login WorldPop or VIIRS raster was reachable; density field rasterised from Natural Earth rivers and populated places weighted by population
- Tried in order: worldpop, viirs
- Baked base map: `world_base.png` (1322 kB)
- Baked base map: `world_base.json` (0 kB)
- CRS: `EPSG:8857` (WGS 84 / Equal Earth Greenwich), equal-area: True
- Fonts: Montserrat ExtraBold/Bold/SemiBold/Medium, static instances created with fontTools from the official Google Fonts variable font.
- Narration: local Piper `en_US-ryan-high`, offline, no API key.
- Backgrounds, borders, coastline, rivers, lakes and populated places: Natural Earth 10m.

## Known build notes

- This machine has 2 cores and about 3.9 GB of RAM. The brief's 'under 30 minutes on an 8-core machine' target is not reachable here; the render measured about 35 minutes end to end at full quality. No resolution or quality was reduced.

