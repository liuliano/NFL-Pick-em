#!/usr/bin/env python3
"""Build a new NFL Pick'em week without copying stale week-specific state.

Usage:
  python3 scripts/weekly_update.py rollover --week 9
  python3 scripts/weekly_update.py picks --week 9 --file downloads/week9.csv
  python3 scripts/weekly_update.py check --week 9

Run from the repository root. Commit generated changes after reviewing them.
"""
import argparse
import csv
import datetime as dt
import json
import pathlib
import re
import sys
import urllib.request
from zoneinfo import ZoneInfo

ROOT = pathlib.Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/season.json"
EASTERN = ZoneInfo("America/New_York")
ABBREV = {"JAX": "JAC", "WSH": "WAS", "LA": "LAR"}
def norm(value):
    return ABBREV.get(str(value).strip().upper(), str(value).strip().upper())
def read_config():
    return json.loads(CONFIG.read_text(encoding="utf-8"))
def write_config(cfg):
    CONFIG.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")
def scoreboard(season, week):
    url = ("https://site.api.espn.com/apis/site/v2/sports/football/nfl/"
           "scoreboard?dates=%s&seasontype=2&week=%s&limit=100" % (season, week))
    with urllib.request.urlopen(url, timeout=25) as response:
        return json.load(response)
def get_schedule(season, week):
    rows = []
    for event in scoreboard(season, week).get("events", []):
        comp = (event.get("competitions") or [{}])[0]
        teams = comp.get("competitors") or []
        away = next((t for t in teams if t.get("homeAway") == "away"), None)
        home = next((t for t in teams if t.get("homeAway") == "home"), None)
        if not away or not home:
            continue
        kickoff = dt.datetime.fromisoformat(event["date"].replace("Z", "+00:00")).astimezone(EASTERN)
        rows.append({
            "away": norm(away["team"]["abbreviation"]),
            "home": norm(home["team"]["abbreviation"]),
            "kickoff": kickoff.isoformat(timespec="seconds"),
            "stadium": comp.get("venue", {}).get("fullName", "Venue TBD"),
            "broadcast": ", ".join(comp.get("broadcasts", [{}])[0].get("names", [])) or "TV TBD",
            "espnId": event.get("id")
        })
    rows.sort(key=lambda x: (x["kickoff"], x["away"]))
    if not 1 <= len(rows) <= 16 or len({(r["away"], r["home"]) for r in rows}) != len(rows):
        raise ValueError("ESPN schedule incomplete or duplicated: %s games" % len(rows))
    return rows
def swap_const(html, name, value):
    pattern = r"(const " + re.escape(name) + r"=)[^;]+;"
    updated, count = re.subn(pattern, lambda m: m.group(1) + json.dumps(value, separators=(",", ":")) + ";", html, count=1)
    if count != 1:
        raise ValueError("Template missing constant " + name)
    return updated
def rollover(week):
    cfg = read_config()
    season = int(cfg["season"])
    rows = get_schedule(season, week)
    template = (ROOT / cfg["template"]).read_text(encoding="utf-8")
    # Reuse the full dashboard while replacing ALL week-specific schedule fields.
    html = swap_const(template, "games", [[r["away"], r["home"]] for r in rows])
    html = swap_const(html, "stadiums", ["📺 " + r["broadcast"] for r in rows])
    html = swap_const(html, "week7Stadiums", [r["stadium"] for r in rows])
    html = swap_const(html, "kickoffET", [r["kickoff"] for r in rows])
    previous = int(cfg["currentWeek"])
    html = html.replace("week=%s&seasontype" % previous, "week=%s&seasontype" % week)
    html = html.replace("WEEK %s • %s" % (previous, season), "WEEK %s • %s" % (week, season))
    html = html.replace("Week %s players" % previous, "Week %s players" % week)
    html = html.replace('class="big">%s</div><div>%s NFL' % (previous, season),
                        'class="big">%s</div><div>%s NFL' % (week, season))
    html = re.sub(r'nflw\d+(results|liveodds|favorites|entries)',
                  lambda m: "nflw%s%s" % (week, m.group(1)), html)
    html = re.sub(r'let raw=localStorage.getItem\("nflw\d+entries"\)\|\|"";',
                  'let raw=localStorage.getItem("nflw%sentries")||"";' % week, html)
    # Navigation is generated from the current week; no copied old sync scripts.
    html = re.sub(r'<script id="week8-nav-consistency-20261027">.*?</script>', "", html, flags=re.S)
    html = re.sub(r'<script id="week\d+-nav-consistency[^"]*">.*?</script>', "", html, flags=re.S)
    html = re.sub(r'<script id="generated-week-nav">.*?</script>', "", html, flags=re.S)
    nav = """<script id="generated-week-nav">(function(){
function sync(){const bar=document.getElementById('multiweek-bar');if(!bar)return;
const btn=bar.querySelector('#week-picker-button'),menu=bar.querySelector('#week-picker-menu');
if(!btn||!menu)return;const week=__WEEK__;
btn.innerHTML=week+' · Current <span aria-hidden="true">⌄</span>';
menu.innerHTML='';
for(let n=2;n<=week;n++){const a=document.createElement('a');
a.setAttribute('role','menuitem');a.href=n===5?'../index.html?week=5':'week-'+String(n).padStart(2,'0')+'.html'+(n<week?'?history=1':'');
a.textContent=n+' · '+(n===week?'Current ✓':'Final');
if(n===week)a.setAttribute('aria-current','page');menu.appendChild(a);}
}if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',sync);else sync();
})();</script>""".replace("__WEEK__", str(week))
    html = html.replace("</body>", nav + "</body>", 1)
    # Clear copied embedded picks and never publish another week's selections.
    html = re.sub(r'const week7OfficialPicks="[^"]*";', 'const week7OfficialPicks="";', html)
    html = re.sub(r'const week7ArchivedPicks="[^"]*";', 'const week7ArchivedPicks="";', html)
    html = re.sub(r'let raw=week7OfficialPicks;', 'let raw=localStorage.getItem("nflw%sentries")||"";' % week, html)
    html = re.sub(r'localStorage.setItem\("nflw\d+entries",week7OfficialPicks\);', "", html)
    # Remove any stale hard-coded current-week header or picker script from template.
    html = re.sub(r'(id="week-picker-button"[^>]*>)[^<]*(?=<span)', r'\g<1>%s · Current ' % week, html)
    if ("week=%s&seasontype" % week) not in html:
        raise ValueError("ESPN endpoint did not update; aborting")
    target = ROOT / ("weeks/week-%02d.html" % week)
    if target.exists():
        raise FileExistsError("%s exists; refusing to overwrite" % target)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(html, encoding="utf-8")
    data = ROOT / ("data/weeks/week-%02d.json" % week)
    data.parent.mkdir(parents=True, exist_ok=True)
    data.write_text(json.dumps({"season":season,"week":week,"status":"picks-pending","games":rows},indent=2)+"\n",encoding="utf-8")
    cfg["currentWeek"] = week
    cfg["status"] = "picks-pending"
    write_config(cfg)
    print("Created %s with %s ESPN games; picks pending" % (target.relative_to(ROOT),len(rows)))
    print("Review the generated week, then update the homepage redirect in index.html.")
