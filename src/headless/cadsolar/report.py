"""
Self-contained HTML report.

One file, no network, no server, no build step: geometry and numbers are
embedded, so it opens by double-clicking and survives being emailed to a
client. That constraint rules out CDN libraries, so the viewer is a small
axonometric renderer on a 2D canvas.

Axonometric rather than perspective because that is how massing is read in
architecture, and because parallel projection keeps heights comparable
across the model. Voxels are convex and disjoint, so painter's sorting by
depth with back-face culling is correct for them.
"""

import json

VIEWER_JS = r"""
const M = DATA.model, S = DATA.summary;
const cv = document.getElementById('view');
const ctx = cv.getContext('2d');

let cam = { az: -35, el: 28, zoom: 1, panX: 0, panY: 0 };
let show = { kept: true, removed: true, context: true, points: true,
             grid: true, edges: true };

// ---- build faces once -------------------------------------------------
function prismFaces(p, kind) {
  const ring = p.r, n = ring.length, lo = p.z0, hi = p.z1, out = [];
  const bottom = ring.map(q => [q[0], q[1], lo]);
  const top = ring.map(q => [q[0], q[1], hi]);
  out.push({ v: bottom.slice().reverse(), kind, nz: -1 });
  out.push({ v: top, kind, nz: 1 });
  for (let i = 0; i < n; i++) {
    const j = (i + 1) % n;
    out.push({ v: [bottom[i], bottom[j], top[j], top[i]], kind, nz: 0 });
  }
  return out;
}

let FACES = [];
function rebuild() {
  FACES = [];
  const add = (list, kind) => list.forEach(p => {
    prismFaces(p, kind).forEach(f => FACES.push(f));
  });
  if (show.kept) add(M.kept, 'kept');
  if (show.removed) add(M.removed, 'removed');
  if (show.context) add(M.context, 'context');
  FACES.forEach(f => {
    let cx = 0, cy = 0, cz = 0;
    f.v.forEach(v => { cx += v[0]; cy += v[1]; cz += v[2]; });
    f.c = [cx / f.v.length, cy / f.v.length, cz / f.v.length];
    const a = f.v[0], b = f.v[1], c = f.v[2];
    const u = [b[0]-a[0], b[1]-a[1], b[2]-a[2]];
    const w = [c[0]-a[0], c[1]-a[1], c[2]-a[2]];
    f.n = [u[1]*w[2]-u[2]*w[1], u[2]*w[0]-u[0]*w[2], u[0]*w[1]-u[1]*w[0]];
    const L = Math.hypot(f.n[0], f.n[1], f.n[2]) || 1;
    f.n = [f.n[0]/L, f.n[1]/L, f.n[2]/L];
  });
}

// ---- projection -------------------------------------------------------
function basis() {
  const a = cam.az * Math.PI / 180, e = cam.el * Math.PI / 180;
  const ca = Math.cos(a), sa = Math.sin(a), ce = Math.cos(e), se = Math.sin(e);
  return {
    right: [ca, -sa, 0],
    up:    [-sa * se, -ca * se, ce],
    view:  [-sa * ce, -ca * ce, -se]
  };
}

function fit(B, w, h) {
  // Project the eight bounding-box corners and fit what the screen actually
  // needs, so a plan view fills the frame as well as an axonometric one.
  const b = M.focus, c = M.center;
  let minx = Infinity, maxx = -Infinity, miny = Infinity, maxy = -Infinity;
  for (let i = 0; i < 8; i++) {
    const q = [(i & 1 ? b[3] : b[0]) - c[0],
               (i & 2 ? b[4] : b[1]) - c[1],
               (i & 4 ? b[5] : b[2]) - c[2]];
    const x = q[0]*B.right[0] + q[1]*B.right[1] + q[2]*B.right[2];
    const y = q[0]*B.up[0]    + q[1]*B.up[1]    + q[2]*B.up[2];
    if (x < minx) minx = x; if (x > maxx) maxx = x;
    if (y < miny) miny = y; if (y > maxy) maxy = y;
  }
  const sx = (maxx - minx) || 1, sy = (maxy - miny) || 1;
  return Math.min(w / sx, h / sy) * 0.82;
}

function project(p, B, k, ox, oy) {
  const q = [p[0]-M.center[0], p[1]-M.center[1], p[2]-M.center[2]];
  const x = q[0]*B.right[0] + q[1]*B.right[1] + q[2]*B.right[2];
  const y = q[0]*B.up[0]    + q[1]*B.up[1]    + q[2]*B.up[2];
  const d = q[0]*B.view[0]  + q[1]*B.view[1]  + q[2]*B.view[2];
  return [ox + x*k, oy - y*k, d];
}

// Read the actual theme so labels stay legible in light and dark.
const DARK = window.matchMedia &&
  window.matchMedia('(prefers-color-scheme: dark)').matches;
const INK = DARK
  ? { text: '#eef3f8', halo: 'rgba(16,20,24,0.85)' }
  : { text: '#1c2530', halo: 'rgba(255,255,255,0.9)' };

const PALETTE = {
  kept:    [ 92, 141, 106],
  removed: [190, 106,  96],
  context: [140, 146, 154]
};

function shade(rgb, t) {
  const f = 0.55 + 0.45 * t;
  return `rgb(${Math.round(rgb[0]*f)},${Math.round(rgb[1]*f)},${Math.round(rgb[2]*f)})`;
}

function draw() {
  const dpr = window.devicePixelRatio || 1;
  const w = cv.clientWidth, h = cv.clientHeight;
  if (cv.width !== w*dpr || cv.height !== h*dpr) {
    cv.width = w*dpr; cv.height = h*dpr;
  }
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, w, h);

  const B = basis();
  const k = fit(B, w, h) * cam.zoom;
  const ox = w/2 + cam.panX, oy = h/2 + cam.panY;
  const light = [-0.4, -0.5, 0.76];

  if (show.grid) drawGround(B, k, ox, oy);

  const vis = [];
  for (const f of FACES) {
    const dot = f.n[0]*B.view[0] + f.n[1]*B.view[1] + f.n[2]*B.view[2];
    if (dot >= -0.0001) continue;                      // back-face cull
    const c = project(f.c, B, k, ox, oy);
    vis.push({ f, d: c[2] });
  }
  // view points away from the camera, so a larger depth is farther:
  // paint those first and let nearer faces cover them.
  vis.sort((a, b) => b.d - a.d);

  for (const item of vis) {
    const f = item.f;
    const pts = f.v.map(v => project(v, B, k, ox, oy));
    ctx.beginPath();
    ctx.moveTo(pts[0][0], pts[0][1]);
    for (let i = 1; i < pts.length; i++) ctx.lineTo(pts[i][0], pts[i][1]);
    ctx.closePath();
    const lum = Math.max(0, f.n[0]*light[0] + f.n[1]*light[1] + f.n[2]*light[2]);
    if (f.kind === 'removed') {
      ctx.fillStyle = 'rgba(190,106,96,0.16)';
      ctx.fill();
      ctx.strokeStyle = 'rgba(190,106,96,0.5)';
      ctx.lineWidth = 0.6; ctx.stroke();
      continue;
    }
    ctx.fillStyle = shade(PALETTE[f.kind], lum);
    ctx.fill();
    if (show.edges) {
      ctx.strokeStyle = f.kind === 'context'
        ? 'rgba(60,66,74,0.30)' : 'rgba(28,44,34,0.42)';
      ctx.lineWidth = 0.7; ctx.stroke();
    }
  }

  if (show.points) drawPoints(B, k, ox, oy);
  drawCompass(B, w, h);
}

function drawGround(B, k, ox, oy) {
  const b = M.bbox, step = M.grid_step;
  const x0 = Math.floor(b[0]/step)*step - step, x1 = Math.ceil(b[3]/step)*step + step;
  const y0 = Math.floor(b[1]/step)*step - step, y1 = Math.ceil(b[4]/step)*step + step;
  ctx.strokeStyle = 'rgba(120,130,140,0.22)';
  ctx.lineWidth = 0.6;
  ctx.beginPath();
  for (let x = x0; x <= x1 + 1e-6; x += step) {
    const a = project([x, y0, 0], B, k, ox, oy), c = project([x, y1, 0], B, k, ox, oy);
    ctx.moveTo(a[0], a[1]); ctx.lineTo(c[0], c[1]);
  }
  for (let y = y0; y <= y1 + 1e-6; y += step) {
    const a = project([x0, y, 0], B, k, ox, oy), c = project([x1, y, 0], B, k, ox, oy);
    ctx.moveTo(a[0], a[1]); ctx.lineTo(c[0], c[1]);
  }
  ctx.stroke();
}

function drawPoints(B, k, ox, oy) {
  M.points.forEach((p, i) => {
    const s = project([p.x, p.y, p.z], B, k, ox, oy);
    const ok = S.points[i].meets_requirement;
    ctx.beginPath();
    ctx.arc(s[0], s[1], 6, 0, Math.PI*2);
    ctx.fillStyle = ok ? '#2f7d4f' : '#c0392b';
    ctx.fill();
    ctx.strokeStyle = '#fff'; ctx.lineWidth = 2; ctx.stroke();
    const label = `P${i} ${S.points[i].final_hours.toFixed(2)}h`;
    ctx.font = '600 12px ui-sans-serif, system-ui, sans-serif';
    ctx.lineJoin = 'round';
    ctx.lineWidth = 3.5;
    ctx.strokeStyle = INK.halo;
    ctx.strokeText(label, s[0] + 10, s[1] - 8);
    ctx.fillStyle = INK.text;
    ctx.fillText(label, s[0] + 10, s[1] - 8);
  });
}

function drawCompass(B, w, h) {
  const cx = w - 52, cy = 52, r = 24;
  const brg = (M.north_bearing || 0) * Math.PI / 180;
  const nWorld = [-Math.sin(-brg), Math.cos(-brg), 0];
  const x = nWorld[0]*B.right[0] + nWorld[1]*B.right[1];
  const y = nWorld[0]*B.up[0] + nWorld[1]*B.up[1];
  const L = Math.hypot(x, y) || 1;
  ctx.beginPath(); ctx.arc(cx, cy, r, 0, Math.PI*2);
  ctx.fillStyle = DARK ? 'rgba(28,34,41,0.88)' : 'rgba(255,255,255,0.82)'; ctx.fill();
  ctx.strokeStyle = 'rgba(90,100,110,0.45)'; ctx.lineWidth = 1; ctx.stroke();
  ctx.beginPath(); ctx.moveTo(cx, cy);
  ctx.lineTo(cx + x/L*r*0.8, cy - y/L*r*0.8);
  ctx.strokeStyle = '#c0392b'; ctx.lineWidth = 2.5; ctx.stroke();
  ctx.fillStyle = '#c0392b';
  ctx.font = '700 11px ui-sans-serif, system-ui, sans-serif';
  ctx.fillText('N', cx + x/L*r*1.05 - 4, cy - y/L*r*1.05 + 4);
}

// ---- interaction ------------------------------------------------------
let drag = null;
cv.addEventListener('pointerdown', e => {
  drag = { x: e.clientX, y: e.clientY, pan: e.shiftKey || e.button === 1 };
  cv.setPointerCapture(e.pointerId);
});
cv.addEventListener('pointermove', e => {
  if (!drag) return;
  const dx = e.clientX - drag.x, dy = e.clientY - drag.y;
  drag.x = e.clientX; drag.y = e.clientY;
  if (drag.pan) { cam.panX += dx; cam.panY += dy; }
  else {
    cam.az -= dx * 0.4;
    cam.el = Math.max(-89, Math.min(89, cam.el + dy * 0.35));
  }
  draw();
});
cv.addEventListener('pointerup', () => { drag = null; });
cv.addEventListener('wheel', e => {
  e.preventDefault();
  cam.zoom = Math.max(0.25, Math.min(8, cam.zoom * (e.deltaY < 0 ? 1.1 : 0.9)));
  draw();
}, { passive: false });

function setView(az, el) {
  cam.az = az; cam.el = el; cam.panX = 0; cam.panY = 0; cam.zoom = 1; draw();
}
document.querySelectorAll('[data-view]').forEach(b => {
  b.onclick = () => {
    const [az, el] = b.dataset.view.split(',').map(Number);
    setView(az, el);
    document.querySelectorAll('[data-view]').forEach(x => x.classList.remove('on'));
    b.classList.add('on');
  };
});
document.querySelectorAll('[data-toggle]').forEach(b => {
  b.onclick = () => {
    const key = b.dataset.toggle;
    show[key] = !show[key];
    b.classList.toggle('off', !show[key]);
    rebuild(); draw();
  };
});

document.getElementById('save').onclick = () => {
  const a = document.createElement('a');
  a.download = (document.title || 'view').replace(/[\\/:*?"<>|]/g, '_') + '.png';
  a.href = cv.toDataURL('image/png');
  a.click();
};

window.addEventListener('resize', draw);
rebuild();
draw();
"""


