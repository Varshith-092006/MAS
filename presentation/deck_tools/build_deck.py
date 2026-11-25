"""2nd-review deck, redesigned: white-first, black accents, Calibri.
Same headings and order as the template-based version. Content fact-checked against the code
and results.csv (see DECISIONS / chat for the eight corrections)."""
import os
import sys

from lxml import etree
from PIL import Image, ImageChops
from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE, XL_LABEL_POSITION
from pptx.enum.dml import MSO_LINE_DASH_STYLE
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Emu, Inches, Pt

OUT, SHOTS, WORK = sys.argv[1], sys.argv[2], sys.argv[3]

INK, BODY, MUTED, LINE, PANEL, BLACK, WHITE = "111111", "3A3A3A", "8A8A8A", "D6D6D6", "F3F3F3", "000000", "FFFFFF"
MID = "6E6E6E"
FONT = "Calibri"
X0, CW = 0.55, 8.9  # left margin, content width
FOOTER = "AI Software Engineering Team  ·  Batch 20"

prs = Presentation()
prs.slide_width, prs.slide_height = Inches(10), Inches(5.625)
BLANK = prs.slide_layouts[6]


def rgb(h):
    return RGBColor.from_string(h)


# ------------------------------------------------------------------ text
def _bullet(p, on):
    pPr = p._p.get_or_add_pPr()
    for tag in ("a:buNone", "a:buChar", "a:buFont"):
        for el in pPr.findall(qn(tag)):
            pPr.remove(el)
    if on:
        pPr.set("marL", "171450")
        pPr.set("indent", "-171450")
        bf = etree.SubElement(pPr, qn("a:buFont"))
        bf.set("typeface", "Arial")
        bc = etree.SubElement(pPr, qn("a:buChar"))
        bc.set("char", "•")
    else:
        etree.SubElement(pPr, qn("a:buNone"))


def fill_tf(tf, paras, size=12, color=BODY, bold=False, align="l", font=FONT, bullets=False, space=4, spacing=None):
    tf.clear()
    tf.word_wrap = True
    for i, para in enumerate(paras):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        if isinstance(para, tuple):
            runs, po = [para], para[1]
        elif isinstance(para, list):
            runs, po = para, {}
        else:
            runs, po = [(para, {})], {}
        p.alignment = {"l": PP_ALIGN.LEFT, "c": PP_ALIGN.CENTER, "r": PP_ALIGN.RIGHT}[po.get("align", align)]
        p.space_after = Pt(po.get("space", space))
        _bullet(p, po.get("bullet", bullets))
        for text, o in runs:
            r = p.add_run()
            r.text = text
            f = r.font
            f.name = o.get("font", font)
            f.size = Pt(o.get("size", size))
            f.bold = o.get("bold", bold)
            f.italic = o.get("italic", False)
            f.color.rgb = rgb(o.get("color", color))
            sp = o.get("spacing", spacing)
            if sp:
                r._r.get_or_add_rPr().set("spc", str(int(sp * 100)))


def _frame(sh, anchor, inset_x=0.1, inset_y=0.06):
    tf = sh.text_frame
    tf.margin_left = tf.margin_right = Inches(inset_x)
    tf.margin_top = tf.margin_bottom = Inches(inset_y)
    tf.vertical_anchor = {"t": MSO_ANCHOR.TOP, "m": MSO_ANCHOR.MIDDLE, "b": MSO_ANCHOR.BOTTOM}[anchor]
    return tf


def tb(slide, x, y, w, h, paras, anchor="t", inset=0.0, **kw):
    sh = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    fill_tf(_frame(sh, anchor, inset, 0.02), paras if isinstance(paras, list) else [paras], **kw)
    return sh


def shape(slide, x, y, w, h, fill=None, line=None, kind=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.08, text=None,
          anchor="m", inset=0.12, line_w=1.0, dash=False, **kw):
    sh = slide.shapes.add_shape(kind, Inches(x), Inches(y), Inches(w), Inches(h))
    if kind == MSO_SHAPE.ROUNDED_RECTANGLE:
        sh.adjustments[0] = radius
    if fill:
        sh.fill.solid()
        sh.fill.fore_color.rgb = rgb(fill)
    else:
        sh.fill.background()
    if line:
        sh.line.color.rgb = rgb(line)
        sh.line.width = Pt(line_w)
        if dash:
            sh.line.dash_style = MSO_LINE_DASH_STYLE.DASH
    else:
        sh.line.fill.background()
    sh.shadow.inherit = False
    tf = _frame(sh, anchor, inset, min(0.06, h * 0.08))
    if text is not None:
        fill_tf(tf, text if isinstance(text, list) else [text], **kw)
    return sh


def line(slide, x1, y1, x2, y2, color=INK, width=1.0, head=True, dash=False):
    c = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Inches(x1), Inches(y1), Inches(x2), Inches(y2))
    c.line.color.rgb = rgb(color)
    c.line.width = Pt(width)
    if dash:
        c.line.dash_style = MSO_LINE_DASH_STYLE.DASH
    if head:
        t = etree.SubElement(c.line._get_or_add_ln(), qn("a:tailEnd"))
        t.set("type", "triangle")
        t.set("w", "med")
        t.set("len", "med")
    return c


# ------------------------------------------------------------------ components
def slide(kicker, title, notes=None):
    s = prs.slides.add_slide(BLANK)
    s.background.fill.solid()
    s.background.fill.fore_color.rgb = rgb(WHITE)
    tb(s, X0, 0.32, CW, 0.26, [(kicker.upper(), {"bold": True, "spacing": 1.5})], size=9, color=MUTED)
    tb(s, X0, 0.55, CW, 0.6, [(title, {"bold": True})], size=24, color=INK)
    n = len(prs.slides)
    tb(s, X0, 5.2, 6, 0.25, FOOTER, size=8, color=MUTED)
    tb(s, 8.45, 5.2, 1.0, 0.25, str(n), size=9, color=MUTED, align="r")
    if notes:
        s.notes_slide.notes_text_frame.text = notes
    return s


def num_badge(s, x, y, n, d=0.36, fill=BLACK, color=WHITE, size=11):
    return shape(s, x, y, d, d, fill=fill, kind=MSO_SHAPE.OVAL, text=[(f"{n:02d}" if isinstance(n, int) else n, {"bold": True})],
                 size=size, color=color, align="c", inset=0)


def card(s, x, y, w, h, title, body, n=None, sub=None, size=11.5, tag=None, title_size=13.5):
    shape(s, x, y, w, h, fill=PANEL, radius=0.05)
    ty = y + 0.16
    tx = x + 0.18
    if n is not None:
        num_badge(s, tx, ty, n)
        ty += 0.48
    if tag:
        llm = tag == "LLM"
        shape(s, x + w - 0.95, y + 0.16, 0.78, 0.26, fill=BLACK if llm else WHITE, line=None if llm else INK, radius=0.5,
              text=[(tag, {"bold": True})], size=8.5, color=WHITE if llm else INK, align="c", inset=0)
    paras = [(title, {"bold": True, "size": title_size, "color": INK, "space": 2})]
    if sub:
        paras.append((sub, {"size": 10, "color": MUTED, "space": 6}))
    tb(s, tx, ty, w - 0.36 - (0.85 if tag and n is None else 0), 0.62 if sub else 0.42, paras, size=title_size)
    body_y = ty + (0.66 if sub else 0.42)
    items = body if isinstance(body, list) else [body]
    tb(s, tx, body_y, w - 0.36, y + h - body_y - 0.12, items, size=size, color=BODY, space=4)


def node(s, x, y, w, h, title, sub=None, llm=True, size=11, emphasis=False):
    paras = [(title, {"bold": True})]
    if sub:
        paras.append((sub, {"size": 8.5, "bold": False}))
    if llm:
        return shape(s, x, y, w, h, fill=BLACK, radius=0.18, text=paras, size=size, color=WHITE, align="c", space=0, inset=0.06)
    return shape(s, x, y, w, h, fill=WHITE, line=INK, line_w=2.0 if emphasis else 1.0, radius=0.18, text=paras, size=size,
                 color=INK, align="c", space=0, inset=0.06)


