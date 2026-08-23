#!/usr/bin/env python3
"""Minimal `strings` (ASCII, printable runs) with byte offsets."""
import argparse, re, sys

ap = argparse.ArgumentParser()
ap.add_argument('path')
ap.add_argument('-n', type=int, default=6)
ap.add_argument('--offsets', action='store_true')
a = ap.parse_args()

data = open(a.path, 'rb').read()
pat = re.compile(rb'[\x20-\x7e\t]{%d,}' % a.n)
for m in pat.finditer(data):
    s = m.group().decode('ascii')
    print(f'{m.start():#010x}  {s}' if a.offsets else s)
