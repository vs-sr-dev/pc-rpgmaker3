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
* **`.iab` audio decoded**: interleaved SPU-ADPCM in 8192-byte blocks, with
  a header declaring rate, channels, duration and — when present — a
  640x448 video track.
* **`.smp` identified**: database preset records, fixed size per category,
  matching the `CEdPro*` classes.
* **`.bin` identified** as pre-built DMA/VIF1 chains (not meshes).
* **Engine architecture mapped** from the executable's RTTI names: 224
  classes, including the whole `SG_*` scene graph, the ~100 `CEdEv*` event
  commands, the `CEdPro*` data model and the keyframe cutscene sequencer.
* Ten curiosities documented in `04-curiosities.md`.

Tools written: `rpgsp_index.py`, `p64_decode.py`, `pstrings.py`.

Next step: the project format (`sample/game/*`), which is the core of the
engine.
