# Translation fit report (de, es)

Generated with `python3 tools/l10n/fit.py` (de and es, about 1217 measurements each). Menus were not edited.

## What was measured

- Pixel width of every translated menu string, using the engine formula (`Text_Width` in `iortcw/SP/code/ui/ui_main.c`):
  sum of glyph `xSkip` over the Latin-1 bytes, colour codes skipped, times scale times font `glyphScale`, truncated.
  Fonts come from the Steam `fontImage_{12,16,17,24}.dat`. `textfont` NORMAL/BIG/SMALL/HANDWRITING map to 16/24/12/17 pt.
  With no `textfont`, the font is 12 pt at scale <= 0.25, 24 pt above 0.4, otherwise 16 pt.
- Space available: the item rect (centred and aligned buttons), or the distance to the next element on the row
  (label, then the value column for YESNO / MULTI / SLIDER / BIND / EDITFIELD rows), plus the 640 px screen edge.
  Fullscreen menus are forced to 0 0 640 480 and item borders are counted.
- Rule: a string passes when it fits. It is only "tolerated" when it does not fit but is not wider than the English
  text, which overflows by the same amount.
- Text pages (`textfile` items): the engine's greedy wrap (`Item_Text_AutoWrapped_Paint`) is simulated and the last
  baseline is compared with the rect height. A page passes when it is no taller than the larger of the rect and the
  English page. Each file also gets a UTF-8 check, the 4000 byte Latin-1 limit and a check for characters that fold to '?'.
- Extras: key-bind status line, savegame list date column, old-save strings, and the character limits of the
  `ui_main.c` / `cgame` strings.
- Consistency: the quoted control names in `training*.txt` must be the translated Controls-menu labels.

## Result

| | before | after |
|---|---|---|
| de FAIL | 32 menu + 55 page | 11 (all layout-only, see below) |
| es FAIL | 37 menu + 35 page | 8 (all layout-only, see below) |

Both `strings.txt` files parse with all 589 English keys exactly once (no duplicates, nothing missing, nothing
extra). All 206 text files per language are valid UTF-8, with a largest page of 1250 bytes in Latin-1 (limit 4000)
and no new '?' folds.

## Fixes: strings.txt

Widths are in px at the item's own font and scale; "en" is the English width.

### German

| key | before | after | width (before -> after, en) |
|---|---|---|---|
| CD KEY | CD-KEY | CD KEY | 45 -> 44 (44) |
| This will apply video | Dies übernimmt die | Übernimmt Video- | now one phrase with the next line |
| This will apply sound | Dies übernimmt die | Übernimmt Ton- | 103 (132) |
| settings and return (shared by video, sound, restart) | Videoeinstellungen und | einstellungen und | 146 -> 112 (120) |
| to the Main Menu. | kehrt zum Hauptmenü zurück. | zurück ins Menü. | 191 -> 106 (113) |
| This will Set | Dies setzt die | Setzt die | 80 -> 52 (77) |
| and return to the Main Menu. | und kehrt zum Hauptmenü zurück. | und zurück zum Hauptmenü. | 218 -> 181 (184) |
| and return to the game. | und kehrt zum Spiel zurück. | dann zurück zum Spiel. | 175 -> 145 (149) |
| DEFAULTS | STANDARD | ORIGINAL | 66 -> 61 (62) |
| SELECT A SKILL LEVEL | SCHWIERIGKEITSGRAD WÄHLEN | SCHWIERIGKEIT | 197 -> 99 (138) |
| Autosaved Games | Autospeicherstände | Autosaves | 112 -> 59 (102) |
| ACTIVATE TO SHOW AUTOSAVED GAMES | AKTIVIEREN FÜR AUTOSPEICHERSTÄNDE | AUTOSAVES ANZEIGEN | 262 -> 148 (260) |
| ACTIVATE TO SHOW MANUAL SAVEGAMES | AKTIVIEREN FÜR MANUELLE SPIELSTÄNDE | MANUELLE SPIELSTÄNDE ANZEIGEN | 273 -> 232 (271) |
| SELECT SAVE GAME TO LOAD | SPIELSTAND ZUM LADEN WÄHLEN | SPIELSTAND WÄHLEN | 218 -> 139 (186) |
| SELECT TO PLAY LEVEL | STUFE ZUM SPIELEN WÄHLEN | STUFE WÄHLEN | 189 -> 101 (149) |
| Save (ingame_save window tab) | Speichern | Sichern | 61 -> 47 (29; room 44) |
| Save As: | Speichern als: | Dateiname: | label 95 -> 78 (label may be at most 79) |
| controller hint (controls_pad / ingame_controls_pad) | long sentence | shortened | 801 -> 659 (en 665) |

