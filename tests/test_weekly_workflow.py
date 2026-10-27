#!/usr/bin/env python3
"""Offline integration test: Week 8 rollover and Thursday picks using fixture data."""
import csv
import importlib.util
import json
import pathlib
import shutil
import tempfile

ROOT=pathlib.Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("weekly",ROOT/"scripts/weekly_update.py")
weekly=importlib.util.module_from_spec(spec)
spec.loader.exec_module(weekly)
data=json.loads((ROOT/"data/weeks/week-08.json").read_text())
assert len(data["games"])==14
with tempfile.TemporaryDirectory() as temp:
    root=pathlib.Path(temp)
    for folder in ("config","weeks","data/weeks","data/picks"):
        (root/folder).mkdir(parents=True,exist_ok=True)
    shutil.copy2(ROOT/"config/season.json",root/"config/season.json")
    shutil.copy2(ROOT/"weeks/week-08.html",root/"weeks/week-07.html")
    shutil.copy2(ROOT/"index.html",root/"index.html")
    cfg=json.loads((root/"config/season.json").read_text())
    cfg["currentWeek"]=7
    cfg["template"]="weeks/week-07.html"
    (root/"config/season.json").write_text(json.dumps(cfg))
    # Simulate Tuesday with the provided Week 8 matchups; no network needed.
    weekly.ROOT=root
    weekly.CONFIG=root/"config/season.json"
    weekly.get_schedule=lambda season,week:data["games"]
    weekly.rollover(8)
    weekly.check(8)
    generated=(root/"weeks/week-08.html").read_text()
    assert "7 · Current" not in generated
    assert "8 · Current" in generated
    assert "7 · Final" in generated
    assert "week=8&seasontype" in generated
    assert 'const week7OfficialPicks="";' in generated
    assert len(json.loads((root/"data/weeks/week-08.json").read_text())["games"])==14
    assert 'week-08.html' in (root/"index.html").read_text()
    print("PASS: Tuesday rollover, 14 matchups, landing page, current/final labels")
    # Simulate Thursday with 3 players, all 14 picks, and numeric tiebreakers.
    sheet=root/"test-picks.csv"
    columns=["name"]+["game_%02d"%(i+1) for i in range(14)]+["tiebreaker"]
    with sheet.open("w",newline="") as f:
        w=csv.DictWriter(f,fieldnames=columns)
        w.writeheader()
        for idx,name in enumerate(("Alice","Bob","Carol")):
            w.writerow(dict(zip(columns,[name]+[g["away"] if idx%2==0 else g["home"] for g in data["games"]]+[str(40+idx)])))
    weekly.picks(8,str(sheet))
    weekly.check(8)
    updated=(root/"weeks/week-08.html").read_text()
    assert "Alice|" in updated and "Bob|" in updated and "Carol|" in updated
    assert json.loads((root/"data/weeks/week-08.json").read_text())["status"]=="picks-uploaded"
    print("PASS: Thursday import, 3 players, 14 valid picks each, and tiebreakers")
    # Negative test: reject missing selection.
    with sheet.open("w",newline="") as f:
        w=csv.DictWriter(f,fieldnames=columns)
        w.writeheader()
        w.writerow(dict(zip(columns,["Bad Player"]+["" for _ in data["games"]]+["44"])))
    try:
        weekly.picks(8,str(sheet))
    except ValueError:
        print("PASS: Invalid picks rejected")
    else:
        raise AssertionError("Invalid picks were accepted")
print("PASS: Offline integration test complete. Live main branch untouched.")
