# Writing a memory card

`tools/ps2mc.py` reads and writes the `.ps2` images PCSX2 keeps. Reading was
already there; writing needed one thing, the ECC in each page's spare area.

    python tools/ps2mc.py card.ps2 --verify-ecc
    python tools/ps2mc.py card.ps2 --replace PATH=file --out new.ps2

## The page

A card is 16,384 pages of 528 bytes: 512 of data, then a 16-byte spare area.
The spare holds four three-byte ECC triples, one per 128-byte quarter of the
page, and four bytes of FF. An erased page has an all-FF spare and no ECC to
check.

## The code, derived rather than looked up

The ECC is a GF(2) parity over the 128-byte chunk read as a 128 x 8 bit
array, so it is linear, and a linear function can be recovered from examples.
Taking every written page of `empty.ps2` as equations and running Gaussian
elimination over the 1,024 unknowns, 1,605 chunks were enough to fix all
1,024 basis vectors. The structure that came out is plain:

    ecc[0]   bit k of a byte contributes (k << 4) | (7 - k)
    ecc[1]   a byte of odd parity at index i contributes ~i & 0x7F
    ecc[2]   the same bytes contribute i

So both halves are the same idea at two scales — the index of every set bit
XORed together, kept in true and complement form, across the 8 columns for
`ecc[0]` and across the 128 rows for the other two. The result is stored
complemented, which is why an all-zero chunk reads `77 7F 7F` and not zero.

An all-FF chunk gives the same `77 7F 7F`: 0xFF has even parity and even
column parity, so it contributes nothing. That is why a handful of pages of
genuine FF data are distinguishable from erased ones only by their spare.

Three dozen lines, no table:

    for i, v in enumerate(chunk):
        col ^= _COL[v]
        if _PAR[v]:
            rowc ^= ~i & 0x7F
            row ^= i
    return bytes((~col & 0x77, ~rowc & 0x7F, ~row & 0x7F))

## Checking it

`--verify-ecc` recomputes every written page and compares. Across the eleven
cards in `PS2saves/` — 5,489 written pages each, about 60,000 pages and
240,000 chunks in total — it disagrees with PCSX2 nowhere.

That only proves the encoder matches on data PCSX2 wrote. Two splices prove
the writer:

* **Identity.** Extract the project from `healfx.ps2` and put it straight
  back: nothing is rewritten and the image comes out byte-identical.
* **Reconstruction.** Take `skillanim.ps2`, splice in `healfx.prj`, and
  compare against the real `healfx.ps2`. Two pages are rewritten and both
  match PCSX2's own bytes exactly. Done again from `empty.ps2`, which shares
  far less with the target, 97 pages are rewritten and **all 3,898 pages the
  project occupies come out bit-identical** to the card PCSX2 wrote, ECC
  included. The 84 pages that still differ belong to the system save, the
  directory timestamps and `info.dat` — files the splice never touched.

## What the writer will not do

`replace()` refuses a length change. A project is always 1,994,768 bytes so
this never comes up, and honouring it would mean allocating clusters and
rewriting the FAT. Pages whose content does not actually change are left
alone, spare and all, so a splice never disturbs an erased page.

Timestamps are not touched either. A card we write keeps the directory entry
the editor last stamped, which is wrong in principle and has not mattered yet.

## predict.ps2

The payoff, and an experiment. `PS2saves/predict.ps2` is `healfx.ps2` with a
project we edited by hand through `tools/rpgproj.py`, checksummed, and spliced
back. Four pages differ from the original. Every value in it was chosen
because our reading of the format predicts what the editor should show:

    entry 0  HOLYSWORD    animation 7        -> should read "Attack 5"
    entry 1  SunderArmor  category 1         -> names one of the two unused
    entry 2  Soothe       visual effect 10   -> should read "Heal 10"
                          add-effect 3       -> settles the recovery list
    entry 3  MADEBYUS     built from nothing but the layout, category 2

Entry 3 is the real test: a special skill that no editor ever created, written
into a blank slot from the field table alone, with its own name, description,
type, category, animation, effect points and cost. If the editor lists it and
lets it be used, the layout is not merely described — it is understood.
