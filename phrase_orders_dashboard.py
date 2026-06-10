#!/usr/bin/env python3
"""
Phrase Translation Orders Dashboard
=====================================
Fetches all translation orders across all projects and generates
a self-contained HTML file you can open in any browser.

Usage:
    pip install requests
    python phrase_orders_dashboard.py

Output:
    phrase_orders_dashboard.html   ← open this in your browser

Run daily (or set up a cron job) to keep the dashboard fresh.
"""

import json
import os
import time
import sys
import requests
from datetime import datetime, timezone
from pathlib import Path

# ── CONFIGURE ─────────────────────────────────────────────────────────────────
PHRASE_TOKEN = os.environ.get("PHRASE_TOKEN", "YOUR_API_TOKEN_HERE")
BASE_URL     = "https://api.phrase.com/v2"
OUTPUT_FILE  = "phrase_orders_dashboard.html"
# ─────────────────────────────────────────────────────────────────────────────

HEADERS = {"Authorization": f"token {PHRASE_TOKEN}"}


def api_get(path: str, params: dict = None) -> list | dict:
    results, page = [], 1
    while True:
        p = {"per_page": 100, "page": page, **(params or {})}
        for attempt in range(5):
            resp = requests.get(f"{BASE_URL}{path}", headers=HEADERS, params=p)
            if resp.status_code == 429:
                wait = 10 * (attempt + 1)
                print(f"  Rate limited — waiting {wait}s…")
                time.sleep(wait)
                continue
            resp.raise_for_status()
            break
        data = resp.json()
        if not data:
            break
        if isinstance(data, list):
            results.extend(data)
            if len(data) < 100:
                break
            page += 1
        else:
            return data
        time.sleep(0.5)
    return results


def fetch_all_orders() -> list[dict]:
    print("Fetching projects…")
    projects = api_get("/projects")
    print(f"  Found {len(projects)} projects")

    all_orders = []
    for i, proj in enumerate(projects, 1):
        print(f"  [{i}/{len(projects)}] {proj['name']}", end="", flush=True)
        try:
            orders = api_get(f"/projects/{proj['id']}/orders")
            for o in orders:
                o["_project_name"] = proj["name"]
                o["_project_id"] = proj["id"]
            all_orders.extend(orders)
            print(f" → {len(orders)} orders")
        except Exception:
            print(" → skipped")
        time.sleep(0.5)

    return all_orders


def fmt_date(iso: str) -> str:
    if not iso:
        return ""
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return dt.strftime("%-d %b %Y")
    except Exception:
        return iso[:10]


def generate_html(orders: list[dict]) -> str:
    total       = len(orders)
    in_progress = sum(1 for o in orders if o.get("state") in ("in_progress", "confirmed"))
    completed   = sum(1 for o in orders if o.get("state") == "completed")
    avg_pct     = round(sum(o.get("progress_percent", 0) for o in orders) / total) if total else 0
    projects_with_orders = len({o["_project_id"] for o in orders})
    generated   = datetime.now(timezone.utc).strftime("%-d %b %Y at %H:%M UTC")

    orders_json = json.dumps(orders, ensure_ascii=False)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Phrase Orders Dashboard</title>
