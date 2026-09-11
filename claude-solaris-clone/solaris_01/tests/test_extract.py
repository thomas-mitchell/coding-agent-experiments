"""Check that romdata.py really is what the assembly says.

Every value here was read straight out of solaris_annotated.asm (line numbers in
the comments).  If the extractor ever regresses, these catch it before a wrong
table turns into a mysterious gameplay bug.
"""

from solaris import romdata as r


def test_data_stream_is_intact():
    assert len(r.DATA) == 6627
    assert len(r.LABELS) == 428
    # every entry is a byte or a label reference, nothing else
    for v in r.DATA:
        assert isinstance(v, (int, r.R))
        if isinstance(v, int):
            assert 0 <= v <= 0xFF


def test_unresolved_refs_are_all_code_handlers():
    """Refs that are not data labels must be AI/animation/VM handlers.

    Those are the `<BRAN11` style dispatch entries, which the port maps to
    Python functions.  Anything else would mean a table went missing.
    """
    unresolved = {v.name for v in r.DATA if isinstance(v, r.R) and v.name not in r.LABELS}
    for name in unresolved:
        assert name[:4] in ("BRAI", "BRAN", "BRN1", "GRAP", "NEWB", "NEWO", "DIS5",
                            "DIS7", "PLN5", "PLN7"), name


def test_zero_page_map():
    # lines 440-558: ORG $80 then a run of DS directives
    assert r.ZP["MAZRAM"] == 0x80
    assert r.ZP["CURSOR"] == 0x88
    assert r.ZP["JMPCNT"] == 0x89
    # "MUST BE RIGHT AFTER JMPCNT (FOR FINDV)" - line 446
    assert r.ZP["MAZSTA"] == r.ZP["JMPCNT"] + 1
    assert r.ZP["PROGST"] == 0x8D
    assert r.ZP["HGRAP1"] == 0xA1
    assert r.ZP["HGRAP0"] == 0xA5      # HGRAP1 + 3 player bytes + 1 pad
    assert r.ZP["HVERP1"] == 0xB3
    assert r.ZP["IQPATH"] == 0xC4
    assert r.ZP["SCORE"] == 0xDC
    assert r.ZP["HHITP0"] == 0xF8
    assert r.ZP["STAK1"] == 0xFC
    # STARS+1 IS NEWAVE - line 743
    assert r.ZP["STARS"] + 1 == 0xC9


def test_game_constants():
    # lines 689-706
    assert r.EQU["PBLK"] == 0xE0       # $60 + $80, the empty-slot sentinel
    assert r.EQU["TOPSCN"] == 0x99
    assert r.EQU["SCNSIZ"] == 0x99 + 39
    assert r.EQU["VSHIP"] == 0x1D
    assert r.EQU["ZVIS"] == 0x78
    assert r.EQU["VCENT"] == 0x53
    assert r.EQU["POFF"] == 0xA8
    assert r.EQU["MTNTOP"] == 0x62
    assert r.EQU["TRNTOP"] == 0x62
    assert r.EQU["SCLR"] == 0xF2


def test_crazy_is_the_full_160_pixel_table():
    # line 4678; 20 rows of 8.  Index = pixel X, so the port just uses the index.
    crazy = r.table("CRAZY", 160)
    assert crazy[:8] == [0x60, 0x71, 0x50, 0x61, 0x40, 0x51, 0x30, 0x41]
    assert crazy[-8:] == [0xFB, 0xDA, 0xEB, 0xCA, 0xDB, 0xBA, 0xCB, 0xAA]


def test_packed_velocity_magnitudes():
    # BRNTB5, line 3495 - and quoted in the file header, section 3
    assert r.table("BRNTB5", 16) == [0, 1, 2, 3, 4, 5, 6, 7,
                                     8, 0x0C, 0x10, 0x14, 0x18, 0x1C, 0x20, 0x24]


def test_takeoff_start_positions():
    # lines 5176-5177, consumed by INIT10
    assert r.table("INTAB1", 4) == [0x05, 0x14, 0x27, 0x48]   # distances
    assert r.table("INTAB2", 4) == [0x78, 0x28, 0x68, 0x3B]   # X positions


def test_shared_tables_overlap_rather_than_truncate():
    """`;SHARE n` means the tail of one table is the head of the next."""
    # LIVTAB (5 bytes, line 5182) is followed by SJOYT2 (line 5184) under ;SHARE 2
    assert r.table("LIVTAB", 5) == [0x80, 0xE0, 0xE0, 0xC0, 0x80]
    assert r.table("SJOYT2", 4) == [0x00, 0x00, 0x80, 0x40]
    # FINTB2 is 3 bytes but is read as 4, borrowing SMHTB2's first byte
    assert r.table("FINTB2", 4)[3] == r.table("SMHTB2", 1)[0]


def test_sprites_come_out_top_row_first():
    """Sprites are stored bottom-row-first and the label sits AFTER the block.

    The display kernel reaches an object's top row at address LABEL-1 (see
    DIS150/DIS102, lines 6552-6570: it waits for Y < objY, then DEYs once more
    before the first fetch, so the first address is MTABL1[type]-2 == LABEL-1).
    """
    # line 9522: the block before RPL8 is $00,$00,$24,$66,$FF,$18,$3C,$5E,$0F,$5E,$3C,$18
    assert r.sprite("RPL8") == [0x18, 0x3C, 0x5E, 0x0F, 0x5E, 0x3C, 0x18, 0xFF, 0x66, 0x24]
    # The label names the block BEFORE it, so the `RPL3 .byte ...` line at 9528
    # actually holds RPL2's bitmap and the bare `RPL1` at 9530 holds RPL2's line.
    assert r.sprite("RPL2") == [0x18, 0x3C, 0x18, 0x3C, 0x24]
    assert r.sprite("RPL1") == [0x18]        # the most distant tower: one pixel row
    # your ship, line 7265 - the block also holds smaller takeoff variants,
    # separated by the $00 bytes that terminate each one
    assert r.sprite("YGR1") == [0x04, 0x04, 0x0E, 0x0E, 0x1F, 0x1F, 0x3F, 0x7F, 0xF1]


