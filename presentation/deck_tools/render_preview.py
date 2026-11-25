"""Minimal PPTX preview renderer (no LibreOffice/PowerPoint here).

Draws backgrounds, rectangles/rounded rectangles/ellipses, lines, pictures and wrapped text with
real Arial metrics, and reports text that overflows its box. Approximate, for QA only.
Usage: python render.py deck.pptx outdir [slide numbers...]
"""
import io
import os
import sys

from PIL import Image, ImageDraw, ImageFont
from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE
from pptx.oxml.ns import qn
from pptx.util import Emu

SCALE = 128  # px per inch
FONT_DIR = r"C:\Windows\Fonts"
_fonts = {}


def font(size_pt, bold=False, mono=False, face="Arial"):
    key = (round(size_pt * 2) / 2, bold, mono, face)
    if key not in _fonts:
        if mono:
            name = "consolab.ttf" if bold else "consola.ttf"
        elif face and face.startswith("Calibri"):
            name = "calibrib.ttf" if bold else "calibri.ttf"
        elif face and "Symbol" in face:
            name = "seguisym.ttf"
        else:
            name = "arialbd.ttf" if bold else "arial.ttf"
        px = max(6, int(size_pt / 72 * SCALE))
        _fonts[key] = ImageFont.truetype(os.path.join(FONT_DIR, name), px)
    return _fonts[key]


def theme_colors(prs):
    master = prs.slide_master
    rel = [r for r in master.part.rels.values() if r.reltype.endswith("/theme")][0]
    from lxml import etree

    root = etree.fromstring(rel.target_part.blob)
    ns = {"a": "http://schemas.openxmlformats.org/drawingml/2006/main"}
    out = {}
    for name in ["dk1", "lt1", "dk2", "lt2", "accent1", "accent2", "accent3", "accent4", "accent5", "accent6"]:
        el = root.find(f".//a:clrScheme/a:{name}", ns)
        c = el[0]
        out[name] = c.get("val") if c.tag.endswith("srgbClr") else c.get("lastClr", "000000")
    out.update({"tx1": out["dk1"], "bg1": out["lt1"], "tx2": out["dk2"], "bg2": out["lt2"]})
    return out


def color_of(el, theme):
    """Colour from an element that contains srgbClr/schemeClr; None if none."""
    if el is None:
        return None
    for c in el.iter():
        if c.tag == qn("a:srgbClr"):
            return "#" + c.get("val")
        if c.tag == qn("a:schemeClr"):
            return "#" + theme.get(c.get("val"), "000000")
    return None


def px(emu):
    return int(Emu(emu).inches * SCALE)


def wrap(draw, text, fnt, width):
    lines = []
    for para in text.split("\n"):
        words = para.split(" ")
        cur = ""
        for w in words:
            trial = (cur + " " + w) if cur else w
            if draw.textlength(trial, font=fnt) <= width or not cur:
                cur = trial
            else:
                lines.append(cur)
                cur = w
        lines.append(cur)
    return lines


