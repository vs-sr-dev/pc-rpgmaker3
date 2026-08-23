# Engine architecture

`SLUS_211.78` is **not section-stripped**: 47 section headers, a separate
`.vutext`, and — most importantly — the **C++ RTTI names** in `.rodata`.
Those give us a near-complete map of the engine's classes.

    .text              2,600,168   EE code
    .vutext               51,488   VU1 microcode
    .DVP.overlay.*        ~33 KB   16 VU1 microprograms as overlays
    .data              1,322,008
    .rodata              184,816
    .bss                 448,496

There is no `.symtab`, but the type_info strings are enough.

## The toolchain was modern C++ (for 2005)

The binary contains `boost::bad_weak_ptr`, `boost::detail::sp_counted_base`,
`boost::checked_array_deleter` and the path
`C:/usr/local/sce/ee/include/boost/shared_array.hpp`. The engine uses
`shared_ptr` / `shared_array`, exceptions, `std::basic_string` and RTTI on a
console with 32 MB of RAM — a distinctly unusual choice for a 2005 console
title.

Full extracted list: [`rtti_classes.txt`](rtti_classes.txt) (224 names).

## `SG_*` — rendering scene graph

    SG_base
      SG_displayobject_base
        SG_objcluster              grouping
        SG_polygonObjectTRS        static mesh with TRS transform
        SG_skinObject              skinned mesh
        SG_skinObject_1material    single-material variant
        SG_skinObj1mat
        SG_sprite / SG_sprite4v / SG_sprite3dTRS
        SG_fieldObject
        SG_textwindow
          SG_textwindow_asciipart
          SG_textwindow_kanjipart
        SG_scissorObject / SG_scissorObject2d / SG_scissorObjectNone
        SG_scissorCancelObject / SG_scissorCancelObjectNone
      SG_camera
      SG_light_base
        SG_light_ambient
        SG_light_direction
        SG_light_pointLight
        SG_light_pseudoPoint       approximated point light
      SG_texture / SG_texturetrans_base
      SG_interspace_base / SG_planespace_base    spatial partitioning
      SG_debugscreen                              on-screen debug text
      SG_rootObject

Notes relevant to the port:

* characters are **skinned**, not rigid: a real skinning system is required;
* `SG_light_pseudoPoint` is an approximated point light, a typical VU1
  shortcut — on PC a true point light can be used instead;
* text rendering is **split** between an ASCII part and a kanji part, with
  dedicated fonts (`ascii16/20`, `jis16/20`);
* `SG_interspace_base` / `SG_planespace_base` suggest a plane/cell
  partitioning scheme for room culling.

## `FF_*` — low-level graphics layer

    FF_sop2_matrix1, FF_sop2_dmatag, FF_pack, FF_packedmpic, FF_scall
    Matrix44f, Vector4f, Qword

`FF_sop2_dmatag` and `Qword` confirm that geometry travels as DMA chains to
VIF1. `FF_packedmpic` is the `.mpic` texture loader.

## `CEdPro*` — project data model

These are the objects the user creates, and what ends up in
`sample/game/*`:

    CEdProGameSystem, CEdProHuman, CEdProHumanModeEdit, CEdProClassType,
    CEdProMonster, CEdProMonsterParty, CEdProMonsterPartySet,
    CEdProMonsterPartySize{S,M,L}, CEdProSkill, CEdProSkillMonster,
    CEdProRoom, CEdProSavePoint,
    CEdProItemBase, CEdProItem1, CEdProItem2_1, CEdProItem2_2,
    CEdProItem2_3, CEdProItem3,
    CEdProShop1, CEdProShop2, CEdProShop3,
    CEdProBaseEvent, CEdProBaseEventTrg, CEdProBoxEvent, CEdProDoorEvent,
    CEdProEntranceEvent, CEdProWarpEvent, CEdProSwitchEvent,
    CEdProTrapEvent, CEdProDecorationEvent

These map directly onto the `.smp` record sizes.

## `CEdEv*` — event commands (~100)

The game's visual scripting language. Categories:

* **Messaging / flow**: `Message`, `KeyWait`, `Wait`, `EveEnd`,
  `RunEvent`, `Escape`, `GameOver`, `Ending`
* **Branching**: `BranchSel`, `BranchQA`, `BranchVal`, `BranchBtl`
* **Switches and variables**: `CommonSwAdd/Sub/Change/Copy`,
  `LocalSwAdd/Sub/Change/Copy`
* **Party**: `PartyJoin`, `PartyRemove`, `PartyActiveChange`,
  `PartyHeal`, `PartyDamage`, `PartyRaise`, `PartyFullRecovery`,
  `PartyPoisonState`, `PartyCurePoison`
* **Character**: `HumanLevelAdd/Sub/Change`, `HumanAbilityAdd/Sub/Change`,
  `HumanHeal`, `HumanDamage`, `HumanRaise`, `HumanFullRecovery`,
  `HumanPoisonState`, `HumanCurePoison`, `HumanNameChange`,
  `HumanNameInput`, `ExpGet`, `SpecialLearn`, `SpecialForget`
* **Inventory**: `ItemGet`, `ItemDrop`, `EventItemGet`, `EventItemDrop`,
  `GoldGet`, `GoldDrop`
* **Presentation**: `FadeIn`, `FadeOut`, `DispOn/Off/Reset`, `DispShake`,
  `DispFlash`, `DispEffect`, `DecorateDispOn/Off`, `AnimationPlay`,
  `MotionPlay`, `Move`, `Spine`
* **Audio**: `BgmPlay`, `BgmStop`, `SePlay`, `MelodyPlay`
* **World**: `SeasonChange`, `TimeChange`, `WeatherChange`, `WarpLong`,
  `ModeChange`, `ModeInc`, `ModeDec`,
  `FieldPropatySet`, `TownPropatySet`, `RoomPropatySet`,
  `DungeonPropatySet`, `DungeonTrapDamageChange`
* **Battle**: `Battle`, `BattleHuman`
* **Narration**: `StoryPlay`

(`Propaty` is a consistent misspelling of `Property` by the original
authors — a handy signature for identifying original code.)

## Timeline cutscene editor

    STSEditor, KeyEditor,
    ActorKeyEditor, ObjectKeyEditor, MessageKeyEditor,
    BGMKeyEditor, SEKeyEditor, EffectKeyEditor, BackgroundKeyEditor

The "Storyteller" is not a command list but a **multi-track keyframe
sequencer**: actors, objects, messages, BGM, sound effects, visual effects
and background, each on its own track.

## UI widgets

    CGUI_BTN, CGUI_LMENU, CGUI_MENUBTN, CGUI_OK, CGUI_SELCUR, CBTN_BASE,
    CPL_MSGWIN, CPL_NAMEWIN, CPL_SELWIN, CPL_SIGNBOARD,
    CSYSPIC_PARTS, CSYSPIC_PARTS3D, CSYSPIC_SYSWIN,
    CSPRT_BASE, CSPRT4V_BASE, CMASK_SPRT,
    SpriteWidget, ClipSprite, CrossSprite, PenantSprite, ToolTipSprite,
    CountBar, CountObj, StatusWin, CHelpKey, CHelpMsg, NPCMan, SESet

`CSYSPIC_*` reads directly from `syspic.p64`, the UI atlas.

## VU1 microprograms

The `.DVP.overlay..<addr>.<hash>.<size>.<chunk>` sections describe **16
distinct microprograms**, loaded at micro-mem addresses `0x0`, `0x800` and
`0x1000`. Source names are not preserved (hashes only), so identification
has to be done by disassembly.

## IOP modules actually loaded

From the references in `.rodata`:

    iop/sio2man, sio2d, dbcman, mc2_s1, padman, libsd, sdrdrv, bindstm2
    iop2/dev9, atad, hdd, pfs, usbd, usbkb,
         modhsyn, modmsin, sksound, skhsynth, skmsin

`usbkb` = **USB keyboard** for text entry. `modhsyn` + `skhsynth` +
`modmsin` = a MIDI sequencer with a **software synth**: music is not only
streamed, there is also a MIDI pipeline driving the `.hd`/`.bd` banks.