def build_model(scene, result, settings):
    """Geometry payload for the viewer, in metres."""
    def prism(p):
        return {
            "r": [[round(x, 3), round(y, 3)] for x, y in p.polygon],
            "z0": round(p.z_low, 3),
            "z1": round(p.z_high, 3),
        }

    massing = list(result["kept"]) + list(result["removed"])
    everything = massing + list(scene.context)
    boxes = [p.bbox for p in everything]
    points = scene.protected_points

    xs = [b[0] for b in boxes] + [b[3] for b in boxes] + [p[0] for p in points]
    ys = [b[1] for b in boxes] + [b[4] for b in boxes] + [p[1] for p in points]
    zs = [b[2] for b in boxes] + [b[5] for b in boxes] + [p[2] for p in points]

    bbox = [min(xs), min(ys), min(zs), max(xs), max(ys), max(zs)]

    # The view frames the massing and its protected points; context buildings
    # are allowed to run off-frame the way they would on a drawing.
    fx = [b[0] for b in (p.bbox for p in massing)] + [p[0] for p in points]
    fX = [b[3] for b in (p.bbox for p in massing)] + [p[0] for p in points]
    fy = [b[1] for b in (p.bbox for p in massing)] + [p[1] for p in points]
    fY = [b[4] for b in (p.bbox for p in massing)] + [p[1] for p in points]
    fz = [b[2] for b in (p.bbox for p in massing)] + [p[2] for p in points]
    fZ = [b[5] for b in (p.bbox for p in massing)] + [p[2] for p in points]
    focus = [min(fx), min(fy), min(fz), max(fX), max(fY), max(fZ)]
    span = max(bbox[3] - bbox[0], bbox[4] - bbox[1], 1.0)
    step = 10.0

    for candidate in (5.0, 10.0, 20.0, 50.0, 100.0):
        if span / candidate <= 16:
            step = candidate
            break

    return {
        "kept": [prism(p) for p in result["kept"]],
        "removed": [prism(p) for p in result["removed"]],
        "context": [prism(p) for p in scene.context],
        "points": [
            {"x": round(x, 3), "y": round(y, 3), "z": round(z, 3)}
            for x, y, z in points
        ],
        "bbox": [round(v, 3) for v in bbox],
        "focus": [round(v, 3) for v in focus],
        "center": [
            round((focus[0] + focus[3]) / 2, 3),
            round((focus[1] + focus[4]) / 2, 3),
            round((focus[2] + focus[5]) / 2, 3),
        ],
        "grid_step": step,
        "north_bearing": -settings.north_angle,
    }


