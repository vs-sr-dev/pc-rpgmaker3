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

Follow-up on the naming: `tukuru` is ツクール, the Japanese name of the
series, which makes `tukuru.mpic` holding the Agetec logo a straight
substitution into the Japanese ident's slot. Chasing that turned up a whole
seam of kunrei-style romaji in the asset names — curiosity 15.

Still open: the short per-frame header before the macroblock stream, whose
length varies per file. See `05-open-questions.md`.

Next step: the project format (`sample/game/*`), which is the core of the
engine.

## Session 3 — the project format, opened with a memory card

Goal: the project format (`sample/game/*`), the engine's central data
structure.

The lever was two PCSX2 memory cards captured a minute apart: one holding a
project created and saved with nothing in it, the other the same project
after adding a single Sword & Shield class with every field left at its
default. Diffing those two isolates one object exactly.

Results:

* **`tools/ps2mc.py`** reads PS2 memory card images (PCSX2's 528-byte pages
  included), walks the FAT and extracts the save directories.
* **Memory-card saves are the project format**: `BASLUS-21178a` is
  1,994,768 bytes, the same size and the same header tables as
  `sample/game/sample1`. Every experiment we can run in the emulator now
  applies directly to the disc samples.
* **The 16-byte wrapper is generic.** `capacity` is always the file size
  minus 16, on projects, on `info.dat`, on the in-game save slots and on the
  editor's system save alike.
* **Everything past `bytes_used` is uninitialised memory.** A new project
  uses 2,844 bytes of its 1.99 MB yet the file is non-zero nearly to the
  end. The 56 % byte difference between the three samples that session 2
  measured was mostly leftover heap. Two saves from the same session carry
  identical garbage, which is exactly what makes the differential method
  work.
* **The schema is three tables of twenty `u16`.** Table A at `+0x24` is the
  `sizeof` of each of the twenty record types; table C at `+0x7EA` is the
  next free ID per type. Adding one class incremented `C[4]` and appended
  `A[4]` = 4,172 bytes.
* **Records are laid end to end from 0xB30**, `id` and `type` in the first
  two words, name at `+0x4C` in Shift-JIS. Confirmed on the controlled save
  and cross-checked on the samples, where name strings chain at exactly the
  stride table A predicts for twelve of the twenty types.
* **A class record dissected**: fifteen empty 240-byte entries at `+0x230`,
  almost certainly its technique table.
* Full write-up in `08-project-format.md`.
* Two more curiosities (16, 17): two of the three sample games shipped in
  the USA release are still entirely in Japanese, and one of them is a
  developer's layout test.

Still open: the checksum at `+0x04` resisted every additive scheme and every
usual CRC-32 variant, and the record walk desynchronises partway through the
disc samples, so at least one record kind is variable-length.

## Session 4 — the project format, finished

Goal: the two things session 3 left open — the checksum at `+0x04`, and the
record walk that desynchronised on the disc samples.

Three more memory-card captures, each one change past the last: a second
default class, then the first class renamed to `ZZZZTESTZZZZ`, then one
attack stat moved from 0 to 1.

Results:

* **The checksum is CRC-32** of `data[0x10 : 0x10 + bytes_used]` — the arena,
  from where it starts, for exactly its own declared length. It verifies on
  all eight projects we hold. Session 3 had tested the right polynomial but
  never that range, which ends 16 bytes further in than anything tried.
  Found by exploiting the linearity of CRCs: the *difference* of two
  checksums depends only on the differing bytes and the number of bytes
  after them, so the one-byte capture reduced a four-dimensional search to
  feeding zeros into a register until it matched. One hit, no ambiguity.
* **Confirmed in the executable**: `crc32_init_table` at 0x00357B98,
  `crc32_update` at 0x00357C70, and the caller at 0x001C0F70 that writes
  `bytes_used`, `checksum` and `capacity` into the wrapper.
* **The record walk is exact.** The step is
  `A[type] + B[type] + 16 + extra`, where `extra` is the u32 immediately
  before the record. Table B — the "second per-type table" that had been a
  mystery since session 3 — is the size of each type's *variable* part. It
  reads 4 for every fixed type, which is why those records just step by
  `sizeof + 20`. All eight projects now walk to their last byte, and the
  record count matches the file's own `objects` field every time: 578 for
  `sample1`, 284 for `sample2`, 502 for `sample3`.
* **The twenty record types have names**, recovered from the registration
  code at 0x00100F48: Field, Dungeon, Town, Story, Class, Human, Monster,
  monster groups, Item, Equip, Important, Room, Castle, System, two kinds of
  Event, Save Event, Warp Event, Chest Event, Entrance. Every one matches
  what the records actually hold, which independently confirms the walk.
  The whole database of a real game — 578 records of `sample1`, *Dear Brave
  Heart* — is now readable.
