"""KiCad schematic generator library.

Extracts symbol definitions from the stock KiCad symbol libraries and emits
KiCad 8-format .kicad_sch files (readable by KiCad 9/10) with symbols placed
and connected via global labels / power symbols placed at pin endpoints.
"""
import os
import re
import sys
import uuid as uuidlib

KICAD_SYMBOL_DIR = r"C:\Program Files\KiCad\10.0\share\kicad\symbols"


def new_uuid():
    return str(uuidlib.uuid4())


# ---------------------------------------------------------------- s-expr utils

def extract_top_blocks(text, keyword):
    """Yield (name, block_text) for every top-level '(keyword "name"' block."""
    out = []
    i = 0
    pat = re.compile(r'\(\s*' + keyword + r'\s+"((?:[^"\\]|\\.)*)"')
    while True:
        m = pat.search(text, i)
        if not m:
            break
        start = m.start()
        depth = 0
        j = start
        in_str = False
        while j < len(text):
            c = text[j]
            if in_str:
                if c == '\\':
                    j += 2
                    continue
                if c == '"':
                    in_str = False
            else:
                if c == '"':
                    in_str = True
                elif c == '(':
                    depth += 1
                elif c == ')':
                    depth -= 1
                    if depth == 0:
                        j += 1
                        break
            j += 1
        out.append((m.group(1), text[start:j]))
        i = j
    return out


class SExpr:
    """Minimal s-expression parser producing nested lists of str/atoms."""

    @staticmethod
    def parse(text):
        tokens = SExpr._tokenize(text)
        pos = [0]

        def read():
            tok = tokens[pos[0]]
            pos[0] += 1
            if tok == '(':
                lst = []
                while tokens[pos[0]] != ')':
                    lst.append(read())
                pos[0] += 1
                return lst
            return tok

        return read()

    @staticmethod
    def _tokenize(text):
        toks = []
        i = 0
        n = len(text)
        while i < n:
            c = text[i]
            if c in ' \t\r\n':
                i += 1
            elif c in '()':
                toks.append(c)
                i += 1
            elif c == '"':
                j = i + 1
                buf = []
                while j < n:
                    if text[j] == '\\':
                        buf.append(text[j:j + 2])
                        j += 2
                    elif text[j] == '"':
                        break
                    else:
                        buf.append(text[j])
                        j += 1
                toks.append('"' + ''.join(buf) + '"')
                i = j + 1
            else:
                j = i
                while j < n and text[j] not in ' \t\r\n()':
                    j += 1
                toks.append(text[i:j])
                i = j
        return toks


def unquote(tok):
    if tok.startswith('"') and tok.endswith('"'):
        return tok[1:-1]
    return tok


# ------------------------------------------------------------- symbol library

class Symbol:
    def __init__(self, lib, name, block):
        self.lib = lib          # e.g. "Device"
        self.name = name        # e.g. "R"
        self.block = block      # raw s-expr text of (symbol "name" ...)
        self.pins = []          # list of dicts: number, name, x, y, angle
        self._parse_pins()

    @property
    def lib_id(self):
        return f"{self.lib}:{self.name}"

    def _parse_pins(self):
        tree = SExpr.parse(self.block)
        # walk sub-symbols (units)
        for node in tree:
            if isinstance(node, list) and node and node[0] == 'symbol':
                for sub in node:
                    if isinstance(sub, list) and sub and sub[0] == 'pin':
                        self._add_pin(sub)

    def _add_pin(self, pin):
        info = {'etype': unquote(pin[1]) if len(pin) > 1 else 'passive'}
        for item in pin:
            if isinstance(item, list):
                if item[0] == 'at':
                    info['x'] = float(item[1])
                    info['y'] = float(item[2])
                    info['angle'] = float(item[3]) if len(item) > 3 else 0.0
                elif item[0] == 'name':
                    info['name'] = unquote(item[1])
                elif item[0] == 'number':
                    info['number'] = unquote(item[1])
        self.pins.append(info)