The invented abbreviation "GWA" (and the glued "GWAüberlaufen") is gone from `sfm.txt`; the pages now say
"Geheimwaffenanlage". The "Videoeinstellungen" wording on the sound-restart menu (shared key) was a real bug and is fixed.

### Spanish

| key | before | after | width (before -> after, en) |
|---|---|---|---|
| CD KEY | CLAVE CD | CD KEY | 60 -> 44 (44) |
| Gyro Aiming: | Apuntado con giroscopio: | Apuntar con giro: | 161 -> 117 (room 160) |
| Gyro Sensitivity: | Sensibilidad del giroscopio: | Sensib. del giroscopio: | 174 -> 143 (room 160) |
| Shadow Map Size: | Tamaño del mapa de sombras: | Tamaño de sombras: | 161 -> 109 (room 160) |
| This will apply video | Aplicará los ajustes | Aplicará el vídeo | 104 |
| This will apply sound | Aplicará los ajustes de sonido | Aplicará el sonido | 180 -> 110 (132) |
| settings and return (shared video/sound) | de vídeo y volverá | y volverá | 114 -> 59 (120); was wrong on the sound menu |
| to the Main Menu. | al menú principal. | al menú inicial. | 115 -> 99 (113) |
| This will Set | Se establecerán | Fijará | 95 -> 37 (77) |
| recommended video settings | ajustes de vídeo recomendados | ajustes de vídeo óptimos | 187 -> 149 (174) |
| and return to the Main Menu. | y se volverá al menú principal. | y volverá al menú principal. | 195 -> 179 (184) |
| and return to the game. | y se volverá al juego. | y volverá al juego. | 116 |
| DEFAULTS | RESTAURAR | ORIGINAL | 73 -> 61 (62) |
| Refresh | Renovar | Buscar | 51 -> 42 (room 44) |
| Go to Multiplayer mode? | ¿Ir al modo multijugador? | ¿Ir a multijugador? | 176 -> 132 (165) |
| Save (window tab) | Guardar | Grabar | 52 -> 44 (room 44) |
| Save As: | Guardar como: | Nombre: | 100 -> 58 (label may be at most 79) |
| (no savegames) | (sin partidas guardadas) | (sin partidas) | 24 -> 14 chars (limit 20) |
| (old savegame) | (partida antigua) | (partida vieja) | 17 -> 15 chars (limit 16) |
| (old savegame ver: %d) | (partida antigua ver: %d) | (partida vieja v%d) | 25 -> 20 chars (limit 24) |
| (old save ver: %d) | (guardado antiguo ver: %d) | (guardado viejo v%d) | 26 -> 20 chars (limit 24); date column 170 -> fits |
| controller hint | long sentence | shortened | 619 (en 665) |

German "Nein" is kept unchanged (NEIN) because nothing shorter is natural; see below.

## Fixes: text pages

Pages were up to 40% too tall in German (German is about 30% longer than English). All were rewritten shorter while
keeping the meaning. No page now exceeds the larger of the rect and the English height.

- Briefings (`briefing` / `pregame` / `test` menus, 254x456): de and es `boss2`, `dam`, `escape1`, `escape2`, `forest`, `sfm`,
  `tram`, `xlabs`; es `village2`.
