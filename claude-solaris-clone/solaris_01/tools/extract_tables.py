"""Extract every data table in solaris_annotated.asm into solaris/romdata.py.

Why this exists
---------------
Solaris is a table-driven game: sprites, colour ramps, AI dispatch, flight paths,
sound sequences, the star chart and the wave-spawn bytecode are all `.byte` data.
There are ~1025 `.byte` directives in the disassembly.  Transcribing them by hand
would inject errors that are effectively undebuggable once the game is running,
so the port reads them straight out of the assembly instead.

Model
-----
The assembly is not re-assembled -- that would need a full 6502 opcode table.
Instead every `.byte` in the file, in file order, is appended to ONE global data
stream, and every label is recorded as an index into that stream.  That is enough
for everything the port needs:

  * a table is `DATA[LABELS[name] : ...]`
  * `;SHARE n` tables fall out for free, because the sharing tables are adjacent
    in file order and simply read past their own end
  * a sprite is the block *preceding* its label (see `sprite()` below)
  * TYPTAB's `LABEL+n-W` branch operands resolve by subtracting LABELS['TYPTAB']

Symbolic entries (`<FGR8+U`, `<BRAN11`, `Z+$D`) cannot be numbers without real
addresses, so they are kept as `R(name, offset)` references.  That is better than
a number anyway: the port maps `R('BRAN11', 0)` to a Python function and
`R('FGR8', 1)` to a sprite, which is what the byte meant in the first place.
"""

import re
import sys
from pathlib import Path

ASM = Path(__file__).resolve().parents[2] / "solaris_annotated.asm"
OUT = Path(__file__).resolve().parents[1] / "solaris" / "romdata.py"

# Directives that carry no data and need no bookkeeping beyond ending a block.
IGNORED = {
    "SEG", "SEG.U", "PROCESSOR", "END", "LIST", "INCLUDE",
}


class Ref:
    """An unresolvable-without-addresses table entry: `<LABEL+offset`."""

    __slots__ = ("name", "offset")

    def __init__(self, name, offset=0):
        self.name = name
        self.offset = offset

    def __repr__(self):
        return f"R({self.name!r}, {self.offset})" if self.offset else f"R({self.name!r})"


def split_operands(operand):
    """Split on commas that are not inside a quoted string."""
    out, cur, in_str = [], [], False
    for ch in operand:
        if ch == '"':
            in_str = not in_str
        if ch == "," and not in_str:
            out.append("".join(cur).strip())
            cur = []
        else:
            cur.append(ch)
    if "".join(cur).strip():
        out.append("".join(cur).strip())
    return [o for o in out if o]


def strip_comment(code):
    """Drop everything after ';', unless the ';' is inside a quoted string."""
    if '"' not in code:
        return code.split(";", 1)[0]
    out, in_str = [], False
    for ch in code:
        if ch == '"':
            in_str = not in_str
        if ch == ";" and not in_str:
            break
        out.append(ch)
    return "".join(out)


