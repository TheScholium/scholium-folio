"""Reference implementation of the Folio generator, in Python.

The live generator is docs/folio.js; parity.py checks the two agree
page for page, link for link and moon for moon.

The Folio: a hyperlinked academic-year planner for the Supernote Nomad.

Builds one PDF at the Nomad's native 1404 x 1872 px. Every page carries a
tab rail on the right edge (index, year, months, courses, research, notes),
and every dated page has breadcrumbs and previous / next links. All links
are internal PDF links, which the Supernote follows with a tap.

    python3 build_folio.py                      # daily edition, Aug 2026 - Jul 2027
    python3 build_folio.py --weekly             # no day pages
    python3 build_folio.py --start 2027-01 --months 6 --courses 5
"""
import argparse
import base64
import calendar
import datetime as dt
import html
import pathlib
import re
from zoneinfo import ZoneInfo

from playwright.sync_api import sync_playwright

import moon  # noqa: reference implementation

HERE = pathlib.Path(__file__).resolve().parent
ASSETS = HERE.parent / "docs"
W, H = 1404, 1872
RAIL = 54            # tab rail width, drawn in the templates' blank right margin
PAD_R = RAIL + 24
ROMAN = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII"]

STARP = "M12 1.5 14.3 9.7 22.5 12 14.3 14.3 12 22.5 9.7 14.3 1.5 12 9.7 9.7z"
STAR = f"<svg class=st viewBox='0 0 24 24'><path d='{STARP}'/></svg>"


def b64(path: pathlib.Path) -> str:
    return base64.b64encode(path.read_bytes()).decode()


def mark_svg(fill="#111") -> str:
    svg = (HERE / "schol-mark.svg").read_text()
    d = re.search(r"d='([^']+)'", svg).group(1)
    vb = re.search(r"viewBox='([^']+)'", svg).group(1)
    return f"<svg viewBox='{vb}' class=mark><path d='{d}' fill='{fill}'/></svg>"


def moon_svg(phase: float, size: int = 34) -> str:
    """A moon at phase 0 (new) .. 0.5 (full) .. 1, lit side on the right
    while waxing, as seen from the northern hemisphere."""
    r = size / 2 - 1.5
    c = size / 2
    import math
    k = math.cos(2 * math.pi * phase)          # +1 new, -1 full
    waxing = phase < 0.5
    # lit limb: semicircle on the right (waxing) or left (waning)
    sweep_limb = 1 if waxing else 0
    rx = abs(k) * r
    # terminator bulges toward the lit side when gibbous (k < 0)
    sweep_term = (0 if k > 0 else 1) if waxing else (1 if k > 0 else 0)
    lit = (f"M{c:.2f},{c - r:.2f} A{r:.2f},{r:.2f} 0 0 {sweep_limb} {c:.2f},{c + r:.2f} "
           f"A{rx:.2f},{r:.2f} 0 0 {sweep_term} {c:.2f},{c - r:.2f} Z")
    return (f"<svg class=moon width={size} height={size} viewBox='0 0 {size} {size}'>"
            f"<circle cx={c} cy={c} r={r:.2f} fill='#5a5a5a' stroke='none' />"
            f"<path d='{lit}' fill='#fff' stroke='none'/>"
            f"<circle cx={c} cy={c} r={r:.2f} fill='none' stroke='#333' stroke-width=1.4 /></svg>")


