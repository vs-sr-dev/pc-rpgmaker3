# Container formats

All values are **little-endian**. Structures marked ✅ have been verified
against real files; those marked 🔍 are hypotheses still to be confirmed.

## CDIMAGE.TBL — index into RPGSP.DAT ✅

    u32 count;                      // 3818 on the USA disc
    struct {
        char name[128];             // absolute path, NUL-padded, '/' separated
        u32  offset;                // byte offset in RPGSP.DAT, 2048-aligned
        u32  size;                  // exact size
    } entry[count];                 // 136 bytes per record

`4 + 3818 * 136 = 519,252` = the exact file size.

Records are sorted by ascending offset and the files are packed
sequentially with sector (2048 B) padding.

## RPGSP.DAT ✅

A raw concatenation of the 3818 files, with no header of its own. The first
file (`/stream/2msoundtest.iab`) starts at offset 0.

## .p64 — texture container ✅

    u16 count;                      // number of textures
    u16 hdr_size;                   // always 64
    u32 payload_size;               // filesize - 64
    u32 reserved;                   // 0
    u32 tex_offset[count];          // relative to the end of the header
    // ... texture blocks

## .mpic — single texture ✅

A `.mpic` file is **exactly one texture block**, with no container header.
The same block is the unit stored inside `.p64` files.

    u16  fmt;        // 1 = 8 bpp indexed, 0 = 4 bpp indexed
    u16  unk;        // always 2
    u16  width;
    u16  height;
    u16  ncolors;    // 256 or 16
    u16  pal_bytes;  // 1024 or 64
    u32  data_bytes; // width*height (8bpp) or width*height/2 (4bpp)
    u32  minus_one;  // 0xFFFFFFFF
    u32  zero;
    u32  checksum;   // 🔍 often 0
    char magic[4];   // "V20\0"
    char source[96]; // the artist's Windows path, NUL-terminated
    u8   pixels[data_bytes];        // row-major, NOT swizzled
    u8   palette[pal_bytes];        // RGBA, at the END of the file

Important details:

* the palette comes **after** the pixels, not before;
* alpha uses the PS2 `0..128` range (128 = opaque) and must be rescaled;
* for `ncolors == 256` the palette is in the GS **CSM1** order: within each
  group of 32 entries, the two middle runs of 8 are swapped. No swap for
  16-colour palettes.

Implemented and verified in `tools/p64_decode.py`.

## .iab — interleaved audio/video stream ✅ (audio) / 🔍 (video)

64-byte header:

    u32 hdr_qwords;   // 0x10 -> 16 quadwords = 64 bytes
    u32 sample_rate;  // 22050 / 24000 / 44100 / 48000
    u32 channels;     // 2
    u32 interleave;   // 8192
    u32 audio_blocks; // blocks of `interleave` bytes per channel
    f32 audio_secs;
    u32 nsub;         // 1
    u32 total_size;
    // if a video track is present:
    u32 frames;
    u32 unk1, unk2;   // 🔍 scale with bitrate
    f32 fps;          // 29.97 or 59.94
    f32 video_secs;
    u32 width;        // 640
    u32 height;       // 448
    u32 total_size;

The body is a sequence of 8192-byte blocks alternating between the audio
and video tracks.

**Audio**: PS2 SPU-ADPCM (VAG) — 16-byte blocks, first byte
`shift | filter<<4`, second byte loop flags. 28 samples per 16 bytes; the
durations declared in the header match exactly.

**Video**: 640x448, but **not an MPEG-2 elementary stream**: no
`00 00 01 B3` / `B8` / `BA` start codes appear anywhere in the file. Codec
still unidentified (see `docs/05-open-questions.md`).

## .smp — database preset records ✅

One file = one fixed-size record, with ASCII text at the front
(`char name[20]; char description[...]`) followed by numeric fields. The
record size is constant per category:

    ed_ct        3784 B   28 rec   classes
    ed_monster   3736 B   49 rec   monsters
    ed_st        1104 B    1 rec   storyteller
    ed_town       988 B   40 rec   towns
    ed_dungeon    272 B   40 rec   dungeons
    ed_i_s        240 B   20 rec   items (shields)
    ed_i_a        220 B   20 rec   items (armour)
    ed_field      216 B   31 rec   field maps
    ed_i_d        216 B   62 rec   items
    ed_human      208 B   54 rec   characters
    ed_i_w        208 B   58 rec   weapons
    ed_i_g        200 B   24 rec   items
    ed_i_i        184 B   47 rec   items

These sizes are effectively the `sizeof` of the editor's `CEdPro*` classes
(see `docs/03-engine-architecture.md`).

## sample/game/sample{1,2,3} — complete projects 🔍

Three sample projects, **all exactly 1,994,768 bytes**. The fixed size
suggests a constant-capacity memory arena, which is what the "Memory"
gauge in the editor UI measures.

Preliminary header:

    +0x00 u32  0x000F5C44
    +0x04 u32  checksum? (0xACF46581)
    +0x08 u32  0x001E7000 = filesize - 16
    +0x0C u32  0x00A02A00
    +0x10 ...  section table: u16 (count, stride) pairs 🔍

This is the engine's central data format and the priority for the next
session.

## .bin — VU1/GIF display lists 🔍

Nested chunk header:

    u16 count; u16 stride(=16); u32 total_size; u32 zero;
    u32 chunk_offset[count];        // relative to the end of the 48 bytes

The payload is **not** a friendly mesh format: these are **pre-built VIF1
packets**. `UNPACK V4_32` VIFcodes (`cmd = 0x6C`) are clearly recognisable,
e.g. `0x6C058000` = unpack 5 quadwords at address 0 with double buffering.
Porting will require a VIF/GIF decoder and an understanding of the
microprograms in `.vutext`.

## .fnt — bitmap font 🔍

    char magic[4];   // "ASC\0"
    u32  width;      // 8
    u32  height;     // 16
    u32  advance;    // 8
    u32  nchars;     // 256
    u32  data_off;   // 64

Present: `ascii16`, `ascii20`, `jis16`, `jis20`.

## .hd / .bd — SCE sound banks ✅

Standard Sony format (`sdmacro`): magic `IECSsreV` = `SCEI`+`Vers` with
per-word byte swapping. `.hd` = header (programs, regions, VAG table),
`.bd` = ADPCM body. Three banks: `system`, `play01`, `battle01`.
