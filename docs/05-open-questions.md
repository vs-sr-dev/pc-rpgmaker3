# Open questions

Ordered by priority for the port.

## 1. Project format — SOLVED

The structure is fully mapped in `08-project-format.md`: 16-byte wrapper,
CRC-32 at `+0x04` over `data[0x10 : 0x10 + bytes_used]`, a global header
carrying the engine's own type schema, and records stepping by
`A[type] + B[type] + 16 + extra`. All eight projects we hold walk end to end
and agree with their own `objects` count.

What remains is meaning, not structure:

* **The flag** in the type descriptor — 1 for Dungeon, Town and Human, 0 for
  the other seventeen.
* **The trailing 19,584 bytes** of a Field record's map data, after the
  140 x 140 tile plane. Distribution suggests height or attributes.
* **Field-by-field layout of each record type.** Only two are pinned so far
  (a class's name at `+0x4C` and an attack stat at `+0x120`). The editor
  makes this cheap: change one value, save, diff. `.smp` presets give the
  same fields from the other side.
* **The fixed header fields** between `+0xA4` and `+0x200`.

## 2. Writing a project back to a memory card

We can now build a project file and checksum it correctly, but not put it
back where the editor will find it. A `.ps2` image stores 512-byte pages with
a 16-byte spare area holding ECC, which has to be recomputed for every page
touched. That is the last step before we can feed the original engine a file
we wrote and watch it load — the strongest possible validation of the port.

## 3. `.bin` geometry and VU1 microprograms

The `.bin` files are pre-built DMA/VIF1 chains, not meshes. We need:

* a VIF/GIF disassembler for the `.bin` files;
* a disassembly of the 16 microprograms in `.vutext` / `.DVP.overlay.*` to
  understand the input vertex format and the skinning pipeline.

`tools/mipsdis.py` disassembles the EE side by virtual address, which is a
start; the VU side needs its own decoder.

Also open: the meaning of the fields after each chunk header (the runs of
four consecutive `1.0f` values look like matrices or bounding boxes).

## 4. The `.iab` frame header — SOLVED IN PART

The codec itself is identified (see `06-iab-video.md`): MPEG-2 intra, 4:2:0,
`intra_vlc_format = 1`, no slice layer, start codes stripped. What remains is
the short per-frame header. Bits 10..14 are the `quantiser_scale_code`, but
the number of bits before the first macroblock differs per file (17 in
`logo.iab`, 13 in `rpg_640_448.iab`) and the `eb_ci` videos do not decode
cleanly at any offset yet.

Writing a proper MPEG-2 B-15 coefficient parser would settle this: with it
the first macroblock's exact bit length can be measured instead of guessed,
and it is needed for the port anyway.

## 5. Size discrepancy on some videos

For `opening8m.iab` the header's `total_size` field declares 171,354,304
bytes, while `CDIMAGE.TBL` records 87,469,616. For `logo.iab` the two agree.
We need to determine whether the header describes the pre-encoding master,
whether the on-disc file is truncated, or whether the field mapping is wrong
for video files.

## 6. Exact `.smp` layout beyond the text

The leading text is clear; the numeric fields that follow (stats, model
references, prices) need mapping field by field. This is now the same job as
question 1's record layouts, approached from the other end — the `.smp`
presets and the project records describe the same objects.

## 7. Remaining checksums

The field at `+0x18` of the texture block is still unidentified. Every
checksum the *save* path writes is now accounted for: the same CRC-32
verifies on projects, on `info.dat` and on the editor's system save alike, so
it belongs to the 16-byte wrapper rather than to any one file type.

## 8. Identifying the 16 VU1 microprograms

Source names are replaced by hashes in the `.DVP.overlay` sections. They
need to be identified by function: static, skinned, sprite, effects.