class SymbolLibrary:
    """Loads and caches symbols from stock libraries; resolves 'extends'."""

    def __init__(self, symdir=KICAD_SYMBOL_DIR):
        self.symdir = symdir
        self._filecache = {}
        self._cache = {}

    def _lib_text(self, lib):
        if lib not in self._filecache:
            path = os.path.join(self.symdir, lib + '.kicad_sym')
            with open(path, encoding='utf-8') as f:
                self._filecache[lib] = f.read()
        return self._filecache[lib]

    def _raw_block(self, lib, name):
        text = self._lib_text(lib)
        for nm, block in extract_top_blocks(text, 'symbol'):
            if nm == name:
                return block
        raise KeyError(f"{lib}:{name} not found")

    def get(self, lib, name):
        key = (lib, name)
        if key in self._cache:
            return self._cache[key]
        block = self._raw_block(lib, name)
        m = re.search(r'\(extends\s+"([^"]+)"\)', block)
        if m:
            block = self._flatten_derived(lib, name, block, m.group(1))
        sym = Symbol(lib, name, block)
        self._cache[key] = sym
        return sym

    def _flatten_derived(self, lib, name, child_block, parent_name):
        parent = self.get(lib, parent_name)
        pblock = parent.block
        # rename parent -> child (header and unit names)
        pblock = pblock.replace(f'"{parent_name}"', f'"{name}"', 1)
        pblock = re.sub(r'\(symbol\s+"' + re.escape(parent_name) + r'(_\d+_\d+)"',
                        lambda m2: f'(symbol "{name}{m2.group(1)}"', pblock)
        # override properties from the child block
        child_props = {}
        for prop in re.finditer(
                r'\(property\s+"([^"]+)"\s+"((?:[^"\\]|\\.)*)"', child_block):
            child_props[prop.group(1)] = prop.group(2)

        def repl_prop(m2):
            pname = m2.group(1)
            if pname in child_props:
                return f'(property "{pname}" "{child_props[pname]}"'
            return m2.group(0)

        pblock = re.sub(r'\(property\s+"([^"]+)"\s+"((?:[^"\\]|\\.)*)"',
                        repl_prop, pblock)
        return pblock


# ------------------------------------------------------------------ placement

def pin_endpoint(sym, part_x, part_y, pin):
    """Schematic coords of a pin's connection point, rotation 0 placement."""
    return (round(part_x + pin['x'], 4), round(part_y - pin['y'], 4))


def label_angle(pin_angle):
    """Angle for a label/stub pointing away from the symbol body.

    Screen convention: 0 = right, 90 = up, 180 = left, 270 = down.
    The symbol-space y-flip cancels against the pin-angle convention,
    leaving a simple 180-degree flip.
    """
    return (pin_angle + 180.0) % 360.0


# ------------------------------------------------------------------ emit

def fmt(v):
    s = f"{v:.4f}".rstrip('0').rstrip('.')
    return s if s else '0'


class Part:
    def __init__(self, ref, lib, name, value, x, y, pinmap, footprint="",
                 value_offset=(0, -2.54), ref_offset=(0, 2.54), fields=None):
        self.ref = ref
        self.lib = lib
        self.name = name
        self.value = value
        # snap to the 1.27mm (50 mil) connection grid
        self.x = round(round(x / 1.27) * 1.27, 4)
        self.y = round(round(y / 1.27) * 1.27, 4)
        self.pinmap = pinmap or {}   # key: pin number OR pin name -> net
        self.footprint = footprint
        self.value_offset = value_offset
        self.ref_offset = ref_offset
        self.fields = fields or {}


class Sheet:
    def __init__(self, filename, title, project):
        self.filename = filename
        self.title = title
        self.project = project
        self.uuid = new_uuid()
        self.parts = []            # Part objects
        self.power = []            # (libname, net_display, x, y, angle)
        self.labels = []           # (net, x, y, angle)
        self.no_connects = []      # (x, y)
        self.wires = []            # (x1,y1,x2,y2)
        self.texts = []            # (text, x, y, size)
        self.junctions = []        # (x, y)

    def add(self, part):
        self.parts.append(part)


POWER_SYMS = {}  # populated lazily: name -> block


def power_block(libdb, name):
    if name not in POWER_SYMS:
        POWER_SYMS[name] = libdb.get('power', name)
    return POWER_SYMS[name]


