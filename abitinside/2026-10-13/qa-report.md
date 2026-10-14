# QA report - A Bit Inside, 2026-10-13

Run against `video/sample-final.mp4` on 2026-10-14 UTC.

**41 of 41 checks passed.**

| # | gate | result | detail | measurement |
|---|---|---|---|---|
| 1 | 1a codec h264 High, yuv420p | PASS | h264/High/yuv420p | h264 High yuv420p |
| 2 | 1b geometry 1080x1920 | PASS | 1080x1920 | 1080x1920 |
| 3 | 1c constant frame rate 30 fps | PASS | 30/1, 3326 frames vs timeline 3326 | 30/1 nb_frames=3326 |
| 4 | 1d audio AAC 48 kHz stereo | PASS | aac 48000 Hz 2ch | aac 48000 2 |
| 5 | 1e duration inside the 65-175 s window | PASS | 110.867 s | 110.867s |
| 6 | 1f A/V duration difference <= 40 ms | PASS | 18.7 ms | 18.7 ms |
| 7 | 1g colour tags bt709 | PASS | bt709/bt709/bt709 | bt709 |
| 8 | 1h file size under 150 MB | PASS | 11.8 MB | 11.8 MB |
| 9 | 2a integrated loudness -14 +/-0.5 LUFS | PASS | -14.00 LUFS | -14.00 LUFS |
| 10 | 2b true peak <= -1.5 dBTP | PASS | -3.59 dBTP | -3.59 dBTP |
| 11 | 2c no digital clipping | PASS | sample peak -3.59 dBFS | -3.59 dBFS |
| 12 | 2d a real noise floor, so silence never reads as dead | PASS | 5th percentile RMS 0.013214 | 0.013214 |
| 13 | 2e no silent gap longer than 1.2 s (designed pre-reveal drop <= 0.4 s) | PASS | longest quiet run 1.05 s | 1.05 s |
| 14 | 3a all content inside x 120-960 | PASS | content spans x 119..960 | min=119 max=960 |
| 15 | 3b nothing below y=1610 | PASS | lowest content y = 1562 (frame 1470) | 1562 |
| 16 | 3c illustration area clear of y 1420-1462 (captions start at 1470) | PASS | 0 lit px in the gap band | 0 px |
| 17 | 3d caption band present (sound-off comprehension) | PASS | 1458221 lit px in the caption band | 1458221 px |
| 18 | 3e every 15th frame had content | PASS | no empty or stray frames | 222 frames decoded every 15 |
| 19 | 3h the illustration band is never empty (no dead frame after a cut) | PASS | minimum 11485 lit px in the band, longest sparse stretch 0.00 s | min=11485 px, longest gap=0.00 s, dead=0 |
| 20 | 3f headline lines fit the safe zone and are centred on x=540 | PASS | all headline lines centred | 13 scenes |
| 21 | 3g caption groups fit the safe zone and are centred on x=540 | PASS | 167 groups, widest 770 px | widest=770px |
| 22 | 4a every on-screen glyph exists in the font (no .notdef boxes) | PASS | 69 distinct characters checked, all present | 69 chars |
| 23 | 5a spelling of the script and all on-screen text | PASS | no unknown words outside the allow-list | 221 strings spell-checked |
| 24 | 6a every number in the script and on screen maps to facts.json | PASS | 8 distinct numeric tokens, all mapped | 8 tokens |
| 25 | 6b every source URL returned HTTP 200 when re-fetched in this run | PASS | all source URLs re-fetched with HTTP 200 in this run | 4 URLs re-fetched |
| 26 | 7a impact/chime onsets land within +/-1 frame of their cue (cross-correlation of the SFX stem against the SFX isolated from the delivered file) | PASS | worst offset 0.0 ms over 5 cues | 0.0 ms |
| 27 | 7b every sentence's speech onset lands within +/-1 frame of the timeline position its caption groups use | PASS | worst offset 0.0 ms over 30 sentences | 0.0 ms |
| 28 | 7c every caption group belongs to the scene that contains it | PASS | 167 of 167 groups placed inside their scene | 167/167 |
| 29 | 8a text and artwork present by frame 4 | PASS | frame 4 has 111185 lit px | 111185 px |
| 30 | 8b motion already present in the first frames | PASS | largest mean frame delta in frames 1-6 = 1.747 | 1.747 |
| 31 | 8c first sound by frame 4 | PASS | peak amplitude in the first 4 frames = 0.347 | 0.347 |
| 32 | 8d the hook sentence starts by 0.3 s | PASS | hook starts at 133 ms | 133 ms |
| 33 | 9a a visual change at least every 4 s | PASS | longest static run 1.67 s | 1.67 s |
| 34 | 9b final payoff held at least 1.5 s | PASS | payoff hold 2.27 s | 2.27 s |
| 35 | 9c end card at most 1.5 s | PASS | end card 1.20 s | 1.20 s |
| 36 | 9d last frame equals the first frame (seamless loop) | PASS | source frames differ by 0.0000 levels; the decoded pair differs by 0.1460 levels, which is the I-frame/P-frame quality gap, not content | source 0.0000, encoded 0.1460 |
| 37 | 10a no external asset pipeline, no forbidden service in the source | PASS | clean | 17 source files scanned |
| 38 | 10b every binary asset is one this repo downloaded or generated | PASS | 4 font files, 1 voice model(s), all under abitinside/assets/ | 4 fonts / 1 voices |
| 39 | 10c ILLUSTRATIVE label appears on the scenes that draw mock-ups | PASS | label present on 43 sampled frames | 43 frames |
| 40 | 10d the description states the synthetic voice and illustrative animation | PASS | both statements present | description checked |
| 41 | 11a contact sheet written at one frame per second | PASS | contact-sheet.png (2030 kB, 111 frames) | 111 frames |

## Delivery parameters actually measured

- container duration: 110.867 s (3326 frames at 30 fps)
- integrated loudness: **-14.00 LUFS** (target -14 +/-0.5)
- true peak: **-3.59 dBTP** (target <= -1.5)
- loudness range: 1.9 LU
- music bed ducking: -6.5 dB, attack 0.02 s, release 0.4 s
- file size: 11.8 MB

## What this report cannot tell you

These gates are measurements on decoded frames and audio. They cannot judge
whether the video *feels* right to watch. See Known limitations in the final
build report: a human must watch the finished mp4 once with sound on and once
muted before it is uploaded.
