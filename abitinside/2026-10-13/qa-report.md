# QA report - A Bit Inside, 2026-10-13

Run against `video/sample-final.mp4` on 2026-10-14 UTC.

**44 of 44 checks passed.**

| # | gate | result | detail | measurement |
|---|---|---|---|---|
| 1 | 1a codec h264 High, yuv420p | PASS | h264/High/yuv420p | h264 High yuv420p |
| 2 | 1b geometry 1080x1920 | PASS | 1080x1920 | 1080x1920 |
| 3 | 1c constant frame rate 30 fps | PASS | 30/1, 3645 frames vs timeline 3645 | 30/1 nb_frames=3645 |
| 4 | 1d audio AAC 48 kHz stereo | PASS | aac 48000 Hz 2ch | aac 48000 2 |
| 5 | 1e duration inside the 65-175 s window | PASS | 121.500 s | 121.500s |
| 6 | 1f A/V duration difference <= 40 ms | PASS | 7.0 ms | 7.0 ms |
| 7 | 1g colour tags bt709 | PASS | bt709/bt709/bt709 | bt709 |
| 8 | 1h file size under 150 MB | PASS | 14.0 MB | 14.0 MB |
| 9 | 2a integrated loudness -14 +/-0.5 LUFS | PASS | -14.00 LUFS | -14.00 LUFS |
| 10 | 2b true peak <= -1.5 dBTP | PASS | -3.65 dBTP | -3.65 dBTP |
| 11 | 2c no digital clipping | PASS | sample peak -3.65 dBFS | -3.65 dBFS |
| 12 | 2d a real noise floor, so silence never reads as dead | PASS | 5th percentile RMS 0.013177 | 0.013177 |
| 13 | 2e no silent gap longer than 1.2 s (designed pre-reveal drop <= 0.4 s) | PASS | longest quiet run 1.00 s | 1.00 s |
| 14 | 3a all content inside x 120-960 | PASS | content spans x 119..960 | min=119 max=960 |
| 15 | 3b nothing below y=1610 | PASS | lowest content y = 1562 (frame 570) | 1562 |
| 16 | 3c illustration area clear of y 1420-1462 (captions start at 1470) | PASS | 0 lit px in the gap band | 0 px |
| 17 | 3d caption band present (sound-off comprehension) | PASS | 3999851 lit px in the caption band | 3999851 px |
| 18 | 3e every 15th frame had content | PASS | no empty or stray frames | 243 frames decoded every 15 |
| 19 | 3h the illustration band is never empty (no dead frame after a cut) | PASS | minimum 7617 lit px in the band, longest sparse stretch 0.00 s | min=7617 px, longest gap=0.00 s, dead=0 |
| 20 | 3f headline lines fit the safe zone and are centred on x=540 | PASS | all headline lines centred | 13 scenes |
| 21 | 3g caption groups fit the safe zone and are centred on x=540 | PASS | 104 groups, widest 796 px | widest=796px |
| 22 | 4a every on-screen glyph exists in the font (no .notdef boxes) | PASS | 70 distinct characters checked, all present | 70 chars |
| 23 | 5a spelling of the script and all on-screen text | PASS | no unknown words outside the allow-list | 158 strings spell-checked |
| 24 | 6a every number in the script and on screen maps to facts.json | PASS | 8 distinct numeric tokens, all mapped | 8 tokens |
| 25 | 6b every source URL returned HTTP 200 when re-fetched in this run | PASS | all source URLs re-fetched with HTTP 200 in this run | 4 URLs re-fetched |
| 26 | 7a impact/chime onsets land within +/-1 frame of their cue (cross-correlation of the SFX stem against the SFX isolated from the delivered file) | PASS | worst offset 0.0 ms over 5 cues | 0.0 ms |
| 27 | 7b every sentence's speech onset lands within +/-1 frame of the timeline position its caption groups use | PASS | worst offset 0.0 ms over 30 sentences | 0.0 ms |
| 28 | 7c every caption group belongs to the scene that contains it | PASS | 104 of 104 groups placed inside their scene | 104/104 |
| 29 | 8a text and artwork present by frame 4 | PASS | frame 4 has 110792 lit px | 110792 px |
| 30 | 8b motion already present in the first frames | PASS | largest mean frame delta in frames 1-6 = 1.697 | 1.697 |
| 31 | 8c first sound by frame 4 | PASS | peak amplitude in the first 4 frames = 0.355 | 0.355 |
| 32 | 8d the hook sentence starts by 0.3 s | PASS | hook starts at 133 ms | 133 ms |
| 33 | 9a a visual change at least every 4 s | PASS | longest static run 1.83 s | 1.83 s |
| 34 | 9b final payoff held at least 1.5 s | PASS | payoff hold 2.23 s | 2.23 s |
| 35 | 9c end card at most 1.5 s | PASS | end card 1.20 s | 1.20 s |
| 36 | 9d last frame equals the first frame (seamless loop) | PASS | source frames differ by 0.0000 levels; the decoded pair differs by 0.1450 levels, which is the I-frame/P-frame quality gap, not content | source 0.0000, encoded 0.1450 |
| 37 | 10a no external asset pipeline, no forbidden service in the source | PASS | clean | 18 source files scanned |
| 38 | 10b every binary asset is one this repo downloaded or generated | PASS | 4 font files, 1 voice model(s), all under abitinside/assets/ | 4 fonts / 1 voices |
| 39 | 10c ILLUSTRATIVE label appears on the scenes that draw mock-ups | PASS | label present on 48 sampled frames | 48 frames |
| 40 | 10d the description states the synthetic voice and illustrative animation | PASS | both statements present | description checked |
| 41 | 11a contact sheet written at one frame per second | PASS | contact-sheet.png (2384 kB, 122 frames) | 122 frames |
| 42 | 12a Andrew voice on every segment | PASS | en-US-AndrewNeural | en-US-AndrewNeural |
| 43 | 12b captions keep spaces and end when the last word ends | PASS | 104 groups keep spaces and word ends | 104 groups keep spaces and word ends |
| 44 | 12c publish file is named from the title | PASS | how-hackers-heated-150-supermarket-fridges-to-50c.mp4 | how-hackers-heated-150-supermarket-fridges-to-50c.mp4 |

## Delivery parameters actually measured

- container duration: 121.500 s (3645 frames at 30 fps)
- integrated loudness: **-14.00 LUFS** (target -14 +/-0.5)
- true peak: **-3.65 dBTP** (target <= -1.5)
- loudness range: 2.6 LU
- music bed ducking: -6.5 dB, attack 0.02 s, release 0.4 s
- file size: 14.0 MB

## What this report cannot tell you

These gates are measurements on decoded frames and audio. They cannot judge
whether the video *feels* right to watch. See Known limitations in the final
build report: a human must watch the finished mp4 once with sound on and once
muted before it is uploaded.