def callout(s, x, y, w, h, paras, size=13, fill=BLACK, color=WHITE, align="l"):
    return shape(s, x, y, w, h, fill=fill, radius=0.12, text=paras if isinstance(paras, list) else [paras],
                 size=size, color=color, bold=True, align=align, inset=0.2)


def panel(s, x, y, w, h, paras, size=11.5, anchor="m", **kw):
    return shape(s, x, y, w, h, fill=PANEL, radius=0.08, text=paras if isinstance(paras, list) else [paras],
                 size=size, color=BODY, anchor=anchor, inset=0.2, **kw)


def legend(s, x, y):
    shape(s, x, y + 0.03, 0.26, 0.18, fill=BLACK, radius=0.3)
    tb(s, x + 0.33, y, 1.4, 0.25, "Calls the LLM", size=9.5, color=MID)
    shape(s, x + 1.55, y + 0.03, 0.26, 0.18, fill=WHITE, line=INK, radius=0.3)
    tb(s, x + 1.88, y, 1.6, 0.25, "Deterministic code", size=9.5, color=MID)


def bullets(items, **o):
    return [(t, dict({"bullet": True}, **o)) for t in items]


def table(s, x, y, col_w, rows, size=11, row_h=0.32, first_bold=True):
    t = s.shapes.add_table(len(rows), len(rows[0]), Inches(x), Inches(y), Inches(sum(col_w)), Inches(row_h * len(rows))).table
    tblPr = t._tbl.tblPr
    tblPr.set("bandRow", "0")
    tblPr.set("firstRow", "0")
    sid = tblPr.find(qn("a:tableStyleId"))
    if sid is not None:
        sid.text = "{5940675A-B579-460E-94D1-54222C63F5DA}"
    for i, w in enumerate(col_w):
        t.columns[i].width = Inches(w)
    for r, row in enumerate(rows):
        t.rows[r].height = Inches(row_h)
        for c, val in enumerate(row):
            cell = t.cell(r, c)
            cell.margin_left = cell.margin_right = Inches(0.08)
            cell.margin_top = cell.margin_bottom = Inches(0.02)
            cell.vertical_anchor = MSO_ANCHOR.MIDDLE
            cell.fill.solid()
            cell.fill.fore_color.rgb = rgb(BLACK if r == 0 else (PANEL if r % 2 == 0 else WHITE))
            fill_tf(cell.text_frame, [val], size=size, bold=(r == 0) or (first_bold and c == 0),
                    color=WHITE if r == 0 else (INK if c == 0 else BODY), space=0)
    return t


def crop_shot(path):
    im = Image.open(path).convert("RGB")
    im = im.crop((256, 0, im.width, im.height))
    bg = Image.new("RGB", im.size, im.getpixel((im.width - 5, im.height - 5)))
    b = ImageChops.difference(im, bg).getbbox()
    if b:
        im = im.crop((max(0, b[0] - 16), max(0, b[1] - 12), min(im.width, b[2] + 16), min(im.height, b[3] + 12)))
    out = os.path.join(WORK, "c2_" + os.path.basename(path))
    im.save(out)
    return out


def shot(s, name, x, y, w, max_h, caption):
    path = crop_shot(os.path.join(SHOTS, name))
    iw, ih = Image.open(path).size
    w2, x2 = w, x
    if w * ih / iw > max_h:
        w2 = max_h * iw / ih
        x2 = x + (w - w2) / 2
    pic = s.shapes.add_picture(path, Inches(x2), Inches(y), width=Inches(w2))
    pic.line.color.rgb = rgb(LINE)
    pic.line.width = Pt(0.75)
    tb(s, x, y + max_h + 0.06, w, 0.26, caption, size=10, color=MUTED)


# ================================================================== 1 Title
s = prs.slides.add_slide(BLANK)
s.background.fill.solid()
s.background.fill.fore_color.rgb = rgb(WHITE)
s.shapes.add_picture(os.path.join(WORK, "brain_bw_crop.png"), Inches(5.95), Inches(0), width=Inches(4.05), height=Inches(5.625))
tb(s, X0, 0.6, 5.2, 0.3, [("FINAL YEAR PROJECT  ·  2ND REVIEW", {"bold": True, "spacing": 2})], size=10, color=MUTED)
tb(s, X0, 1.0, 5.2, 1.4, [("AI Software Engineering Team", {"bold": True})], size=36, color=INK)
tb(s, X0, 2.35, 5.2, 0.45, "Using LLM-Based Multi-Agent Systems", size=18, color=MID)
shape(s, X0, 3.05, 0.6, 0.05, fill=BLACK, radius=0)
tb(s, X0, 3.35, 2.4, 1.4, [[("Guide  ", {"color": MUTED}), ("S. Karthik", {"bold": True, "color": INK})],
                           [("In-Charge  ", {"color": MUTED}), ("Dr. Z. Sunitha Bai", {"bold": True, "color": INK})],
                           [("Batch  ", {"color": MUTED}), ("20", {"bold": True, "color": INK})]], size=11.5, space=5)
tb(s, 3.05, 3.35, 2.8, 1.4, [("Team Members", {"bold": True, "color": INK}),
                            ("K. Varshith  ·  Y23CS072", {}), ("K. Sri Varshitha  ·  Y23CS075", {}), ("P. Sravani  ·  Y23CS132", {})],
   size=11.5, space=3)

# ================================================================== 2 Introduction
s = slide("Introduction", "Introduction")
for i, (t, b) in enumerate([("LLMs", "Reasoning, natural-language understanding and code generation."),
                            ("AI Agents", "An LLM given goals, state, tools and actions."),
                            ("Multi-Agent Systems", "Several specialised agents collaborate on a shared objective.")]):
    card(s, X0 + i * 3.03, 1.35, 2.84, 1.75, t, b, n=i + 1)
panel(s, X0, 3.3, CW, 1.6, [
    [("Software development ", {"bold": True, "color": INK}), ("spans requirements, planning, coding, testing, debugging and review.", {})],
    [("LLM-based agents ", {"bold": True, "color": INK}), ("can reason over tasks and work with development tools.", {})],
    [("LLM-based MAS ", {"bold": True, "color": INK}), ("adds specialised roles and coordinates their work.", {})],
    [("Our project ", {"bold": True, "color": INK}), ("builds an AI software engineering team on this paradigm.", {})]], size=12.5, space=5)

# ================================================================== 3 Background
s = slide("Introduction", "Background: Single Agent to Multi-Agent")
cols = [("Single-Agent Systems", "One LLM agent perceives, decides and acts alone. Fast and simple, but limited by a knowledge bottleneck: no team to fall back on."),
        ("Why Move to MAS?", "Multi-agent systems spread decision-making across agents, enabling cooperation, competition and hierarchy for complex problems."),
        ("Pre-LLM MAS (RL era)", "Dominated by reinforcement-learning agents doing narrow, well-defined tasks with little interaction: rigid and data-hungry.")]
for i, (t, b) in enumerate(cols):
    card(s, X0 + i * 3.03, 1.35, 2.84, 2.2, t, b, n=i + 1, size=11.5)
panel(s, X0, 3.75, 4.35, 1.15, [("Structures", {"bold": True, "color": INK, "size": 12}),
                               ("Hierarchical, decentralized, centralized or shared-memory: this shapes how agents organise and communicate.", {})], size=11)
panel(s, X0 + 4.55, 3.75, 4.35, 1.15, [("Why LLMs change this", {"bold": True, "color": INK, "size": 12}),
                                      ("Natural-language understanding gives agents richer, more flexible interaction than rule-based or RL-only systems.", {})], size=11)

# ================================================================== NEW PROBLEM_MOT
s = slide("Problem Statement", "Problem Statement and Motivation")
tb(s, X0, 1.3, 5.6, 0.3, [("THE PROBLEM", {"bold": True, "spacing": 1.5})], size=10, color=MUTED)
tb(s, X0, 1.62, 5.6, 1.95, bullets([
    "AI assistants handle single tasks well, but real projects need coordinated stages.",
    "One agent checking its own work misses requirements and defects.",
    "Long, multi-step tasks make the project context hard to keep consistent.",
    "Systems such as iCoder raise quality, but at a high token cost per task."]), size=12, space=5)