class Extractor:
    def __init__(self, text, known_labels=None):
        self.lines = text.splitlines()
        # Pass 1 runs with `known_labels=None` and tolerates forward references
        # (TYPTAB branches to labels defined later in the same table).  Because
        # every `.byte` operand contributes exactly one byte whatever its value,
        # pass 1 still lands every label on its correct index; pass 2 then reruns
        # with those indices seeded and resolves for real.
        self.prepass = known_labels is None
        self.data = []          # the global byte stream (int | Ref)
        self.labels = dict(known_labels or {})   # name -> index into self.data
        self.code_labels = []   # labels that turned out to precede code
        self.equ = {}           # EQU constants that evaluate to plain ints
        self.opcode_refs = {}   # EQU constants that are really addresses
        self.zp = {}            # zero-page symbol -> address
        self.blocks = []        # (start, end) of each contiguous .byte run
        self.addr = {}          # label -> its real ROM address, where knowable
        self._addr = None       # the running assembly address
        self._block_addr = None
        self._skipping = False  # inside the not-taken arm of an IFCONST
        self._pending = []      # bare labels waiting to be classified
        self._z = None          # the current `Z EQM ...` value
        self._org = None        # current ORG, only tracked in the DS section
        self._block_start = None

    # -- helpers ----------------------------------------------------------
    def flush_pending(self, is_data):
        for name in self._pending:
            if is_data:
                self.labels[name] = len(self.data)
                if self._addr is not None:
                    self.addr[name] = self._addr
            else:
                self.code_labels.append(name)
        self._pending = []

    def end_block(self):
        if self._block_start is not None:
            self.blocks.append((self._block_start, len(self.data), self._block_addr))
            self._block_start = None
            self._block_addr = None

    # -- expression evaluation --------------------------------------------
    def value(self, expr):
        """Evaluate a DASM operand to an int, or a Ref when it needs an address."""
        expr = expr.strip()
        if expr == "Z":
            return self._z
        if expr[:2] in ("Z+", "Z-"):
            if self._z is None:
                raise ValueError(f"Z used before it was set: {expr}")
            sign = 1 if expr[1] == "+" else -1
            return Ref(self._z.name, self._z.offset + sign * self.number(expr[2:]))
        if expr in self.opcode_refs:
            # a spawn-VM opcode: `LVS EQU <NEWB50` means the opcode byte IS the
            # low byte of its handler's address, so keep the handler name
            return self.opcode_refs[expr]
        if expr[0] in "<>":
            # low/high byte of an address: keep it symbolic
            inner = expr[1:].strip()
            if inner.startswith("(") and inner.endswith(")"):
                inner = inner[1:-1]
            name, off = self.split_symbol(inner)
            return Ref(name, off)
        return self.number(expr)

    def split_symbol(self, expr):
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)\s*(.*)$", expr)
        if not m:
            raise ValueError(f"not a symbol reference: {expr}")
        name, rest = m.group(1), m.group(2).strip()
        off = 0
        for sign, term in re.findall(r"([+-])\s*([^+-]+)", rest):
            off += (1 if sign == "+" else -1) * self.number(term)
        return name, off

    def number(self, expr):
        """Arithmetic over EQUs, zero-page symbols and data-label indices."""
        expr = expr.strip()
        if not expr:
            return 0
        total, sign = 0, 1
        for tok in re.findall(r"[+-]|\$[0-9A-Fa-f]+|[A-Za-z_][A-Za-z0-9_]*|\d+", expr):
            if tok == "+":
                sign = 1
            elif tok == "-":
                sign = -1
            elif tok.startswith("$"):
                total += sign * int(tok[1:], 16)
            elif tok.isdigit():
                total += sign * int(tok)
            else:
                total += sign * self.symbol(tok)
        return total

    def symbol(self, name):
        if name in self.equ:
            return self.equ[name]
        if name in self.zp:
            return self.zp[name]
        if name in self.labels:
            return self.labels[name]
        if name in self._pending:
            # a bare label whose data has not been emitted yet, e.g.
            # `TYPTAB` on one line and `W EQU TYPTAB` on the next
            return len(self.data)
        if self.prepass:
            return 0
        raise KeyError(name)

    # -- the main pass ----------------------------------------------------
    def run(self):
        for lineno, raw in enumerate(self.lines, 1):
            try:
                self.line(raw)
            except Exception as exc:  # noqa: BLE001 - surface the line that broke
                raise RuntimeError(f"line {lineno}: {raw!r}\n  {exc}") from exc
        self.flush_pending(is_data=False)
        self.end_block()

    def line(self, raw):
        code = strip_comment(raw)
        stripped = code.strip()
        if not stripped:
            return

        indented = code[0] in " \t"
        parts = stripped.split(None, 1)
        head = parts[0]
        rest = parts[1] if len(parts) > 1 else ""

        # `LABEL DIRECTIVE ...` vs ` DIRECTIVE ...`
        if indented:
            label, directive, operand = None, head, rest
        elif rest:
            d = rest.split(None, 1)
            label, directive = head, d[0]
            operand = d[1] if len(d) > 1 else ""
        else:
            label, directive, operand = head, None, ""

        du = (directive or "").upper()

        if du in ("BYTE", ".BYTE"):
            before = len(self.data)
            self.emit_bytes(label, operand)
            if self._addr is not None:
                self._addr += len(self.data) - before
            return

        if directive is None:
            if self._addr is not None:
                self.addr[label] = self._addr
            if self._block_start is not None:
                # A bare label sitting immediately after a `.byte` run names
                # that run (the file's convention throughout), so record it as
                # data now even if code follows -- SHCL, the ship colour ramp,
                # is exactly this case.
                self.labels[label] = len(self.data)
            # A bare label on its own line.  We cannot tell yet whether it names
            # data or code, so hold it until the next directive says which.  It
            # also must not end the current block: several sprites are named by
            # stacked bare labels sitting between two `.byte` runs.
            self._pending.append(label)
            return

        self.end_block()

        if du == "EQM":
            # `Z EQM <CF` - a textual macro used to build the MTABL2/MTABL3 rows
            if label != "Z":
                raise ValueError(f"unexpected EQM symbol {label}")
            self._z = self.value(operand)
            return

        if du == "EQU" and self._skipping:
            return

        if du == "EQU":
            # Deliberately does NOT flush pending labels: an EQU may sit between
            # a bare label and the `.byte` block that label names.
            try:
                v = self.value(operand)
            except (KeyError, ValueError):
                return
            if isinstance(v, Ref):
                # `LVS EQU <NEWB50` -- an address we cannot compute, and one the
                # port wants by name anyway
                self.opcode_refs[label] = v
            else:
                self.equ[label] = v
            return

        if du == "DS":
            # the zero-page map: `ORG $80` then `LABEL DS n`.  A bare label on
            # its own line (CHTBLK) names the address the next DS starts at.
            if self._org is not None:
                for name in self._pending:
                    self.zp[name] = self._org
                if label:
                    self.zp[label] = self._org
                self._org += self.number(operand)
            self.flush_pending(is_data=False)
            return

        if du == "ORG":
            try:
                v = self.number(operand)
            except KeyError:
                # e.g. `ORG HACKCLI`, a development-system patch point
                self._org = None
                return
            # only the $80/$E3 ORGs describe zero page; $2000+ are ROM segments
            self._org = v if v < 0x200 else None
            self._addr = None if v < 0x200 else v
            return

        if du == "IFNCONST":
            self._skipping = True
            return
        if du == "IFCONST":
            self._skipping = False
            return
        if du == "ELSE":
            # the shipped ROM is built with BURN defined, so the ELSE arm (the
            # development-system bank mapping at $C000..$F000) is not assembled
            self._skipping = True
            return
        if du == "ENDIF":
            self._skipping = False
            return

        if du in ("WORD", ".WORD"):
            self.flush_pending(is_data=False)
            return

        if du == "RORG":
            # RORG gives the address the code will really run at, which is what
            # the `<LABEL` low-byte comparisons in the game are against.
            try:
                self._addr = self.number(operand)
            except KeyError:
                self._addr = None
            return

        if du in IGNORED:
            # Segment/ORG bookkeeping.  It must NOT classify a pending label:
            # `YGR3` (your ship, banked left) is a bare label sitting between
            # its own `.byte` block and an `ORG`/`RORG` pair.
            return

        # anything else on this line is a 6502 instruction.  The port does not
        # assemble code, so the running address is unknown from here until the
        # next ORG -- which is why only labels inside a pure data run get one.
        self._addr = None
        # every label waiting behind it names code, not data
        if label:
            self._pending.append(label)
        self.flush_pending(is_data=False)

    def emit_bytes(self, label, operand):
        if label:
            self._pending.append(label)
        self.flush_pending(is_data=True)
        if self._block_start is None:
            self._block_start = len(self.data)
            self._block_addr = self._addr
        for item in split_operands(operand):
            if item.startswith('"'):
                for ch in item.strip('"'):
                    self.data.append(ord(ch))
            else:
                v = self.value(item)
                self.data.append(v if isinstance(v, Ref) else v & 0xFF)


