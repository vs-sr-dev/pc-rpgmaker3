#!/usr/bin/env python3
"""List and extract files from a PlayStation 2 memory card image (.ps2).

Handles both raw 8 MB images and the 528-byte-page images (512 bytes of data
plus 16 bytes of ECC/spare) that PCSX2 writes by default.

    python tools/ps2mc.py card.ps2 --list
    python tools/ps2mc.py card.ps2 --extract out/
    python tools/ps2mc.py card.ps2 --verify-ecc
    python tools/ps2mc.py card.ps2 --replace PATH=file --out new.ps2
"""
import argparse
import os
import struct
import sys

MAGIC = b"Sony PS2 Memory Card Format"

# Three ECC bytes guard each 128-byte quarter of a page, and the four triples
# fill the first twelve bytes of the 16-byte spare area; the last four are
# always FF.  The code is a plain GF(2) parity over the chunk read as a 128 x 8
# bit array, and it is stored complemented, which is why an all-zero chunk
# comes out as 77 7F 7F rather than zero:
#
#   ecc[0]  the column index of every set bit, XORed together, kept both true
#           (high nibble) and complemented (low nibble)
#   ecc[1]  the row index of every odd-parity byte, complemented
#   ecc[2]  the same row indices, true
#
# Derived from, and checked against, every written page of the nine cards in
# PS2saves/ rather than copied from a table.
_COL = [0] * 256
_PAR = [0] * 256
for _v in range(256):
    for _k in range(8):
        if _v >> _k & 1:
            _COL[_v] ^= (_k << 4) | (7 - _k)
            _PAR[_v] ^= 1


def ecc(chunk):
    """The three ECC bytes for one 128-byte chunk."""
    col = row = rowc = 0
    for i, v in enumerate(chunk):
        col ^= _COL[v]
        if _PAR[v]:
            rowc ^= ~i & 0x7F
            row ^= i
    return bytes((~col & 0x77, ~rowc & 0x7F, ~row & 0x7F))


