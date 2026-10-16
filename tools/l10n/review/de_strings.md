# German strings and text files: doubts

Most doubtful first. strings.txt: 589 keys. text/: 206 files (all under 1600 bytes, Latin-1 safe, CRLF kept).

## Over maxlen (menus do not wrap; German does not fit)

- `BACK` -> `ZURÜCK` (6 chars, maxlen 5). Used on every Back button. Alternative: `ZURÜ`/`<` not sensible; consider widening the button or using `BACK`-style short `ZUR.`.
- `NO` -> `NEIN` (4 chars, maxlen 2). Used in all confirm dialogs. No shorter German word; button width must grow.
- `Save` -> `Speichern` (9 chars, maxlen 5). Title/button in the save menu. Possible shorter: `Sichern` (7), still over.
- `Chickening out already?` -> `Schon kneifen?` (14, maxlen 12; the English itself is 23, so maxlen is probably not binding).
- Restart-confirm lines (`This will apply video` etc.): English already exceeds maxlen 14, German is similar length; assumed non-binding.
- Load menu labels (`Manual Saved Games`, `Autosaved Games`, `ACTIVATE TO SHOW ...`): English exceeds maxlen, German is longer by 1-4 chars (`AKTIVIEREN FÜR AUTOSPEICHERSTÄNDE` 33 chars). Check these visually.

## Terminology doubts

1. `Läufer` for "Lopers" (X-creature class, text/boss2, xlabs, mission5d). Invented term; "Springer"/"Schleicher" are alternatives. Subtitle side says "trabende Kreatur".
2. `Operation Wiederauferstehung` for "Operation Resurrection" and `Über-Soldat` / `Supersoldat` split: user decision applied (Über-Soldat for the project name, Supersoldat for "Super Soldier"). Mission 7 title reads "OPERATION WIEDERAUFERSTEHUNG".
3. Deathshead is "Totenkopf" everywhere (user decision), including the title "MISSION 5: DEATHSHEADS SPIELPLATZ" -> now "TOTENKOPFS SPIELPLATZ".
4. `GWA` as abbreviation of Geheimwaffenanlage ("SWF") in objective screens and footnotes ("GWA = Geheimwaffenanlage"). Invented abbreviation, used to save width.
5. `Tram` -> `Seilbahn` (cable car). The English "tram" at Castle Wolfenstein is a cable car; if the game visuals show a rail tram, use `Bahn`.
6. `Schloss` for both "Castle" (Wolfenstein) and "Chateau" (Schufstaffel). Both translated identically; `Burg Wolfenstein` would be the usual German name but `Schloss Wolfenstein` was kept for consistency with the subtitles.
7. `Eagle's Nest` / `Mother Hen` kept in English as radio callsigns (coordinator decision).
8. Key names inside training texts follow the German control labels in strings.txt (`Angriff`, `Aktivieren`, `Treten`, `Springen`, `Ducken`, `Nachladen`, `Heranzoomen`). `Rennen`, `Sekundärfeuer`, `Alternativfeuer` have no matching strings.txt label (the engine's bind names are English); verify against the bind menu.

## Strings with unclear context

- `Health` -> `Gesundheit` (pickup name and savegame info label; the HUD shows "%s benutzt" via `Use %s` -> `%s benutzt`. Verify word order in-game: the English is "Use <item>").
- `Lookup:  ` -> `Hochsehen:  ` (key binding "look up"; trailing spaces kept).
- Credits: names and company names left unchanged; role titles translated (`QUALITÄTSSICHERUNG` etc.).
- Debug/internal strings (clipboard script errors, `popup` message) left in English.
- 97 keys are identical in German (numerics, brand names, debug text, "Audio").

## Text-file layout risks

- Briefing and objective pages keep the same line counts as English except res_p4 (one line shorter). Pages `res_p*` were re-wrapped by hand to 42 columns; German is longer, so page 1 (`res_p1`) and page 8 are the tightest.
- Objective lines were shortened with imperative phrases (`Hinterausgang des Schlosses finden`) to avoid extra lines; lines are up to ~40 characters after a 11-space indent. If the objective box is narrower than the English longest line, they may clip.
- Briefing pages split mid-sentence (m1_*_p2/p3, m2_l4_p3, m4_l13_p2/p4, m5_l18_p2/p3, m6_l20..l22). German word order puts the verb at the end, so the split point was moved to a clause boundary equivalent to the English.
- `zbook1.txt` is "blah blah" placeholder text, copied unchanged.
- Notebook letters (cl_*) keep period voice; `Strasse` (Zemph's skeptic in zem_p1) was left as "Strasse" (not the Wilhelm Strasse of the subtitles; same name though, so consistent).