* **The allocator is settled**: a 20-byte header per allocation, records
  contiguous, `bytes_used` pointing at the header of the allocation that
  would come next.
* **The world map is a fixed 140 x 140 grid**, and fully addressed. Every
  Field record in every sample has the same 39,208-byte tail, opening with a
  24-byte header that states the two dimensions. A capture that paints a
  single tile settled the layout outright: the editor reported X=100, Y=76,
  Z=128 and the one changed cell sits at index 10,740 = 76 x 140 + 100, so
  the grid is row-major with X contiguous. The second grid is Z — 128
  everywhere in a new field, 0 for every one of *Elgiza Isle*'s 12,687 sea
  cells. `tools/rpgproj.py --maps --png` renders both, and the island comes
  out with coastline, rivers, a lake and islets.
* **Three class fields pinned outright** by the single-change captures: the
  name is inline at `+0x4C`, `+0x120` is an attack stat (one byte), and
  `+0x140` starts an array of **sixteen 240-byte special-skill slots** —
  session 3 had guessed fifteen at `+0x230`, and both guesses end at the same
  offset, which is why the wrong one looked right. Creating one skill named
  `HOLYSWORD`, then a second one with an effect, pinned the entry base at
  `+0x154` and its stride at 240, with `bytes_used` unchanged both times: the
  array is part of the fixed record. Inside an entry: a 22-byte name, a
  162-byte description, then a numeric block whose effect id is confirmed —
  the editor wrote 22 for *Strong vs. Demons*, and `sample1`'s *Megid Arc*,
  "damages demonic foes", carries the same 22. Read back, the demo's whole
  skill list comes out: Sonic Blade, Volcano Rave, Megid Arc, Thunder Slash
  for the Swordfighter, down to Meteo Most Fowl for the Chicken.
* **Curiosity 20**: the Japanese skill names are still in those fields, behind
  the NUL, because the English overwrote them in place and is shorter.
* The file contains **no pointers**; `+0x0C` is not a relocation base.
* `tools/mipsdis.py` added — disassemble the executable by virtual address.

What is left of the format is meaning rather than structure: the flag in the
type descriptor, the trailing half of a map's tile data, and the field-by-field
layout of each record type.

## Session 5 — the skill entry, finished

One capture closed the last of the special-skill layout. `skillcost.ps2`
reopened `HOLYSWORD` and set three things at once: cost 33, effect 77 points,
and the target from *1 target* to *all enemies*.

* **Three fields pinned in a single diff.** Outside the checksum the file
  differs in exactly one contiguous 13-byte run, at `+0x0D8` of entry 0 —
  target, effect points, and cost, with the already-known effect id sitting
  between two of them and holding still. There is no room left to misread the
  alignment.
* It confirms what Session 4 had only inferred: `+0x0DC` runs 128, 96, 256,
  200 across the Swordfighter's four skills and `+0x0E4` runs 10, 20, 30, 20.
  The 30 was not a cap — the editor took 33.
* **The target flag reads back true across the whole demo.** Every 0 is a
  melee strike, every 1 is a spell, a beam or a party heal.
* A wider read **corrected a Session 4 line**: `+0x0BC` is not healing-only,
  it is 1 on *Infernal Flames* as well. And three of the block's words —
  `+0x0C4`, `+0x0CC`, `+0x0D4` — are zero on all sixteen named skills in the
  demo, so what is still unexplained in a 240-byte entry is four fields, not
  seven.

A second capture the same session finished the entry. `skillanim.ps2` set
`HOLYSWORD`'s animation to *Special Attack* and its visual effect to *Cross
(Red)* — the editor splits presentation into those two, with the sound baked
into each — and again the diff outside the checksum is one contiguous run:
`+0x0D0` to 6, `+0x0C8` to 17.

* **Both pick-lists are in the executable**, and both resolve. Animation is
  eight 16-byte names at `0x3EDE20`, *Special Attack* sitting at index 6 —
  so the 0..7 range measured across the demo is the whole domain, not a
  sample. Visual effect is 64 records of `{ char name[22]; i16 id, id2, se }`
  at `0x3A80D8`.
* **The effect index counts the list the editor shows, not the table.**
  *Cross (Red)* is row 19 of 64, but the field holds 17: three rows carry
  `id == -3` and are hidden, and dropping them lands it exactly. Recovery
  skills index a sub-list of their own, so the value is relative to whatever
  `+0x0C0` selects.
* **`+0x0BC` is Skill Type**, which the executable spells out in two strings
  and no more — skills use HP, magic uses MP. Those same strings give
  `+0x0DC` its name: *effect points*.
* Decoded through both lists the demo reads true — *Thunder Slash* draws
  Thunder, *Meteo Most Fowl* draws Meteor, *Butler Beam* draws Demon (Beams),
  every sword technique uses an *Attack* animation and every spell a
  *Magic/Item* one. `tools/rpgproj.py --skills --elf` prints it.