def picks(week, filename):
    cfg = read_config()
    data = json.loads((ROOT / ("data/weeks/week-%02d.json" % week)).read_text(encoding="utf-8"))
    games = data["games"]
    expected = [{g["away"], g["home"]} for g in games]
    rows = []
    with open(filename, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            name = (row.get("name") or "").strip()
            values = [(row.get("game_%02d" % (i+1)) or "").strip().upper() for i in range(len(games))]
            if not name or any(norm(v) not in expected[i] for i,v in enumerate(values)):
                raise ValueError("Invalid or missing selection for %s" % (name or "unnamed player"))
            tb = (row.get("tiebreaker") or "").strip()
            if not tb.isdigit():
                raise ValueError("Missing numeric tiebreaker for " + name)
            rows.append((name, [norm(v) for v in values], int(tb)))
    if not rows or len({r[0].casefold() for r in rows}) != len(rows):
        raise ValueError("No picks or duplicate player names")
    target = ROOT / ("data/picks/week-%02d.csv" % week)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("name,"+",".join("game_%02d" % (i+1) for i in range(len(games)))+",tiebreaker\n"+
                      "\n".join(",".join([name]+values+[str(tb)]) for name,values,tb in rows)+"\n",encoding="utf-8")
    page = ROOT / ("weeks/week-%02d.html" % week)
    html = page.read_text(encoding="utf-8")
    payload = "\\n".join(name+"|"+",".join(values)+"|"+str(tb) for name,values,tb in rows)
    html, count = re.subn(r'const week7OfficialPicks="[^"]*";',
                           lambda _: "const week7OfficialPicks="+json.dumps(payload)+";", html, count=1)
    if count != 1:
        raise ValueError("Picks insertion point missing")
    html = re.sub(r'let raw=localStorage.getItem\("nflw\d+entries"\)\|\|"";',
                  'let raw=week7OfficialPicks;', html)
    page.write_text(html, encoding="utf-8")
    data["status"]="picks-uploaded"
    (ROOT / ("data/weeks/week-%02d.json" % week)).write_text(json.dumps(data,indent=2)+"\n",encoding="utf-8")
    cfg["status"]="picks-uploaded"
    write_config(cfg)
    print("Validated and loaded %s player pick sheets for Week %s" % (len(rows),week))
def check(week):
    cfg=read_config()
    data=json.loads((ROOT / ("data/weeks/week-%02d.json" % week)).read_text(encoding="utf-8"))
    html=(ROOT / ("weeks/week-%02d.html" % week)).read_text(encoding="utf-8")
    games=data["games"]
    assert len(games)>0 and len({(x["away"],x["home"]) for x in games})==len(games)
    assert "week=%s&seasontype" % week in html
    assert "generated-week-nav" in html or (week==8 and "week8-nav-consistency" in html)
    assert "Week %s players" % week in html
    assert "7 · Current" not in html if week>7 else True
    print("PASS: Week %s, %s games, navigation, ESPN endpoint, and labels" % (week,len(games)))
def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest="command",required=True)
    for name in ("rollover","picks","check"):
        p=sub.add_parser(name)
        p.add_argument("--week",type=int,required=True)
        if name=="picks":p.add_argument("--file",required=True)
    a=parser.parse_args()
    if a.command=="rollover":rollover(a.week)
    elif a.command=="picks":picks(a.week,a.file)
    else:check(a.week)
if __name__=="__main__":
    main()