callout(s, 6.35, 1.3, 3.1, 2.2, [("RESEARCH QUESTION", {"size": 9.5, "color": "BBBBBB", "spacing": 1.5, "space": 8}),
                                 ("Can specialised LLM agents collaboratively automate a reliable software-development workflow?", {"size": 14.5})],
        size=14.5)
tb(s, X0, 3.65, CW, 0.28, [("MOTIVATION", {"bold": True, "spacing": 1.5})], size=10, color=MUTED)
mot = [("Complexity", "Tasks can be split and delegated"), ("Specialisation", "Each agent focuses on one job"),
       ("Tool use", "Files, test runners, code analysers"), ("Feedback", "Results flow back every round"),
       ("Less repetition", "Routine work is automated"), ("Research value", "A platform to study coordination")]
tw = (CW - 0.15 * 5) / 6
for i, (t, b) in enumerate(mot):
    shape(s, X0 + i * (tw + 0.15), 3.97, tw, 1.0, fill=PANEL, radius=0.08, anchor="t", inset=0.1,
          text=[(t, {"bold": True, "color": INK, "size": 11, "space": 2}), (b, {"size": 9.5})], size=9.5)

# ================================================================== 6 Objectives
s = slide("Objectives", "Objectives")
objs = ["Design a code-based LLM multi-agent software engineering system.",
        "An orchestrator (MASWorkflow) controls the overall workflow.",
        "Router and Architect agents decompose requirements by complexity.",
        "A Developer agent writes and repairs the source files.",
        "Automated tests are written, executed, and their results captured.",
        "A Reflection agent scores each round and decides to stop or repeat.",
        "A Reviewer agent evaluates correctness, security and maintainability.",
        "Shared project state is kept across all agent interactions.",
        "Evaluate with the iCoder metrics against ChatDev and a single agent."]
for i, t in enumerate(objs):
    col, row = (0, i) if i < 5 else (1, i - 5)
    x = X0 + col * 4.55
    y = 1.35 + row * 0.72
    num_badge(s, x, y + 0.02, i + 1, d=0.4)
    tb(s, x + 0.55, y, 3.85, 0.62, t, size=12.5, color=BODY, anchor="m")

# ================================================================== NEW ICODER_ARCH
s = slide("Existing System  ·  Base Paper", "iCoder Architecture (You et al., 2026)",
          "iCoder is the base paper we build on. Explain the four agents left to right, then the review-first, test-second loop. "
          "All four agents are LLM-driven (paper, Sec. 4.3).")
tb(s, X0, 1.22, CW, 0.32, "iCoder embeds classic software-engineering practice into four LLM agents, coordinated in Sprint cycles.",
   size=12, color=BODY)
bots = [("RABot", "Requirement Iteration Layer", "Splits the requirement into subsystems, user stories and Sprints, sized by task complexity"),
        ("UMLBot", "Architecture Design Layer", "Produces multi-view UML designs; reverse-engineers the code to check it against the design"),
        ("DevBot", "Code Development Layer", "Generates Python code for each Sprint under the UML design constraints"),
        ("ReviewBot", "Quality Assurance Layer", "Builds a reverse code-dependency graph, reviews the code, then runs tests")]
bw, bg = 2.0, (CW - 2.0 * 4) / 3
for i, (n, layer, desc) in enumerate(bots):
    x = X0 + i * (bw + bg)
    node(s, x, 1.7, bw, 0.55, n, "LLM agent", llm=True, size=12)
    if i:
        line(s, x - bg, 1.975, x, 1.975)
    shape(s, x, 2.38, bw, 1.45, fill=PANEL, radius=0.06, anchor="t", inset=0.12,
          text=[(layer, {"bold": True, "color": INK, "size": 10.5, "space": 3}), (desc, {"size": 10})], size=10)
line(s, X0 + 3 * (bw + bg) + bw / 2, 3.83, X0 + 3 * (bw + bg) + bw / 2, 4.0, head=False, dash=True)
line(s, X0 + 3 * (bw + bg) + bw / 2, 4.0, X0 + 2 * (bw + bg) + bw / 2, 4.0, head=False, dash=True)
line(s, X0 + 2 * (bw + bg) + bw / 2, 4.0, X0 + 2 * (bw + bg) + bw / 2, 3.83, dash=True)
tb(s, X0 + 2 * (bw + bg) + 0.1, 4.03, 4.2, 0.25, "review feedback → fix → review again", size=9, color=MID)
callout(s, X0, 4.28, CW, 0.8, [("Iteration control:  S_i = (C_i, R_i, D_i, T_i).  ", {}),
                               ("Review first (D_i); only when the review passes is the code tested (T_i); a failed test goes back to review. "
                                "1–3 iterations per Sprint, with an interface for manual intervention.", {"bold": False})], size=10.5)

# ================================================================== NEW ICODER_RESULTS
s = slide("Existing System  ·  Base Paper", "iCoder: Published Results and Limitations",
          "These are the paper's own numbers (GPT-4o, 20 SRDD tasks). We could not run iCoder because its code was never released.")
rows = [["Metric (paper, GPT-4o, 20 tasks)", "iCoder", "ChatDev"],
        ["Completeness", "0.996", "1.000"],
        ["Executability", "0.95", "0.80"],
        ["Consistency", "0.837", "0.819"],
        ["Quality", "0.792", "0.655"],
        ["Tokens per task", "104,883", "30,417"],
        ["Time per task", "1,620 s", "1,059 s"]]
table(s, X0, 1.35, [2.55, 1.05, 1.05], rows, size=11, row_h=0.4)
tb(s, X0, 4.25, 4.65, 0.7, "With GPT-3.5 on 100 tasks: Quality 0.690 vs 0.591, tokens 411,145 vs 22,327 per task. "
                           "Source: You et al., IST 198 (2026) 108224, Tables 1–4.", size=9.5, color=MUTED)
card(s, 5.45, 1.35, 4.0, 3.6, "Limitations we address", bullets([
    "High cost: 3.4× ChatDev's tokens on GPT-4o, 18× on GPT-3.5 (the paper calls it trading compute for quality)",
    "All four agents are LLM-driven, including design checks and review decisions",
    "Tests run only after the LLM review passes, not every round",
    "Default model settings and one run per task",
    "Code not released, so results cannot be reproduced"]), size=12)

# ================================================================== 9-11 Literature
s = slide("Literature Survey  ·  Papers 1–3 of 8", "Software & Agent Collaboration")
lit = [("ChatDev", "Qian et al., ACL 2024", ["Virtual software company", "Role-based agents", "Design → coding → testing",
                                             "Agents talk to build applications"]),
       ("MetaGPT", "Hong et al., ICLR 2024", ["Models a software company", "Product Manager, Architect, Engineer, QA",
                                             "Standard Operating Procedures", "Role specialisation and workflow"]),
       ("Generative Agents", "Park et al., UIST 2023", ["LLM agents with memory", "Experience retrieval and reflection",
                                                        "Planning from past experience", "Relevant to project memory"])]
for i, (t, sub, items) in enumerate(lit):
    card(s, X0 + i * 3.03, 1.35, 2.84, 2.95, t, bullets(items), sub=sub, size=12.5)

# ================================================================== NEW LIT2
s = slide("Literature Survey  ·  Papers 4–8 of 8", "LLM-MAS, Software Engineering and Supporting Works")
card(s, X0, 1.3, 4.35, 1.65, "LLM-Based MAS for Software Engineering",
     "Vision for LLM-MAS in software engineering; names coordination, reliability and evaluation challenges.",
     sub="He, Treude & Lo, 2024", size=10.5, title_size=12.5)
card(s, X0 + 4.55, 1.3, 4.35, 1.65, "LLM-Based Multi-Agent Systems Survey",
     "Five modules (Profile, Perception, Self-Action, Mutual Interaction, Evolution); reliability is an open challenge.",
     sub="Li et al., 2024", size=10.5, title_size=12.5)
