# NFL Pick'em — weekly update workflow (development branch)

This branch is **not published to GitHub Pages**. The live `main` branch and the Android/iPhone layouts are unchanged.

## Single source of truth

- `config/season.json`: season, current week, template, and picks status
- `data/weeks/week-XX.json`: schedule and venues; generated from ESPN
- `data/picks/week-XX.csv`: validated player picks
- `scripts/weekly_update.py`: Tuesday rollover, Thursday import, and pre-publish checks
- `weeks/week-XX.html`: existing rich scoreboard generated from the approved Week 8 design

## Tuesday

Run from the repository root:

```bash
python3 scripts/weekly_update.py rollover --week 9
python3 scripts/weekly_update.py check --week 9
```

The rollover reads the ESPN scoreboard schedule, creates the next week page and JSON, changes the homepage redirect, updates the current week, clears old selections, and generates the week dropdown. It refuses to overwrite an existing week. **Review the generated page and test Android/iPhone Safari before merging to main.**

## Thursday

Use a CSV with columns `name,game_01,...,game_14,tiebreaker` (the number of game columns must equal that week's schedule length). Game picks are team abbreviations, in the same chronological order as `data/weeks/week-XX.json`. Example: `CAR` or `GB` for game 1 in Week 8. All players must have exactly one valid selection for every game and a numeric Monday tiebreaker.

```bash
python3 scripts/weekly_update.py picks --week 9 --file /path/to/week9.csv
python3 scripts/weekly_update.py check --week 9
```

The importer rejects invalid picks, missing tiebreakers, and duplicate names. It keeps historical weeks intact.

## Safety rules

1. Never overwrite a historical week. No Week 7 picks should appear in Week 8.
2. Do not invent missing player picks or ESPN schedule data.
3. Do not change Android/iPhone layout CSS during a routine rollover.
4. Verify current/final dropdown labels, all game cards, ESPN Refresh, player counts, and picks/leaderboard before publishing.
5. Commit to this development branch first. Merge only after device testing.
6. The existing Tuesday/Thursday scheduled ChatGPT tasks must be updated to use these scripts **after** this workflow is validated and merged.

## Known limitations before production rollout

- The generator currently uses the full Week 8 HTML as its master, rather than fully extracting shared CSS/JS into a single dashboard. This preserves approved styling but remains a transitional architecture.
- ESPN's public endpoint may change, and TV networks may be unavailable for some games.
- The picks importer accepts CSV; PDF/image picks sheets need conversion to CSV before import.
- No automated browser/device regression tests are installed yet. Keep the development branch isolated until those checks are complete.