CSS = """
@font-face{font-family:EBG;src:url(data:font/woff2;base64,%EBG%);font-weight:400 600}
@font-face{font-family:EBG;src:url(data:font/woff2;base64,%EBGI%);font-style:italic;font-weight:400 600}
@font-face{font-family:CG;src:url(data:font/woff2;base64,%CG%);font-weight:400 600}
@font-face{font-family:CG;src:url(data:font/woff2;base64,%CGI%);font-style:italic;font-weight:400 600}
@page{size:1404px 1872px;margin:0}
*{box-sizing:border-box;margin:0;padding:0}
html,body{background:#fff;color:#111;font-family:EBG;-webkit-print-color-adjust:exact;print-color-adjust:exact}
a{color:inherit;text-decoration:none}
.page{position:relative;width:1404px;height:1872px;overflow:hidden;break-after:page;page-break-after:always}
.body{position:absolute;left:%PL%px;right:%PR%px;top:40px;bottom:34px;display:flex;flex-direction:column}
.tpl{position:absolute;left:0;top:0;width:1404px;height:1872px}

/* rail */
.rail{position:absolute;right:0;top:40px;bottom:34px;width:%RAIL%px;display:flex;flex-direction:column;gap:5px}
.rail a{flex:1;display:flex;align-items:center;justify-content:center;border:1.4px solid #9a9a9a;border-right:none;
  background:#fff;color:#333;font-variant:small-caps;letter-spacing:.12em;font-size:19px;white-space:nowrap}
.rail a span{transform:rotate(-90deg);display:block}
.rail a.on{background:#111;border-color:#111;color:#fff}
.rail a.gap{margin-top:12px}

/* page furniture */
.crumbs{display:flex;align-items:center;gap:14px;font-variant:small-caps;letter-spacing:.12em;font-size:21px;color:#555;height:34px}
.crumbs a{border-bottom:1.2px solid #bbb}
.crumbs .sep{color:#aaa}
.crumbs .nav{margin-left:auto;display:flex;gap:10px}
.crumbs .nav a{border:1.4px solid #888;border-radius:6px;padding:0 16px;font-size:24px;line-height:32px;color:#222}
.mast{display:flex;align-items:flex-end;justify-content:space-between;gap:30px;padding:8px 0 12px}
.mast h1{font-family:CG;font-weight:500;font-size:62px;line-height:1;white-space:nowrap}
.mast h1 i{font-weight:500}
.mast .meta{display:flex;align-items:center;gap:16px;font-variant:small-caps;letter-spacing:.1em;font-size:22px;color:#444;white-space:nowrap}
.rule{height:1.5px;background:#222;margin-bottom:20px;flex:none}
.lbl{display:flex;align-items:center;gap:12px;font-variant:small-caps;letter-spacing:.14em;font-size:24px;color:#222;margin:0 0 9px;white-space:nowrap}
.lbl .st{width:14px;height:14px;fill:#444;flex:none}
.lbl .r{margin-left:auto;font-size:19px;color:#666}
.ruled{background-image:repeating-linear-gradient(to bottom,transparent 0 50.5px,#b4b4b4 50.5px 52px)}
.top{border-top:2px solid #222}
.grid{border:1.5px solid #8a8a8a;background-image:linear-gradient(#d2d2d2 1px,transparent 1px),linear-gradient(90deg,#d2d2d2 1px,transparent 1px);background-size:44px 44px;background-position:-1px -1px}
.dots{background-image:radial-gradient(circle,#8a8a8a 1.6px,transparent 2.2px);background-size:44px 44px;background-position:21px 21px;border:1.5px solid #bdbdbd}
.foot{display:flex;align-items:baseline;justify-content:center;gap:14px;padding-top:10px;white-space:nowrap;flex:none}
.foot q{font-family:CG;font-style:italic;font-size:21px;color:#333;quotes:"\\201C" "\\201D"}
.foot small{font-size:15px;font-variant:small-caps;letter-spacing:.12em;color:#666}
.dia{display:flex;align-items:center;gap:12px;margin:8px 0 0;flex:none}
.dia::before,.dia::after{content:'';flex:1;height:0;border-top:1.2px solid #999}
.dia i{width:8px;height:8px;border:1.3px solid #555;transform:rotate(45deg)}
table{border-collapse:collapse;width:100%;font-size:22px}
th{font-weight:400;font-variant:small-caps;letter-spacing:.1em;color:#333;text-align:left;padding:4px 10px 8px;border-bottom:2px solid #222;white-space:nowrap}
td{height:54px;border-bottom:1.5px solid #b4b4b4;padding:0 10px}
td+td,th+th{border-left:1.5px solid #d0d0d0}
.o{display:inline-block;width:22px;height:22px;border:1.8px solid #555;border-radius:50%;vertical-align:-4px}
.sq{display:inline-block;width:22px;height:22px;border:1.8px solid #555;vertical-align:-4px}
.col{display:flex;flex-direction:column}
.small{font-size:19px;font-variant:small-caps;letter-spacing:.1em;color:#555}
.mark{height:1em;width:auto}

/* calendars */
.cal{display:grid;grid-template-columns:64px repeat(7,1fr);border-top:2px solid #222;flex:1}
.cal .h{font-variant:small-caps;letter-spacing:.12em;font-size:21px;color:#333;padding:8px 10px;border-bottom:1.5px solid #222}
.cal .wk{display:flex;align-items:flex-start;justify-content:center;padding-top:10px;font-size:18px;font-variant:small-caps;letter-spacing:.08em;color:#666;border-bottom:1.5px solid #c4c4c4;border-right:1.5px solid #c4c4c4}
.cal .wk a{border:1.3px solid #999;border-radius:5px;padding:1px 6px}
.cal .d{border-bottom:1.5px solid #c4c4c4;border-right:1.5px solid #e0e0e0;padding:6px 10px;position:relative}
.cal .d a.n{font-family:CG;font-size:34px;line-height:1;color:#111;display:inline-block;min-width:42px}
.cal .d.out a.n{color:#bbb}
.cal .d .ph{display:inline-block;margin-left:6px;vertical-align:4px}
.mini{display:grid;grid-template-columns:repeat(7,1fr);gap:2px 0;font-size:19px;text-align:center}
.mini .h{font-variant:small-caps;color:#777;font-size:16px;letter-spacing:.06em;padding-bottom:4px}
.mini a{display:block;line-height:34px;color:#222}
.mini .x{color:transparent}
.mt{font-family:CG;font-size:34px;font-weight:500;display:block;margin-bottom:8px;border-bottom:1.5px solid #222;padding-bottom:4px}

/* schedule */
.sched{border-top:2px solid #222}
.sched .hr{display:flex;flex:1;border-bottom:1.5px solid #b4b4b4;position:relative}
.sched .hr::after{content:'';position:absolute;left:74px;right:0;top:50%;border-top:1.3px dotted #c8c8c8}
.sched .hr b{width:74px;font-weight:400;font-family:CG;font-size:24px;color:#444;padding:6px 0 0 4px;border-right:1.5px solid #d0d0d0}
.wday{display:flex;border-bottom:1.5px solid #b4b4b4}
.wday .dn{width:150px;padding:10px 12px;border-right:1.5px solid #d0d0d0;flex:none}
.wday .dn a{display:block}
.wday .dn .nm{font-variant:small-caps;letter-spacing:.12em;font-size:21px;color:#444}
.wday .dn .num{font-family:CG;font-size:46px;line-height:1.05;color:#111}
.wday .ln{flex:1}
.ring{display:inline-block;width:30px;height:30px;border:1.8px solid #666;border-radius:50%}

/* index */
.toc a{display:flex;align-items:baseline;gap:12px;font-size:28px;padding:6px 0;border-bottom:1.3px solid #ddd}
.toc a .lead{flex:1;border:none;background:none;border-bottom:1.6px dotted #aaa;transform:translateY(-6px)}
.toc a .pg{font-variant:small-caps;letter-spacing:.1em;color:#666;font-size:20px}
.toc h3{font-variant:small-caps;letter-spacing:.14em;font-weight:400;font-size:24px;color:#222;margin:22px 0 4px}
"""