for i, (t, sub, b) in enumerate([("AutoGen", "Wu et al., 2023", "A manager agent splits tasks across child agents; informs our orchestrator."),
                                 ("ChatEval", "Chan et al., 2023", "Multi-agent debate for evaluation; relevant to our Reviewer."),
                                 ("DyLAN", "Liu et al., 2023", "Optimises the agent team structure during execution.")]):
    card(s, X0 + i * 3.03, 3.1, 2.84, 1.7, t, b, sub=sub, size=10.5, title_size=12.5)
tb(s, X0, 4.88, CW, 0.28, "8 papers across two slides (above the 5-paper minimum), plus the iCoder base paper.", size=9.5, color=MUTED)

# ================================================================== 12 Research gap
s = slide("Research Gap", "Research Gap")
tb(s, X0, 1.22, CW, 0.3, [("OPEN PROBLEMS IN THE SURVEY  ·  LI ET AL., 2024, SECTION 5.1", {"bold": True, "spacing": 1})], size=9.5, color=MUTED)
gaps = [("Intrinsic Constraints", "Black-box decisions, hallucination and bias are hard to verify."),
        ("Misuse", "MAS capability can be used for harmful or deceptive ends."),
        ("Scaling Up MAS", "More agents raise cost and coordination overhead."),
        ("Dynamic Adaptation", "Agents struggle as inputs and conditions change.")]
gw = (CW - 0.2 * 3) / 4
for i, (t, b) in enumerate(gaps):
    card(s, X0 + i * (gw + 0.2), 1.55, gw, 1.35, t, b, size=10.5, title_size=12)
callout(s, X0, 3.05, CW, 0.85, "The gap: these problems are rarely tested where correctness can be checked objectively. "
                               "Software engineering, with test-based verification, is an ideal and underexplored domain.", size=12)
tb(s, X0, 4.0, CW, 0.95, [("Our focus", {"bold": True, "color": INK, "size": 12.5})] + bullets([
    "Code-first LLM-MAS verified by objective tests, not only LLM self-assessment",
    "Orchestrator with explicit task state to limit coordination overhead",
    "A review → repair → re-test loop with an auditable record of every agent step"]), size=11.5, space=2)

# ================================================================== NEW IMPROVEMENTS
s = slide("Proposed System", "How MAS Improves on iCoder",
          "Read each row as: what iCoder does, what MAS does instead, and why it helps. Be open that some iCoder features are simplified.")
rows = [["iCoder (existing)", "MAS (proposed)", "Benefit"],
        ["RABot judges complexity with the LLM; splits work into subsystems and Sprints", "Rule-based Complexity Router (0 LLM calls); Architect only for larger tasks", "Fewer calls on small tasks"],
        ["UMLBot multi-view UML design", "Architect: class diagram, files and user stories (larger tasks only)", "Lighter design step"],
        ["Reverse architecture validation", "AST design-conformance check, 0 LLM calls", "Objective and free"],
        ["ReviewBot code-dependency graph", "AST import graph and cycle detection, 0 LLM calls", "Objective and free"],
        ["Review first; tests only after the review passes", "Real execution tests every round; the Reviewer sees the results", "Errors caught early"],
        ["Loop until review and tests pass (D_i, T_i)", "Weighted score S_t: stop when clean, on a plateau or after 3 rounds; best round kept", "Bounded cost"],
        ["Default settings, one run, ~105k tokens per task (GPT-4o)", "Temperature 0, pinned model, frozen evaluator, paired statistics; 14.7k tokens per task", "Reproducible, cheaper"]]
table(s, X0, 1.28, [3.25, 3.95, 1.7], rows, size=9.5, row_h=0.43)
tb(s, X0, 4.82, CW, 0.3, "Simplified in MAS: one Sprint per run, two complexity levels, text class diagrams only.", size=9.5, color=MUTED)

# ================================================================== 13 Proposed system flow
s = slide("Proposed System", "How MAS Builds a Project",
          "Read the top row left to right, then the bottom row right to left. Black boxes call the LLM, outlined boxes are plain code.")
top = [("Requirement", "plain-English task", False), ("Manager", "TaskPlan", True), ("Complexity Router", "score 0–9", False),
       ("Architect", "STRUCTURED only", True), ("Developer", "writes the files", True)]
bot = [("Deterministic checks", "AST, smoke run", False), ("Tester", "runs the program", False), ("Reviewer", "finds defects", True),
       ("Reflection", "score S_t", False), ("Final project", "code + scores", False)]
nw, gap = 1.5, (CW - 1.5 * 5) / 4
xs = [X0 + i * (nw + gap) for i in range(5)]
y1, y2 = 1.45, 3.1
for x, (t, sub, llm) in zip(xs, top):
    node(s, x, y1, nw, 0.72, t, sub, llm=llm)
for a, b in zip(xs, xs[1:]):
    line(s, a + nw, y1 + 0.36, b, y1 + 0.36)
for x, (t, sub, llm) in zip(reversed(xs), bot):
    node(s, x, y2, nw, 0.72, t, sub, llm=llm, emphasis=(t == "Final project"))
for a, b in zip(list(reversed(xs)), list(reversed(xs))[1:]):
    line(s, a, y2 + 0.36, b + nw, y2 + 0.36)
line(s, xs[4] + nw * 0.75, y1 + 0.72, xs[4] + nw * 0.75, y2)
tb(s, xs[2], y1 + 0.76, nw * 2 + gap, 0.25, "SIMPLE tasks skip the Architect", size=9, color=MUTED, align="c")
loop_y = 2.68
lx = xs[1] + nw / 2
line(s, lx, y2, lx, loop_y, head=False, dash=True)
line(s, lx, loop_y, xs[4] + nw * 0.25, loop_y, head=False, dash=True)
line(s, xs[4] + nw * 0.25, loop_y, xs[4] + nw * 0.25, y1 + 0.72, dash=True)
tb(s, lx + 0.1, loop_y - 0.27, 4.0, 0.25, [("CONTINUE: repair and try again, at most 3 rounds", {"bold": True})], size=9, color=INK)
legend(s, X0, 4.2)
panel(s, 4.05, 4.05, 5.4, 0.85, "4 of the 7 roles call the LLM. The Router, Tester and Reflection are plain code, so checks are objective and cheap.",
      size=11)

# ================================================================== 14 Roles
s = slide("Proposed System", "Agent Roles and Responsibilities")
roles = [("Manager", "LLM", "Turns the requirement into a TaskPlan: files, goals and acceptance criteria."),
         ("Router + Architect", "Mixed", "Router scores complexity (code). For larger tasks the Architect designs classes, files and user stories (LLM)."),
         ("Developer", "LLM", "Writes every file; gets one targeted repair call if the automatic checks fail."),
         ("Tester", "No LLM", "Runs the program, checks --help, scans for empty functions, runs the developer's tests."),
         ("Reviewer", "LLM", "Reviews code, test report and analysis results; lists critical, major and minor findings."),
         ("Reflection", "No LLM", "Computes the round score S_t and decides STOP or CONTINUE (at most 3 rounds).")]
