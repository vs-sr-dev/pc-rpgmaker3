#!/usr/bin/env python3
"""Disassemble a range of the PS2 executable, by virtual address.

    python tools/mipsdis.py SLUS_211.78 0x002CD948 --count 80

The single PT_LOAD segment maps file offset 0x1000 at vaddr 0x00100000, so
vaddr = file offset + 0xFF000 throughout.
"""
import argparse
import capstone

BASE = 0xFF000


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("elf")
    ap.add_argument("vaddr")
    ap.add_argument("--count", type=int, default=64)
    args = ap.parse_args()

    data = open(args.elf, "rb").read()
    va = int(args.vaddr, 0)
    off = va - BASE
    md = capstone.Cs(capstone.CS_ARCH_MIPS,
                     capstone.CS_MODE_MIPS64 | capstone.CS_MODE_LITTLE_ENDIAN)
    md.skipdata = True          # PS2 uses COP2/VU macro-mode opcodes capstone rejects
    for i in md.disasm(data[off:off + args.count * 4], va):
        print("  %08X  %-8s %s" % (i.address, i.mnemonic, i.op_str))


if __name__ == "__main__":
    main()