* **Curiosity 21**: those three hidden rows are the only three in the list
  still carrying Japanese names — two Poison Ball variants and *Enhance 8*.
  They were cut before translation, by setting an id to -3 rather than
  deleting the row, which is why the Japanese survives and why every effect
  below them is silently renumbered.

A third capture closed the sub-list question and one more field with it.
`healfx.ps2` created *Soothe* — Magic, Recovery, 500 points, cost 20, visual
effect *Heal 5*, one ally.

* **The visual effect is sub-list relative.** The field holds 5, not the 30
  an absolute index would need. The demo's heals really are *Heal 1*,
  *Heal 1* and *Heal 10*.
* **`+0x0C0` is the category, and 3 is Recovery**, named by the editor rather
  than inferred.
* **`+0x0E0` resolves too.** It indexes a pointer table at `0x357F78` that
  labels itself "Add Effects: Attacks", with *None* in the slot at -1 —
  exactly the -1 a skill with no effect stores. *Megid Arc* holds 22, which
  is *Strong vs. Demons*; *Thunder Slash* holds 2, which is **Stop**, a
  lightning strike that paralyses. Three agreements from one table.
* The editor says "1 ally" for a recovery skill and "1 target" for an
  attacking one but stores the same 0, so the target flag is only ever
  one-versus-all. And 500 effect points went in fine, so the demo's 256 was
  never a ceiling.
* Creating a skill in entry 2 left `bytes_used` alone and marked blank entry
  3, the same behaviour `onetech` showed for entry 0.

The special-skill entry is now finished: every field the demo ever sets has a
name, and `tools/rpgproj.py --skills --elf` prints a project's skills with all
three lists resolved.

### Writing a memory card

With captures paused, the session pivoted to the one mechanical step the
project format still needed: putting a file back. `tools/ps2mc.py` now writes.

* **The ECC was derived, not looked up.** It is a GF(2) parity, so it is
  linear, so it can be solved for. 1,605 chunks of `empty.ps2` fed into a
  Gaussian elimination over 1,024 unknowns fixed the whole basis, and the
  structure that fell out is one idea at two scales: the index of every set
  bit XORed together, in true and complement form, across the 8 columns for
  the first ECC byte and across the 128 rows for the other two, the lot
  stored complemented. Three dozen lines, no magic table.
* **It agrees with PCSX2 on every written page of all eleven cards** — some
  60,000 pages, 240,000 chunks, no disagreement.
* **The writer is proved by reconstruction.** Splicing `healfx.prj` into
  `empty.ps2` rewrites 97 pages, and all 3,898 pages the project occupies
  come out bit-identical to the real `healfx.ps2`, ECC included. The identity
  splice is a no-op and returns the image unchanged.
* **`PS2saves/predict.ps2`** is the payoff and an experiment: a project edited
  by our own tools, checksummed and spliced back, with four values chosen so
  that the editor's display tests our reading — including a special skill in
  entry 3 written from the field table alone, that no editor ever created.

See `09-memory-card.md`.

### What predict.ps2 came back with

The card loaded. Every field of **MADEBYUS** — the special skill written into
a blank slot from the field table alone, by no editor — read back exactly as
written: name, description, Magic, category Disabling, all targets, 123 effect
points, cost 45, visual effect *Fireball (Green)*, animation *Attack 2*. The
layout is understood, not merely described.

* **The category is fully named.** A pointer table at `0x32ADAC`, labelled
  "Effects", holds *Attacks, Enhancing, Disabling, Recovery, Special Traits*.
  The card confirmed 1 and 2 by writing them and reading the names off the
  screen; `healfx` had already given 3 from the editor's side.
* **The visual-effect sub-list is only special for Recovery.** A Disabling
  skill with visual effect 4 showed *Fireball (Green)*, index 4 of the main
  list, and *Soothe* with 10 showed *Heal 10*.
* **The animation list was wrong, and the card caught it.** Animation 7 shows
  *Throw*, not *Attack 5*. The real list is a table of pointers at `0x370414`;
  reading the strings inline works for 0 to 6 and then index 7 points away,
  leaving an unreferenced "Attack 5" behind. The eighth animation was renamed
  and the old string never removed.
* **Each category has its own add-effect table**, and only *Attacks* offers a
  *None*. Writing -1 into an Enhancing and a Disabling skill made the editor
  show each group's first entry — a fallback rather than a reading — and it
  did the same to a Recovery skill holding 3. That the demo's own heals all
  store -1 now makes sense: the field is an *added* effect, and a Recovery
  skill with none still heals for its effect points.

`predict2.ps2` follows up with six skills carrying in-range add-effects across
four categories, to find out what the editor does when the value is legal.