HEADER = '''"""Data extracted verbatim from solaris_annotated.asm.

GENERATED BY tools/extract_tables.py -- DO NOT EDIT BY HAND.

DATA    every `.byte` in the assembly, in file order.  Entries are ints, or
        R(name, offset) where the assembly wrote `<LABEL+n` and the value is
        really an address the port resolves to a function or a sprite.
LABELS  label name -> index into DATA.
BLOCKS  (start, end) of each contiguous run of `.byte` directives.
EQU     the EQU constants (PBLK, TOPSCN, ZVIS, ...).
ZP      the zero-page variable addresses from the `ORG $80` map.
"""


class R:
    """A reference to a label: what `<LABEL+offset` meant in the assembly."""

    __slots__ = ("name", "offset")

    def __init__(self, name, offset=0):
        self.name = name
        self.offset = offset

    def __eq__(self, other):
        return (isinstance(other, R) and self.name == other.name
                and self.offset == other.offset)

    def __hash__(self):
        return hash((self.name, self.offset))

    def __repr__(self):
        return f"R({self.name!r}, {self.offset})" if self.offset else f"R({self.name!r})"


def low(entry):
    """The byte a table entry really holds.

    Most entries are already plain bytes; a `<LABEL+n` entry holds the low byte
    of that address, which a few comparisons in the game test directly.
    """
    if isinstance(entry, int):
        return entry
    return (ADDR[entry.name] + entry.offset) & 0xFF


def index_for_addr(addr):
    """The DATA index of a real ROM address, for the few places the game does
    pointer arithmetic in the ROM's own address space -- notably the starfield,
    which reads `(STARS),Y` straight across a page of delta tables."""
    for start, end, base in BLOCKS:
        if base is not None and base <= addr < base + (end - start):
            return start + (addr - base)
    raise KeyError(f"no data block covers ${addr:04X}")


def table(name, count):
    """The `count` bytes starting at `name`, reading past the end if the
    assembly marked the table `;SHARE n` and let it overlap its neighbour."""
    i = LABELS[name]
    return DATA[i:i + count]


class Table:
    """A table addressed the way the 6502 addressed it: an index off a base.

    Several tables are read past their own end on purpose -- `;SHARE n` overlaps,
    and lookups like `LDA BRNT20,Y` where Y can exceed the table's length and
    lands in whatever follows.  Indexing the global DATA stream reproduces that
    exactly, instead of raising or silently clamping.
    """

    __slots__ = ("base", "name")

    def __init__(self, name, offset=0):
        self.name = name
        self.base = LABELS[name] + offset

    def __getitem__(self, i):
        return DATA[self.base + i]

    def __repr__(self):
        return f"Table({self.name!r})"


def tab(name, offset=0):
    """`TABLE` or the fused `TABLE-$40,Y` form -- pass the offset as a negative."""
    return Table(name, offset)


def sprite(name):
    """The sprite rows for a graphic label, TOP ROW FIRST.

    Sprites are stored bottom-row-first and the label sits AFTER its block, so
    the bitmap is the `.byte` run *preceding* the label, reversed, with the
    leading $00 pad (the display kernel's BEQ terminator) dropped.
    """
    rows = []
    i = LABELS[name] - 1
    while i >= 0 and isinstance(DATA[i], int) and DATA[i] != 0:
        rows.append(DATA[i])
        i -= 1
    return rows
'''