def render_sheet(sheet, libdb, root_uuid, sheet_inst_uuid, page):
    """Return .kicad_sch text for a child sheet."""
    used = {}
    for p in sheet.parts:
        sym = libdb.get(p.lib, p.name)
        used[sym.lib_id] = sym
    for entry in sheet.power:
        sym = power_block(libdb, entry[0])
        used[sym.lib_id] = sym

    out = []
    out.append('(kicad_sch (version 20231120) (generator "dronemagnav_gen")')
    out.append(f'  (uuid "{sheet.uuid}")')
    out.append('  (paper "A3")')
    out.append('  (title_block')
    out.append(f'    (title "{sheet.title}")')
    out.append('    (company "DroneMagNav Project")')
    out.append('    (rev "A")')
    out.append('  )')
    out.append('  (lib_symbols')
    for lib_id, sym in sorted(used.items()):
        block = sym.block
        # ensure the embedded name is the full lib_id
        block = block.replace(f'(symbol "{sym.name}"',
                              f'(symbol "{sym.lib_id}"', 1)
        out.append('    ' + block)
    out.append('  )')

    for (x, y) in sheet.junctions:
        out.append(f'  (junction (at {fmt(x)} {fmt(y)}) (diameter 0) '
                   f'(color 0 0 0 0) (uuid "{new_uuid()}"))')
    for (x1, y1, x2, y2) in sheet.wires:
        out.append(f'  (wire (pts (xy {fmt(x1)} {fmt(y1)}) (xy {fmt(x2)} {fmt(y2)}))'
                   f' (stroke (width 0) (type default)) (uuid "{new_uuid()}"))')
    for (x, y) in sheet.no_connects:
        out.append(f'  (no_connect (at {fmt(x)} {fmt(y)}) (uuid "{new_uuid()}"))')
    for (net, x, y, ang) in sheet.labels:
        out.append(
            f'  (global_label "{net}" (shape input) '
            f'(at {fmt(x)} {fmt(y)} {fmt(ang)}) (fields_autoplaced yes)\n'
            f'    (effects (font (size 1.27 1.27)) '
            f'(justify {"right" if ang in (180.0, 270.0) else "left"}))\n'
            f'    (uuid "{new_uuid()}")\n'
            f'    (property "Intersheetrefs" "${{INTERSHEET_REFS}}" '
            f'(at {fmt(x)} {fmt(y)} 0) '
            f'(effects (font (size 1.27 1.27)) (hide yes)))\n  )')
    for (text, x, y, size) in sheet.texts:
        out.append(f'  (text "{text}" (exclude_from_sim no) (at {fmt(x)} {fmt(y)} 0)'
                   f' (effects (font (size {size} {size})) (justify left bottom))'
                   f' (uuid "{new_uuid()}"))')

    path = f"/{root_uuid}/{sheet_inst_uuid}"

    # power symbols
    pcount = 0
    for (pname, x, y, ang) in sheet.power:
        pcount += 1
        sym = power_block(libdb, pname)
        ref = f"#PWR{page}{pcount:03d}"
        out.append(f'''  (symbol (lib_id "power:{pname}") (at {fmt(x)} {fmt(y)} {fmt(ang)}) (unit 1)
    (exclude_from_sim no) (in_bom yes) (on_board yes) (dnp no)
    (uuid "{new_uuid()}")
    (property "Reference" "{ref}" (at {fmt(x)} {fmt(y + 5)} 0) (effects (font (size 1.27 1.27)) (hide yes)))
    (property "Value" "{pname}" (at {fmt(x)} {fmt(y + 3.5 if ang == 0 else y - 3.5)} 0) (effects (font (size 1.27 1.27))))
    (property "Footprint" "" (at {fmt(x)} {fmt(y)} 0) (effects (font (size 1.27 1.27)) (hide yes)))
    (property "Datasheet" "" (at {fmt(x)} {fmt(y)} 0) (effects (font (size 1.27 1.27)) (hide yes)))
    (pin "1" (uuid "{new_uuid()}"))
    (instances (project "{sheet.project}" (path "{path}" (reference "{ref}") (unit 1))))
  )''')

    for p in sheet.parts:
        sym = libdb.get(p.lib, p.name)
        pins_out = []
        for pin in sym.pins:
            pins_out.append(f'    (pin "{pin["number"]}" (uuid "{new_uuid()}"))')
        rx, ry = p.x + p.ref_offset[0], p.y + p.ref_offset[1]
        vx, vy = p.x + p.value_offset[0], p.y + p.value_offset[1]
        extra = []
        for fname, fval in p.fields.items():
            extra.append(f'    (property "{fname}" "{fval}" (at {fmt(p.x)} {fmt(p.y)} 0) '
                         f'(effects (font (size 1.27 1.27)) (hide yes)))')
        out.append(f'''  (symbol (lib_id "{sym.lib_id}") (at {fmt(p.x)} {fmt(p.y)} 0) (unit 1)
    (exclude_from_sim no) (in_bom yes) (on_board yes) (dnp no)
    (uuid "{new_uuid()}")
    (property "Reference" "{p.ref}" (at {fmt(rx)} {fmt(ry)} 0) (effects (font (size 1.27 1.27))))
    (property "Value" "{p.value}" (at {fmt(vx)} {fmt(vy)} 0) (effects (font (size 1.27 1.27))))
    (property "Footprint" "{p.footprint}" (at {fmt(p.x)} {fmt(p.y)} 0) (effects (font (size 1.27 1.27)) (hide yes)))
    (property "Datasheet" "" (at {fmt(p.x)} {fmt(p.y)} 0) (effects (font (size 1.27 1.27)) (hide yes)))
{chr(10).join(extra) if extra else ''}
{chr(10).join(pins_out)}
    (instances (project "{sheet.project}" (path "{path}" (reference "{p.ref}") (unit 1))))
  )''')

    out.append(')')
    return '\n'.join(out)


