# Coordinator review of flagged subtitle lines (2026-10-16)

Checked against the game's own text (briefings, notebook files, map script comments in the Steam paks).

## English source fixes (confident; apply to cache.json as manual edits, then re-translate those lines)

| Path | Was | Fix | Evidence |
|---|---|---|---|
| cs6/cs06_mur_04_1 | Catamarandi | Katamarunde | briefing: "SS rocket base at Katamarunde" |
| boss1/en_01 | We read your mother, Ham. | This is Eagle's Nest. We read you, Mother Hen. What is your status? | script comment "WE read you Mother Hen" |
| boss1/mh_01 | Mother Hand | Mother Hen | same |
| cs6/cs06_jac_04_2 | this dark night | this Dark Knight | briefings: "Dark Knights" |
| boss2/dh_only_delaying | Your only delay is inevitable. | You're only delaying the inevitable. | |
| boss2/dh_winning_how | H-H-H-H-Hauen! | H-h-h-how? | |
| boss2/dh_have_to_do_better | Or you'll have to... | You'll have to... | |
| rocket/sci_quick_guards | The quick gods! | Quick! Guards! | filename |
| escape1/axis1_american_is_loose | They're making it loose! | The American is loose! | filename |
| escape1/axis1_give_order | an author | an order | filename |
| escape2/axis11_heard | Reichsmasters' office | Reichsmarschall's office | |
| escape2/axis1_doubled_guard | doubled the gather | doubled the guard | filename |
| village2/kemph_my_apologies | Man-General | Herr General | |
| village2/gen_where_is_my_latour, klugg_no_such_wine | 38 litre / 38 Le Tour | '38 Latour | filename |
| norway/g3_bad_water | The Metics | The medics | |
| dam/1933_reichstag | (garbled) | The government of the national uprising is determined to fulfil the task entrusted to it by the German people. It therefore comes before the Reichstag today with the ardent wish to find in it support for carrying out its mission. | Hitler's 23 March 1933 speech |
| chateau/gen1_did_you_know | Burghalter | Burkhalter | cl_27_himm_burk.txt |
| dam/driver_delivery_for_gen | von Staff | von Stauff | notebook files |
| boss1/hel_04 etc. | Zempf | Zemph | cl_5_zemph_blav.txt |

## Translation decisions

- Spanish: Deathshead uses "usted" with B.J. throughout (menacing politeness), not a tú/usted mix.
- Black Guard division (forest/axis10_misdrop): DE "Schwarze Garde", ES "Guardia Negra" (enemy unit name).
- Pending user: names of Deathshead / Operation Resurrection / Uber Soldat in DE/ES; listening list in
  `tools/l10n/build/listen/index.html`.
