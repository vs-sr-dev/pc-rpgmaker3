# Disc layout

Original USA DVD, `SLUS-21178`, ~2.45 GB.

    CDIMAGE.TBL        519,252   index into RPGSP.DAT
    RPGSP.DAT    2,509,103,104   monolithic archive: the entire game
    SLUS_211.78      4,228,720   EE executable (ELF, MIPS R5900)
    IOPRP300.IMG       275,345   IOP module image
    IOP/                         25 IRX modules (pad, MC, audio, network)
    IOP2/                        16 IRX modules (HDD, USB, MIDI/synth)
    SYSTEM.CNF, ICON.SYS, INFO.SYS, HDDICON.ICO, RPGSP.ICO, JKT_001.PNG

`SYSTEM.CNF`:

    BOOT2 = cdrom0:\SLUS_211.78;1
    VER = 1.02
    VMODE = NTSC
    HDDUNITPOWER = NICHDD

`HDDUNITPOWER`, together with the `ATAD`/`HDD`/`PFS` modules in `IOP2/`,
indicates support for **installing to the PS2 HDD**. The executable carries
both path pairs:

    cdrom0:\RPGSP.DAT   /  pfs0:/rpgsp.dat
    cdrom0:\CDIMAGE.TBL /  pfs0:/cdimage.tbl

That explains the dual-quality asset sets (see `stream` / `stream22` and the
`2m` / `4m` / `8m` videos): the game picks a set based on the bandwidth of
the medium it is running from.

## Leftover development paths

The executable still holds the `host0:` fallbacks used on DECR devkits,
which reveal the original source tree:

    host0:../cdimage/%s          <- becomes RPGSP.DAT
    host0:../arcimage/%s
    host0:../cdimage/../pictures/%s
    host0:../cdimage/iop/%s
    host0:/usr/local/sce/iop/modules/netcnfif.irx
    host0:c:/usr/local/sce/conf/net/net.db

In other words: the project's `cdimage/` directory was packed verbatim into
`RPGSP.DAT`, keeping its absolute paths as entry names.
