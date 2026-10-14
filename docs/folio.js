/*
 * The Folio: a hyperlinked academic-year planner for e-ink tablets.
 * One generator, used by the web builder and by the command-line build.
 *
 *   Folio.render(config, container)  -> builds every page into container
 *   Folio.paper(root)                 -> draws ruled, grid and dot paper as SVG
 *
 * Dates are integer day numbers (days since 1970-01-01), so nothing here
 * depends on the time zone of the computer that runs it. Only the moon
 * phases use a time zone, through Intl, to put each phase on its local date.
 */
(function (global) {
  "use strict";

  const RAIL = 54;
  const ROMAN = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII"];
  const MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
  const MABBR = MONTHS.map((m) => m.slice(0, 3));
  const DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
  const DABBR = DAYS.map((d) => d.slice(0, 3));
  const STARP = "M12 1.5 14.3 9.7 22.5 12 14.3 14.3 12 22.5 9.7 14.3 1.5 12 9.7 9.7z";
  const STAR = `<svg class=st viewBox='0 0 24 24'><path d='${STARP}'/></svg>`;
  const PHASE_NAMES = ["new moon", "first quarter", "full moon", "last quarter"];
  const QUOTES = [
    ["What I cannot create, I do not understand.", "Richard Feynman"],
    ["Experience is the name every one gives to their mistakes.", "Oscar Wilde, 1892"],
    ["If I have seen further it is by standing on the shoulders of Giants.", "Isaac Newton, 1675"],
    ["Do not worry about your difficulties in mathematics. I can assure you mine are still greater.", "Albert Einstein, 1943"],
    ["Nothing in life is to be feared, it is only to be understood.", "attributed to Marie Curie"],
    ["Mathematics is the art of giving the same name to different things.", "Henri Poincaré"],
  ];

  const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const pad = (n) => String(n).padStart(2, "0");

  /* ---------- calendar arithmetic on day numbers ---------- */
  const dayNum = (y, m, d) => Math.round(Date.UTC(y, m - 1, d) / 864e5);
  const ymd = (n) => { const t = new Date(n * 864e5); return { y: t.getUTCFullYear(), m: t.getUTCMonth() + 1, d: t.getUTCDate() }; };
  const weekday = (n) => (((n + 3) % 7) + 7) % 7; // 0 = Monday
  const monthLen = (y, m) => new Date(Date.UTC(y, m, 0)).getUTCDate();
  const dayOfYear = (n) => n - dayNum(ymd(n).y, 1, 1) + 1;
  const key = (n) => { const t = ymd(n); return `${t.y}${pad(t.m)}${pad(t.d)}`; };

  /* ---------- moon: Meeus, Astronomical Algorithms, ch. 49 ---------- */
  const DELTA_T = 70; // s
  function phaseJDE(k) {
    const T = k / 1236.85, r = Math.PI / 180, s = Math.sin;
    let jde = 2451550.09766 + 29.530588861 * k + 0.00015437 * T * T - 0.00000015 * T ** 3 + 0.00000000073 * T ** 4;
    const E = 1 - 0.002516 * T - 0.0000074 * T * T;
    const M = r * (2.5534 + 29.1053567 * k - 0.0000014 * T * T - 0.00000011 * T ** 3);
    const Mp = r * (201.5643 + 385.81693528 * k + 0.0107582 * T * T + 0.00001238 * T ** 3 - 0.000000058 * T ** 4);
    const F = r * (160.7108 + 390.67050284 * k - 0.0016118 * T * T - 0.00000227 * T ** 3 + 0.000000011 * T ** 4);
    const Om = r * (124.7746 - 1.56375588 * k + 0.0020672 * T * T + 0.00000215 * T ** 3);
    const frac = Math.round(((k % 1) + 1) % 1 * 4) % 4;
    let c;
    if (frac === 0 || frac === 2) {
      const a = frac === 0 ? [-0.4072, 0.17241, 0.01608, 0.01039, 0.00739, -0.00514, 0.00208] : [-0.40614, 0.17302, 0.01614, 0.01043, 0.00734, -0.00515, 0.00209];
      c = a[0] * s(Mp) + a[1] * E * s(M) + a[2] * s(2 * Mp) + a[3] * s(2 * F) + a[4] * E * s(Mp - M) + a[5] * E * s(Mp + M) + a[6] * E * E * s(2 * M)
        - 0.00111 * s(Mp - 2 * F) - 0.00057 * s(Mp + 2 * F) + 0.00056 * E * s(2 * Mp + M) - 0.00042 * s(3 * Mp)
        + 0.00042 * E * s(M + 2 * F) + 0.00038 * E * s(M - 2 * F) - 0.00024 * E * s(2 * Mp - M) - 0.00017 * s(Om);
    } else {
      c = -0.62801 * s(Mp) + 0.17172 * E * s(M) - 0.01183 * E * s(Mp + M) + 0.00862 * s(2 * Mp) + 0.00804 * s(2 * F)
        + 0.00454 * E * s(Mp - M) + 0.00204 * E * E * s(2 * M) - 0.0018 * s(Mp - 2 * F) - 0.0007 * s(Mp + 2 * F) - 0.0004 * s(3 * Mp)
        - 0.00034 * E * s(2 * Mp - M) + 0.00032 * E * s(M + 2 * F) + 0.00032 * E * s(M - 2 * F) - 0.00028 * E * E * s(Mp + 2 * M)
        + 0.00027 * E * s(2 * Mp + M) - 0.00017 * s(Om);
      const W = 0.00306 - 0.00038 * E * Math.cos(M) + 0.00026 * Math.cos(Mp) - 0.00002 * Math.cos(Mp - M) + 0.00002 * Math.cos(Mp + M) + 0.00002 * Math.cos(2 * F);
      c += frac === 1 ? W : -W;
    }
    return jde + c;
  }
  const jdeToMs = (jde) => (jde - 2440587.5) * 864e5 - DELTA_T * 1000;

  function phasesBetween(msA, msB) {
    const yr = 1970 + msA / (365.25 * 864e5);
    let k = Math.floor((yr - 2000) * 12.3685) - 2;
    const out = [];
    for (;;) {
      for (let q = 0; q < 4; q++) {
        const t = jdeToMs(phaseJDE(k + q / 4));
        if (t > msB) return out;
        if (t >= msA) out.push([t, q]);
      }
      k++;
    }
  }

  /* ---------- time zones ---------- */
  function zoned(tz) {
    const fmt = new Intl.DateTimeFormat("en-US", { timeZone: tz, hourCycle: "h23", year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", second: "2-digit" });
    const parts = (ms) => { const o = {}; for (const p of fmt.formatToParts(new Date(ms))) o[p.type] = p.value; return o; };
    const offset = (ms) => { const p = parts(ms); return Date.UTC(+p.year, +p.month - 1, +p.day, +p.hour % 24, +p.minute, +p.second) - Math.floor(ms / 1000) * 1000; };
    return {
      local(ms) { const p = parts(ms); return { day: dayNum(+p.year, +p.month, +p.day), hh: p.hour % 24, mm: p.minute }; },
      instant(n, hour) { const guess = n * 864e5 + hour * 36e5; return guess - offset(guess - offset(guess)); },
    };
  }

  /* ---------- drawing helpers ---------- */
  function moonSvg(phase, size = 34) {
    const r = size / 2 - 1.5, c = size / 2;
    const k = Math.cos(2 * Math.PI * phase), waxing = phase < 0.5;
    const limb = waxing ? 1 : 0, rx = Math.abs(k) * r;
    const term = waxing ? (k > 0 ? 0 : 1) : (k > 0 ? 1 : 0);
    const f = (x) => x.toFixed(2);
    const lit = `M${f(c)},${f(c - r)} A${f(r)},${f(r)} 0 0 ${limb} ${f(c)},${f(c + r)} A${f(rx)},${f(r)} 0 0 ${term} ${f(c)},${f(c - r)} Z`;
    return `<svg class=moon width=${size} height=${size} viewBox='0 0 ${size} ${size}'><circle cx=${c} cy=${c} r=${f(r)} fill='#5a5a5a'/><path d='${lit}' fill='#fff'/><circle cx=${c} cy=${c} r=${f(r)} fill='none' stroke='#333' stroke-width=1.4 /></svg>`;
  }
  function markSvg(fill) {
    const m = global.SCHOL_MARK;
    return m ? `<svg viewBox='${m.vb}' class=mark><path d='${m.d}' fill='${fill}'/></svg>` : "";
  }

  const CSS = `
@page{size:1404px 1872px;margin:0}
.folio *{box-sizing:border-box;margin:0;padding:0}
.folio{color:#111;font-family:EBG,Georgia,serif;-webkit-print-color-adjust:exact;print-color-adjust:exact}
.folio a{color:inherit;text-decoration:none}
.folio .page{position:relative;width:1404px;height:1872px;overflow:hidden;background:#fff;break-after:page;page-break-after:always}
.folio .body{position:absolute;right:${RAIL + 24}px;top:40px;bottom:34px;display:flex;flex-direction:column}
.folio .tpl{position:absolute;left:0;top:0;width:1404px;height:1872px}
.folio .rail{position:absolute;right:0;top:40px;bottom:34px;width:${RAIL}px;display:flex;flex-direction:column;gap:5px}
.folio .rail a{position:relative;flex:1;display:flex;align-items:center;justify-content:center;border:1.4px solid #9a9a9a;border-right:none;color:#333;font-variant:small-caps;letter-spacing:.12em;font-size:19px;white-space:nowrap}
.folio .rail a span{transform:rotate(-90deg);display:block;position:relative}
.folio .rail a.on{border-color:#111;color:#fff}
.folio .rail a.on svg{position:absolute;inset:0;width:100%;height:100%}
.folio .rail a.gap{margin-top:12px}
.folio .crumbs{display:flex;align-items:center;gap:14px;font-variant:small-caps;letter-spacing:.12em;font-size:21px;color:#555;height:34px}
.folio .crumbs a{border-bottom:1.2px solid #bbb}
.folio .crumbs .sep{color:#aaa}
.folio .crumbs .nav{margin-left:auto;display:flex;gap:10px}
.folio .crumbs .nav a{border:1.4px solid #888;border-radius:6px;padding:0 16px;font-size:24px;line-height:32px;color:#222}
.folio .mast{display:flex;align-items:flex-end;justify-content:space-between;gap:30px;padding:8px 0 12px}
.folio .mast h1{font-family:CG,Georgia,serif;font-weight:500;font-size:62px;line-height:1;white-space:nowrap}
.folio .mast h1 i{font-weight:500}
.folio .mast .meta{display:flex;align-items:center;gap:16px;font-variant:small-caps;letter-spacing:.1em;font-size:22px;color:#444;white-space:nowrap}
.folio .rule{height:0;border-top:1.5px solid #222;margin-bottom:20px;flex:none}
.folio .lbl{display:flex;align-items:center;gap:12px;font-variant:small-caps;letter-spacing:.14em;font-size:24px;color:#222;margin:0 0 9px;white-space:nowrap}
.folio .lbl .st{width:14px;height:14px;fill:#444;flex:none}
.folio .lbl .r{margin-left:auto;font-size:19px;color:#666}
.folio .top{border-top:2px solid #222}
.folio .grid{border:1.5px solid #8a8a8a}
.folio .dots{border:1.5px solid #bdbdbd}
.folio .foot{display:flex;align-items:baseline;justify-content:center;gap:14px;padding-top:10px;white-space:nowrap;flex:none}
.folio .foot q{font-family:CG,Georgia,serif;font-style:italic;font-size:21px;color:#333;quotes:"\\201C" "\\201D"}
.folio .foot small{font-size:15px;font-variant:small-caps;letter-spacing:.12em;color:#666}
.folio .dia{display:flex;align-items:center;gap:12px;margin:8px 0 0;flex:none}
.folio .dia::before,.folio .dia::after{content:'';flex:1;height:0;border-top:1.2px solid #999}
.folio .dia i{width:8px;height:8px;border:1.3px solid #555;transform:rotate(45deg)}
.folio table{border-collapse:collapse;width:100%;font-size:22px}
.folio th{font-weight:400;font-variant:small-caps;letter-spacing:.1em;color:#333;text-align:left;padding:4px 10px 8px;border-bottom:2px solid #222;white-space:nowrap}
.folio td{height:54px;border-bottom:1.5px solid #b4b4b4;padding:0 10px}
.folio td+td,.folio th+th{border-left:1.5px solid #d0d0d0}
.folio .sq{display:inline-block;width:22px;height:22px;border:1.8px solid #555;vertical-align:-4px}
.folio .col{display:flex;flex-direction:column}
.folio .small{font-size:19px;font-variant:small-caps;letter-spacing:.1em;color:#555}
.folio .mark{height:1em;width:auto}
.folio .cal{display:grid;grid-template-columns:64px repeat(7,1fr);border-top:2px solid #222;flex:1}
.folio .cal .h{font-variant:small-caps;letter-spacing:.12em;font-size:21px;color:#333;padding:8px 10px;border-bottom:1.5px solid #222}
.folio .cal .wk{display:flex;align-items:flex-start;justify-content:center;padding-top:10px;font-size:18px;font-variant:small-caps;letter-spacing:.08em;color:#666;border-bottom:1.5px solid #c4c4c4;border-right:1.5px solid #c4c4c4}
.folio .cal .wk a{border:1.3px solid #999;border-radius:5px;padding:1px 6px}
.folio .cal .d{border-bottom:1.5px solid #c4c4c4;border-right:1.5px solid #e0e0e0;padding:6px 10px;position:relative}
.folio .cal .d .n{font-family:CG,Georgia,serif;font-size:34px;line-height:1;color:#111;display:inline-block;min-width:42px}
.folio .cal .d.out .n{color:#bbb}
.folio .cal .d .n.dead{color:#ccc}
.folio .cal .d .ph{display:inline-block;margin-left:6px;vertical-align:4px}
.folio .mini{display:grid;grid-template-columns:repeat(7,1fr);gap:2px 0;font-size:19px;text-align:center}
.folio .mini .h{font-variant:small-caps;color:#777;font-size:16px;letter-spacing:.06em;padding-bottom:4px}
.folio .mini a{display:block;line-height:34px;color:#222}
.folio .mini .x{color:transparent}
.folio .mt{font-family:CG,Georgia,serif;font-size:34px;font-weight:500;display:block;margin-bottom:8px;border-bottom:1.5px solid #222;padding-bottom:4px}
.folio .sched{border-top:2px solid #222}
.folio .sched .hr{display:flex;flex:1;border-bottom:1.5px solid #b4b4b4;position:relative}
.folio .sched .hr::after{content:'';position:absolute;left:74px;right:0;top:50%;border-top:1.3px dotted #c8c8c8}
.folio .sched .hr b{width:74px;font-weight:400;font-family:CG,Georgia,serif;font-size:24px;color:#444;padding:6px 0 0 4px;border-right:1.5px solid #d0d0d0}
.folio .wday{display:flex;border-bottom:1.5px solid #b4b4b4;flex:1}
.folio .wday .dn{width:150px;padding:10px 12px;border-right:1.5px solid #d0d0d0;flex:none}
.folio .wday .dn a{display:block}
.folio .wday .dn .nm{font-variant:small-caps;letter-spacing:.12em;font-size:21px;color:#444}
.folio .wday .dn .num{display:block;font-family:CG,Georgia,serif;font-size:46px;line-height:1.05;color:#111}
.folio .wday .ln{flex:1}
.folio .ring{display:inline-block;width:30px;height:30px;border:1.8px solid #666;border-radius:50%}
.folio .toc a{display:flex;align-items:baseline;gap:12px;font-size:28px;padding:6px 0;border-bottom:1.3px solid #ddd}
.folio .toc a .lead{flex:1;border-bottom:1.6px dotted #aaa;transform:translateY(-6px)}
.folio .toc a .pg{font-variant:small-caps;letter-spacing:.1em;color:#666;font-size:20px}
.folio .toc h3{font-variant:small-caps;letter-spacing:.14em;font-weight:400;font-size:24px;color:#222;margin:22px 0 4px}
`;

  function fontCSS(base) {
    return `@font-face{font-family:EBG;src:url(${base}fonts/ebg-roman.woff2) format('woff2');font-weight:400 600}
@font-face{font-family:EBG;src:url(${base}fonts/ebg-italic.woff2) format('woff2');font-style:italic;font-weight:400 600}
@font-face{font-family:CG;src:url(${base}fonts/cg-roman.woff2) format('woff2');font-weight:400 600}
@font-face{font-family:CG;src:url(${base}fonts/cg-italic.woff2) format('woff2');font-style:italic;font-weight:400 600}`;
  }

  /* ---------- the generator ---------- */
  class Builder {
    constructor(cfg) {
      this.cfg = cfg;
      const [sy, sm] = cfg.start.split("-").map(Number);
      this.months = [];
      for (let i = 0; i < cfg.months; i++) this.months.push([sy + Math.floor((sm - 1 + i) / 12), ((sm - 1 + i) % 12) + 1]);
      const [ly, lm] = this.months[this.months.length - 1];
      this.start = dayNum(sy, sm, 1);
      this.end = dayNum(ly, lm, monthLen(ly, lm));
      this.ws = cfg.sunday ? 6 : 0;
      this.daily = !cfg.weekly;
      this.courseList = cfg.courses.map((c, i) => [c.name || `Course ${ROMAN[i]}`, (c.tab || c.name || `C·${ROMAN[i]}`).slice(0, 8)]);
      this.weeks = [];
      for (let w = this.weekOf(this.start); w <= this.end; w += 7) this.weeks.push(w);
      this.weekIndex = new Map(this.weeks.map((w, i) => [w, i]));
      this.days = [];
      for (let d = this.start; d <= this.end; d++) this.days.push(d);
      const y0 = this.months[0][0], y1 = this.months[this.months.length - 1][0];
      this.yearLabel = y0 !== y1 ? `${y0}–${String(y1).slice(2)}` : String(y0);
      this.title = cfg.title || `Academic year ${this.yearLabel}`;
      this.pages = [];
      this.ids = [];
      this.moons();
    }

    moons() {
      const z = zoned(this.cfg.tz);
      this.zone = z;
      const ev = phasesBetween(z.instant(this.start - 40, 0), z.instant(this.end + 40, 0));
      this.events = new Map();
      for (const [t, q] of ev) {
        const l = z.local(t);
        if (!this.events.has(l.day)) this.events.set(l.day, [q, l]);
      }
      this.newmoons = ev.filter(([, q]) => q === 0).map(([t]) => t);
    }
    phase(n) {
      const t = this.zone.instant(n, 12);
      let prev = -Infinity, next = Infinity;
      for (const m of this.newmoons) { if (m <= t && m > prev) prev = m; if (m > t && m < next) next = m; }
      return (t - prev) / (next - prev);
    }
    static phaseName(p) { return ["waxing crescent", "waxing gibbous", "waning gibbous", "waning crescent"][Math.min(3, Math.floor(p * 4))]; }

    // ids
    did(n) { return `d${key(n)}`; }
    mid(y, m) { return `m${y}${pad(m)}`; }
    hid(y, m) { return `h${y}${pad(m)}`; }
    wid(n) { return `w${key(n)}`; }
    off(n) { return (weekday(n) - this.ws + 7) % 7; }
    weekOf(n) { return n - this.off(n); }
    wnum(w) { return this.weekIndex.get(w) + 1; }
    get dnames() { return DABBR.slice(this.ws).concat(DABBR.slice(0, this.ws)); }
    dayTarget(n) { return this.daily ? this.did(n) : this.wid(this.weekOf(n)); }
    inMonths(y, m) { return this.months.some(([a, b]) => a === y && b === m); }

    rail(on) {
      const tabs = [["index", "Index"], ["year", "Year"]]
        .concat(this.months.map(([y, m]) => [this.mid(y, m), MABBR[m - 1]]))
        .concat(this.courseList.map((c, i) => [`c${i}`, c[1]]))
        .concat([["research", "Res."], ["notes", "Notes"]]);
      const gaps = [2, 2 + this.months.length, 2 + this.months.length + this.courseList.length];
      return "<nav class=rail>" + tabs.map(([tid, label], i) => {
        const cls = [tid === on ? "on" : "", gaps.includes(i) ? "gap" : ""].filter(Boolean).join(" ");
        const fs = label.length <= 5 ? "" : label.length <= 7 ? " style='font-size:16px;letter-spacing:.06em'" : " style='font-size:14px;letter-spacing:.03em'";
        const fill = tid === on ? "<svg preserveAspectRatio='none' viewBox='0 0 10 10'><rect width=10 height=10 fill='#111'/></svg>" : "";
        return `<a href='#${tid}' class='${cls}'>${fill}<span${fs}>${esc(label)}</span></a>`;
      }).join("") + "</nav>";
    }
    crumbs(items, prev, next) {
      const parts = items.map(([href, label], i) => (i ? "<span class=sep>/</span>" : "") + (href ? `<a href='#${href}'>${label}</a>` : `<span>${label}</span>`));
      const nav = prev || next ? `<span class=nav>${prev ? `<a href='#${prev}'>‹</a>` : ""}${next ? `<a href='#${next}'>›</a>` : ""}</span>` : "";
      return `<div class=crumbs>${parts.join("")}${nav}</div>`;
    }
    add(pid, body, on, template) {
      const inner = template ? "" : `<div class=body style='left:${this.cfg.left}px'>${body}</div>`;
      const bg = template ? `<img class=tpl src='${this.cfg.base}tpl/${template}.png' alt=''>` : "";
      this.pages.push(`<section class=page id='${pid}'>${bg}${inner}${this.rail(on)}</section>`);
      this.ids.push(pid);
    }
    lbl(t, right) { return `<div class=lbl>${STAR}${t}${right ? `<span class=r>${right}</span>` : ""}</div>`; }
    foot(q, who) { return `<div class=dia><i></i></div><div class=foot><q>${q}</q><small>${who}</small></div>`; }

    get terms() {
      if (this._terms) return this._terms;
      const termOf = (m) => (m >= 8 ? "Fall" : m <= 5 ? "Spring" : "Summer");
      const blocks = [];
      let cur = [], name = null;
      for (const [y, m] of this.months) {
        const t = termOf(m);
        if (cur.length && t !== name) { blocks.push(cur); cur = []; }
        cur.push([y, m]); name = t;
      }
      if (cur.length) blocks.push(cur);
      this.termMonths = {};
      this._terms = blocks.map((b) => {
        const tid = `t${b[0][0]}${pad(b[0][1])}`;
        this.termMonths[tid] = b;
        return [tid, `${termOf(b[0][1])} ${b[0][0]}`];
      });
      return this._terms;
    }

    cover() {
      this.add("cover", `
<div style="flex:1;display:flex;flex-direction:column;justify-content:center;align-items:flex-start;padding-left:40px">
  <div class=small style="font-size:26px;letter-spacing:.3em">the scholium</div>
  <div style="font-family:CG,Georgia,serif;font-size:200px;line-height:.9;margin:18px 0 10px;font-weight:500">The <i>Folio</i></div>
  <div style="font-family:CG,Georgia,serif;font-style:italic;font-size:46px;color:#333">${esc(this.title)}</div>
  <div style="width:420px;border-top:1.5px solid #222;margin:56px 0 30px"></div>
  <div class=small style="font-size:24px">this folio belongs to</div>
  <div style="width:760px;border-bottom:1.5px solid #888;height:70px;font-family:CG,Georgia,serif;font-size:44px;display:flex;align-items:flex-end;padding-bottom:6px">${esc(this.cfg.owner || "")}</div>
  <div class=small style="font-size:24px;margin-top:34px">if found, please return to</div>
  <div style="width:760px;border-bottom:1.5px solid #888;height:70px"></div>
</div>
<div style="display:flex;align-items:center;justify-content:space-between;font-size:20px;color:#666" class=small>
  <a href="#index" style="border:1.4px solid #888;border-radius:6px;padding:6px 18px;color:#222">open the index ›</a>
  <span style="display:flex;align-items:center;gap:12px;font-size:44px">${markSvg("#222")}</span>
</div>`, "");
    }

    index() {
      const months = this.months.map(([y, m]) => `<a href='#${this.mid(y, m)}'>${MONTHS[m - 1]} ${y}<span class=lead></span><span class=pg>calendar</span></a>`).join("");
      const courses = this.courseList.map((c, i) => `<a href='#c${i}'>${esc(c[0])}<span class=lead></span><span class=pg>hub · logs · notes</span></a>`).join("");
      const terms = this.terms.map(([tid, name]) => `<a href='#${tid}'>${name}<span class=lead></span><span class=pg>deadlines</span></a><a href='#${tid}-map' style='padding-left:28px;font-size:24px'>term map<span class=lead></span><span class=pg>weeks × courses</span></a>`).join("");
      const how = `<p>Tap a tab on the right edge to jump to any month or course. On dated pages, the line at the top shows where you are; tap any part of it to go up a level, and use ‹ › to step back or forward.</p>
<p style="margin-top:14px">In a month, tap a date to open its ${this.daily ? "day" : "week"}, and a week number to open its week. Moon phases are computed for ${esc(this.cfg.tz.replace(/_/g, " "))}.</p>`;
      this.add("index", `${this.crumbs([["cover", "The Folio"], [null, "Index"]])}
<div class=mast><h1>The <i>Index</i></h1><div class=meta>${esc(this.title)}</div></div><div class=rule></div>
<div style="display:flex;gap:56px;flex:1">
 <div class="col toc" style="flex:1">
  <h3>The year</h3><a href='#year'>Year at a glance<span class=lead></span><span class=pg>${this.months.length} months</span></a>${terms}
  <h3>Months</h3>${months}
 </div>
 <div class="col toc" style="flex:1">
  <h3>Courses</h3>${courses}
  <h3>Elsewhere</h3><a href='#research'>Research<span class=lead></span><span class=pg>papers &amp; talks</span></a><a href='#notes'>Notes<span class=lead></span><span class=pg>ruled · grid · dot</span></a>
  <h3>How the Folio works</h3><div style="font-size:23px;line-height:1.45;color:#333">${how}</div>
 </div>
</div>
${this.foot("A scholium is the note in the margin that explains what just happened.", "The Scholium")}`, "index");
    }

    year() {
      const hd = this.dnames.map((c) => `<span class=h>${c[0].toLowerCase()}</span>`).join("");
      const cells = this.months.map(([y, m]) => {
        const first = dayNum(y, m, 1);
        let days = "<span class=x>.</span>".repeat(this.off(first));
        for (let d = 1; d <= monthLen(y, m); d++) days += `<a href='#${this.dayTarget(dayNum(y, m, d))}'>${d}</a>`;
        return `<div><a class=mt href='#${this.mid(y, m)}'>${MONTHS[m - 1]} <span style='color:#777;font-size:26px'>${y}</span></a><div class=mini>${hd}${days}</div></div>`;
      }).join("");
      this.add("year", `${this.crumbs([["index", "Index"], [null, "Year"]])}
<div class=mast><h1>The <i>Year</i></h1><div class=meta>${this.yearLabel}</div></div><div class=rule></div>
<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:34px 44px;align-content:start;flex:none">${cells}</div>
<div style="height:30px;flex:none"></div>${this.lbl("Key dates", "first day · breaks · finals")}<div class="ruled top" style="flex:1"></div>
${this.foot(...QUOTES[5])}`, "year");
    }

    termPages() {
      const rows = "<tr><td style='width:170px'></td><td></td><td style='width:150px'></td><td style='width:110px'></td><td style='width:70px;text-align:center'><span class=sq></span></td></tr>".repeat(25);
      for (const [tid, name] of this.terms) {
        const [season, yr] = name.split(" ");
        this.add(tid, `${this.crumbs([["index", "Index"], [null, name]])}
<div class=mast><h1>${season} <i>Deadlines</i></h1><div class=meta>${yr}</div></div><div class=rule></div>
<div class=small style="margin:-6px 0 14px;font-size:20px">Copy every due date from your syllabi here once, at the start of term.</div>
<table><tr><th>course</th><th>assignment / exam</th><th>due</th><th>weight</th><th>done</th></tr>${rows}</table>
<div style="flex:1"></div>${this.foot(...QUOTES[1])}`, "year");
        this.termMap(tid, name);
      }
    }

    termMap(tid, name) {
      const months = this.termMonths[tid].map(([y, m]) => `${y}-${m}`);
      const weeks = this.weeks.filter((w) => [0, 1, 2, 3, 4, 5, 6].some((k) => { const t = ymd(w + k); return months.includes(`${t.y}-${t.m}`); }));
      const heads = this.courseList.map((c) => `<th style='text-align:center'>${esc(c[1])}</th>`).join("");
      const rows = weeks.map((w) => {
        const a = ymd(w), e = ymd(w + 6);
        return `<tr><td style='width:150px;white-space:nowrap'><a href='#${this.wid(w)}' style='font-family:CG,Georgia,serif;font-size:26px'>week ${this.wnum(w)}</a><span style='display:block;font-size:15px;font-variant:small-caps;letter-spacing:.08em;color:#777;margin-top:-4px'>${a.d} ${MABBR[a.m - 1]} – ${e.d} ${MABBR[e.m - 1]}</span></td>${"<td></td>".repeat(this.courseList.length)}</tr>`;
      }).join("");
      const h = Math.max(46, Math.min(70, Math.floor(1440 / Math.max(1, weeks.length))));
      const [season, yr] = name.split(" ");
      this.add(`${tid}-map`, `${this.crumbs([["index", "Index"], [tid, name], [null, "map"]])}
<div class=mast><h1>${season} <i>Map</i></h1><div class=meta>${yr}</div></div><div class=rule></div>
<div class=small style="margin:-6px 0 14px;font-size:20px">One row per week, one column per course. Write what is due, mark exams, and see the crunch weeks coming.</div>
<table style="table-layout:fixed"><tr><th style='width:150px'>week</th>${heads}</tr>${rows.replace(/<td><\/td>/g, `<td style='height:${h}px'></td>`)}</table>
<div style="flex:1"></div>`, "year");
    }

    monthPages() {
      this.months.forEach(([y, m], i) => {
        const first = dayNum(y, m, 1), n = monthLen(y, m);
        const gs = this.weekOf(first), rows = Math.floor((this.off(first) + n + 6) / 7);
        let cells = "<div class=h></div>" + this.dnames.map((d) => `<div class=h>${d}</div>`).join("");
        for (let r = 0; r < rows; r++) {
          const w = gs + 7 * r;
          cells += `<div class=wk><a href='#${this.wid(w)}'>w${this.weekIndex.has(w) ? this.wnum(w) : ""}</a></div>`;
          for (let c = 0; c < 7; c++) {
            const d = w + c, t = ymd(d), inside = t.m === m;
            let ph = "";
            if (inside && this.events.has(d)) { const q = this.events.get(d)[0]; ph = `<span class=ph title='${PHASE_NAMES[q]}'>${moonSvg([0, 0.25, 0.5, 0.75][q], 26)}</span>`; }
            const link = d >= this.start && d <= this.end ? `<a class=n href='#${this.dayTarget(d)}'>${t.d}</a>` : `<span class='n dead'>${t.d}</span>`;
            cells += `<div class='d${inside ? "" : " out"}'>${link}${ph}</div>`;
          }
        }
        const prev = i ? this.mid(...this.months[i - 1]) : null;
        const next = i + 1 < this.months.length ? this.mid(...this.months[i + 1]) : null;
        this.add(this.mid(y, m), `${this.crumbs([["year", this.yearLabel], [null, MONTHS[m - 1]], [this.hid(y, m), "habits"]], prev, next)}
<div class=mast><h1>${MONTHS[m - 1]} <i style="color:#666">${y}</i></h1><div class=meta><a href='#${this.hid(y, m)}' style="border:1.4px solid #888;border-radius:6px;padding:2px 14px">habits ›</a></div></div><div class=rule style="margin-bottom:0"></div>
<div class=cal style="grid-template-rows:auto repeat(${rows},1fr)">${cells}</div>
<div style="display:flex;gap:34px;height:330px;margin-top:22px;flex:none">
 <div class=col style="flex:1">${this.lbl("This month")}<div class="ruled top" style="flex:1"></div></div>
 <div class=col style="flex:1">${this.lbl("Due this month")}<div class="ruled top" style="flex:1"></div></div>
</div>`, this.mid(y, m));
        this.add(this.hid(y, m), "", this.mid(y, m), `the-month-${n === 29 ? 30 : n}`);
      });
    }

    weekPages() {
      const habits = `<div style='display:flex;align-items:center;gap:8px;margin:8px 0'><b style='flex:1;border-bottom:1.5px solid #9a9a9a;height:30px'></b>${"<span class=ring></span>".repeat(7)}</div>`.repeat(4);
      const due = "<tr><td></td><td style='width:84px'></td><td style='width:52px;text-align:center'><span class=sq></span></td></tr>".repeat(9);
      this.weeks.forEach((w, i) => {
        const a = ymd(w), e = ymd(w + 6);
        const mm = this.inMonths(a.y, a.m) ? [a.y, a.m] : [e.y, e.m];
        const mOn = this.mid(...mm);
        const days = [0, 1, 2, 3, 4, 5, 6].map((k) => {
          const d = w + k, t = ymd(d), inr = d >= this.start && d <= this.end, link = this.daily && inr;
          const ph = this.events.has(d) ? `<span style='margin-left:8px'>${moonSvg([0, 0.25, 0.5, 0.75][this.events.get(d)[0]], 22)}</span>` : "";
          return `<div class=wday><div class=dn>${link ? `<a href='#${this.did(d)}'>` : "<span>"}<span class=nm>${DABBR[weekday(d)]}</span><span class=num>${t.d}</span>${link ? "</a>" : "</span>"}${ph}</div><div class=ln></div></div>`;
        }).join("");
        const prev = i ? this.wid(this.weeks[i - 1]) : null, next = i + 1 < this.weeks.length ? this.wid(this.weeks[i + 1]) : null;
        this.add(this.wid(w), `${this.crumbs([["year", this.yearLabel], [mOn, MONTHS[mm[1] - 1]], [null, `week ${i + 1}`]], prev, next)}
<div class=mast><h1>Week <i>${i + 1}</i></h1><div class=meta>${a.d} ${MABBR[a.m - 1]} – ${e.d} ${MABBR[e.m - 1]} ${e.y}</div></div><div class=rule style="margin-bottom:0"></div>
<div style="display:flex;gap:30px;flex:1;min-height:0">
 <div class=col style="flex:1;border-top:2px solid #222">${days}</div>
 <div class=col style="width:430px">
  ${this.lbl("The one goal")}<div class="ruled top" style="height:156px;flex:none"></div>
  <div style="height:16px"></div>${this.lbl("Due")}<table><tr><th>task</th><th>due</th><th></th></tr>${due}</table>
  <div style="height:16px"></div>${this.lbl("Habits", this.dnames.map((c) => c[0].toLowerCase()).join(" "))}${habits}
  <div style="height:10px"></div>${this.lbl("Wins")}<div class="ruled top" style="flex:1"></div>
 </div>
</div>`, mOn);
      });
    }

    dayPages() {
      const hours = Array.from({ length: 18 }, (_, i) => i + 6).map((h) => `<div class=hr><b>${h <= 12 ? h : h - 12}</b></div>`).join("");
      const todo = "<tr><td></td><td style='width:84px'></td><td style='width:52px;text-align:center'><span class=sq></span></td></tr>".repeat(7);
      const three = [1, 2, 3].map((n) => `<div style='display:flex;align-items:flex-end;gap:12px;height:52px;border-bottom:1.5px solid #b4b4b4'><span style='font-family:CG,Georgia,serif;font-size:28px;color:#555;width:22px'>${n}</span></div>`).join("");
      this.days.forEach((d, i) => {
        const t = ymd(d), p = this.phase(d);
        let pn = Builder.phaseName(p);
        if (this.events.has(d)) { const [q, l] = this.events.get(d); pn = `${PHASE_NAMES[q]} at ${pad(l.hh)}:${l.mm}`; }
        const w = this.weekOf(d);
        const prev = i ? this.did(this.days[i - 1]) : null, next = i + 1 < this.days.length ? this.did(this.days[i + 1]) : null;
        this.add(this.did(d), `${this.crumbs([["year", this.yearLabel], [this.mid(t.y, t.m), MONTHS[t.m - 1]], [this.wid(w), `week ${this.wnum(w)}`], [null, String(t.d)]], prev, next)}
<div class=mast><h1>${DAYS[weekday(d)]}<i style="color:#666;font-size:46px"> &nbsp;${t.d} ${MONTHS[t.m - 1]}</i></h1>
 <div class=meta>${moonSvg(p, 40)}<span>${pn}</span><span style="color:#999">·</span><span>day ${dayOfYear(d)}</span></div></div><div class=rule style="margin-bottom:0"></div>
<div style="display:flex;gap:30px;flex:1;min-height:0">
 <div class="sched col" style="width:400px">${hours}</div>
 <div class=col style="flex:1;padding-top:14px">
  ${this.lbl("Three things")}${three}
  <div style="height:18px"></div>${this.lbl("To do")}<table><tr><th>task</th><th>due</th><th></th></tr>${todo}</table>
  <div style="height:18px"></div>${this.lbl("What I learned today", "close the book first")}<div class=grid style="flex:1"></div>
 </div>
</div>`, this.mid(t.y, t.m));
      });
    }

    coursePages() {
      const plan = [["the-class-hub", "Class Hub", 1], ["the-exam-plan", "Exam Plan", 2], ["the-error-log", "Error Log", 4], ["the-blurt", "Blurt", 4], ["the-time-trial", "Time Trial", 2]];
      const notes = 12;
      const fields = ["course", "number", "professor", "room / time"].map((k) => `<div style='display:flex;align-items:flex-end;gap:14px;margin-top:22px' class=small><span style='width:170px;font-size:23px'>${k}</span><b style='flex:1;border-bottom:1.5px solid #9a9a9a;height:34px'></b></div>`).join("");
      this.courseList.forEach(([full], c) => {
        const cid = `c${c}`, cname = esc(full);
        const toc = plan.map(([tpl, name, k]) => `<a href='#${cid}-${tpl.slice(4)}-0'>${name}${k > 1 ? "s" : ""}<span class=lead></span><span class=pg>${k} page${k > 1 ? "s" : ""}</span></a>`).join("")
          + `<a href='#${cid}-notes-0'>Lecture notes<span class=lead></span><span class=pg>${notes} pages</span></a>`;
        const title = full.startsWith("Course ") ? `Course <i>${ROMAN[c]}</i>` : `<i>${cname}</i>`;
        this.add(cid, `${this.crumbs([["index", "Index"], [null, cname]])}
<div class=mast><h1>${title}</h1><div class=meta>${STAR.replace("class=st", 'style="width:18px;height:18px;fill:#444"')}</div></div><div class=rule></div>
${fields}
<div class=toc style="margin-top:46px">${toc}</div>
<div style="flex:1"></div>
${this.foot(...QUOTES[c % QUOTES.length])}`, cid);
        for (const [tpl, , k] of plan) for (let j = 0; j < k; j++) this.add(`${cid}-${tpl.slice(4)}-${j}`, "", cid, tpl);
        for (let j = 0; j < notes; j++) {
          const kind = ["ruled", "grid", "ruled", "dots"][j % 4];
          this.add(`${cid}-notes-${j}`, `${this.crumbs([[cid, cname], [null, `notes ${j + 1}`]], j ? `${cid}-notes-${j - 1}` : null, j + 1 < notes ? `${cid}-notes-${j + 1}` : null)}
<div style="display:flex;gap:30px;align-items:flex-end;padding:10px 0 12px" class=small><span style="font-size:23px">topic</span><b style="flex:1;border-bottom:1.5px solid #9a9a9a;height:32px"></b><span style="font-size:23px">date</span><b style="width:200px;border-bottom:1.5px solid #9a9a9a;height:32px"></b></div><div class=rule style="margin-bottom:14px"></div>
<div class="${kind}${kind === "ruled" ? " top" : ""}" style="flex:1"></div>`, cid);
        }
      });
    }

    researchPages(n = 12) { for (let j = 0; j < n; j++) this.add(j ? `research-${j}` : "research", "", "research", "the-research"); }

    notesPages(n = 30) {
      for (let j = 0; j < n; j++) {
        const kind = ["ruled", "grid", "dots"][Math.floor(j / 10)];
        const id = (k) => (k ? `notes-${k}` : "notes");
        this.add(id(j), `${this.crumbs([["index", "Index"], [null, `notes · ${kind === "dots" ? "dot grid" : kind} · ${(j % 10) + 1}`]], j ? id(j - 1) : null, j + 1 < n ? id(j + 1) : null)}
<div style="height:12px"></div><div class="${kind}${kind === "ruled" ? " top" : ""}" style="flex:1"></div>`, "notes");
      }
    }

    build() {
      this.cover(); this.index(); this.year(); this.termPages(); this.monthPages(); this.weekPages();
      if (this.daily) this.dayPages();
      this.coursePages(); this.researchPages(); this.notesPages();
      return this.pages.join("");
    }
  }

  /* ---------- paper: ruled, grid and dots as vector SVG ---------- */
  function paper(root) {
    const NS = "http://www.w3.org/2000/svg";
    const kinds = [[".ruled", "r", 52, "#b4b4b4", 1.5], [".wday .ln", "r", 52, "#d6d6d6", 1.5], [".grid", "g", 44, "#d2d2d2", 1], [".dots", "d", 44, "#8a8a8a", 4]];
    for (const [sel, k, p, col, w] of kinds) {
      for (const el of root.querySelectorAll(sel)) {
        if (el.dataset.paper) continue;
        el.dataset.paper = 1;
        const W = el.clientWidth, H = el.clientHeight;
        if (!W || !H) continue;
        if (getComputedStyle(el).position === "static") el.style.position = "relative";
        let d = "";
        if (k === "r") for (let y = p - 0.75; y < H; y += p) d += `M0 ${y.toFixed(2)}H${W}`;
        if (k === "g") { for (let y = p - 0.5; y < H; y += p) d += `M0 ${y.toFixed(2)}H${W}`; for (let x = p - 0.5; x < W; x += p) d += `M${x.toFixed(2)} 0V${H}`; }
        if (k === "d") for (let y = p / 2; y < H; y += p) for (let x = p / 2; x < W; x += p) d += `M${x} ${y}h0`;
        const svg = document.createElementNS(NS, "svg");
        svg.setAttribute("width", W); svg.setAttribute("height", H);
        svg.style.cssText = "position:absolute;left:0;top:0;pointer-events:none;overflow:hidden";
        const path = document.createElementNS(NS, "path");
        path.setAttribute("d", d); path.setAttribute("stroke", col); path.setAttribute("stroke-width", w); path.setAttribute("fill", "none");
        if (k === "d") path.setAttribute("stroke-linecap", "round");
        svg.appendChild(path); el.appendChild(svg);
      }
    }
  }

  const DEFAULTS = {
    start: "2026-08", months: 12, sunday: false, weekly: false, left: 56, owner: "", title: "",
    tz: (Intl.DateTimeFormat().resolvedOptions().timeZone) || "UTC", base: "",
    courses: Array.from({ length: 6 }, () => ({ name: "", tab: "" })),
  };

  function render(cfg, container) {
    cfg = Object.assign({}, DEFAULTS, cfg);
    const b = new Builder(cfg);
    let style = document.getElementById("folio-style");
    if (!style) { style = document.createElement("style"); style.id = "folio-style"; document.head.appendChild(style); }
    style.textContent = fontCSS(cfg.base) + CSS;
    container.classList.add("folio");
    container.innerHTML = b.build();
    return { pages: b.pages.length, ids: b.ids, builder: b };
  }

  global.Folio = { render, paper, DEFAULTS, _internals: { phasesBetween, dayNum, ymd, weekday, zoned, moonSvg } };
})(typeof window !== "undefined" ? window : globalThis);