class PS2MC:
    def __init__(self, data):
        if not data.startswith(MAGIC):
            raise ValueError("not a PS2 memory card image")
        (self.page_len, self.pages_per_cluster, self.pages_per_block,
         _unused) = struct.unpack_from("<HHHH", data, 0x28)
        (self.clusters_per_card, self.alloc_offset, self.alloc_end,
         self.rootdir_cluster) = struct.unpack_from("<IIII", data, 0x30)
        self.ifc_list = struct.unpack_from("<32I", data, 0x50)

        # PCSX2 keeps the 16-byte spare area; derive the on-disk page stride
        # from the file size rather than trusting a flag.
        total_pages = self.clusters_per_card * self.pages_per_cluster
        for spare in (0, 16):
            if len(data) >= total_pages * (self.page_len + spare):
                self.raw_page = self.page_len + spare
        self.data = bytearray(data)
        self.cluster_len = self.page_len * self.pages_per_cluster
        self.spare_len = self.raw_page - self.page_len

    def page(self, n):
        off = n * self.raw_page
        return self.data[off:off + self.page_len]

    def cluster(self, n):
        return b"".join(self.page(n * self.pages_per_cluster + i)
                        for i in range(self.pages_per_cluster))

    def fat(self, n):
        """Resolve one FAT entry through the double-indirect FAT."""
        per = self.cluster_len // 4
        ifc = self.cluster(self.ifc_list[n // (per * per)])
        fat_cluster, = struct.unpack_from(
            "<I", ifc, ((n // per) % per) * 4)
        entry, = struct.unpack_from(
            "<I", self.cluster(fat_cluster), (n % per) * 4)
        return entry

    def chain(self, first):
        """Cluster chain starting at `first`, as file-relative numbers."""
        out = []
        cur = first
        while cur != 0xFFFFFFFF:
            out.append(cur)
            entry = self.fat(cur)
            # bit 31 marks "in use"; 0xFFFFFFFF ends the chain
            if entry == 0xFFFFFFFF or not entry & 0x80000000:
                break
            cur = entry & 0x7FFFFFFF
        return out

    def read_chain(self, first, length):
        buf = bytearray()
        for c in self.chain(first):
            buf += self.cluster(c + self.alloc_offset)
            if len(buf) >= length:
                break
        return bytes(buf[:length])

    def spare(self, n):
        off = n * self.raw_page + self.page_len
        return bytes(self.data[off:off + self.spare_len])

    def check_ecc(self):
        """Yield the number of every written page whose ECC does not verify.

        Erased pages have an all-FF spare and no ECC to check; a page holding
        real data always has the four triples followed by four FF bytes.
        """
        blank = bytes([0xFF]) * self.spare_len
        for n in range(self.clusters_per_card * self.pages_per_cluster):
            sp = self.spare(n)
            if not sp or sp == blank:
                continue
            page = self.page(n)
            want = b"".join(ecc(page[c * 128:(c + 1) * 128])
                            for c in range(self.page_len // 128))
            if sp[:len(want)] != want:
                yield n

    def write_page(self, n, payload):
        """Replace one page's data and recompute its ECC. No-op if unchanged."""
        off = n * self.raw_page
        if self.data[off:off + self.page_len] == payload:
            return False
        self.data[off:off + self.page_len] = payload
        if self.spare_len:
            sp = bytearray(bytes([0xFF]) * self.spare_len)
            for c in range(self.page_len // 128):
                sp[c * 3:c * 3 + 3] = ecc(payload[c * 128:(c + 1) * 128])
            self.data[off + self.page_len:off + self.raw_page] = sp
        return True

    def write_chain(self, first, blob):
        """Overwrite a cluster chain with `blob`, which must fit inside it.

        Bytes of the final page beyond `blob` are left as they were, so a file
        whose length is not a whole number of pages does not drag its
        neighbours' leftovers into the diff.
        """
        pos = written = 0
        for c in self.chain(first):
            base = (c + self.alloc_offset) * self.pages_per_cluster
            for i in range(self.pages_per_cluster):
                if pos >= len(blob):
                    return written
                page = bytearray(self.page(base + i))
                part = blob[pos:pos + self.page_len]
                page[:len(part)] = part
                written += self.write_page(base + i, bytes(page))
                pos += self.page_len
        if pos < len(blob):
            raise ValueError("chain holds %d bytes, blob is %d" % (pos, len(blob)))
        return written

    def replace(self, path, blob):
        """Overwrite one file in place. Its length may not change."""
        for name, e in self.walk():
            if name != path or e.is_dir:
                continue
            if len(blob) != e.length:
                raise ValueError("%s is %d bytes, replacement is %d; changing "
                                 "a file's length would need FAT surgery"
                                 % (path, e.length, len(blob)))
            return self.write_chain(e.cluster, blob)
        raise KeyError(path)

    def entries(self, dir_cluster, count):
        """Directory entries of a directory whose own length is `count`."""
        out = []
        got = 0
        for c in self.chain(dir_cluster):
            blob = self.cluster(c + self.alloc_offset)
            for i in range(0, self.cluster_len, 512):
                if got >= count:
                    return out
                out.append(DirEntry(blob[i:i + 512]))
                got += 1
        return out

    def walk(self, cluster=None, count=None, prefix=""):
        """Yield (path, DirEntry) for every file, recursing into directories."""
        if cluster is None:
            cluster, count = self.rootdir_cluster, 2
            root = self.entries(cluster, count)
            count = root[0].length if root else 2
        for e in self.entries(cluster, count):
            if not e.exists or e.name in (".", ".."):
                continue
            path = prefix + e.name
            if e.is_dir:
                yield path + "/", e
                yield from self.walk(e.cluster, e.length, path + "/")
            else:
                yield path, e


class DirEntry:
    def __init__(self, raw):
        (self.mode, self.length) = struct.unpack_from("<II", raw, 0)
        self.created = struct.unpack_from("<8B", raw, 8)
        self.cluster, = struct.unpack_from("<I", raw, 16)
        self.modified = struct.unpack_from("<8B", raw, 24)
        self.attr, = struct.unpack_from("<I", raw, 32)
        self.name = raw[64:96].split(b"\0")[0].decode("ascii", "replace")

    @property
    def is_dir(self):
        return bool(self.mode & 0x0020)

    @property
    def exists(self):
        return bool(self.mode & 0x8000)

    def stamp(self, t):
        return "%04d-%02d-%02d %02d:%02d:%02d" % (
            t[6] | t[7] << 8, t[5], t[4], t[3], t[2], t[1])


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("image")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--extract", metavar="DIR")
    ap.add_argument("--verify-ecc", action="store_true",
                    help="recompute every written page's ECC and compare")
    ap.add_argument("--replace", metavar="PATH=FILE", action="append",
                    help="overwrite a file in place; length may not change")
    ap.add_argument("--out", metavar="IMG", help="where --replace writes")
    args = ap.parse_args()

    mc = PS2MC(open(args.image, "rb").read())
    if args.verify_ecc:
        pages = mc.clusters_per_card * mc.pages_per_cluster
        bad = list(mc.check_ecc())
        print("%s: %d pages, %d bad ECC%s"
              % (args.image, pages, len(bad),
                 "" if not bad else "  " + " ".join(str(n) for n in bad[:8])))
        return 1 if bad else 0

    if args.replace:
        if not args.out:
            sys.exit("--replace needs --out")
        for spec in args.replace:
            path, _, src = spec.partition("=")
            n = mc.replace(path, open(src, "rb").read())
            print("%s <- %s  (%d pages rewritten)" % (path, src, n))
        open(args.out, "wb").write(bytes(mc.data))
        left = list(mc.check_ecc())
        print("wrote %s; ECC verifies on every written page"
              % args.out if not left else "wrote %s; %d pages FAIL ECC"
              % (args.out, len(left)))
        return 0

    if args.list:
        print("page %d  cluster %d  clusters %d  alloc @%d" % (
            mc.page_len, mc.cluster_len, mc.clusters_per_card, mc.alloc_offset))
    for path, e in mc.walk():
        if args.list:
            print("%10s  %-40s  %s" % (
                "<dir>" if e.is_dir else e.length, path, e.stamp(e.modified)))
        if args.extract and not e.is_dir:
            dest = os.path.join(args.extract, path)
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            open(dest, "wb").write(mc.read_chain(e.cluster, e.length))
    if args.extract:
        print("extracted to %s" % args.extract, file=sys.stderr)


if __name__ == "__main__":
    sys.exit(main() or 0)