QUOTES = [
    ("What I cannot create, I do not understand.", "Richard Feynman"),
    ("Experience is the name every one gives to their mistakes.", "Oscar Wilde, 1892"),
    ("If I have seen further it is by standing on the shoulders of Giants.", "Isaac Newton, 1675"),
    ("Do not worry about your difficulties in mathematics. I can assure you mine are still greater.", "Albert Einstein, 1943"),
    ("Nothing in life is to be feared, it is only to be understood.", "attributed to Marie Curie"),
    ("Mathematics is the art of giving the same name to different things.", "Henri Poincaré"),
]



PAPER_JS = """
() => {
  const NS='http://www.w3.org/2000/svg';
  const kinds=[['.ruled','r',52,'#b4b4b4',1.5],['.wday .ln','r',52,'#d6d6d6',1.5],['.grid','g',44,'#d2d2d2',1],['.dots','d',44,'#8a8a8a',4]];
  for(const [sel,k,p,col,w] of kinds){
    for(const el of document.querySelectorAll(sel)){
      if(el.dataset.paper) continue; el.dataset.paper=1;
      const cs=getComputedStyle(el);
      const bl=parseFloat(cs.borderLeftWidth)||0, bt=parseFloat(cs.borderTopWidth)||0;
      const W=el.clientWidth, H=el.clientHeight;
      if(!W||!H) continue;
      el.style.backgroundImage='none';
      if(cs.position==='static') el.style.position='relative';
      const svg=document.createElementNS(NS,'svg');
      svg.setAttribute('width',W); svg.setAttribute('height',H);
      svg.style.cssText='position:absolute;left:0;top:0;pointer-events:none;overflow:hidden';
      let d='';
      if(k==='r'){ for(let y=p-0.75;y<H;y+=p) d+=`M0 ${y.toFixed(2)}H${W}`; }
      if(k==='g'){ for(let y=p-0.5;y<H;y+=p) d+=`M0 ${y.toFixed(2)}H${W}`; for(let x=p-0.5;x<W;x+=p) d+=`M${x.toFixed(2)} 0V${H}`; }
      if(k==='d'){ for(let y=p/2;y<H;y+=p) for(let x=p/2;x<W;x+=p) d+=`M${x} ${y}h0`; }
      const path=document.createElementNS(NS,'path');
      path.setAttribute('d',d); path.setAttribute('stroke',col); path.setAttribute('stroke-width',w); path.setAttribute('fill','none');
      if(k==='d') path.setAttribute('stroke-linecap','round');
      svg.appendChild(path); el.appendChild(svg);
    }
  }
}
"""