def render(path, outdir, only=None):
    prs = Presentation(path)
    theme = theme_colors(prs)
    W, H = px(prs.slide_width), px(prs.slide_height)
    os.makedirs(outdir, exist_ok=True)
    problems = []
    for idx, slide in enumerate(prs.slides, 1):
        if only and idx not in only:
            continue
        img = Image.new("RGB", (W, H), "white")
        bg = slide._element.find(qn("p:cSld")).find(qn("p:bg"))
        c = color_of(bg, theme) if bg is not None else None
        if c:
            img.paste(c, (0, 0, W, H))
        d = ImageDraw.Draw(img)

        def draw_shape(sh, ox=0, oy=0):
            if sh.shape_type == MSO_SHAPE_TYPE.GROUP:
                for s in sh.shapes:
                    draw_shape(s)
                return
            x, y = px(sh.left or 0), px(sh.top or 0)
            w, h = px(sh.width or 0), px(sh.height or 0)
            if getattr(sh, "has_chart", False) and sh.has_chart:
                d.rectangle([x, y, x + w, y + h], outline="#BBBBBB")
                ch = sh.chart
                vals = list(ch.plots[0].series[0].values)
                cats = list(ch.plots[0].categories)
                mx = ch.value_axis.maximum_scale or max(vals)
                bw = w / (len(vals) * 1.6)
                for i, v in enumerate(vals):
                    bx = x + (i + 0.3) * w / len(vals)
                    bh = (h - 60) * v / mx
                    d.rectangle([bx, y + h - 30 - bh, bx + bw, y + h - 30], fill="#555555")
                    d.text((bx, y + h - 26), str(cats[i]), font=font(9), fill="#333333")
                    d.text((bx, y + h - 46 - bh), f"{v:.3f}", font=font(9, True), fill="#333333")
                d.text((x + 8, y + 6), "chart", font=font(9), fill="#999999")
                return
            if getattr(sh, "has_table", False) and sh.has_table:
                t = sh.table
                cy = y
                for r, row in enumerate(t.rows):
                    rh = px(row.height)
                    cx = x
                    for c, col in enumerate(t.columns):
                        cw = px(col.width)
                        cell = t.cell(r, c)
                        tcPr = cell._tc.tcPr
                        f = color_of(tcPr.find(qn("a:solidFill")), theme) if tcPr is not None and tcPr.find(qn("a:solidFill")) is not None else None
                        d.rectangle([cx, cy, cx + cw, cy + rh], fill=f, outline="#CCCCCC")
                        para = cell.text_frame.paragraphs[0]
                        r0 = para.runs[0] if para.runs else None
                        size = r0.font.size.pt if r0 is not None and r0.font.size else 12
                        fnt = font(size, bool(r0 is not None and r0.font.bold), False, (r0.font.name if r0 is not None else None) or "Arial")
                        col_ = "#FFFFFF" if f in ("#000000",) else "#3A3242"
                        lines = wrap(d, cell.text_frame.text, fnt, cw - 16)
                        lh = int(size / 72 * SCALE * 1.2)
                        if lh * len(lines) > rh + 2:
                            problems.append(f"slide {idx}: table cell r{r}c{c} overflows: {cell.text_frame.text[:40]!r}")
                        ty = cy + (rh - lh * len(lines)) / 2
                        for line in lines:
                            d.text((cx + 8, ty), line, font=fnt, fill=col_)
                            ty += lh
                        cx += cw
                    cy += rh
                return
            spPr = sh._element.find(qn("p:spPr"))
            if sh.shape_type == MSO_SHAPE_TYPE.PICTURE:
                try:
                    im = Image.open(io.BytesIO(sh.image.blob)).convert("RGBA").resize((max(w, 1), max(h, 1)))
                    img.paste(im, (x, y), im)
                except Exception:
                    d.rectangle([x, y, x + w, y + h], outline="red")
                return
            geom = "rect"
            fill = line = None
            if spPr is not None:
                pg = spPr.find(qn("a:prstGeom"))
                if pg is not None:
                    geom = pg.get("prst")
                sf = spPr.find(qn("a:solidFill"))
                fill = color_of(sf, theme) if sf is not None else None
                ln = spPr.find(qn("a:ln"))
                if ln is not None and ln.find(qn("a:noFill")) is None:
                    line = color_of(ln.find(qn("a:solidFill")), theme)
            if sh.shape_type == MSO_SHAPE_TYPE.LINE or geom in ("line", "straightConnector1"):
                d.line([x, y, x + w, y + h], fill=line or "#888888", width=2)
                return
            box = [x, y, x + max(w, 1), y + max(h, 1)]
            if fill or line:
                if geom in ("ellipse",):
                    d.ellipse(box, fill=fill, outline=line)
                elif geom in ("roundRect",):
                    d.rounded_rectangle(box, radius=min(w, h) // 6, fill=fill, outline=line)
                else:
                    d.rectangle(box, fill=fill, outline=line)
            if sh.has_text_frame and sh.text_frame.text.strip():
                draw_text(sh, x, y, w, h)

        def draw_text(sh, x, y, w, h):
            tf = sh.text_frame
            body = tf._txBody.find(qn("a:bodyPr"))
            ins = {k: int(body.get(k, d_)) for k, d_ in (("lIns", 91440), ("rIns", 91440), ("tIns", 45720), ("bIns", 45720))}
            anchor = body.get("anchor", "t")
            ix, iy = x + px(ins["lIns"]), y + px(ins["tIns"])
            iw, ih = w - px(ins["lIns"]) - px(ins["rIns"]), h - px(ins["tIns"]) - px(ins["bIns"])
            blocks = []
            for p in tf.paragraphs:
                text = "".join(r.text for r in p.runs) or ""
                r0 = p.runs[0] if p.runs else None
                size = (r0.font.size.pt if r0 is not None and r0.font.size else 18)
                bold = bool(r0 is not None and r0.font.bold)
                mono = bool(r0 is not None and r0.font.name and ("Consolas" in r0.font.name or "Courier" in r0.font.name))
                col = None
                if r0 is not None:
                    rpr = r0._r.find(qn("a:rPr"))
                    col = color_of(rpr.find(qn("a:solidFill")) if rpr is not None else None, theme)
                pPr = p._p.find(qn("a:pPr"))
                bullet = pPr is not None and pPr.find(qn("a:buChar")) is not None
                algn = (pPr.get("algn") if pPr is not None else None) or "l"
                spc = 0
                if pPr is not None and pPr.find(qn("a:spcAft")) is not None:
                    s = pPr.find(qn("a:spcAft")).find(qn("a:spcPts"))
                    spc = int(s.get("val")) / 100 if s is not None else 0
                face = r0.font.name if r0 is not None and r0.font.name else "Arial"
                blocks.append((text, size, bold, mono, col or "#000000", bullet, algn, spc, face))
            laid = []
            total = 0
            for text, size, bold, mono, col, bullet, algn, spc, face in blocks:
                f = font(size, bold, mono, face)
                indent = int(0.18 * SCALE) if bullet else 0
                lines = wrap(d, text, f, iw - indent) if text else [""]
                lh = int(size / 72 * SCALE * 1.2)
                laid.append((lines, f, col, lh, bullet, indent, algn, int(spc / 72 * SCALE)))
                total += lh * len(lines) + int(spc / 72 * SCALE)
            cy = iy if anchor == "t" else (iy + (ih - total) // 2 if anchor == "ctr" else iy + ih - total)
            if total > ih + 2:
                problems.append(f"slide {idx}: text overflows '{sh.name}' by {(total - ih) / SCALE:.2f}in: {tf.text[:50]!r}")
            for lines, f, col, lh, bullet, indent, algn, spc in laid:
                for li, line in enumerate(lines):
                    tw = d.textlength(line, font=f)
                    lx = ix + indent
                    if algn == "ctr":
                        lx = ix + (iw - tw) / 2
                    elif algn == "r":
                        lx = ix + iw - tw
                    if bullet and li == 0:
                        d.text((ix + 2, cy), "•", font=f, fill=col)
                    d.text((lx, cy), line, font=f, fill=col)
                    cy += lh
                cy += spc

        for sh in slide.shapes:
            draw_shape(sh)
            # off-slide check
            if sh.left is not None and (sh.left + sh.width > prs.slide_width + 9144 or sh.top + sh.height > prs.slide_height + 9144):
                problems.append(f"slide {idx}: '{sh.name}' runs off the slide")
        img.save(os.path.join(outdir, f"s{idx:02d}.png"))
    return problems


if __name__ == "__main__":
    only = [int(a) for a in sys.argv[3:]] or None
    for p in render(sys.argv[1], sys.argv[2], only):
        print(p)
    print("rendered")