<style>
  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
  :root {{
    --bg: #f8f8f6;
    --surface: #ffffff;
    --border: #e4e4e0;
    --text: #1a1a18;
    --muted: #6b6b66;
    --blue-bg: #e8f0fc; --blue-text: #1a44a8;
    --amber-bg: #fef3d8; --amber-text: #8a5a00;
    --green-bg: #e6f4e6; --green-text: #1a6b1a;
    --gray-bg: #f0f0ec; --gray-text: #4a4a46;
    --red-bg: #fce8e8; --red-text: #a81a1a;
    --progress-low: #378ADD; --progress-mid: #BA7517; --progress-done: #639922;
  }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
         background: var(--bg); color: var(--text); font-size: 14px; line-height: 1.5; }}
  .page {{ max-width: 900px; margin: 0 auto; padding: 2rem 1.5rem; }}
  header {{ display: flex; align-items: baseline; justify-content: space-between;
            border-bottom: 1px solid var(--border); padding-bottom: 1rem; margin-bottom: 1.5rem; }}
  h1 {{ font-size: 20px; font-weight: 600; }}
  .generated {{ font-size: 12px; color: var(--muted); }}
  .summary {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
              gap: 12px; margin-bottom: 1.75rem; }}
  .metric {{ background: var(--surface); border: 1px solid var(--border);
             border-radius: 10px; padding: 1rem; }}
  .metric-label {{ font-size: 11px; color: var(--muted); margin-bottom: 4px; text-transform: uppercase; letter-spacing: .04em; }}
  .metric-value {{ font-size: 24px; font-weight: 600; }}
  .toolbar {{ display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 1.25rem; align-items: center; }}
  .toolbar select, .toolbar input {{
    font-size: 13px; padding: 6px 10px; border: 1px solid var(--border);
    border-radius: 8px; background: var(--surface); color: var(--text); outline: none; }}
  .toolbar select:focus, .toolbar input:focus {{ border-color: #888; }}
  #count {{ font-size: 12px; color: var(--muted); margin-left: auto; }}
  .order {{ background: var(--surface); border: 1px solid var(--border);
            border-radius: 10px; padding: 1rem 1.25rem; margin-bottom: 10px; }}
  .order-top {{ display: flex; align-items: flex-start; justify-content: space-between; gap: 8px; margin-bottom: 10px; }}
  .order-name {{ font-size: 14px; font-weight: 600; margin-bottom: 3px; }}
  .order-meta {{ font-size: 12px; color: var(--muted); display: flex; flex-wrap: wrap; gap: 6px; align-items: center; }}
  .proj-tag {{ background: var(--blue-bg); color: var(--blue-text);
               font-size: 11px; padding: 2px 8px; border-radius: 99px; font-weight: 500; }}
  .badge {{ display: inline-block; font-size: 11px; font-weight: 600;
            padding: 3px 10px; border-radius: 99px; white-space: nowrap; }}
  .badge-confirmed   {{ background: var(--blue-bg);  color: var(--blue-text); }}
  .badge-in_progress {{ background: var(--amber-bg); color: var(--amber-text); }}
  .badge-completed        {{ background: var(--green-bg); color: var(--green-text); }}
  .badge-cancelled   {{ background: var(--gray-bg);  color: var(--gray-text); }}
  .badge-completed   {{ background: var(--green-bg); color: var(--green-text); }}
  .badge-unknown     {{ background: var(--red-bg);   color: var(--red-text); }}
  .progress-bar-bg {{ height: 5px; background: var(--border); border-radius: 99px; overflow: hidden; margin: 8px 0 3px; }}
  .progress-bar-fill {{ height: 100%; border-radius: 99px; }}
  .progress-labels {{ display: flex; justify-content: space-between; font-size: 11px; color: var(--muted); }}
  .locales {{ display: flex; flex-wrap: wrap; gap: 4px; margin-top: 8px; }}
  .locale {{ font-size: 11px; background: var(--bg); border: 1px solid var(--border);
             padding: 2px 8px; border-radius: 99px; color: var(--muted); }}
  .empty {{ text-align: center; padding: 3rem; color: var(--muted); }}
  @media(max-width: 600px) {{ .order-top {{ flex-direction: column; }} }}
</style>
</head>
<body>
<div class="page">
  <header>
    <h1>Translation orders</h1>
    <span class="generated">Generated {generated}</span>
  </header>

  <div class="summary">
    <div class="metric"><div class="metric-label">Total orders</div><div class="metric-value">{total}</div></div>
    <div class="metric"><div class="metric-label">In progress</div><div class="metric-value">{in_progress}</div></div>
    <div class="metric"><div class="metric-label">Completed</div><div class="metric-value">{completed}</div></div>
    <div class="metric"><div class="metric-label">Avg. progress</div><div class="metric-value">{avg_pct}%</div></div>
    <div class="metric"><div class="metric-label">Projects</div><div class="metric-value">{projects_with_orders}</div></div>
  </div>

  <div class="toolbar">
    <select id="filter-project" onchange="render()">
      <option value="">All projects</option>
    </select>
    <div id="filter-state" style="display:flex;gap:10px;flex-wrap:wrap;align-items:center;">
      <label style="font-size:13px;display:flex;align-items:center;gap:4px;cursor:pointer;"><input type="checkbox" value="confirmed"   onchange="render()"> Confirmed</label>
      <label style="font-size:13px;display:flex;align-items:center;gap:4px;cursor:pointer;"><input type="checkbox" value="in_progress" onchange="render()"> In progress</label>
      <label style="font-size:13px;display:flex;align-items:center;gap:4px;cursor:pointer;"><input type="checkbox" value="completed"   onchange="render()"> Completed</label>
      <label style="font-size:13px;display:flex;align-items:center;gap:4px;cursor:pointer;"><input type="checkbox" value="cancelled"   onchange="render()"> Cancelled</label>
    </div>
    <input id="search" type="search" placeholder="Search order name…" oninput="render()" style="min-width:180px;">
    <label style="font-size:13px;color:var(--muted);">From</label>
    <input id="date-from" type="date" onchange="render()" style="font-size:13px;">
    <label style="font-size:13px;color:var(--muted);">To</label>
    <input id="date-to" type="date" onchange="render()" style="font-size:13px;">
    <span id="count"></span>
  </div>

  <div id="list"></div>
</div>

<script>
const ALL_ORDERS = {orders_json};

function progressColor(p) {{
  if (p >= 100) return '#639922';
  if (p >= 50)  return '#BA7517';
  return '#378ADD';
}}

function badge(state) {{
  const labels = {{confirmed:'Confirmed',in_progress:'In progress',completed:'Completed',done:'Completed',cancelled:'Cancelled'}};
  const cls = labels[state] ? state : 'unknown';
  return `<span class="badge badge-${{cls}}">${{labels[state] || state}}</span>`;
}}

function render() {{
  const fp = document.getElementById('filter-project').value;
  const selectedStates = new Set(
    [...document.querySelectorAll('#filter-state input:checked')].map(cb => cb.value)
  );
  const q        = document.getElementById('search').value.toLowerCase();
  const dateFrom = document.getElementById('date-from').value;
  const dateTo   = document.getElementById('date-to').value;

  let orders = ALL_ORDERS
    .filter(o => !fp || o._project_id === fp)
    .filter(o => selectedStates.size === 0 || selectedStates.has(o.state))
    .filter(o => !q  || (o.name||'').toLowerCase().includes(q))
    .filter(o => !dateFrom || (o.created_at||'') >= dateFrom)
    .filter(o => !dateTo   || (o.created_at||'') <= dateTo + 'T23:59:59')
    .sort((a,b) => new Date(b.created_at||0) - new Date(a.created_at||0));

  document.getElementById('count').textContent = `${{orders.length}} order${{orders.length===1?'':'s'}}`;

  const list = document.getElementById('list');
  if (!orders.length) {{
    list.innerHTML = '<div class="empty">No orders match the current filter.</div>';
    return;
  }}

  list.innerHTML = orders.map(o => {{
    const pct     = Math.round(o.progress_percent || 0);
    const locales = (o.target_locales||[]).map(l=>`<span class="locale">${{l.code}}</span>`).join('');
    const lsp     = o.lsp ? ` · ${{o.lsp}}` : '';
    const amount  = o.amount_in_cents ? ` · ${{(o.amount_in_cents/100).toFixed(2)}} ${{(o.currency||'').toUpperCase()}}` : '';
    const created = o.created_at ? o.created_at.slice(0,10) : '';
    return `<div class="order">
      <div class="order-top">
        <div>
          <div class="order-name">${{o.name || o.id}}</div>
          <div class="order-meta">
            <span class="proj-tag">${{o._project_name}}</span>
            ${{created}}${{lsp}}${{amount}}
          </div>
        </div>
        ${{badge(o.state)}}
      </div>
      <div class="progress-bar-bg">
        <div class="progress-bar-fill" style="width:${{pct}}%;background:${{progressColor(pct)}};"></div>
      </div>
      <div class="progress-labels"><span>Progress</span><span>${{pct}}%</span></div>
      ${{locales ? `<div class="locales">${{locales}}</div>` : ''}}
    </div>`;
  }}).join('');
}}

(function init() {{
  // Default date range: last 14 days
  const today = new Date();
  const twoWeeksAgo = new Date();
  twoWeeksAgo.setDate(today.getDate() - 14);
  document.getElementById('date-to').value = today.toISOString().slice(0, 10);
  document.getElementById('date-from').value = twoWeeksAgo.toISOString().slice(0, 10);{
  const projects = [...new Map(ALL_ORDERS.map(o=>[o._project_id,o._project_name])).entries()]
    .sort((a,b)=>a[1].localeCompare(b[1]));
  const sel = document.getElementById('filter-project');
  projects.forEach(([id,name]) => {{
    const opt = document.createElement('option');
    opt.value = id; opt.textContent = name;
    sel.appendChild(opt);
  }});
  render();
}})();
</script>
</body>
</html>"""


def main():
    if PHRASE_TOKEN == "YOUR_API_TOKEN_HERE":
        print("ERROR: Set PHRASE_TOKEN before running.")
        sys.exit(1)

    orders = fetch_all_orders()
    print(f"\nTotal orders found: {len(orders)}")

    html = generate_html(orders)
    Path(OUTPUT_FILE).write_text(html, encoding="utf-8")
    print(f"Dashboard written to: {OUTPUT_FILE}")
    print(f"Open it with: open {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