class Folio:
    def __init__(self, start: dt.date, months: int, courses, daily: bool, tz: str, title: str, week_start: int = 0, left: int = 56):
        self.start = start
        self.months = [(start.year + (start.month - 1 + i) // 12, (start.month - 1 + i) % 12 + 1) for i in range(months)]
        y, m = self.months[-1]
        self.end = dt.date(y, m, calendar.monthrange(y, m)[1])
        # courses: an int, or a list of (full name, tab label)
        if isinstance(courses, int):
            courses = [(f"Course {ROMAN[i]}", f"C·{ROMAN[i]}") for i in range(courses)]
        self.course_list = courses
        self.courses = len(courses)
        self.ws = week_start      # 0 = Monday, 6 = Sunday
        self.left = left
        self.daily = daily
        self.tz = ZoneInfo(tz)
        self.title = title
        self.pages = []          # (id, html)
        self.ids = []
        # weeks: Monday of the week containing start .. Monday of week containing end
        first = self.week_of(start)
        self.weeks = []
        d = first
        while d <= self.end:
            self.weeks.append(d)
            d += dt.timedelta(days=7)
        self.days = [start + dt.timedelta(days=i) for i in range((self.end - start).days + 1)]
        self._moons()
        self.tpl = {p.stem: b64(p) for p in (ASSETS / "tpl").glob("*.png")}
        self.year_label = f"{self.months[0][0]}–{str(self.months[-1][0])[2:]}" if self.months[0][0] != self.months[-1][0] else str(self.months[0][0])

    # ---------- astronomy ----------
    def _moons(self):
        z = self.tz
        a = dt.datetime.combine(self.start - dt.timedelta(days=40), dt.time(), tzinfo=z).astimezone(dt.timezone.utc)
        b = dt.datetime.combine(self.end + dt.timedelta(days=40), dt.time(), tzinfo=z).astimezone(dt.timezone.utc)
        ev = moon.phases_between(a, b)
        self.events = {}
        for t, q in ev:
            self.events.setdefault(t.astimezone(z).date(), (q, t.astimezone(z)))
        self.newmoons = [t for t, q in ev if q == 0]

    def phase(self, d: dt.date) -> float:
        t = dt.datetime.combine(d, dt.time(12), tzinfo=self.tz).astimezone(dt.timezone.utc)
        prev = max(n for n in self.newmoons if n <= t)
        nxt = min(n for n in self.newmoons if n > t)
        return (t - prev) / (nxt - prev)

    @staticmethod
    def phase_name(p: float) -> str:
        # Days that hold a principal phase are named from the exact event
        # (see day_pages); every other day falls between two of them.
        return ["waxing crescent", "waxing gibbous", "waning gibbous", "waning crescent"][min(3, int(p * 4))]

    # ---------- ids ----------
    @staticmethod
    def did(d): return f"d{d:%Y%m%d}"
    @staticmethod
    def mid(y, m): return f"m{y}{m:02d}"
    @staticmethod
    def hid(y, m): return f"h{y}{m:02d}"
    @staticmethod
    def wid(monday): return f"w{monday:%Y%m%d}"

    def off(self, d): return (d.weekday() - self.ws) % 7
    def week_of(self, d): return d - dt.timedelta(days=self.off(d))
    def wnum(self, wstart): return self.weeks.index(wstart) + 1
    @property
    def dnames(self):
        names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        return names[self.ws:] + names[:self.ws]

    def day_target(self, d):
        """Where a date links: its day page, or its week page in the weekly edition."""
        return self.did(d) if self.daily else self.wid(self.week_of(d))

    # ---------- furniture ----------
    def rail(self, on: str) -> str:
        tabs = [("index", "Index"), ("year", "Year")]
        tabs += [(self.mid(y, m), calendar.month_abbr[m]) for y, m in self.months]
        tabs += [(f"c{i}", self.course_list[i][1]) for i in range(self.courses)]
        tabs += [("research", "Res."), ("notes", "Notes")]
        out = []
        for i, (tid, label) in enumerate(tabs):
            cls = []
            if tid == on: cls.append("on")
            if i in (2, 2 + len(self.months), 2 + len(self.months) + self.courses): cls.append("gap")
            fs = "" if len(label) <= 5 else (" style='font-size:16px;letter-spacing:.06em'" if len(label) <= 7 else " style='font-size:14px;letter-spacing:.03em'")
            out.append(f"<a href='#{tid}' class='{' '.join(cls)}'><span{fs}>{html.escape(label)}</span></a>")
        return f"<nav class=rail>{''.join(out)}</nav>"

    def crumbs(self, items, prev=None, nxt=None) -> str:
        parts = []
        for i, (href, label) in enumerate(items):
            if i: parts.append("<span class=sep>/</span>")
            parts.append(f"<a href='#{href}'>{label}</a>" if href else f"<span>{label}</span>")
        nav = ""
        if prev or nxt:
            nav = "<span class=nav>" + (f"<a href='#{prev}'>‹</a>" if prev else "") + (f"<a href='#{nxt}'>›</a>" if nxt else "") + "</span>"
        return f"<div class=crumbs>{''.join(parts)}{nav}</div>"

    def add(self, pid, body, on, template=None, raw=False):
        inner = body if raw else f"<div class=body>{body}</div>"
        bg = f"<img class=tpl src='data:image/png;base64,{self.tpl[template]}'>" if template else ""
        self.pages.append(f"<section class=page id='{pid}'>{bg}{inner}{self.rail(on)}</section>")
        self.ids.append(pid)

    @staticmethod
    def lbl(t, right=""):
        return f"<div class=lbl>{STAR}{t}" + (f"<span class=r>{right}</span>" if right else "") + "</div>"

    @staticmethod
    def foot(q, who):
        return f"<div class=dia><i></i></div><div class=foot><q>{q}</q><small>{who}</small></div>"

    # ---------- pages ----------
    def cover(self):
        body = f"""
<div style="flex:1;display:flex;flex-direction:column;justify-content:center;align-items:flex-start;padding-left:40px">
  <div class=small style="font-size:26px;letter-spacing:.3em">the scholium</div>
  <div style="font-family:CG;font-size:200px;line-height:.9;margin:18px 0 10px;font-weight:500">The <i>Folio</i></div>
  <div style="font-family:CG;font-style:italic;font-size:46px;color:#333">{self.title}</div>
  <div style="width:420px;height:1.5px;background:#222;margin:56px 0 30px"></div>
  <div class=small style="font-size:24px">this folio belongs to</div>
  <div style="width:760px;border-bottom:1.5px solid #888;height:70px"></div>
  <div class=small style="font-size:24px;margin-top:34px">if found, please return to</div>
  <div style="width:760px;border-bottom:1.5px solid #888;height:70px"></div>
</div>
<div style="display:flex;align-items:center;justify-content:space-between;font-size:20px;color:#666" class=small>
  <a href="#index" style="border:1.4px solid #888;border-radius:6px;padding:6px 18px;color:#222">open the index ›</a>
  <span style="display:flex;align-items:center;gap:12px;font-size:44px">{mark_svg('#222')}</span>
</div>"""
        self.add("cover", body, "")

    def index(self):
        months = "".join(f"<a href='#{self.mid(y, m)}'>{calendar.month_name[m]} {y}<span class=lead></span><span class=pg>calendar</span></a>" for y, m in self.months)
        courses = "".join(f"<a href='#c{i}'>{html.escape(self.course_list[i][0])}<span class=lead></span><span class=pg>hub · logs · notes</span></a>" for i in range(self.courses))
        tmap = lambda tid: f"<a href='#{tid}-map' style='padding-left:28px;font-size:24px'>term map<span class=lead></span><span class=pg>weeks × courses</span></a>" if self.courses else ""
        terms = "".join(f"<a href='#{tid}'>{name}<span class=lead></span><span class=pg>deadlines</span></a>{tmap(tid)}" for tid, name in self.terms)
        how = f"""<p>Tap a tab on the right edge to jump to any month{" or course" if self.courses else ""}. On dated pages, the line at the top shows where you are; tap any part of it to go up a level, and use ‹ › to step back or forward.</p>
<p style="margin-top:14px">In a month, tap a date to open its day, and a week number to open its week. Moon phases are computed for your time zone.</p>"""
        body = f"""{self.crumbs([("cover", "The Folio"), (None, "Index")])}
<div class=mast><h1>The <i>Index</i></h1><div class=meta>{self.title}</div></div><div class=rule></div>
<div style="display:flex;gap:56px;flex:1">
 <div class="col toc" style="flex:1">
  <h3>The year</h3><a href='#year'>Year at a glance<span class=lead></span><span class=pg>12 months</span></a>{terms}
  <h3>Months</h3>{months}
 </div>
 <div class="col toc" style="flex:1">
  {"<h3>Courses</h3>" + courses if self.courses else ""}
  <h3>Elsewhere</h3><a href='#research'>Research<span class=lead></span><span class=pg>papers &amp; talks</span></a><a href='#notes'>Notes<span class=lead></span><span class=pg>ruled · grid · dot</span></a>
  <h3>How the Folio works</h3><div style="font-size:23px;line-height:1.45;color:#333">{how}</div>
 </div>
</div>
{self.foot("A scholium is the note in the margin that explains what just happened.", "The Scholium")}"""
        self.add("index", body, "index")

    def year(self):
        cells = []
        for y, m in self.months:
            first = dt.date(y, m, 1)
            lead = self.off(first)
            n = calendar.monthrange(y, m)[1]
            days = "".join("<span class=x>.</span>" for _ in range(lead))
            for dd in range(1, n + 1):
                d = dt.date(y, m, dd)
                days += f"<a href='#{self.day_target(d)}'>{dd}</a>"
            hd = "".join(f"<span class=h>{c[0].lower()}</span>" for c in self.dnames)
            cells.append(f"<div><a class=mt href='#{self.mid(y, m)}'>{calendar.month_name[m]} <span style='color:#777;font-size:26px'>{y}</span></a><div class=mini>{hd}{days}</div></div>")
        cols = 3
        body = f"""{self.crumbs([("index", "Index"), (None, "Year")])}
<div class=mast><h1>The <i>Year</i></h1><div class=meta>{self.year_label}</div></div><div class=rule></div>
<div style="display:grid;grid-template-columns:repeat({cols},1fr);gap:34px 44px;align-content:start;flex:none">{''.join(cells)}</div>
<div style="height:30px;flex:none"></div>{self.lbl("Key dates", "first day · breaks · finals")}<div class="ruled top" style="flex:1"></div>
{self.foot(*QUOTES[5])}"""
        self.add("year", body, "year")

    @property
    def terms(self):
        """Split the months into terms: Aug–Dec, Jan–May, Jun–Jul style blocks."""
        out, cur, name = [], [], None
        def term_of(m):
            return "Fall" if m >= 8 else ("Spring" if m <= 5 else "Summer")
        for y, m in self.months:
            t = term_of(m)
            if cur and t != name:
                out.append(cur); cur = []
            cur.append((y, m)); name = t
        if cur: out.append(cur)
        res = []
        for blk in out:
            (y0, m0), (y1, m1) = blk[0], blk[-1]
            res.append((f"t{y0}{m0:02d}", f"{term_of(m0)} {y0}"))
        self._term_months = {f"t{b[0][0]}{b[0][1]:02d}": b for b in out}
        return res

    def term_pages(self):
        rows = "".join("<tr><td style='width:170px'></td><td></td><td style='width:150px'></td><td style='width:110px'></td><td style='width:70px;text-align:center'><span class=sq></span></td></tr>" for _ in range(25))
        for tid, name in self.terms:
            body = f"""{self.crumbs([("index", "Index"), (None, name)])}
<div class=mast><h1>{name.split()[0]} <i>Deadlines</i></h1><div class=meta>{name.split()[1]}</div></div><div class=rule></div>
<div class=small style="margin:-6px 0 14px;font-size:20px">{"Copy every due date from your syllabi here once, at the start of term." if self.courses else "Write every deadline here once, at the start of term."}</div>
<table><tr><th>{"course" if self.courses else "project"}</th><th>assignment / exam</th><th>due</th><th>weight</th><th>done</th></tr>{rows}</table>
<div style="flex:1"></div>{self.foot(*QUOTES[1])}"""
            self.add(tid, body, "year")
            if self.courses: self.term_map(tid, name)

    def term_map(self, tid, name):
        months = set(self._term_months[tid])
        weeks = [w for w in self.weeks if any(((w + dt.timedelta(days=k)).year, (w + dt.timedelta(days=k)).month) in months for k in range(7))]
        heads = "".join(f"<th style='text-align:center'>{html.escape(c[1])}</th>" for c in self.course_list)
        rows = ""
        for w in weeks:
            e = w + dt.timedelta(days=6)
            rows += (f"<tr><td style='width:150px;white-space:nowrap'><a href='#{self.wid(w)}' style='font-family:CG;font-size:26px'>week {self.wnum(w)}</a>"
                     f"<span style='display:block;font-size:15px;font-variant:small-caps;letter-spacing:.08em;color:#777;margin-top:-4px'>{w.day} {calendar.month_abbr[w.month]} – {e.day} {calendar.month_abbr[e.month]}</span></td>"
                     + "<td></td>" * self.courses + "</tr>")
        h = max(46, min(70, (1440 // max(1, len(weeks)))))
        body = f"""{self.crumbs([("index", "Index"), (tid, name), (None, "map")])}
<div class=mast><h1>{name.split()[0]} <i>Map</i></h1><div class=meta>{name.split()[1]}</div></div><div class=rule></div>
<div class=small style="margin:-6px 0 14px;font-size:20px">One row per week, one column per course. Write what is due, mark exams, and see the crunch weeks coming.</div>
<table class=map style="table-layout:fixed"><tr><th style='width:150px'>week</th>{heads}</tr>{rows}</table>
<style>.map td{{height:{h}px}}</style>
<div style="flex:1"></div>"""
        self.add(f"{tid}-map", body, "year")

    def month_pages(self):
        for i, (y, m) in enumerate(self.months):
            first = dt.date(y, m, 1)
            n = calendar.monthrange(y, m)[1]
            gs = self.week_of(first)
            rows = ((self.off(first) + n) + 6) // 7
            hd = "<div class=h></div>" + "".join(f"<div class=h>{d}</div>" for d in self.dnames)
            cells = []
            for r in range(rows):
                monday = gs + dt.timedelta(days=7 * r)
                wk = self.wnum(monday) if monday in self.weeks else ""
                cells.append(f"<div class=wk><a href='#{self.wid(monday)}'>w{wk}</a></div>")
                for c in range(7):
                    d = monday + dt.timedelta(days=c)
                    inside = d.month == m
                    ph = ""
                    if d in self.events and inside:
                        q, _ = self.events[d]
                        ph = f"<span class=ph title='{moon.PHASE_NAMES[q]}'>{moon_svg([0, .25, .5, .75][q], 26)}</span>"
                    link = f"<a class=n href='#{self.day_target(d)}'>{d.day}</a>" if self.start <= d <= self.end else f"<span class=n style='font-family:CG;font-size:34px;color:#ccc'>{d.day}</span>"
                    cells.append(f"<div class='d{'' if inside else ' out'}'>{link}{ph}</div>")
            prev = self.mid(*self.months[i - 1]) if i else None
            nxt = self.mid(*self.months[i + 1]) if i + 1 < len(self.months) else None
            body = f"""{self.crumbs([("year", self.year_label), (None, calendar.month_name[m]), (self.hid(y, m), "habits")], prev, nxt)}
<div class=mast><h1>{calendar.month_name[m]} <i style="color:#666">{y}</i></h1><div class=meta><a href='#{self.hid(y, m)}' style="border:1.4px solid #888;border-radius:6px;padding:2px 14px">habits ›</a></div></div><div class=rule style="margin-bottom:0"></div>
<div class=cal style="grid-template-rows:auto repeat({rows},1fr)">{hd}{''.join(cells)}</div>
<div style="display:flex;gap:34px;height:330px;margin-top:22px;flex:none">
 <div class=col style="flex:1">{self.lbl("This month")}<div class="ruled top" style="flex:1"></div></div>
 <div class=col style="flex:1">{self.lbl("Due this month")}<div class="ruled top" style="flex:1"></div></div>
</div>"""
            self.add(self.mid(y, m), body, self.mid(y, m))
            # habits: the Month template for this month's length, with a breadcrumb strip
            tpl = f"the-month-{n if n in (28, 30, 31) else (30 if n == 29 else n)}"
            self.add(self.hid(y, m), "", self.mid(y, m), template=tpl, raw=True)

    def week_pages(self):
        for i, monday in enumerate(self.weeks):
            sunday = monday + dt.timedelta(days=6)
            wk = i + 1
            span = f"{monday.day} {calendar.month_abbr[monday.month]} – {sunday.day} {calendar.month_abbr[sunday.month]} {sunday.year}"
            m_on = self.mid(monday.year, monday.month) if (monday.year, monday.month) in self.months else self.mid(sunday.year, sunday.month)
            mm = (monday.year, monday.month) if (monday.year, monday.month) in self.months else (sunday.year, sunday.month)
            days = []
            for k in range(7):
                d = monday + dt.timedelta(days=k)
                inr = self.start <= d <= self.end
                nm = calendar.day_abbr[d.weekday()]
                num = f"<a href='#{self.did(d)}'>" if (self.daily and inr) else "<span>"
                endt = "</a>" if (self.daily and inr) else "</span>"
                ph = ""
                if d in self.events:
                    ph = f"<span style='margin-left:8px'>{moon_svg([0, .25, .5, .75][self.events[d][0]], 22)}</span>"
                days.append(f"<div class=wday style='flex:1'><div class=dn>{num}<span class=nm>{nm}</span><span class=num style='display:block'>{d.day}</span>{endt}{ph}</div><div class=ln></div></div>")
            prev = self.wid(self.weeks[i - 1]) if i else None
            nxt = self.wid(self.weeks[i + 1]) if i + 1 < len(self.weeks) else None
            habits = "".join(f"<div style='display:flex;align-items:center;gap:8px;margin:8px 0'><b style='flex:1;border-bottom:1.5px solid #9a9a9a;height:30px'></b>{''.join('<span class=ring></span>' for _ in range(7))}</div>" for _ in range(4))
            due = "".join("<tr><td></td><td style='width:84px'></td><td style='width:52px;text-align:center'><span class=sq></span></td></tr>" for _ in range(9))
            body = f"""{self.crumbs([("year", self.year_label), (m_on, calendar.month_name[mm[1]]), (None, f"week {wk}")], prev, nxt)}
<div class=mast><h1>Week <i>{wk}</i></h1><div class=meta>{span}</div></div><div class=rule style="margin-bottom:0"></div>
<div style="display:flex;gap:30px;flex:1;min-height:0">
 <div class=col style="flex:1;border-top:2px solid #222">{''.join(days)}</div>
 <div class=col style="width:430px">
  {self.lbl("The one goal")}<div class="ruled top" style="height:156px;flex:none"></div>
  <div style="height:16px"></div>{self.lbl("Due")}<table><tr><th>task</th><th>due</th><th></th></tr>{due}</table>
  <div style="height:16px"></div>{self.lbl("Habits", " ".join(c[0].lower() for c in self.dnames))}{habits}
  <div style="height:10px"></div>{self.lbl("Wins")}<div class="ruled top" style="flex:1"></div>
 </div>
</div>"""
            self.add(self.wid(monday), body, m_on)

    def day_pages(self):
        for i, d in enumerate(self.days):
            p = self.phase(d)
            pn = self.phase_name(p)
            if d in self.events:
                q, t = self.events[d]
                pn = f"{moon.PHASE_NAMES[q]} at {t:%H:%M}"
            doy = d.timetuple().tm_yday
            monday = self.week_of(d)
            wk = self.wnum(monday)
            prev = self.did(self.days[i - 1]) if i else None
            nxt = self.did(self.days[i + 1]) if i + 1 < len(self.days) else None
            hours = "".join(f"<div class=hr><b>{h if h <= 12 else h - 12}</b></div>" for h in range(6, 24))
            todo = "".join("<tr><td></td><td style='width:84px'></td><td style='width:52px;text-align:center'><span class=sq></span></td></tr>" for _ in range(7))
            body = f"""{self.crumbs([("year", self.year_label), (self.mid(d.year, d.month), calendar.month_name[d.month]), (self.wid(monday), f"week {wk}"), (None, f"{d.day}")], prev, nxt)}
<div class=mast><h1>{calendar.day_name[d.weekday()]}<i style="color:#666;font-size:46px"> &nbsp;{d.day} {calendar.month_name[d.month]}</i></h1>
 <div class=meta>{moon_svg(p, 40)}<span>{pn}</span><span style="color:#999">·</span><span>day {doy}</span></div></div><div class=rule style="margin-bottom:0"></div>
<div style="display:flex;gap:30px;flex:1;min-height:0">
 <div class="sched col" style="width:400px">{hours}</div>
 <div class=col style="flex:1;padding-top:14px">
  {self.lbl("Three things")}{''.join(f"<div style='display:flex;align-items:flex-end;gap:12px;height:52px;border-bottom:1.5px solid #b4b4b4'><span style='font-family:CG;font-size:28px;color:#555;width:22px'>{n}</span></div>" for n in (1, 2, 3))}
  <div style="height:18px"></div>{self.lbl("To do")}<table><tr><th>task</th><th>due</th><th></th></tr>{todo}</table>
  <div style="height:18px"></div>{self.lbl("What I learned today", "close the book first")}<div class=grid style="flex:1"></div>
 </div>
</div>"""
            self.add(self.did(d), body, self.mid(d.year, d.month))

    def course_pages(self):
        plan = [("the-class-hub", "Class Hub", 1), ("the-exam-plan", "Exam Plan", 2), ("the-error-log", "Error Log", 4),
                ("the-blurt", "Blurt", 4), ("the-time-trial", "Time Trial", 2)]
        notes = 12
        for c in range(self.courses):
            cid = f"c{c}"
            toc = []
            ids = []
            for tpl, name, k in plan:
                for j in range(k):
                    pid = f"{cid}-{tpl[4:]}-{j}"
                    ids.append((pid, tpl))
                toc.append(f"<a href='#{cid}-{tpl[4:]}-0'>{name}{'s' if k > 1 else ''}<span class=lead></span><span class=pg>{k} page{'s' if k > 1 else ''}</span></a>")
            toc.append(f"<a href='#{cid}-notes-0'>Lecture notes<span class=lead></span><span class=pg>{notes} pages</span></a>")
            fields = "".join(f"<div style='display:flex;align-items:flex-end;gap:14px;margin-top:22px' class=small><span style='width:170px;font-size:23px'>{k}</span><b style='flex:1;border-bottom:1.5px solid #9a9a9a;height:34px'></b></div>" for k in ["course", "number", "professor", "room / time"])
            cname = html.escape(self.course_list[c][0])
            title = f"Course <i>{ROMAN[c]}</i>" if cname.startswith("Course ") else f"<i>{cname}</i>"
            body = f"""{self.crumbs([("index", "Index"), (None, cname)])}
<div class=mast><h1>{title}</h1><div class=meta>{STAR.replace('class=st', 'style="width:18px;height:18px;fill:#444"')}</div></div><div class=rule></div>
{fields}
<div class=toc style="margin-top:46px">{''.join(toc)}</div>
<div style="flex:1"></div>
{self.foot(*QUOTES[c % len(QUOTES)])}"""
            self.add(cid, body, cid)
            for pid, tpl in ids:
                self.add(pid, "", cid, template=tpl, raw=True)
            for j in range(notes):
                kind = ["ruled", "grid", "ruled", "dots"][j % 4]
                nb = f"""{self.crumbs([(cid, cname), (None, f"notes {j + 1}")], f"{cid}-notes-{j - 1}" if j else None, f"{cid}-notes-{j + 1}" if j + 1 < notes else None)}
<div style="display:flex;gap:30px;align-items:flex-end;padding:10px 0 12px" class=small><span style="font-size:23px">topic</span><b style="flex:1;border-bottom:1.5px solid #9a9a9a;height:32px"></b><span style="font-size:23px">date</span><b style="width:200px;border-bottom:1.5px solid #9a9a9a;height:32px"></b></div><div class=rule style="margin-bottom:14px"></div>
<div class="{kind}{' top' if kind == 'ruled' else ''}" style="flex:1"></div>"""
                self.add(f"{cid}-notes-{j}", nb, cid)

    def research_pages(self, n=12):
        for j in range(n):
            self.add("research" if j == 0 else f"research-{j}", "", "research", template="the-research", raw=True)

    def notes_pages(self, n=30):
        for j in range(n):
            kind = ["ruled", "grid", "dots"][j // 10]
            nb = f"""{self.crumbs([("index", "Index"), (None, f"notes · {kind if kind != 'dots' else 'dot grid'} · {j % 10 + 1}")], ("notes" if j == 1 else f"notes-{j - 1}") if j else None, f"notes-{j + 1}" if j + 1 < n else None)}
<div style="height:12px"></div><div class="{kind}{' top' if kind == 'ruled' else ''}" style="flex:1"></div>"""
            self.add("notes" if j == 0 else f"notes-{j}", nb, "notes")

    def build(self):
        self.cover(); self.index(); self.year(); self.term_pages(); self.month_pages(); self.week_pages()
        if self.daily: self.day_pages()
        self.course_pages(); self.research_pages(); self.notes_pages()
        css = (CSS.replace("%EBG%", b64(ASSETS / "fonts/ebg-roman.woff2")).replace("%EBGI%", b64(ASSETS / "fonts/ebg-italic.woff2"))
               .replace("%CG%", b64(ASSETS / "fonts/cg-roman.woff2")).replace("%CGI%", b64(ASSETS / "fonts/cg-italic.woff2"))
               .replace("%PL%", str(self.left)).replace("%PR%", str(PAD_R)).replace("%RAIL%", str(RAIL)))
        return f"<!doctype html><html><head><meta charset=utf-8><title>The Folio</title><style>{css}</style></head><body>{''.join(self.pages)}</body></html>"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2026-08")
    ap.add_argument("--months", type=int, default=12)
    ap.add_argument("--courses", type=int, default=6)
    ap.add_argument("--weekly", action="store_true", help="leave out the day pages")
    ap.add_argument("--tz", default="America/New_York")
    ap.add_argument("--sunday", action="store_true", help="weeks start on Sunday")
    ap.add_argument("--left", type=int, default=56, help="left margin in px, for the Nomad toolbar")
    ap.add_argument("--course-names", default=None,
                    help='comma-separated "Full name:TAB" pairs, e.g. "Quantum Mechanics:QM,Real Analysis:Analysis"')
    ap.add_argument("--out", default=None)
    ap.add_argument("--html-only", action="store_true")
    a = ap.parse_args()
    y, m = map(int, a.start.split("-"))
    start = dt.date(y, m, 1)
    courses = a.courses
    if a.course_names:
        courses = []
        for part in a.course_names.split(","):
            full, _, tab = part.partition(":")
            courses.append((full.strip(), (tab or full).strip()[:8]))
    f = Folio(start, a.months, courses, not a.weekly, a.tz, "", week_start=6 if a.sunday else 0, left=a.left)
    f.title = f"Academic year {f.year_label}"
    doc = f.build()
    out = pathlib.Path(a.out or HERE / "out" / f"the-folio-{f.year_label.replace('–', '-')}-{'weekly' if a.weekly else 'daily'}.pdf").resolve()
    out.parent.mkdir(exist_ok=True)
    hp = out.with_suffix(".html")
    hp.write_text(doc)
    print(f"{len(f.pages)} pages -> {hp.name}")
    if a.html_only:
        return
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        pg = b.new_page(viewport={"width": W, "height": H})
        pg.goto(hp.as_uri(), wait_until="load")
        pg.evaluate("document.fonts.ready")
        pg.evaluate(PAPER_JS)
        pg.pdf(path=str(out), width=f"{W}px", height=f"{H}px", print_background=True, margin={"top": "0", "right": "0", "bottom": "0", "left": "0"})
        b.close()
    print(f"wrote {out} ({out.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
