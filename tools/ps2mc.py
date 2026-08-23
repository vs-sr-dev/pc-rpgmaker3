#!/usr/bin/env python3
"""List and extract files from a PlayStation 2 memory card image (.ps2).

Handles both raw 8 MB images and the 528-byte-page images (512 bytes of data
plus 16 bytes of ECC/spare) that PCSX2 writes by default.

    python tools/ps2mc.py card.ps2 --list
    python tools/ps2mc.py card.ps2 --extract out/
"""
import argparse
import os
import struct
import sys

MAGIC = b"Sony PS2 Memory Card Format"


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
        self.data = data
        self.cluster_len = self.page_len * self.pages_per_cluster

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
    args = ap.parse_args()

    mc = PS2MC(open(args.image, "rb").read())
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
    main()
