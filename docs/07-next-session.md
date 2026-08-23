# TODO — session 4

Session 3 opened the project format with a pair of differential memory-card
saves. The same lever will finish it, and the captures needed are listed
first because they are cheap to make and unblock everything else.

## 0. Memory-card captures to make (a few minutes each)

Each one is: make the change in the editor, save, copy the `.ps2` file out.
Keep them one change apart — the value of the method is that exactly one
thing moves.

Building on `empty.ps2` / `newclass.ps2`:

1. **`twoclasses.ps2`** — add a *second* class, everything default. Settles
   the last ambiguity in the allocator: whether records stay contiguous
   (expected stride 4,172) or whether the 16-byte step seen between the
   header and the first record repeats for every allocation.
2. **`renamed.ps2`** — take `newclass.ps2` and only rename the class, to
   something long and distinctive (`ZZZZTESTZZZZ`). Confirms the name field
   and its capacity, and — with `bytes_used` unchanged — gives the checksum a
   clean, tiny input change to work with.
3. **`onestat.ps2`** — from `newclass.ps2`, change one numeric field on the
   class screen (one attack value, by a known amount, say from 10 to 11).
   Pins that field's offset and its width outright.
4. **`onetech.ps2`** — from `newclass.ps2`, add one technique to the class.
   Should light up the first of the fifteen 240-byte entries at `+0x230` and
   confirm what that array is.
5. **`onechar.ps2`** — from `empty.ps2`, add one character instead of a
   class. Identifies which type index characters use, and gives a second
   record type to compare layouts against.

If only one of these is possible, make it number 1.

## 1. Finish the record walk

`tools/rpgproj.py --walk` lands exactly on `bytes_used` for memory-card
saves and desynchronises a few records into the disc samples. Something is
variable-length. Two ways in:

* the samples' failure points are known and small — dump the bytes around
  each and look for a length field;
* capture 5 above gives a second record type built to order, which is a much
  cleaner place to see how a record's tail is terminated.

Once the walk is complete on `sample1`, the whole database of a real game
becomes readable, and the per-type record layouts can be mapped against the
`.smp` presets, whose contents are already known.

## 2. The checksum at `+0x04`

Ruled out so far: word/byte/halfword sums, XOR, Adler-32, and CRC-32 with
reflected and non-reflected polynomials (0x04C11DB7, 0xEDB88320, 0x1EDC6F41,
0x82F63B78) over ranges starting at 0x00/0x04/0x08/0x20 and ending at
`bytes_used`, at the aligned `bytes_used`, and at end of file.

Next: find it in the executable instead of guessing. The routine will be
called right before the memory-card write, so start from the sceMcWrite
call sites in `SLUS_211.78` and walk back. Capture 2 above gives a
minimal-difference pair to test any candidate against.

## 3. `.bin` geometry — start the VIF/GIF disassembler

Unchanged from session 3, and now the largest untouched piece of the engine.
The `.bin` files are pre-built DMA/VIF1 chains; `UNPACK V4_32` codes are
already recognisable. Two halves:

* a VIF/GIF packet disassembler, to see what data is being uploaded;
* a first pass over `.vutext` and the 16 `.DVP.overlay.*` microprograms, to
  learn the vertex layout they expect and how skinning is done.

Aim for reading one simple object end to end (`evobj/a/a00.bin`, 22 KB, with
its 128x128 texture) rather than general coverage.

## 4. Smaller, self-contained wins

* **`.fnt`** — the header is understood; write the glyph decoder and dump
  `ascii16` and `jis16` to PNG sheets. Small and immediately verifiable, and
  `jis16` is now interesting in its own right (curiosity 16).
* **`.hd`/`.bd`** — standard SCE sound banks; a VAG extractor would give us
  the sound effects and confirm the MIDI + sample pipeline.
* **The editor's system save** (`BASLUS-21178system`, 33,792 bytes) uses the
  same 16-byte wrapper but is full rather than bump-allocated, and 485
  separate regions of it changed between two saves a minute apart. Worth an
  hour to find out what the editor keeps there.
* **`info.dat`** — mostly mapped: the same wrapper, a title, and PS2-style
  binary timestamps at `+0x7C` and `+0x84`. The 24 bytes at `+0x64` change
  completely between saves and start with a float in the 0..1 range.

## 5. Loose ends worth a few minutes

* `opening8m.iab` declares 171,354,304 bytes in its header but `CDIMAGE.TBL`
  records 87,469,616. `logo.iab` has no such mismatch. Truncated file,
  pre-encode master, or a misread field?
* `bgm_000.iab` is byte-identical in `stream/` and `stream22/` while every
  other track differs. Deliberate, or a build slip?
* The `net/` configs and the networking modules suggest online features. Is
  any of it reachable in the shipped USA build, or is it all dormant like the
  Japanese logo movie?
* Can the USA editor actually load `sample2` and `sample3`, the two that were
  never translated (curiosity 16)?

## 6. Carried over

The `.iab` frame header work that stood at item 2 last session is untouched
and still open — see `05-open-questions.md` question 3. It sits below the
project format now, because the project format is what the port needs first.
