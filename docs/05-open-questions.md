# Open questions

Ordered by priority for the port.

## 1. Project format — the record walk and the checksum

The format is largely mapped in `08-project-format.md`: 16-byte wrapper, a
global header with three per-type tables, then records laid end to end from
0xB30 with `id`, `type` and a Shift-JIS name.

Two things still block writing a file the engine will load:

* **The checksum at `+0x04`.** Not additive, and not CRC-32 under any of the
  usual polynomial / init / reflection / range combinations tried.
* **The record walk desynchronises on the disc samples** after a few
  records, while it lands exactly on `bytes_used` for memory-card saves. At
  least one record kind must be variable-length or interleaved with data the
  walk does not account for.

Also unmapped: table B at `+0x64`, the fixed fields between `+0xA4` and
`+0x200`, and the 20-byte step between an empty project's `bytes_used`
(0xB1C) and the first record (0xB30).

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
project files look like checksums. Neither algorithm is identified; for the
project field see question 1, where the search so far is recorded. Required
in order to write files the original engine will accept, which is how we
validate the port against an emulator.

## 7. Identifying the 16 VU1 microprograms

Source names are replaced by hashes in the `.DVP.overlay` sections. They
need to be identified by function: static, skinned, sprite, effects.
