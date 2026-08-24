# TODO — session 6

The project format is structurally solved: the checksum verifies, and every
record in every project we hold parses to the last byte. Two directions open
up from here, and they are worth doing in this order because the first one
turns the editor into a measuring instrument for the second.

## 0. Memory-card captures to make (a few minutes each)

Same method as before: make one change in the editor, save, copy the `.ps2`
out. Each capture pins fields outright, because the diff is now down to the
handful of bytes that actually moved.

Building on `onestat.ps2` (two classes, the first renamed `ZZZZTESTZZZZ` with
attack 1):

`skillcost.ps2`, `skillanim.ps2` and `healfx.ps2` are done, and between them
the special-skill entry is finished: every field the demo ever sets has a
name, and all three pick-lists resolve against the executable. What remains:

1. **`onechar.ps2`** — from a fresh project, add one character instead of a
   class. Gives a Human record made to order, and Human is one of the three
   types carrying the mystery flag.
2. **`onedungeon.ps2`** — create one dungeon, then one town. Both carry a
   variable part that is *not* laid out like a Field's, and both are on the
   list of three types with the unexplained flag.
3. **`stats.ps2`** — from `onestat.ps2`, change *several* class numbers at
   once to distinct, recognisable values (attack 11, defence 22, speed 33…).
   One capture then labels a whole block of the class record instead of one
   byte.
4. **`twochar.ps2`** — a second character, to see how a Human's variable part
   grows with dialogue.

Two small ones would tidy what is left around skills. **`healeff.ps2`** —
give a recovery skill an add-effect, say *Cure Poison*; the executable has a
separate recovery list at `0x2EC6D0`, and this says whether `+0x0E0` is
category-relative the way the visual effect turned out to be.
**`skillcat.ps2`** — make one skill in each of the two categories the demo
never uses, to name the remaining values of `+0x0C0`.

If only one is possible, make it number 3, `stats.ps2`: several class numbers
changed at once labels a whole block of the record instead of one byte.

## 1. Boot predict3.ps2

`predict.ps2` and `predict2.ps2` both loaded and both paid for themselves —
see `00-sessions.md`. The second one showed that the editor gives a skill
**two** effect selectors, not one, and that neither of them reads the field we
had been writing. `PS2saves/predict3.ps2` settles which field carries the
first, in a single look.

Ten skills in `ZZZZTESTZZZZ`. The first eight are Recovery and identical
apart from one word each:

    BASE3      nothing set        -> control, should read Recover HP
    WORD-C4    +0x0C4 = 2
    WORD-CC    +0x0CC = 2
    WORD-D4    +0x0D4 = 2
    WORD-E8    +0x0E8 = 2
    WORD-EC    +0x0EC = 2
    PACK-C0    +0x0C0 = 3 | 2<<8   -> also says whether the category word is
    PACK-BC    +0x0BC = 1 | 2<<8      a bitfield, or breaks if it is not

Whichever one reads **Recover HP/MP** instead of *Recover HP* is the Effect
field. If none of them moves, the choice is not in the skill entry at all.

The last two are Attacks skills, and they are the control that matters most:

    ADD-22     +0x0E0 = 22   -> the exact value the editor itself wrote for
                               "Strong vs. Demons" back in twotech
    ADD-1      +0x0E0 = 1    -> "Slow"

If ADD-22 shows *Strong vs. Demons*, `+0x0E0` really is the additional effect
and the earlier *None* was the editor rejecting 5 specifically — which would
mean the list is filtered, the way the visual-effect list is. If ADD-22 shows
*None* too, then something other than the stored value gates it.

Worth reporting for each: the **Effect** and the **Additional effect** columns.

## 2. Map the record types field by field

With the walk exact and the editor able to change one value at a time, this
is now grinding rather than puzzling — and it is what the port actually
needs. Twenty types; the ones that matter first are Class (4,172 bytes),
Human (532 + variable), Item, Equip and Monster.

Two sources meet in the middle: the `.smp` presets on the disc hold the same
objects with known contents (see question 6 in `05-open-questions.md`), and
the editor produces controlled diffs. A field visible in both is a field
identified.

Worth doing early: dump every record of `sample1` per type and eyeball the
non-zero columns. 578 records of a finished game is a large sample, and
fields that are constant across all records of a type are structural rather
than data.

## 3. `.bin` geometry — start the VIF/GIF disassembler

Unchanged, and now the largest untouched piece of the engine. The `.bin`
files are pre-built DMA/VIF1 chains; `UNPACK V4_32` codes are already
recognisable. Two halves:

* a VIF/GIF packet disassembler, to see what data is being uploaded;
* a first pass over `.vutext` and the 16 `.DVP.overlay.*` microprograms, to
  learn the vertex layout they expect and how skinning is done.

Aim for reading one simple object end to end (`evobj/a/a00.bin`, 22 KB, with
its 128x128 texture) rather than general coverage. `tools/mipsdis.py` covers
the EE side already; the VU side needs its own decoder.

## 4. Smaller, self-contained wins

* **`.fnt`** — the header is understood; write the glyph decoder and dump
  `ascii16` and `jis16` to PNG sheets. Small and immediately verifiable, and
  `jis16` is interesting in its own right (curiosity 16).
* **`.hd`/`.bd`** — standard SCE sound banks; a VAG extractor would give us
  the sound effects and confirm the MIDI + sample pipeline.
* **The editor's system save** (`BASLUS-21178system`, 33,792 bytes) uses the
  same wrapper and the same CRC, but is full rather than bump-allocated, and
  485 separate regions of it changed between two saves a minute apart. Worth
  an hour to find out what the editor keeps there.
* **`info.dat`** — the wrapper and its CRC are confirmed; a title and PS2
  binary timestamps at `+0x7C` and `+0x84` are mapped. The 24 bytes at `+0x64`
  change completely between saves and start with a float in 0..1.

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

## 6. Beyond parity — the frame rate

PCSX2 shows the whole game running at 30 fps. Once the port is at parity,
seeing whether it can run at 60 is a genuinely nice thing to try. The
question is not rendering but what else is tied to the frame counter: the
keyframe cutscene sequencer, battle timing, and any event script that counts
frames rather than seconds. The `.iab` movies are a separate clock and would
not be affected.

Worth noting now rather than later, because it is cheap to keep the port's
update step frame-rate independent from the start and expensive to retrofit.

## 7. Carried over

The `.iab` frame header work is untouched and still open — see
`05-open-questions.md` question 4. It sits below the project format because
the project format is what the port needs first.
