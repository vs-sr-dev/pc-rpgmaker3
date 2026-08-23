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
    C:\Documents and Settings\Administrator\<Desktop>\suutiin.mpic

At least four people are visible (`saito`, `iwashita`, `m-akutsu` and a
fourth name written in kanji), several shipping textures were exported
**straight from someone's Desktop**, and one came off an account literally
named `Administrator`. `editer_common` is another recurring
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

## 10. The video codec had no start codes

The `.iab` movies declare 640x448 at 29.97 or 59.94 fps but contain no MPEG
start codes at all, so nothing will play them. They turned out to be
**MPEG-2 intra with the entire sequence, picture and slice layer stripped
out** — see [06-iab-video.md](06-iab-video.md). Two details make it unusual:
`intra_vlc_format = 1`, and no slice layer at all — each macroblock row
re-sends the quantiser through a `macroblock_type = '01'` on its first
macroblock instead.

## 11. The Japanese logo movie ships unused

`logo/logo.iab` is a 7.5-second animation of two meshing gears that resolves
into a card reading **「ツクールシリーズ」** ("Tsukuru Series", the Japanese
name of the RPG Maker line). It decodes perfectly, audio included.

It is never played. The USA release boots three **static** `.mpic` images
instead — Enterbrain, Runtime and Agetec — as confirmed by capturing the
boot sequence. So the Japanese series ident is still on the disc, fully
intact, and no player will ever see it.

The same goes for `logo/rpg_640_448.iab`: two minutes of Japanese staff roll
credits.

## 12. `tukuru.mpic` is the Agetec logo

The file named after the Japanese brand actually contains the American
publisher's logo. **`tukuru` is ツクール** — the Japanese name of the series
is RPGツクール (*RPG Tsukūru*), a pun on 作る *tsukuru* ("to make") and
ツール *tsūru* ("tool"). So this slot originally held the Japanese series
ident, the same one still animated in `logo/logo.iab`.

Its embedded source path gives the substitution away:

    C:\Documents and Settings\<kanji name>\<Desktop>\ageteclogoforscreeneps.mpic

`eb.mpic` and `runtime.mpic` both keep source files of their own name; only
this one points at a completely different file. The localisation dropped the
Agetec logo into the existing slot and never renamed it. Our decode matches a
PCSX2 frame capture to within 0.9 per colour channel.

## 13. The 2D character art is filed by illustrator

`img_2d/` has seven subdirectories of 88 images each, and the file prefixes
inside them settle what the names are:

    nouguchi/nog_NN.mpic     nihei/ni_NN.mpic
    kitazawa/kit_NN.mpic     hanaka/hana_NN.mpic
    iwasaki/iwa_NN.mpic      nagasaku1/na1_NN.mpic
                             nagasaku2/na2_NN.mpic

They are **people**: the staff roll video names 納口龍司 (Nouguchi) and
北沢直樹 (Kitazawa) under 「3Dキャラクターデザイン」. Each illustrator's
portrait set got its own folder, keyed by an abbreviation of their surname,
and that structure shipped on the disc.

## 14. Runtime, Inc. — "Entertainment & Architecture"

The developer's boot logo carries that tagline. The studio behind a 3D RPG
construction kit also did architectural visualisation — which, given that
the game is essentially a real-time level editor, is not a coincidence.

## 15. The asset names are romaji typed on a Japanese IME

The naming is a running mix of English and romanised Japanese, and the
romanisation is **kunrei-style** — つ as `tu`, ち as `ti` — which is how you
type Japanese into an IME, not how you would transliterate it for readers:

    tukuru            つくる  (ツクール, the series name)
    battle/suutiin    すうち  (数値, "numeric value") -- and the file really
                              does hold the battle digits, "MAX" and the bars
    weapon/kakutou    格闘    hand-to-hand, as a weapon class
    weapon/naginata   なぎなた
    pre_ground/pre_jimen.bin  地面 = "ground": the folder is the English of
                              its own file name
    weapon/ya00.p64   矢      "arrow", loose in the weapon folder

Two more slips are pure transliteration accidents:

    weapon/brade/     ブレード "blade", with the classic r/l swap
    room/palas00      パラス   "palace"

And one placeholder never got renamed: the field terrain sets are
`field/hokaidou1..3.p64` — **Hokkaido**.

## 16. Two of the three sample games were never translated

The USA release ships three sample projects. `sample1` is
**"Dear Brave Heart"**, fully localised — 579 ASCII strings, place names
like *Elgiza Isle*, and Enterbrain's own name in Latin letters.

The other two never were. `sample2` is 太陽の昇る街 ("the town where the sun
rises"), 1,271 Japanese strings against 22 ASCII ones — and the 22 are false
positives from binary data, not text. Its cast is intact: アイン,
本編の主人公 ("the protagonist of the main story"). Character bios read in
full, e.g. アーヴィン, 「青い稲妻」「神速の弓手」の二つ名を持つ、若き射手 —
"a young archer who goes by two names, Blue Lightning and the Godspeed
Bowman".

Whether the editor lets a USA player load them is untested, but the data is
there, complete, and in a font the console can render — the Japanese glyph
sheet `jis16.fnt` shipped too.

## 17. One of the samples is a developer's test file

`sample3` is titled タウンレイウトサンプル — "town layout sample". It has 85
objects of one type and 32 of another where the playable samples have a
handful, and no story text to speak of. It is a scratch file for checking
that town layout works, left in the retail directory next to the two real
demos.