def fmt(v):
    return repr(v) if isinstance(v, Ref) else f"0x{v:02X}"


def main():
    text = ASM.read_text(encoding="utf-8", errors="replace")
    first = Extractor(text)
    first.run()
    ex = Extractor(text, known_labels=first.labels)
    ex.run()

    out = [HEADER, "", "DATA = ["]
    for i in range(0, len(ex.data), 8):
        out.append("    " + ", ".join(fmt(v) for v in ex.data[i:i + 8]) + ",")
    out += ["]", ""]

    out.append("LABELS = {")
    out += [f"    {n!r}: {ex.labels[n]}," for n in sorted(ex.labels)]
    out += ["}", ""]

    out.append("# (start index, end index, start address or None)")
    out.append("BLOCKS = [")
    out += [f"    ({a}, {b}, {('0x%04X' % c) if c is not None else None}),"
            for a, b, c in ex.blocks]
    out += ["]", ""]

    out.append("EQU = {")
    out += [f"    {n!r}: {ex.equ[n]}," for n in sorted(ex.equ)]
    out += ["}", ""]

    out.append("# Real ROM addresses, known only for labels inside a contiguous")
    out.append("# `.byte` run after an ORG/RORG.  A handful of comparisons in the game")
    out.append("# are against a label's LOW BYTE (`CMP #<[STARTB+2]`), so those need")
    out.append("# the real address rather than a data index.")
    out.append("ADDR = {")
    out += [f"    {n!r}: 0x{ex.addr[n]:04X}," for n in sorted(ex.addr)]
    out += ["}", ""]

    out.append("ZP = {")
    out += [f"    {n!r}: 0x{ex.zp[n]:02X}," for n in sorted(ex.zp)]
    out += ["}", ""]

    out.append("# `LVS EQU <NEWB50` and friends: the spawn-VM opcode byte is")
    out.append("# literally the low byte of its handler's address.")
    out.append("OPCODE_HANDLERS = {")
    out += [f"    {n!r}: {ex.opcode_refs[n]!r}," for n in sorted(ex.opcode_refs)]
    out += ["}", ""]

    OUT.write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"{len(ex.data)} bytes, {len(ex.labels)} data labels, "
          f"{len(ex.addr)} with known addresses, "
          f"{len(ex.blocks)} blocks, {len(ex.equ)} EQUs, {len(ex.zp)} zero-page vars")
    print(f"-> {OUT}")


if __name__ == "__main__":
    sys.exit(main())
