# Session log

## Session 1 — disc and format analysis

Goal: understand how the disc is built and which formats we will be dealing
with.

Results:

* **`CDIMAGE.TBL` decoded** and verified byte-exact: a 3818-entry index of
  136-byte records into the monolithic `RPGSP.DAT` archive (2.5 GB).
* **`.p64` / `.mpic` decoded and validated**: container plus indexed 4/8 bpp
  texture block, palette stored at the end in CSM1 order, PS2 `0..128`
  alpha. `tools/p64_decode.py` produces correct PNGs.
* **`.iab` audio decoded**: SPU-ADPCM, with a header declaring rate,
  channels, duration and — when present — a 640x448 video track.
* **`.smp` identified**: database preset records, fixed size per category,
  matching the `CEdPro*` classes.
* **`.bin` identified** as pre-built DMA/VIF1 chains (not meshes).
* **Engine architecture mapped** from the executable's RTTI names: 224
  classes, including the whole `SG_*` scene graph, the ~100 `CEdEv*` event
  commands, the `CEdPro*` data model and the keyframe cutscene sequencer.
* Ten curiosities documented in `04-curiosities.md`.

Tools written: `rpgsp_index.py`, `p64_decode.py`, `pstrings.py`.

## Session 2 — cracking the .iab video codec

Goal: identify the video codec, which had no MPEG start codes anywhere and
so could not be played by anything.

Results:

* **The `.iab` body is a chunk chain**, not a fixed interleave: 16-byte
  headers carrying a magic, a float timestamp, size and stride. Walking it
  lands exactly on the end of the file, and gives exactly one chunk per
  frame. The two unknown header fields are the max and min frame size.
* **The codec is MPEG-2 intra** — established by finding the MPEG default
  quantiser matrices in the executable, then showing that the flat frame's
  bitstream is periodic with a period of exactly 42 bits, in 28 runs (one
  per macroblock row of 640x448), and that a macroblock reconstructed from
  the MPEG-2 spec with `intra_vlc_format = 1` matches those 42 bits exactly.
* **There is no slice layer.** The 6 extra bits per row come from the first
  macroblock of each row using `macroblock_type = '01'` (Intra, Quant) to
  re-send the quantiser. Full write-up in `06-iab-video.md`.
* **`tools/iab_video.py`** rebuilds a valid MPEG-2 elementary stream; ffmpeg
  decodes `logo.iab` (220 frames) and `rpg_640_448.iab` (3568 frames) with
  zero errors.
* **`tools/iab_audio.py`** decodes the SPU-ADPCM track to WAV, matching the
  declared duration to the sample.
* **Colour range settled**: the video is full-range YUV, as the PS2 IPU
  produces; decoding it as studio swing blows the highlights out.
* **`.mpic` decoder validated against hardware**: our Agetec logo decode
  matches a PCSX2 frame capture to a mean of 0.9 per colour channel.
* Four more curiosities (11-14), including a fully intact Japanese series
  ident that the USA release never plays.

Still open: the short per-frame header before the macroblock stream, whose
length varies per file. See `05-open-questions.md`.

Next step: the project format (`sample/game/*`), which is the core of the
engine.