def _rows(summary):
    rows = []

    for point in summary["points"]:
        state = (
            "达标" if point["meets_requirement"]
            else ("不达标" if point["solvable_from_baseline"] else "基准即不可解")
        )
        css = (
            "ok" if point["meets_requirement"]
            else ("bad" if point["solvable_from_baseline"] else "warn")
        )
        width = min(100.0, point["final_hours"] / max(summary["required"], 0.01) * 100.0)
        rows.append(
            "<tr><td>P{0}</td><td class=num>{1:.2f}</td><td class=num>{2:.2f}</td>"
            "<td class=num><b>{3:.2f}</b></td>"
            "<td class=barcell><span class=bar style='width:{4:.1f}%'></span></td>"
            "<td class={5}>{6}</td></tr>".format(
                point["index"], point["baseline_hours"], point["initial_hours"],
                point["final_hours"], width, css, state,
            )
        )

    return "\n".join(rows)


def render(scene, settings, result, title="日照约束体量切削"):
    """Return one self-contained HTML document."""
    outcome = result["outcome"]
    grid = result["grid"]
    verification = result["verification"]
    deltas = [
        abs(a - b)
        for a, b in zip(outcome["final_hours"], verification["sun_hours"])
    ]
    worst = max(deltas) if deltas else 0.0

    points = []

    for index in range(len(scene.protected_points)):
        final = outcome["final_hours"][index]
        points.append({
            "index": index,
            "baseline_hours": round(outcome["baseline_hours"][index], 4),
            "initial_hours": round(outcome["initial_hours"][index], 4),
            "final_hours": round(final, 4),
            "meets_requirement": bool(final + 1e-9 >= settings.required_sun_hours),
            "solvable_from_baseline": bool(outcome["solvable_mask"][index]),
        })

    summary = {
        "points": points,
        "required": settings.required_sun_hours,
        "retained": result["retained_ratio"],
        "verified": worst < 1e-9,
    }
    all_ok = all(p["meets_requirement"] for p in points)

    data = {
        "model": build_model(scene, result, settings),
        "summary": summary,
    }
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")

    settings_rows = [
        ("地点", "{0:.4f}°N, {1:.4f}°E, UTC{2:+g}".format(
            settings.latitude, settings.longitude, settings.timezone)),
        ("分析日", "{0:04d}-{1:02d}-{2:02d}".format(
            settings.year, settings.month, settings.day)),
        ("时段", "{0:g}:00–{1:g}:00，步长 {2:g} 分钟".format(
            settings.start_hour, settings.end_hour, settings.time_step)),
        ("日照要求", "连续 {0:g} 分钟起算，需满 {1:g} 小时".format(
            settings.minimum_continuous_minutes, settings.required_sun_hours)),
        ("北向", "{0:g}°（{1}）".format(
            abs(settings.north_angle),
            "正北" if abs(settings.north_angle) < 1e-9 else
            ("北偏东" if -settings.north_angle > 0 else "北偏西"))),
        ("体素尺寸", "{0:g} × {1:g} 米".format(
            settings.voxel_size_xy, settings.voxel_size_z)),
        ("太阳样本", "{0} 个时间区间".format(len(result["samples"]))),
    ]

    stats_rows = [
        ("体素总数", "{0}（{1} 柱）".format(len(grid.records), grid.columns)),
        ("完整 / 边界裁切", "{0} / {1}".format(grid.full_count, grid.clipped_count)),
        ("保留 / 切除", "{0} / {1}".format(len(result["kept"]), len(result["removed"]))),
        ("原始体积", "{0:,.0f} m³".format(grid.total_volume)),
        ("保留体积", "{0:,.0f} m³".format(result["kept_volume"])),
        ("迭代轮数", "{0}".format(len(outcome["iteration_data"]))),
    ]

    def table(rows):
        return "\n".join(
            "<tr><th>{0}</th><td>{1}</td></tr>".format(k, v) for k, v in rows
        )

    return TEMPLATE.format(
        title=title,
        verdict="全部达标" if all_ok else "尚有点位不达标",
        verdict_css="ok" if all_ok else "bad",
        retained="{0:.1f}%".format(result["retained_ratio"] * 100),
        kept_volume="{0:,.0f}".format(result["kept_volume"]),
        total_volume="{0:,.0f}".format(grid.total_volume),
        point_count=len(points),
        required="{0:g}".format(settings.required_sun_hours),
        verify_text=(
            "通过，偏差 {0:.1e} 小时".format(worst) if summary["verified"]
            else "不一致，偏差 {0:.2e} 小时".format(worst)
        ),
        verify_css="ok" if summary["verified"] else "bad",
        rows=_rows(summary),
        settings_rows=table(settings_rows),
        stats_rows=table(stats_rows),
        payload=payload,
        viewer_js=VIEWER_JS,
    )