def test_master_sprite_index_is_symbolic():
    # MTABL1/MTABL3, line 7521: `<FGR8+U` where U EQU 1
    assert r.table("MTABL1", 3) == [r.R("FGR8", 1), r.R("FGR7", 1), r.R("FGR6", 1)]
    assert r.table("MTABL3", 3) == [r.R("FGR8"), r.R("FGR8"), r.R("FGR8")]
    # MTABL2, line 7540: `Z EQM <CF` then `Z+$D`
    assert r.table("MTABL2", 2) == [r.R("CF", 0x0D), r.R("CF", 0x0D)]
    # MTABL4 is 0 for a flat 8-pixel-wide object like the fighter
    assert r.table("MTABL4", 8) == [0] * 8


def test_ai_dispatch_is_symbolic():
    # BRNTB4, line 3440
    assert r.table("BRNTB4", 8) == [
        r.R("BRAN11"), r.R("BRAN11"), r.R("BRAN11"), r.R("BRAN11"),
        r.R("BRAIN9"), r.R("BRAN11"), r.R("BRAN11"), r.R("BRAN32"),
    ]


def test_spawn_vm_bytecode_resolves():
    """TYPTAB opcodes stay symbolic; its branch operands become real offsets.

    `W EQU TYPTAB` (line 3151), so `BLKTYP+6-W` is an offset into the script.
    """
    W = r.LABELS["TYPTAB"]
    assert r.LABELS["BLKTYP"] - W == 1
    # BLKTYP: $CA,$CA,$D6,$D6, LVS,$00, $AB,$AB, BRN,BLKTYP+6-W   (line 3155)
    blk = r.DATA[r.LABELS["BLKTYP"]:r.LABELS["BLKTYP"] + 10]
    assert blk[:4] == [0xCA, 0xCA, 0xD6, 0xD6]
    assert blk[4] == r.R("NEWB50")          # LVS
    assert blk[5] == 0x00
    assert blk[8] == r.R("NEWB51")          # BRN
    assert blk[9] == r.LABELS["BLKTYP"] + 6 - W == 7

    # DONTYP: $A1, $C8, ENB,SHIPST,$01  - the operand is a zero-page ADDRESS
    don = r.DATA[r.LABELS["DONTYP"]:r.LABELS["DONTYP"] + 5]
    assert don[2] == r.R("NEWOB4")          # ENB
    assert don[3] == r.ZP["SHIPST"] == 0xD3
    assert don[4] == 0x01


def test_vm_opcode_handler_names():
    # lines 1108-1118: each opcode byte IS the low byte of its handler address
    assert r.OPCODE_HANDLERS["LVS"] == r.R("NEWB50")
    assert r.OPCODE_HANDLERS["GTO"] == r.R("NEWOB2")
    assert r.OPCODE_HANDLERS["INL"] == r.R("NEWB81")
    assert len(r.OPCODE_HANDLERS) == 11


def test_difficulty_tables():
    assert r.table("BRNT15", 5) == [0x1C, 0x14, 0x0C, 0x08, 0x04]   # min firing range
    assert r.table("BRNT16", 4) == [0x60, 0x40, 0x30, 0x20]
    assert r.table("BRNT17", 5) == [0x18, 0x20, 0x28, 0x30, 0x38]   # max closing speed
    assert r.table("BRNT10", 5) == [0x00, 0x03, 0x06, 0x08, 0x0C]   # shot lead
    assert r.table("HITAB5", 5) == [0x14, 0x14, 0x14, 0x1A, 0x1E]
    # DORT11[level] & 7 is NEWAVE, recomputed every frame in MAIN2 (line 5019)
    assert r.table("DORT11", 16)[:8] == [0x00, 0x00, 0x0B, 0x11, 0xF2, 0x09, 0xF4, 0x0A]


def test_scoring_tables():
    # HITAB1 line 5957; the score is (v >> 1) & $7E, displayed with a trailing 0
    assert r.table("HITAB1", 19)[:8] == [0x60, 0x66, 0x07, 0x12, 0xA0, 0x4F, 0x03, 0x00]
    assert r.table("HITAB4", 4) == [0x02, 0x98, 0x9F, 0xAF]
    assert r.table("HITAB2", 8) == [0x1C, 0x2F, 0x2F, 0x38, 0x7F, 0x7F, 0x7F, 0x7F]
    assert r.table("HITAB3", 8) == [0x00, 0x00, 0x00, 0x08, 0x10, 0x1C, 0x1E, 0x20]


def test_star_chart_tables():
    assert r.table("SMSKTB", 8) == [1, 2, 4, 8, 0x10, 0x20, 0x40, 0x80]
    assert r.table("DORTB3", 4) == [0x00, 0x2A, 0x2F, 0x05]     # wormhole exits
    assert r.table("DORTB8", 4) == [0x23, 0x04, 0x12, 0x2C]     # new-level cursor
    assert r.table("DORTB9", 4) == [0x18, 0x2D, 0x1D, 0x03]     # new-level cells
    assert r.table("DORTB6", 16)[:8] == [0xF3, 0xFB, 0xFF, 0xFE, 0xFF, 0xEF, 0xFB, 0xFF]