- Objective pages (es, 280x200): `m3_l9_br_p1a`, `m4_l13_br_p1a`, `m4_l15_br_p1a` (hard line breaks removed so the engine wraps).
- Notebook pages (215-230 wide): de and es `m1_l1`-`m1_l3` (es), `m2_l4`-`m2_l8`, `m3_l9`, `m3_l10`, `m3_l12`, `m5_l18`,
  `m5_l19`, `m6_l21` (es `m6_l21`), `mission6d`, `zem_p1`, `zem_p2` (de).
- Training clipboards (260x360): de and es `training12`, `13`, `14`, `15`, `17`, `19`, `20`, `21`.
- Side fixes found on the way: German typos "dieOSA" and "schlucken.Wie" (run-together words); a doubled sentence in
  de `xlabs.txt`; untranslated "CLASSIFIED" in de `mission6d` (now "GEHEIM"); `m1_l2` / `m1_l3` (de) now match `m1_l1`.

## Consistency: control names in training pages

Every quoted control name now equals the translated Controls label (case aside, as in English).

| English | de label | es label |
|---|---|---|
| attack | Angriff | Atacar |
| activate | Aktivieren | Activar |
| jump / crouch | Springen / Ducken | Saltar / Agacharse |
| kick | Treten | Patada |
| reload | Nachladen | Recargar arma |
| auto pick-up | Auto-Aufnahme | Recoger objetos auto. |
| zoom in / zoom out | Heranzoomen / Herauszoomen | Acercar zoom / Alejar zoom |
| secondary fire, alternate fire | Alternativwaffe | Cambiar a alternativa |
| run | Rennen / Gehen | Correr / Caminar |
| auto run | Immer rennen | Correr siempre |

Changed: de 'Sekundärfeuer' and 'Alternativfeuer' -> 'Alternativwaffe', 'Rennen' -> 'Rennen / Gehen',
'Automatisch rennen' -> 'Immer rennen'; es 'fuego secundario' and 'fuego alternativo' -> 'cambiar a alternativa',
'recargar' -> 'recargar arma', 'correr' -> 'correr / caminar'. `fit.py` now checks this (`check_controls`).

## Remaining overflow (needs a menu layout change; menus not edited)

These cannot be fixed by wording without an unnatural abbreviation. All are on short fixed buttons.

| item | key | de (needed) | es (needed) | available |
|---|---|---|---|---|
| `setup.menu:368 back`, `:396 back_alt`; `play.menu:335 back`, `:353 back_alt`; `load.menu:423 back`, `:441 back_alt` (rect 30 450 40 14, font NORMAL, scale .23, textalignx 6) | BACK | ZURÜCK 49 px | ATRÁS 40 px | 34 px (en BACK 33) |
| `load.menu:460 accept`, `:478 accept_alt` (rect 560 450 40 14) | LOAD | LADEN 41 px | CARGAR 51 px | 34 px (en 33) |
| `quit.menu:127 no`, `multiplayer_pop.menu:91 no` (centred, rect 354..380, scale .3) | NO | NEIN 39 px | none (NO fits) | 26 px (en 23) |
| `ingame_save.menu:194 window` (tab, centred, rect 282..327) | Save | Sichern 47 px | none (Grabar 44 fits) | 44 px (en 29) |

Suggested layout fix: widen the back/load buttons to about 56 px (or 60 px for CARGAR) and the quit `no` rect to
about 44 px; the BACK key is shared with the big 180 px buttons, so the translation is the same everywhere.
Nothing sits to the right of the back buttons, so the visible effect today is a few px of overhang, not overlap.

The controller hint (`controls_pad.menu:225`, `ingame_controls_pad.menu:213`, rect 240..580, font NORMAL, scale .18) is
a single unwrapped line. English is already 665 px (off the 640 px screen). Translations are now no wider than the
English (de 659, es 619) but still overflow; the menu needs an autowrapped item (about 340 px wide, 4 lines).

The savegame date column (room about 138 px) now fits for all the old-save strings in both languages.

## Re-running

    python3 tools/l10n/fit.py                 # de and es, failures only
    python3 tools/l10n/fit.py --lang de -v    # also list items that fit
    python3 tools/l10n/fit.py --width "TEXT" FONT SCALE
