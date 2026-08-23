# The .iab video codec

`.iab` files carry the game's movies and streamed music. The audio track was
easy — it is plain PS2 SPU-ADPCM. The video track was not: **no MPEG start
code appears anywhere in the file**, so no demuxer or player will touch it.

This is how it was identified, and how to decode it.

## The chunk chain

Past the 64-byte file header the body is not a fixed interleave but a chain
of variable-size chunks, each with a 16-byte header:

    u32 magic;        // 0x12481248 = audio, 0x84218421 = video
    f32 timestamp;    // seconds from the start of the stream
    u32 size;         // payload bytes
    u32 stride;       // = align16(size + 16), i.e. offset to the next chunk

Walking the chain from offset 0x40 lands exactly on the end of the file.
For `logo.iab` it yields **25 audio chunks and 220 video chunks** — matching
`audio_blocks = 25` and `frames = 220` in the file header. So **one video
chunk is exactly one frame**, and the two "unknown" header fields turn out to
be the largest and smallest frame size in the file (useful for sizing the
decode buffer).

## Finding the codec

The stream contains no start codes, but the executable does contain the
**MPEG default intra quantiser matrix** (`08 10 10 13 10 13 16 16 ...`) and
two complete intra + non-intra matrix pairs. So it is MPEG-derived, feeding
the PS2 IPU.

Taking the smallest frame — a flat, featureless picture — its bitstream is
**periodic with a period of exactly 42 bits**, and the periodic region breaks
into **28 runs**, one per macroblock row of a 640x448 picture (448/16 = 28).
The step between runs is 1686 bits = 40 x 42 + 6, and 640/16 = 40
macroblocks per row.

42 bits is then exactly what a flat intra macroblock costs in MPEG-2 if — and
only if — `intra_vlc_format = 1`, which selects coefficient table B-15 whose
End-of-Block code is `0110` (4 bits) rather than B-14's `10` (2 bits):

    macroblock_address_increment  '1'                 1 bit
    macroblock_type (Intra)       '1'                 1 bit
    4 x luma block                '100' + '0110'      4 x 7 bits
    2 x chroma block              '00'  + '0110'      2 x 6 bits
                                                    = 42 bits

That reconstructed string matches the data **bit for bit**, and repeats every
42 bits across the picture.

## Why there is no slice layer

The extra 6 bits per row are not a slice header. The **first macroblock of
each row uses `macroblock_type = '01'` (Intra, Quant)** instead of `'1'`,
which is 2 bits plus a 5-bit `quantiser_scale_code` — exactly 6 bits more.
That is how the encoder re-sends the quantiser per row without a slice.

So a frame is **one uninterrupted run of 1120 macroblocks**, with no slice
start codes, no byte alignment between rows, and nothing for a normal
demuxer to latch onto.

## Summary of the format

* MPEG-2 video, **I-pictures only**, 4:2:0, 640x448, 29.97 or 59.94 fps
* `intra_vlc_format = 1` (coefficient table B-15)
* `intra_dc_precision = 0` (8-bit DC)
* all start codes stripped; sequence, picture and slice layers absent
* one frame per `0x84218421` chunk, preceded by a short frame header

## Colour range

The decoded YUV is **full range (0..255)**, matching the conversion the PS2
IPU performs, not the studio-swing 16..235 an MPEG decoder assumes by
default. Decoding it as limited range pushes a background at Y=239 past 255
and blows the highlights out to white. Always convert explicitly:

    ffmpeg -i out.m2v -vf scale=in_range=full:out_range=limited \
           -pix_fmt yuv420p out.mp4

## The frame header — partially understood

Each frame's payload starts with a short header before the first macroblock:

    bits 0..9    fixed per file (0110000001 in logo.iab and rpg_640_448.iab,
                 0110001001 in the eb_ci videos)
    bits 10..14  quantiser_scale_code -- verified: it tracks the bitrate
                 (1..10 in logo.iab, 18 in the 2 Mbit videos, 2 in the 8 Mbit
                 ones) and correlates with frame complexity as rate control
                 would predict
    then         the macroblock stream

The number of bits before the first macroblock is **17 in `logo.iab`** —
established by parsing the first macroblock's six blocks and confirming it
ends exactly where the second begins — but **13 in `rpg_640_448.iab`**, and
the `eb_ci` videos do not decode cleanly at any offset yet. Getting this
wrong does not break macroblock parsing; it only shifts the initial DC
predictor, so the picture comes out with a constant brightness offset.

`tools/iab_video.py` therefore exposes `--offset`.

## Verification

`logo.iab` (220 frames) and `rpg_640_448.iab` (3568 frames) rebuild into
MPEG-2 elementary streams that ffmpeg decodes with **zero errors**, and the
audio decodes to exactly the duration the header declares (7.47 s for
`logo.iab`, matching to the sample).

Independently, the `.mpic` decoder was checked against a PCSX2 frame capture
of the Agetec boot logo: **mean difference 0.9 per channel**, i.e. effectively
pixel-exact.
