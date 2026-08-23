# Curiosities and surprises

Things the disc reveals beyond its bare technical structure.

## 1. The game is mostly audio

Out of 2.5 GB, the `.iab` streams take up **1.96 GB (78 %)**. Geometry
(`.bin`) is 285 MB, textures (`.p64` + `.mpic`) 247 MB. Add the videos
(`logo/` alone is 492 MB) and nearly 90 % of the disc is linear content.
The engine itself is tiny by comparison.

## 2. Two asset sets, for DVD and for HDD

`/stream/` (77 files, 1.00 GB) and `/stream22/` (66 files, 467 MB) hold the
same tracks at different quality: 48 kHz versus 22 kHz. Likewise the videos
exist in `2m` / `4m` / `8m` bitrate variants. The selector is the bandwidth
of the medium: DVD, or an install on the PS2 HDD.

A curiosity inside the curiosity: `bgm_000.iab` is **identical** in both
directories (44.1 kHz in each), unlike every other track. Either a specially
handled piece of music, or a build oversight.

Eleven files exist **only** in `/stream/`: `bgm_999.iab`,
`ebci-001-0001.iab` and nine `eve_*.iab` (event/cutscene audio).

## 3. The internal `cdimage.tbl` is a build manifest

Inside `RPGSP.DAT` there is a **second copy** of `cdimage.tbl`, larger than
the one on the disc: **3896 entries versus 3818**, and with every offset and
size **zeroed out**. It is not a working index: it is the manifest generated
at build time, packed along with the assets by accident.

The 78 extra entries are IOP modules that are **not** on the final disc:

    ilink.irx, ilsock.irx      i.LINK (FireWire) networking
    mtapman.irx                multitap
    mcxman.irx, mcxserv.irx    extended memory cards
    pad2/*.irx (18 modules)    DualShock 1/2, DigitalCon, etc. drivers
    cdvdstm.irx, stradpcm.irx, sksadpcm.irx, spucodec.irx
    modsesq2, moddelay, modssyn, modmono, modsein
    old/rspu2drv.irx           "old" SPU2 driver
    scrtchpd.irx, spduart.irx, usbmload.irx

The `pad2/*` set and `ilink` hint at features that were evaluated and then
cut — or simply at the full SDK set being dragged along by the project.

## 4. Networking: the game was meant to go online

The disc carries `NET.DB`, `net_host.db` and eighteen Sony `.cnf`
configuration files, plus the `INET`, `PPP`, `PPPOE`, `SMAP`, `NETCNF` and
`DEV9` modules. The `.cnf` files include the period's list of supported USB
Ethernet adapters:

    Melco LUA-TX, I-O Data ET/TX, PLANEX UE-100TX, Corega USB-TX,
    Linksys USB100TX, D-Link DSB-650TX / DU-E100, ADMtek Pegasus

The executable contains strings such as *"A connection error occurred
during..."* and *"An error occurred while accessing the internal..."*.

## 5. The Japanese dictionary survives in the USA release

    /dic/mwnn.dat      70,584 B    Wnn dictionary (kana-kanji)
    /dic/wd.fzk        25,620 B    fuzoku-go (particle) table
    /dic/wd.stm       421,496 B
    /dic/wdlearn.dat    5,705 B    learning dictionary
    /font/jis16.fnt   565,632 B
    /font/jis20.fnt 1,060,448 B

**mWnn** is the classic Japanese IME. The American version still carries the
entire kana-kanji conversion engine and the full JIS fonts — over 2 MB an
English-speaking player can never use. Consistent with the
`SG_textwindow_kanjipart` class and with the supported USB keyboard.

## 6. The engine uses Boost on PlayStation 2

    C:/usr/local/sce/ee/include/boost/shared_array.hpp

The developers installed Boost inside Sony's SDK include tree and used
`shared_ptr`/`shared_array`, RTTI and C++ exceptions on a console with
32 MB of RAM. In 2005 that was a decidedly contrarian choice for a console
title.

## 7. The team's fingerprints

Every texture keeps the source path from the artist's machine:

    C:\saito\render\mpic\bg_000.mpic
    C:\saito\cg_data\airport00\image\airport00.mpic
    C:\saito\2D_menu\sys\syspic\editer_common.mpic
    D:\cg_data\human\B\A00\A00_a\image\chihuahua.mpic
    D:\home\iwashita\ps2\system_font\N_FONT12.mpic
    C:\Documents and Settings\<kanji name>\<Desktop>\mainmenu_logo.mpic
    C:\Documents and Settings\m-akutsu\<Desktop>\check\a00\image\a00.mpic

At least four people are visible (`saito`, `iwashita`, `m-akutsu` and a
fourth name written in kanji), and some shipping textures were exported
**straight from someone's Desktop**. `editer_common` is another recurring
misspelling (for `editor`).

Also worth noting: `chihuahua.mpic` is the texture name for the first human
character.

## 8. A debug menu and a playtest mode

Among the strings: `Debug Menu`, `Playtest`, `StringInputTestHelp`,
`SG_debugscreen`, plus a series of `Error!` messages and per-category
warnings (`Field Warnings`, `Town Warnings`, `Dungeon Warnings`,
`Storyteller Warnings`, `Class Warnings`, `Character Warnings`,
`Monster Warnings`, `Monster Party Warnings`, `Item Warnings`). The project
validator was organised by data type.

## 9. Projects live in a fixed-size arena

The three sample projects are **exactly 1,994,768 bytes each**. That is no
coincidence: a project lives in a constant-capacity arena, and that is
precisely what the editor UI's "Memory" gauge measures. The creative limit
of the game is, literally, a 1.9 MB buffer.

## 10. The video codec is not MPEG

The `.iab` files with a video track declare 640x448 at 29.97 or 59.94 fps,
yet contain no MPEG-2 start codes at all. `opening8m.iab` reaches **8448
frames at 59.94 fps** (141 seconds). The codec is still unidentified.
