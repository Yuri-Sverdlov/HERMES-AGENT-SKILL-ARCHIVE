"""Repair broken ToUnicode CMaps in PDFs without OCR: match embedded subset glyph outlines
against the original Google font (Crimson Pro / EB Garamond / Noto Sans), then rewrite
each font's /ToUnicode stream so text extraction returns the true characters."""
import io, os, re, sys, urllib.request
import pymupdf
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont
from fontTools import agl

WORK = os.environ.get("BOOK_WORK_DIR") or os.path.join(os.environ["LOCALAPPDATA"], "hermes", "audio-work")
FONTS = {"CrimsonPro-Regular": ("CrimsonPro-var.ttf", 400),
         "CrimsonPro-Bold": ("CrimsonPro-var.ttf", 700),
         "CrimsonPro-Italic": ("CrimsonPro-Italic-var.ttf", 400),
         "CrimsonPro-BoldItalic": ("CrimsonPro-Italic-var.ttf", 700),
         "EBGaramond": ("EBGaramond-var.ttf", 400),
         "NotoSans": ("NotoSans-var.ttf", 400)}
TOL = 40          # max outline deviation (font units, upem=1024)
WIDTH_TOL = 6     # advance-width tolerance


def outline(tt, name):
    g = tt["glyf"][name]
    try:
        g.expand(tt["glyf"])
    except Exception:
        pass
    c = getattr(g, "coordinates", None)
    pts = [(int(x), int(y)) for x, y in c] if c is not None else []
    return (g.numberOfContours, pts, tt["hmtx"][name][0])


class Orig:
    def __init__(self, fname, wght):
        tt = TTFont(os.path.join(WORK, "fonts", fname))
        self.tt = instantiateVariableFont(tt, {"wght": wght}, inplace=True, updateFontNames=False)
        self.rev = {}
        for cp, gname in (self.tt.getBestCmap() or {}).items():
            self.rev.setdefault(gname, chr(cp))
        self.index = {}
        self.by_width = {}
        for n in self.tt.getGlyphOrder():
            nc, pts, adv = outline(self.tt, n)
            self.index.setdefault((nc, len(pts)), []).append(n)
            self.by_width.setdefault(round(adv / 8), []).append(n)

    def candidates(self, nc, npts, adv):
        cands = self.index.get((nc, npts), [])
        if not cands:
            cands = []
            for (nc2, np2), names in self.index.items():
                if nc2 == nc and abs(np2 - npts) <= 2:
                    cands += names
        wide = [n for n in cands if abs(outline(self.tt, n)[2] - adv) <= WIDTH_TOL]
        if wide:
            return wide
        return [n for n in self.by_width.get(round(adv / 8), []) if outline(self.tt, n)[0] == nc]


_orig_cache = {}
def orig(kind):
    if kind not in _orig_cache:
        _orig_cache[kind] = Orig(*FONTS[kind])
    return _orig_cache[kind]


def kind_of(basefont):
    bf = basefont.split("+")[-1]
    for k in FONTS:
        if bf.startswith(k):
            return k
    return None


def map_font(doc, xref, kind, sub_tt):
    o = orig(kind)
    out, missed = {}, []
    for gid, name in enumerate(sub_tt.getGlyphOrder()):
        nc, pts, adv = outline(sub_tt, name)
        if not pts:                      # empty glyph (space etc.)
            space_adv = None
            for n2 in sub_tt.getGlyphOrder():
                nc2, p2, a2 = outline(sub_tt, n2)
                if not p2 and 200 <= a2 <= 400:
                    space_adv = a2
                    break
            if nc == 0 and space_adv is not None and abs(adv - space_adv) <= 8:
                out[gid] = " "
            else:
                out[gid] = " "
            continue
        best, bd = None, None
        for cn in o.candidates(nc, len(pts), adv):
            op = outline(o.tt, cn)[1]
            d = max(min(abs(x - xo) + abs(y - yo) for xo, yo in op) for x, y in pts)
            if bd is None or d < bd:
                best, bd = cn, d
        if best is not None and bd is not None and bd <= TOL:
            c = o.rev.get(best) or agl.toUnicode(best)
            if c:
                out[gid] = c
            else:
                missed.append((gid, best))
        else:
            missed.append((gid, best))
    return out, missed


def to_cmap(g2c):
    ent = [f"<{c:04X}> <{''.join(f'{ord(ch):04X}' for ch in g2c[c])}>" for c in sorted(g2c) if g2c[c]]
    return ("/CIDInit /ProcSet findresource begin\n12 dict begin\nbegincmap\n"
            "/CIDSystemInfo << /Registry (Adobe) /Ordering (UCS) /Supplement 0 >> def\n"
            "/CMapName /Adobe-Identity-UCS def\n/CMapType 2 def\n"
            "1 begincodespacerange\n<0000> <FFFF>\nendcodespacerange\n"
            f"{len(ent)} beginbfchar\n" + "\n".join(ent) + "\nendbfchar\nendcmap\n"
            "CMapName currentdict /CMap defineresource pop\nend\nend\n").encode("latin-1")


def fix(src, dst):
    doc = pymupdf.open(src)
    seen, stats = set(), []
    for pno in range(doc.page_count):
        for f in doc[pno].get_fonts(full=True):
            xref, basefont = f[0], f[3]
            kind = kind_of(basefont)
            if not kind:
                continue
            key = doc.xref_get_key(xref, "ToUnicode")
            m = re.search(r"(\d+) 0 R", str(key[1]))
            if not m:
                continue
            tu = int(m.group(1))
            if tu in seen:
                continue
            seen.add(tu)
            try:
                sub = TTFont(io.BytesIO(doc.extract_font(xref)[3]), lazy=True)
            except Exception:
                continue
            if "glyf" not in sub:
                continue
            g2c, missed = map_font(doc, xref, kind, sub)
            if len(g2c) < 5:
                continue
            doc.update_stream(tu, to_cmap(g2c))
            stats.append((basefont, kind, len(g2c), len(missed)))
    doc.save(dst, garbage=3, deflate=True)
    doc.close()
    return stats


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit("usage: fix_tounicode.py <src.pdf> [dst.pdf]   (fonts in $BOOK_WORK_DIR/fonts)")
    src = sys.argv[1]
    dst = sys.argv[2] if len(sys.argv) > 2 else src.replace(".pdf", "_fixed.pdf")
    st = fix(src, dst)
    tot = sum(s[2] for s in st)
    miss = sum(s[3] for s in st)
    print(f"{os.path.basename(src)} -> {os.path.basename(dst)}: {len(st)} fonts patched, {tot} glyphs mapped, {miss} unmatched")