TEMPLATE = """<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<style>
:root {{
  --bg:#f6f7f8; --card:#fff; --ink:#1c2530; --muted:#6b7683;
  --line:#e3e7ea; --ok:#2f7d4f; --bad:#c0392b; --warn:#b8860b;
}}
@media (prefers-color-scheme: dark) {{
  :root {{ --bg:#14181c; --card:#1c2229; --ink:#e8edf2; --muted:#95a1ad;
           --line:#2b333c; --ok:#5fbe86; --bad:#e2705f; --warn:#d6a545; }}
}}
* {{ box-sizing:border-box; }}
body {{ margin:0; background:var(--bg); color:var(--ink);
  font:15px/1.6 ui-sans-serif,system-ui,"PingFang SC","Microsoft YaHei",sans-serif; }}
.wrap {{ max-width:1180px; margin:0 auto; padding:28px 20px 60px; }}
h1 {{ font-size:22px; margin:0 0 4px; letter-spacing:-.01em; }}
.sub {{ color:var(--muted); font-size:13px; margin-bottom:22px; }}
.cards {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(170px,1fr));
  gap:12px; margin-bottom:20px; }}
.card {{ background:var(--card); border:1px solid var(--line);
  border-radius:10px; padding:14px 16px; }}
.card .k {{ color:var(--muted); font-size:12px; }}
.card .v {{ font-size:24px; font-weight:650; margin-top:3px; letter-spacing:-.02em; }}
.card .v small {{ font-size:13px; font-weight:400; color:var(--muted); }}
.ok {{ color:var(--ok); }} .bad {{ color:var(--bad); }} .warn {{ color:var(--warn); }}
.panel {{ background:var(--card); border:1px solid var(--line);
  border-radius:10px; margin-bottom:18px; overflow:hidden; }}
.panel h2 {{ font-size:14px; margin:0; padding:13px 16px; border-bottom:1px solid var(--line);
  font-weight:600; }}
.panel .body {{ padding:14px 16px; }}
#view {{ display:block; width:100%; height:520px; background:
  linear-gradient(180deg,rgba(140,160,180,.10),transparent); touch-action:none;
  cursor:grab; }}
#view:active {{ cursor:grabbing; }}
.bar-row {{ display:flex; gap:6px; flex-wrap:wrap; padding:11px 16px;
  border-bottom:1px solid var(--line); }}
button {{ font:inherit; font-size:12.5px; padding:5px 11px; border-radius:6px;
  border:1px solid var(--line); background:transparent; color:var(--ink);
  cursor:pointer; }}
button:hover {{ border-color:var(--muted); }}
button.on {{ background:var(--ink); color:var(--card); border-color:var(--ink); }}
button.off {{ opacity:.4; }}
.legend {{ display:flex; gap:16px; flex-wrap:wrap; padding:10px 16px;
  font-size:12.5px; color:var(--muted); border-top:1px solid var(--line); }}
.sw {{ display:inline-block; width:11px; height:11px; border-radius:2px;
  margin-right:5px; vertical-align:-1px; }}
table {{ width:100%; border-collapse:collapse; font-size:13.5px; }}
th, td {{ text-align:left; padding:8px 10px; border-bottom:1px solid var(--line); }}
th {{ color:var(--muted); font-weight:500; white-space:nowrap; }}
td.num {{ text-align:right; font-variant-numeric:tabular-nums; white-space:nowrap; }}
.barcell {{ width:34%; }}
.bar {{ display:block; height:7px; border-radius:4px; background:var(--ok); min-width:2px; }}
.two {{ display:grid; grid-template-columns:1fr 1fr; gap:18px; }}
@media (max-width:820px) {{ .two {{ grid-template-columns:1fr; }} }}
.note {{ font-size:12.5px; color:var(--muted); border-left:3px solid var(--line);
  padding:10px 14px; margin-top:6px; }}
@media print {{
  body {{ background:#fff; }} .bar-row {{ display:none; }}
  .panel, .card {{ break-inside:avoid; }}
}}
</style></head><body><div class="wrap">

<h1>{title}</h1>
<div class="sub">日照约束体量切削结果 · 设计阶段近似，非报审结论</div>

<div class="cards">
  <div class="card"><div class="k">结论</div>
    <div class="v {verdict_css}">{verdict}</div></div>
  <div class="card"><div class="k">体积保留率</div>
    <div class="v">{retained}</div></div>
  <div class="card"><div class="k">保留体积</div>
    <div class="v">{kept_volume} <small>/ {total_volume} m³</small></div></div>
  <div class="card"><div class="k">保护点</div>
    <div class="v">{point_count} <small>个 · 要求 {required}h</small></div></div>
  <div class="card"><div class="k">独立复核</div>
    <div class="v {verify_css}" style="font-size:15px;padding-top:7px">{verify_text}</div></div>
</div>

<div class="panel">
  <h2>可建体量</h2>
  <div class="bar-row">
    <button data-view="-35,28" class="on">轴测 西南</button>
    <button data-view="35,28">轴测 东南</button>
    <button data-view="-145,28">轴测 西北</button>
    <button data-view="0,89">顶视</button>
    <button data-view="0,0">南立面</button>
    <button data-view="-90,0">西立面</button>
    <span style="flex:1"></span>
    <button data-toggle="kept">保留体量</button>
    <button data-toggle="removed">切除体量</button>
    <button data-toggle="context">周边建筑</button>
    <button data-toggle="points">保护点</button>
    <button data-toggle="grid">地面网格</button>
    <button data-toggle="edges">棱线</button>\n    <button id="save">导出图片</button>
  </div>
  <canvas id="view"></canvas>
  <div class="legend">
    <span><i class="sw" style="background:rgb(92,141,106)"></i>保留体量</span>
    <span><i class="sw" style="background:rgba(190,106,96,.45)"></i>切除体量</span>
    <span><i class="sw" style="background:rgb(140,146,154)"></i>周边建筑</span>
    <span><i class="sw" style="background:#2f7d4f"></i>达标保护点</span>
    <span><i class="sw" style="background:#c0392b"></i>不达标保护点</span>
    <span style="margin-left:auto">拖拽旋转 · 滚轮缩放 · Shift+拖拽平移</span>
  </div>
</div>

<div class="panel">
  <h2>逐点日照</h2>
  <div class="body" style="padding:0">
    <table>
      <tr><th>点</th><th class=num>基准</th><th class=num>切削前</th>
          <th class=num>切削后</th><th>相对要求</th><th>状态</th></tr>
      {rows}
    </table>
  </div>
  <div class="body">
    <div class="note">
      <b>基准</b>：只有周边建筑时能晒多久。<b>切削前</b>：加上原设计体量后剩多少。
      <b>切削后</b>：本次结果。<br>
      “基准即不可解”表示周边现状本身已让该点不达标，删设计体量也救不回来。
    </div>
  </div>
</div>

<div class="two">
  <div class="panel"><h2>计算参数</h2>
    <div class="body" style="padding:0"><table>{settings_rows}</table></div></div>
  <div class="panel"><h2>体素与切削</h2>
    <div class="body" style="padding:0"><table>{stats_rows}</table></div></div>
</div>

<div class="panel"><h2>适用边界</h2><div class="body">
  <div class="note" style="border-color:var(--warn)">
    本结果为<b>设计阶段近似</b>。采样对象是三维点，不是法规规定的窗台或满窗测点，
    <b>不能作为日照报审结论</b>。切削采用确定性贪心启发式，给出一个可用解，
    不声称是体积最大的解；结果随体素尺寸变化，引用时须连体素尺寸一并说明。
    几何限于平面轮廓竖直拉伸，不含悬挑、斜屋面与曲面表皮。
  </div>
</div></div>

</div>
<script>const DATA = {payload};</script>
<script>{viewer_js}</script>
</body></html>
"""
