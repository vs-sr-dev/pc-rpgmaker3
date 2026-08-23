# pc-rpgmaker3

A native PC reimplementation of the **RPG Maker 3** engine
(PlayStation 2, SLUS-21178, Enterbrain / Runtime Inc., 2005).

RPG Maker 3 is the odd one out in the series: while the PC releases stayed
anchored to 2D tiles, the PS2 edition is a full **real-time 3D engine** with
an on-console editor — scene graph, skinned characters, dynamic lights,
pre-rendered backdrops and a multi-track keyframe cutscene editor. This
project documents the disc and its formats, with the goal of bringing that
engine to modern hardware.

## BYOA — Bring Your Own Assets

This repository contains **documentation and tools only**. No game data, no
executables, no assets. You need your own original RPG Maker 3 disc.

## Layout

    docs/     disc, format and engine analysis
    tools/    Python tools (no external dependencies)

## Tools

All of them need only Python 3.8+.

```sh
# disc index
python tools/rpgsp_index.py E:/CDIMAGE.TBL --stats
python tools/rpgsp_index.py E:/CDIMAGE.TBL --list

# extraction (filter paths take no leading slash)
python tools/rpgsp_index.py E:/CDIMAGE.TBL --dat E:/RPGSP.DAT \
    --extract out/ --filter img_2d/bg/

# textures -> PNG
python tools/p64_decode.py out/img_2d/bg/bg_000.mpic -o png/

# .iab movie -> playable MPEG-2 (the video track has no start codes)
python tools/iab_video.py out/logo/logo.iab -o logo.m2v
ffmpeg -i logo.m2v -vf scale=in_range=full:out_range=limited \
       -pix_fmt yuv420p logo.mp4

# .iab audio track -> WAV
python tools/iab_audio.py out/logo/logo.iab -o logo.wav

# ASCII strings with offsets
python tools/pstrings.py E:/SLUS_211.78 -n 6 --offsets
```

ffmpeg is only needed for the movie pipeline; the Python tools have no
dependencies at all.

## Status

Sessions 1-2 — disc, formats and the movie codec. See
[docs/00-sessions.md](docs/00-sessions.md) for the progress log.