def connect_part(sheet, libdb, part, nc_rest=False):
    """Resolve part.pinmap into labels / power symbols / no-connects.

    pinmap values:
      "~NET"      -> global label NET
      "#GND" etc  -> power symbol (name after #)
      "NC"        -> explicit no-connect
    keys match pin number first, then pin name (name matches ALL pins
    sharing that name, e.g. VDD).
    """
    sym = libdb.get(part.lib, part.name)
    handled = set()
    for pin in sym.pins:
        key = None
        if pin['number'] in part.pinmap:
            key = pin['number']
        elif pin.get('name') in part.pinmap:
            key = pin['name']
        ex, ey = pin_endpoint(sym, part.x, part.y, pin)
        if key is None:
            if nc_rest:
                sheet.no_connects.append((ex, ey))
            continue
        handled.add(key)
        val = part.pinmap[key]
        if val == 'NC':
            sheet.no_connects.append((ex, ey))
        elif val.startswith('#'):
            pname = val[1:]
            ang = 0.0
            # power symbol pin points up (GND-style) or down; the power pin
            # sits at the power symbol origin, so just place at endpoint.
            sheet.power.append((pname, ex, ey, ang))
        else:
            # draw a visible wire stub from the pin, put the net label at
            # its far end (angle: away from the symbol body)
            ang = label_angle((pin.get('angle', 0.0)))
            stub = 5.08
            dx = {0.0: stub, 180.0: -stub}.get(ang, 0.0)
            dy = {90.0: -stub, 270.0: stub}.get(ang, 0.0)
            sx = round(ex + dx, 4)
            sy = round(ey + dy, 4)
            sheet.wires.append((ex, ey, sx, sy))
            sheet.labels.append((val, sx, sy, ang))
    missing = set(part.pinmap) - handled
    if missing:
        raise KeyError(f"{part.ref}: pins not found: {missing}")


def inspect(libdb, lib, name):
    sym = libdb.get(lib, name)
    print(f"== {lib}:{name}  ({len(sym.pins)} pins)")
    for p in sorted(sym.pins, key=lambda q: (len(q['number']), q['number'])):
        print(f"  {p['number']:>4}  {p.get('name', '?'):<24} at ({p['x']}, {p['y']}) ang {p['angle']} {p['etype']}")


if __name__ == '__main__':
    db = SymbolLibrary()
    for spec in sys.argv[1:]:
        lib, name = spec.split(':', 1)
        inspect(db, lib, name)