for i, (t, tag, b) in enumerate(roles):
    card(s, X0 + (i % 3) * 3.03, 1.35 + (i // 3) * 1.78, 2.84, 1.62, t, b, tag=tag if tag != "Mixed" else "Mixed", size=11)
tb(s, X0, 4.95 - 0.02, CW, 0.25, "Agents exchange typed, validated artifacts (Pydantic models), never free text.", size=10, color=MUTED)

# ================================================================== 16 Methodology
s = slide("Methodology", "Methodology")
steps = [("Requirement Analysis", "Manager builds a TaskPlan with acceptance criteria (1 LLM call)."),
         ("Complexity Routing", "Rule-based score 0–9; ≥ 4 means STRUCTURED, otherwise SIMPLE."),
         ("Design", "Architect plans components, classes and files (STRUCTURED only)."),
         ("Code Generation", "Developer writes files as === FILE === blocks; one repair if checks fail."),
         ("Verification", "AST graph, design conformance, Ruff, Bandit, Radon, Tester, Reviewer."),
         ("Reflection & Stopping", "Score S_t each round; stop when clean, when gain < 0.02 twice, or after 3.")]
for i, (t, b) in enumerate(steps):
    card(s, X0 + (i % 3) * 3.03, 1.35 + (i // 3) * 1.55, 2.84, 1.4, t, b, n=None, size=11, title_size=13)
    num_badge(s, X0 + (i % 3) * 3.03 + 2.84 - 0.52, 1.35 + (i // 3) * 1.55 + 0.14, i + 1, d=0.36, size=10)
callout(s, X0, 4.5, CW, 0.5, "Develop  →  Check  →  Test  →  Review  →  Reflect  →  STOP, or repair and repeat (max 3 rounds)", size=12, align="c")

# ================================================================== 17 Architecture
s = slide("System Architecture", "System Architecture",
          "Top to bottom: browser, API, orchestrator, the seven agents (black ones call the LLM), shared services, storage. "
          "Right: the Gemini model and the evaluation pipeline used for the benchmark.")
L, W = X0, 6.6
y = 1.3
for t, sub in [("React Web App", "Overview · Generate · Benchmark · All Runs · Run Details · Compare · Status"),
               ("FastAPI Backend", "/runs  ·  /evaluations  ·  /config  ·  /runs/{id}/quick-test  ·  /runs/{id}/open"),
               ("MAS Workflow Orchestrator", "MASWorkflow.run(): shared state, round loop, checkpoints")]:
    node(s, L, y, W, 0.48, t, sub, llm=False, size=11)
    line(s, L + W / 2, y + 0.48, L + W / 2, y + 0.58)
    y += 0.58
agents = ["Manager", "Router", "Architect", "Developer", "Tester", "Reviewer", "Reflection"]
aw = (W - 0.06 * 6) / 7
for i, a in enumerate(agents):
    node(s, L + i * (aw + 0.06), y, aw, 0.4, a, llm=a in ("Manager", "Architect", "Developer", "Reviewer"), size=9)
line(s, L + W / 2, y + 0.4, L + W / 2, y + 0.5)
y += 0.5
sv = [("LLM client + quota", "12 req/min · 450/day"), ("Sandbox runner", "Docker or isolated"), ("Analysis tools", "AST · Ruff · Bandit · Radon"),
      ("Typed artifacts", "Pydantic validation")]
sw = (W - 0.06 * 3) / 4
for i, (t, sub) in enumerate(sv):
    shape(s, L + i * (sw + 0.06), y, sw, 0.55, fill=PANEL, radius=0.08, inset=0.04,
          text=[(t, {"bold": True, "color": INK, "space": 0}), (sub, {"size": 8, "color": MUTED})], size=9.5, align="c")
line(s, L + W / 2, y + 0.55, L + W / 2, y + 0.65)
y += 0.65
st = [("mas.db (SQLite)", "runs · steps · scores"), ("Workspaces", "generated code"), ("results.csv + reports", "benchmark results")]
tw = (W - 0.06 * 2) / 3
for i, (t, sub) in enumerate(st):
    shape(s, L + i * (tw + 0.06), y, tw, 0.5, fill=WHITE, line=INK, dash=True, radius=0.1,
          text=[(t, {"bold": True, "color": INK, "space": 0}), (sub, {"size": 8.5, "color": MUTED})], size=9.5, align="c", inset=0.05)
RX, RW = 7.35, 2.1
node(s, RX, 1.3, RW, 0.75, "Gemini API", "gemini-3.5-flash-lite", llm=True, size=11)
line(s, RX, 1.68, L + W, 2.6)
panel(s, RX, 2.25, RW, 2.6, [("Evaluation pipeline", {"bold": True, "color": INK, "size": 11, "space": 4})] + bullets(
    ["Resumable benchmark runner", "Baselines: ChatDev, single agent", "Frozen neutral evaluator", "Bootstrap CI, Wilcoxon test"]),
      size=9.5, anchor="t")
line(s, RX, 3.5, L + W, 3.5)
legend(s, X0, 4.95 - 0.02 if False else 4.92)

# ================================================================== NEW TECH
s = slide("System Architecture", "Tech Stack",
          "No LangChain or LangGraph: we wrote our own orchestrator to control and measure every API call on the free tier.")
techs = [("AI model", "Google Gemini gemini-3.5-flash-lite (free tier), OpenAI-compatible API"),
         ("Language", "Python 3.11"),
         ("Backend", "FastAPI + Uvicorn; Pydantic 2 typed artifacts"),
         ("Database", "SQLite through SQLAlchemy 2 (mas.db)"),
         ("Code analysis", "Python ast, Ruff, Bandit, Radon"),
         ("Sandbox", "Docker (python:3.11-slim, no network) or an isolated process"),
         ("Evaluation", "sentence-transformers (all-MiniLM-L6-v2), NumPy, SciPy"),
         ("Frontend", "React 18 + Vite 5, Tailwind CSS")]
tw = (CW - 0.2 * 3) / 4
for i, (t, b) in enumerate(techs):
    x = X0 + (i % 4) * (tw + 0.2)
    y = 1.35 + (i // 4) * 1.62
    shape(s, x, y, tw, 1.45, fill=PANEL, radius=0.06, anchor="t", inset=0.16,
          text=[(t.upper(), {"bold": True, "color": MUTED, "size": 9, "spacing": 1, "space": 4}), (b, {"color": INK, "size": 12})], size=12)
panel(s, X0, 4.62, CW, 0.42, [[("Also  ", {"bold": True, "color": INK}),
                               ("pytest (375 offline tests)  ·  ChatDev baseline (pinned commit)  ·  own orchestrator, no LangChain or LangGraph", {})]],
      size=10.5)

# ================================================================== 19 Modules overview
s = slide("Modules", "Modules", "Presenters to be decided by the team: fill in the blank lines.")
mods = [("Requirement Analysis & Planning", ["Manager agent: TaskPlan", "Complexity Router", "Architect agent", "Validation, retry, checkpoints"]),
        ("Code Generation & Verification", ["Developer + targeted repair", "Checks, AST, Ruff, Bandit, Radon", "Tester and Reviewer", "Reflection: S_t and stopping"]),
        ("Evaluation, Benchmark & Web App", ["Frozen evaluator: iCoder metrics", "ChatDev and single-agent baselines", "Quota governor, resumable runner", "FastAPI + React web app"])]
for i, (name, items) in enumerate(mods):
    x = X0 + i * 3.03
    shape(s, x, 1.35, 2.84, 3.55, fill=PANEL, radius=0.05)
    tb(s, x + 0.2, 1.5, 2.5, 0.6, [(f"{i + 1:02d}", {"bold": True})], size=30, color=INK)
    tb(s, x + 0.2, 2.15, 2.5, 0.6, [(name, {"bold": True})], size=13.5, color=INK)
    tb(s, x + 0.2, 2.8, 2.5, 1.4, bullets(items), size=11, space=3)
    tb(s, x + 0.2, 4.4, 2.5, 0.35, [[("Presented by  ", {"color": MUTED}), ("________________", {"color": INK})]], size=10.5)


# ================================================================== 20-22 Module slides
def module(n, title, items, right, note):
    s = slide(f"Module {n}  ·  Presented by ________________", title, note)
    tb(s, X0, 1.35, 4.2, 0.3, [("WHAT THIS MODULE DOES", {"bold": True, "spacing": 1.5})], size=9.5, color=MUTED)
    tb(s, X0, 1.68, 4.25, 3.3, bullets(items), size=11.5, space=6)
    right(s)
    return s


def m1(s):
    X, Wd = 5.05, 4.4
    for i, (t, llm) in enumerate([("Requirement", False), ("Manager", True), ("TaskPlan", False)]):
        node(s, X + i * 1.53, 1.35, 1.34, 0.5, t, llm=llm, size=10.5)
        if i:
            line(s, X + i * 1.53 - 0.19, 1.6, X + i * 1.53, 1.6)
    panel(s, X, 2.05, Wd, 1.95, [("Complexity Router  ·  no LLM", {"bold": True, "color": INK, "size": 12, "space": 4})] + bullets(
        ["+1 per feature: storage, login, roles, integrations, analytics, workflow", "+1 for 4+ list separators, +2 for 7+",
         "+1 if longer than 80 words"]) + [("Score ≥ 4 → STRUCTURED, else SIMPLE", {"bold": True, "color": INK, "space": 0})],
          size=10.5, anchor="t")
    node(s, X, 4.2, 2.1, 0.7, "SIMPLE", "→ Developer directly", llm=False, size=11)
    node(s, X + 2.3, 4.2, 2.1, 0.7, "STRUCTURED", "→ Architect → Developer", llm=True, size=11)


module(1, "Requirement Analysis & Planning",
       ["Manager agent (1 LLM call) turns the requirement into a TaskPlan: description, files, goals, acceptance criteria.",
        "Complexity Router scores the requirement with fixed rules (0–9) and picks the SIMPLE or STRUCTURED path.",
        "Architect agent (STRUCTURED only, 2 calls) designs components, a class diagram, the file list and user stories.",
        "Every output is a Pydantic artifact: invalid output is retried with the error, then rolled back to a checkpoint.",
        "Code: mas/agents/manager.py, router.py, architect.py, base.py"], m1,
       "Explain how one requirement becomes a plan, and why a cheap rule-based router decides whether the Architect is needed.")


def m2(s):
    X, Wd = 5.05, 4.4
    callout(s, X, 1.35, Wd, 1.25, [("ROUND SCORE  ·  REFLECTION, NO LLM", {"size": 9, "color": "BBBBBB", "spacing": 1, "space": 4}),
                                   ("S_t = 0.30·tests + 0.10·ruff + 0.15·bandit + 0.10·radon + 0.15·review + 0.20·(completeness + runs)/2",
                                    {"size": 11.5})], size=11.5)
    panel(s, X, 2.75, Wd, 1.35, [("Stop rules (first that holds)", {"bold": True, "color": INK, "size": 12, "space": 4})] + bullets(
        ["Clean: no critical defect, every check passed", "Plateau: gain below 0.02 for 2 rounds", "Limit: 3 rounds (best round kept)"]),
          size=10.5, anchor="t")
    seq = [("Developer", True), ("Checks", False), ("Tester", False), ("Reviewer", True), ("Reflection", False)]
    cw = (Wd - 0.12 * 4) / 5
    for i, (t, llm) in enumerate(seq):
        node(s, X + i * (cw + 0.12), 4.3, cw, 0.55, t, llm=llm, size=8.5)
        if i:
            line(s, X + i * (cw + 0.12) - 0.12, 4.575, X + i * (cw + 0.12), 4.575)


module(2, "Code Generation & Verification",
       ["Developer agent writes files as === FILE === blocks, which a small model handles better than JSON.",
        "Automatic checks: main.py exists, files parse, no empty functions, smoke run; one repair call fixes failures.",
        "Analysis without the LLM: import graph and cycles, design conformance, Ruff, Bandit, Radon.",
        "Tester runs the program, --help, the empty-function scan and the developer's own tests.",
        "Reviewer (LLM) lists critical, major and minor findings for the next round.",
        "Code: mas/agents/developer.py, tester.py, reviewer.py, reflection.py"], m2,
       "Explain the loop: real tools check the code first, the Reviewer adds judgement, and S_t decides whether another round is worth it.")


def m3(s):
    X, Wd = 5.05, 4.4
    panel(s, X, 1.35, Wd, 0.45, [("20 SRDD tasks  ·  same text, same model, temperature 0", {"bold": True, "color": INK})], size=10.5, align="c")
    cw = (Wd - 0.2) / 3
    for i, t in enumerate(["MAS", "ChatDev", "Single agent"]):
        node(s, X + i * (cw + 0.1), 1.98, cw, 0.45, t, llm=(t == "MAS"), size=10.5)
        line(s, X + i * (cw + 0.1) + cw / 2, 2.43, X + i * (cw + 0.1) + cw / 2, 2.66)
    shape(s, X, 2.66, Wd, 1.4, fill=WHITE, line=INK, radius=0.06, anchor="t", inset=0.18,
          text=[("Frozen neutral evaluator", {"bold": True, "color": INK, "size": 12, "space": 3})] + bullets(
              ["Completeness = 1 − unimplemented / all functions", "Executability = program runs without error",
               "Consistency = similarity of requirement and code"]) + [("Quality = C × E × S", {"bold": True, "color": INK})],
          size=10, color=BODY)
    line(s, X + Wd / 2, 4.06, X + Wd / 2, 4.26)
    node(s, X, 4.26, Wd, 0.5, "results.csv → statistics → reports + web app", llm=False, size=10.5)


module(3, "Evaluation, Benchmark & Web App",
       ["Runs MAS, ChatDev and a single-agent baseline on the same 20 SRDD tasks with identical settings.",
        "A frozen evaluator computes the iCoder paper's four metrics, the same code for every system.",
        "Quota governor keeps within the free tier (12 requests/min, 450/day); the runner resumes the next day.",
        "Statistics: bootstrap 95% confidence intervals and the paired Wilcoxon test.",
        "FastAPI + React web app: generate a project, inspect runs, run the code, compare systems.",
        "Code: eval/runner.py, eval/neutral_evaluator.py, mas/core/governor.py, mas/api/, frontend/"], m3,
       "Explain how the comparison is kept fair and how the free-tier limits were handled by stopping cleanly and resuming.")

# ================================================================== NEW HALLUC
s = slide("Proposed System", "Handling Hallucinations",
          "Key line: we never trust the model's own claims; every output is checked by something that cannot hallucinate.")
rows = [["Kind of hallucination", "Example", "How MAS catches it"],
        ["Invented functions or modules", "import colorlib (does not exist)", "The sandbox runs the program; the crash text goes back for one targeted repair"],
        ["Empty code that looks done", "a function with only pass or TODO", "AST placeholder scan; the Developer must implement it"],
        ["Malformed output", "broken JSON, missing fields", "Pydantic validation, retry with the error, rollback to a checkpoint"],
        ["Reviewer says “it works”", "PASSED although it crashes", "Grounded review: exit code, test results, Ruff, Bandit; safe fallback NEEDS_REVISION"],
        ["Stopping too early", "optimism ends the loop", "S_t is 85% objective signals; a clean stop needs every check to pass"],
        ["Drift from design or model", "planned files missing; model swapped", "AST conformance check; abort on model mismatch; temperature 0"]]
table(s, X0, 1.28, [2.3, 2.5, 4.1], rows, size=9.5, row_h=0.47)
panel(s, X0, 4.7, CW, 0.38, [[("Result  ", {"bold": True, "color": INK}),
                              ("MAS programs ran in 20 of 20 tasks, ChatDev's in 2 of 20.   ", {}),
                              ("Limit  ", {"bold": True, "color": INK}), ("code that runs can still be logically wrong.", {})]], size=10.5)

# ================================================================== NEW EVAL_SETUP
s = slide("Evaluation", "Evaluation Setup: Fair Comparison and the Logging Proxy",
          "The proxy is how we measure ChatDev exactly like MAS without changing its agents.")
node(s, X0, 1.45, 1.25, 0.5, "ChatDev", llm=False, size=11)
node(s, X0 + 1.6, 1.45, 1.35, 0.5, "Logging proxy", llm=False, size=11, emphasis=True)
node(s, X0 + 3.3, 1.45, 1.05, 1.35, "Gemini API", llm=True, size=11)
line(s, X0 + 1.25, 1.7, X0 + 1.6, 1.7)
line(s, X0 + 2.95, 1.7, X0 + 3.3, 1.7)
node(s, X0, 2.3, 1.25, 0.5, "MAS", llm=False, size=11)
line(s, X0 + 1.25, 2.55, X0 + 3.3, 2.55)
tb(s, X0 + 1.35, 2.27, 1.9, 0.25, "own client, same rules", size=9, color=MID)
panel(s, X0, 3.0, 4.35, 1.98, [("What the proxy does on every call", {"bold": True, "color": INK, "size": 11.5, "space": 4})] + bullets(
    ["Forces temperature 0 and the 8,192-token output cap", "Pins the model and rejects any other model",
     "Sends requests through the same quota governor", "Records provider-reported tokens per call and run"]),
      size=11.5, anchor="t")
card(s, X0 + 4.55, 1.35, 4.35, 3.63, "Same for every system", bullets(
    ["Same 20 SRDD tasks and requirement text (+ the python main.py rule)", "One pinned model, no fallback",
     "One frozen evaluator for all scores", "Official result = first attempt without an infrastructure failure",
     "Outages are rerun; bad code is never rerun", "Compared per task, as pairs"]), size=12)

# ================================================================== NEW WORKED
s = slide("Evaluation", "Metrics with a Worked Example",
          "All numbers were recomputed from the saved code folders with the evaluator's own functions; they match results.csv exactly.")
tb(s, X0, 1.25, 5.3, 0.3, [("Task srdd_crea_01  ·  “Color Palette Picker”", {"bold": True, "color": INK})], size=11.5)
rows = [["Metric", "MAS", "Single", "ChatDev"],
        ["Functions (empty)", "14 (0)", "17 (0)", "0 (unreadable)"],
        ["Completeness C", "1.0", "1.0", "1.0"],
        ["Executability E", "1", "1", "0"],
        ["Consistency S", "0.654", "0.628", "0.630"],
        ["Quality C × E × S", "0.654", "0.628", "0.000"]]
table(s, X0, 1.6, [1.85, 1.0, 1.0, 1.35], rows, size=10.5, row_h=0.36)
panel(s, X0, 3.95, 5.2, 1.0, [[("Why ChatDev scores 0  ", {"bold": True, "color": INK}),
                               ("its main.py holds only the text “main.py” (NameError) and palette_picker.py has a syntax error. "
                                "Completeness stays 1.0, but Quality multiplies, so one failing part gives 0.", {})]], size=10.5, anchor="t")
panel(s, 5.95, 1.25, 3.5, 3.7, [("Algorithms", {"bold": True, "color": INK, "size": 12, "space": 4})] + bullets(
    ["Completeness = 1 − empty ÷ all functions (AST)", "Executability = sandbox smoke run, 1 or 0",
     "Consistency = cosine of MiniLM embeddings (first 2,000 characters)", "Quality = C × E × S",
     "Bootstrap 95% CI, 10,000 resamples", "Wilcoxon signed-rank test, paired by task", "Effect size d_z"]),
      size=10.5, anchor="t")

# ================================================================== 23 Status
s = slide("Work Done", "Implementation Status", "Everything listed is implemented and tested; the numbers come from the test suite and the final benchmark.")
done = ["Seven-role agent pipeline with typed, validated artifacts",
        "Deterministic Tester, AST analysis, Ruff, Bandit and Radon checks",
        "Adaptive stopping with the S_t score, keeping the best round",
        "Frozen evaluator with the four iCoder metrics",
        "ChatDev and single-agent baselines under identical settings",
        "Quota governor and resumable multi-day benchmark runner",
        "FastAPI backend and React web app",
        "Final benchmark: 20 tasks × 3 systems = 60 official runs"]
for i, t in enumerate(done):
    y = 1.35 + i * 0.45
    shape(s, X0, y + 0.06, 0.28, 0.28, fill=BLACK, kind=MSO_SHAPE.OVAL, text=[("✓", {"font": "Segoe UI Symbol", "bold": True})],
          size=9, color=WHITE, align="c", inset=0)
    tb(s, X0 + 0.42, y, 4.75, 0.4, t, size=11.5, anchor="m")
for i, (big, small) in enumerate([("7", "agent roles"), ("375", "automated tests passing"), ("60", "official benchmark runs"),
                                   ("20 / 20", "MAS programs that run")]):
    x = 5.85 + (i % 2) * 1.82
    y = 1.35 + (i // 2) * 1.8
    shape(s, x, y, 1.68, 1.62, fill=BLACK if i == 3 else PANEL, radius=0.06,
          text=[(big, {"bold": True, "size": 30}), (small, {"size": 10.5})], color=WHITE if i == 3 else INK, align="c", space=2)

# ================================================================== NEW SHOTS
s = slide("Work Done", "Web Application (Screenshots)", "Screenshots of the running web app. If time allows, show it live instead.")
shot(s, "generate.png", X0, 1.3, 4.35, 2.85, "Generate a Project: requirement, system and model")
shot(s, "run_details.png", X0 + 4.55, 1.3, 4.35, 2.85, "Run Details: scores and agent steps of one MAS run")
panel(s, X0, 4.55, CW, 0.45, [[("Run it  ", {"bold": True, "color": INK}),
                               ("python -m uvicorn mas.api.main:app --port 8000   ·   npm run dev   →   http://localhost:3000", {"font": "Consolas", "size": 10})]],
      size=10.5)

# ================================================================== 26 Code + output
s = slide("Work Done", "Code and Program Output",
          "Left: our Reflection agent's stop rule (messages shortened). Right: real output from the web app's Run Program tab, "
          "which runs a program exactly as the evaluator did.")
code = ["def evaluate_stop(self, iteration, current_score,",
        "                  previous_score, has_critical_defects, tests_pass):",
        "    delta = round(current_score - previous_score, 4)",
        "    if not has_critical_defects and tests_pass:",
        "        return \"STOP\", \"clean_result\", delta",
        "    if delta < self.stop_epsilon:",
        "        self.consecutive_low_gain += 1",
        "    else:",
        "        self.consecutive_low_gain = 0",
        "    if self.consecutive_low_gain >= self.patience:",
        "        return \"STOP\", \"marginal_gain_plateau\", delta",
        "    if iteration >= self.max_iterations:",
        "        return \"STOP\", \"max_iterations\", delta",
        "    return \"CONTINUE\", f\"iteration {iteration + 1}\", delta"]
tb(s, X0, 1.28, 4.9, 0.28, [("mas/agents/reflection.py", {"bold": True, "color": INK}), ], size=10.5)
tb(s, X0 + 1.85, 1.28, 3.0, 0.28, "stop rule, simplified excerpt", size=10, color=MUTED)
shape(s, X0, 1.58, 4.95, 3.42, fill=PANEL, radius=0.04, anchor="t", inset=0.15,
      text=[(c.replace(" ", " "), {"font": "Consolas", "size": 9, "color": INK}) for c in code], space=0)


def term(x, y, w, h, label, ok, lines):
    tb(s, x, y, w - 0.8, 0.28, [(label, {"bold": True, "color": INK})], size=10.5)
    shape(s, x + w - 0.72, y + 0.01, 0.72, 0.26, fill=BLACK if ok else WHITE, line=None if ok else INK, radius=0.5,
          text=[("PASS" if ok else "FAIL", {"bold": True})], size=8.5, color=WHITE if ok else INK, align="c", inset=0)
    shape(s, x, y + 0.32, w, h - 0.32, fill=WHITE, line=LINE, radius=0.04, anchor="t", inset=0.15,
          text=[(t.replace(" ", " "), {"font": "Consolas", "size": 9, "color": c, "bold": b}) for t, c, b in lines], space=0)


term(5.7, 1.28, 3.75, 1.6, "MAS · mas_srdd_crea_01_r1", True,
     [("$ python main.py", MID, False), ("Enter path to image (PPM format or sample):", INK, False), ("Exiting.", INK, False),
      ("exit code 0: runs without error", INK, True)])
term(5.7, 3.05, 3.75, 1.95, "ChatDev · cd_srdd_crea_01_r1", False,
     [("$ python main.py", MID, False), ('File "main.py", line 1, in <module>', INK, False), ("    main.py", INK, False),
      ("NameError: name 'main' is not defined", INK, True), ("exit code 1: line 1 of the file is", INK, False),
      ("the file name, not code", INK, False)])

# ================================================================== 27 Results
s = slide("Results", "Final 20-Task Benchmark",
          "All numbers are the 60 official runs (gemini-3.5-flash-lite, one repeat per task). Consistency is about equal for all three, "
          "so the quality gap comes from whether the program runs. MAS vs the single agent is not statistically significant.")
cd = CategoryChartData()
cd.categories = ["MAS", "Single agent", "ChatDev"]
cd.add_series("Quality", (0.4929, 0.3833, 0.0546))
ch = s.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(X0 - 0.1), Inches(1.25), Inches(3.75), Inches(3.05), cd).chart
ch.has_title = True
ch.chart_title.text_frame.text = "Average quality score (0–1)"
tr = ch.chart_title.text_frame.paragraphs[0].runs[0]
tr.font.size, tr.font.bold, tr.font.name = Pt(11), True, FONT
tr.font.color.rgb = rgb(INK)
ch.has_legend = False
pl = ch.plots[0]
pl.gap_width = 60
pl.has_data_labels = True
dl = pl.data_labels
dl.number_format, dl.number_format_is_linked = "0.000", False
dl.position = XL_LABEL_POSITION.OUTSIDE_END
dl.font.size, dl.font.bold, dl.font.name = Pt(11), True, FONT
dl.font.color.rgb = rgb(INK)
for i, c in enumerate([BLACK, "7A7A7A", "C4C4C4"]):
    pt = pl.series[0].points[i]
    pt.format.fill.solid()
    pt.format.fill.fore_color.rgb = rgb(c)
va = ch.value_axis
va.maximum_scale, va.minimum_scale = 0.6, 0
va.major_gridlines.format.line.color.rgb = rgb("E6E6E6")
va.tick_labels.font.size, va.tick_labels.font.name = Pt(9), FONT
va.tick_labels.font.color.rgb = rgb(MUTED)
va.format.line.fill.background()
ca = ch.category_axis
ca.tick_labels.font.size, ca.tick_labels.font.name = Pt(10.5), FONT
ca.tick_labels.font.color.rgb = rgb(INK)
ca.format.line.color.rgb = rgb(LINE)
rows = [["Metric", "MAS", "Single agent", "ChatDev"],
        ["Quality (95% CI)", "0.493 [0.433–0.549]", "0.383 [0.282–0.487]", "0.055 [0.000–0.141]"],
        ["Programs that run", "20 / 20", "16 / 20", "2 / 20"],
        ["Completeness", "1.000", "1.000", "0.950"],
        ["Consistency", "0.493", "0.494", "0.501"],
        ["Tokens per task", "14,689", "3,815", "47,191"],
        ["LLM calls per task", "4.4", "1.0", "14.8"],
        ["Time per task", "38 s", "13 s", "342 s"]]
table(s, 4.3, 1.3, [1.45, 1.3, 1.2, 1.2], rows, size=9.5, row_h=0.37)
panel(s, X0, 4.4, 4.35, 0.62, [[("19 of 20 tasks ", {"bold": True, "color": INK}), ("MAS beats ChatDev  ·  p = 0.000004, significant", {})]],
      size=11)
panel(s, X0 + 4.55, 4.4, 4.35, 0.62, [[("12 of 20 tasks ", {"bold": True, "color": INK}), ("MAS beats single agent  ·  p = 0.19, not significant", {})]],
      size=11)

# ================================================================== NEW ICODER_CMP
s = slide("Results", "Comparison with iCoder (Published Results)",
          "Compare ratios, not raw numbers. Much of the 9× gap comes from ChatDev struggling on the small model.")
rows = [["Metric", "iCoder (paper, GPT-4o)", "ChatDev (paper)", "MAS (ours, Flash Lite)", "ChatDev (ours)"],
        ["Completeness", "0.996", "1.000", "1.000", "0.950"],
        ["Executability", "0.95", "0.80", "1.00", "0.10"],
        ["Consistency", "0.837", "0.819", "0.493", "0.501"],
        ["Quality", "0.792", "0.655", "0.493", "0.055"],
        ["Tokens per task", "104,883", "30,417", "14,689", "47,191"],
        ["Quality vs ChatDev", "1.2×", "—", "9.0×", "—"]]
table(s, X0, 1.3, [1.85, 1.9, 1.55, 1.95, 1.65], rows, size=10.5, row_h=0.36)
panel(s, X0, 3.95, 4.35, 1.05, [("Targets met", {"bold": True, "color": INK, "size": 11.5, "space": 3})] + bullets(
    ["Beat ChatDev: 19 of 20 tasks, p = 0.000004", "Executability above iCoder's 0.95", "Fewer tokens than ChatDev (iCoder used 3.4× more)"]),
      size=10, anchor="t")
panel(s, X0 + 4.55, 3.95, 4.35, 1.05, [("Why absolute scores differ", {"bold": True, "color": INK, "size": 11.5, "space": 3})] + bullets(
    ["Consistency scale: the paper min-max normalises, we clip raw cosine", "GPT-4o vs a small free model; different tasks",
     "So published numbers are indicative only"]), size=10, anchor="t")

# ================================================================== NEW CONCL
s = slide("Conclusion", "Conclusion, Limitations and Future Work")
card(s, X0, 1.3, 2.84, 3.15, "Conclusion", bullets(
    ["MAS ran 20 of 20 tasks; ChatDev 2 of 20", "Quality 0.493 vs 0.055, with 69% fewer tokens",
     "Gain over a single agent not yet significant (p = 0.19)", "Objective checks make the code run, at a fraction of iCoder's cost"]),
     n=1, size=11)
card(s, X0 + 3.03, 1.3, 2.84, 3.15, "Limitations", bullets(
    ["One repeat, 20 tasks", "One small free-tier model", "Consistency is text similarity", "Running code can still be logically wrong",
     "iCoder numbers indicative only"]), n=2, size=11)
card(s, X0 + 6.06, 1.3, 2.84, 3.15, "Future Work", bullets(
    ["More tasks and repeats", "Feature tests from acceptance criteria", "Larger models, still one pinned", "Docker sandbox for every run",
     "Multi-Sprint mode like iCoder"]), n=3, size=11)
callout(s, X0, 4.55, CW, 0.5, "Specialised agents with objective verification can automate a reliable small-project workflow.", size=12, align="c")
# ================================================================== 30 References
s = slide("References", "References")
refs = ["Li, X., Wang, S., Zeng, S., Wu, Y., Yang, Y. — LLM-based Multi-Agent Systems: survey, framework and applications, 2024.",
        "Qian, C. et al. — ChatDev: Communicative Agents for Software Development, ACL 2024.",
        "Hong, S. et al. — MetaGPT: Meta Programming for Multi-Agent Collaborative Framework, ICLR 2024.",
        "Park, J. S. et al. — Generative Agents: Interactive Simulacra of Human Behavior, UIST 2023.",
        "He, J., Treude, C., Lo, D. — LLM-Based Multi-Agent Systems for Software Engineering: Vision and the Road Ahead, 2024.",
        "Wu, Q. et al. — AutoGen: Enabling Next-Gen LLM Applications via Multi-Agent Conversation, 2023.",
        "Chan, C. et al. — ChatEval: Towards Better LLM-Based Evaluators through Multi-Agent Debate, 2023.",
        "Liu, Z. et al. — DyLAN: Dynamic LLM-Agent Network for Collaborative Reasoning, 2023.",
        "You, Y. et al. — iCoder: A Multi-Agent Software Development Platform, Information and Software Technology 198 (2026) 108224.",
        "Course term-paper source: Mapping the Rise of LLM Multi-Agent Systems.",
        "R.V.R. & J.C. College of Engineering, CSE — review requirements notices."]
tb(s, X0, 1.3, 6.3, 3.7, [[(f"{i + 1}.  ", {"bold": True, "color": INK}), (r, {})] for i, r in enumerate(refs)], size=10, space=4)
callout(s, 7.15, 1.35, 2.3, 3.55, [("Thank You", {"size": 24}), ("Questions?", {"size": 13, "color": "BBBBBB"})], align="c")


assert len(prs.slides) == 30, len(prs.slides)
prs.save(OUT)
print("saved", OUT, len(prs.slides))
