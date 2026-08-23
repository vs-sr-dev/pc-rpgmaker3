# Open questions

Ordered by priority for the port.

## 1. Project format (`sample/game/*`) — highest priority

This is the heart of the engine: maps, events, database, cutscenes. Partial
header in `docs/02-container-formats.md`. We need to map the section table
at offset `0x10` and correlate it with the `CEdPro*` classes and the `.smp`
record sizes.

Starting point: the three samples share the same size but differ in content
— diffing them isolates the regions actually in use.

## 2. `.bin` geometry and VU1 microprograms

The `.bin` files are pre-built DMA/VIF1 chains, not meshes. We need:

* a VIF/GIF disassembler for the `.bin` files;
* a disassembly of the 16 microprograms in `.vutext` / `.DVP.overlay.*` to
  understand the input vertex format and the skinning pipeline.

Also open: the meaning of the fields after each chunk header (the runs of
four consecutive `1.0f` values look like matrices or bounding boxes).

## 3. The `.iab` frame header — SOLVED IN PART

The codec itself is identified (see `06-iab-video.md`): MPEG-2 intra, 4:2:0,
`intra_vlc_format = 1`, no slice layer, start codes stripped. What remains is
the short per-frame header. Bits 10..14 are the `quantiser_scale_code`, but
the number of bits before the first macroblock differs per file (17 in
`logo.iab`, 13 in `rpg_640_448.iab`) and the `eb_ci` videos do not decode
cleanly at any offset yet.

Writing a proper MPEG-2 B-15 coefficient parser would settle this: with it
the first macroblock's exact bit length can be measured instead of guessed,
and it is needed for the port anyway.

## 4. Size discrepancy on some videos

For `opening8m.iab` the header's `total_size` field declares 171,354,304
bytes, while `CDIMAGE.TBL` records 87,469,616. For `logo.iab` the two agree.
We need to determine whether the header describes the pre-encoding master,
whether the on-disc file is truncated, or whether the field mapping is wrong
for video files.

## 5. Exact `.smp` layout beyond the text

The leading text is clear; the numeric fields that follow (stats, model
references, prices) need mapping field by field. Made easier by the fact
that the values are visible in the game's own editor.

## 6. Checksums

The field at `+0x18` of the texture block and the one at `+0x04` of the
project files look like checksums. The algorithm needs identifying —
required in order to write files the original engine will accept, which is
useful for validating the port against an emulator.

## 7. Identifying the 16 VU1 microprograms

Source names are replaced by hashes in the `.DVP.overlay` sections. They
need to be identified by function: static, skinned, sprite, effects.
