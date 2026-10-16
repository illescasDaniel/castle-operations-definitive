# English subtitle alignment with the wiki transcripts (2026-10-16)

Method: `tools/l10n/align.py` fuzzy-matches each of the 125 wiki quotes (Deathshead, OSA Director, Jack Stone) to
cache.json clips (windows of up to 6 consecutive clips per quote, or several quotes per clip) and prints similarity
scores plus the differing words. Every match was reviewed by hand. Rule: wiki wording wins when words differ (names,
terms, misheard, missing/extra words); our text stays when only punctuation, casing, spelling variant (learned/learnt,
favor/favour), number style (48 / forty-eight), contractions (that's / that is), or filler words (uh, ah, um, heh)
differ, or when the wiki line is plainly its own typo. All edits are `manual: true`; `orig` kept (changed only for kook,
new for death_i_will_deal). `subtitles.txt` was regenerated and the pk3 repacked.

Totals: 65 lines changed (wiki 38, coordinator 21, user 6). Full list in `en_changes.json` (the lines translators must redo).

## Name normalisation (whole subtitles.txt)

Strasser -> Strasse (cs01_jac_09, cs14_jac_06_2, cs14_jac_07), Zempf -> Zemph (hel_04, church/dispatch),
Burghalter -> Burkhalter (gen1_did_you_know), von Staff -> von Stauff (driver_delivery_for_gen, driver_ja_ja),
Cobra -> Kobra (cs06_dir_09, cs06_hig_04_7, cs09_jac_01_2; game text spells it "Kobra"). "von Bulow" unchanged.
Über-Soldat now spelled with the umlaut and hyphen in the three cutscene lines edited (dh_well_agent, cs11_jac_02,
cs14_jac_07), as the wiki does. Not touched: "Kempf" in village2 lines (the clip names say Kemph; not in the brief).

## Wiki quotes without a clip

- "I will deal with him." (Deathshead): clip `xlabs/death_i_will_deal.wav` existed with empty text; text added.
- No other wiki quote is unmatched. Quotes #26/#27 and #25 share clip cs01_dir_06/dir_04 (see below); the wiki lines
  "Come in." / "Yes sir." repeat across several clips.

## Clips of these characters with no wiki quote (left as is)

dh_winning_what ("What? It's not possible." is the first half of wiki #21), cs14_dir_06_3 "Please.", cs14_jac_04_3
"Yes, sir.", cs19_dir_01_5 / cs9/cs01_dir_01_2 "Come in.", cs19_jac_03_4 "Yes, sir.", cs06_jac_03_4 "But.",
cs09_dir_02_4 "Well, Jack?", forest/axis15_deathshead, norway/m2_dh_himself, xlabs/death_better_be_important
("This had better be important.").

## Ambiguous cases (decision and reasoning)

- **dh_only_delaying**: wiki "Your delaying! The end is inevitable." vs coordinator "You're only delaying the
  inevitable." Whisper heard "Your only delay is inevitable", which contains "only" and "delay"; I used the coordinator
  fix. If the user prefers the wiki: "You're delaying! The end is inevitable."
- **dh_i_suppose**: wiki "I suppose I expected much from you. After all, you are of flesh and blood." vs ours "...too
  much... you are, after all, only flesh and blood." Ours is idiomatic and Whisper's confidence was fine; the wiki
  looks like a mishearing. Left unchanged.
- **it vs him** (dh_well_agent, dh_make_it_easy, dh_my_pleasure, dh_quite_the_toy, dh_see_what_i_mean): wiki
  consistently says "it" for the Super Soldier; applied. "Quite a scientific little toy" replaced "deadly".
- **cs06_dir_11_3**: wiki "any link projects" vs ours "any links to projects": kept ours (wiki is ungrammatical).
- **cs09_dir_11_4**: wiki "weapon facility" vs ours "weapons facility": kept ours (wiki #50 says "Weapons Facility").
- **cs01_jac_09**: wiki "special project division" vs ours "Special Projects Division" (the real unit name): kept ours
  apart from Strasse.
- **cs14_jac_05**: wiki "from mantra" vs ours "from Ultra": kept "Ultra" (British codebreaking source; "mantra" is
  surely a mishearing). "Dakota" -> "decoded" applied.
- **cs14_jac_06_2**: dropped "one" before "Wilhelm Strasse" per wiki; "communique" kept (wiki "communicate" is a typo).
- **cs09_dir_04_3**: "I've read" -> "I read" per wiki; **cs19_dir_02_5**: dropped "It's"; **cs09_jac_03**: "link
  between" -> "link to"; **cs11_jac_03_6**: "involves" -> "involved". All follow the wiki on small word differences;
  each could be a wiki mishearing, so spot-check by ear if wanted.
- **cs19_dir_06_1**: wiki "Hahaha excellent excellent" replaces our "Ah"; rendered "Ha ha ha, excellent, excellent."
- **dh_winning_what / dh_winning_meet_again**: wiki joins them into one quote; clips kept separate ("shall" -> "will").
- **cs01_dir_06 / dir_07**: wiki "What did we missed?" is a wiki slip; ours "What did we miss?" kept.
- **Fillers** (uh, ah, um, heh, "Hmmm...") ignored; **spelling/number variants** (learned, favor, 48 hours) kept.
- Weak matches: none left; every wiki quote scored 0.75+ at its clip (lower scores were multi-clip artefacts).

## All changes
| Path | Source | Old | New |
|---|---|---|---|
| scenaric/cs1/cs01_dir_04.wav | user | Damn. Quarter meeting, Jack. | Damn! Call a meeting, Jack. |
| scenaric/chateau/off_check_again.wav | user | Well, check again, Damio, and be quick about it. | Well, check again, damn you, and be quick about it. |
| scenaric/village1/p4_come_inside.wav | user | Late! Don't shoot! Come inside! | Wait! Don't shoot! Come inside! |
| scenaric/village1/axis5_according_to_otto.wav | user | According to Arthur, one of them is a special assistant to the Reichsführer SS himself. | According to Otto, one of them is a special assistant to the Reichsführer SS himself. |
| player/infantryss/orders/kook.wav | user | Fuck! An American! | Look! An American! |
| scenaric/end/eg_solo_loop.wav | user | Hic est ius hominum, mordes una miras. [Here is the law of men, you devour marvels all at once.] | [Chanting in Latin] |
| scenaric/cs6/cs06_mur_04_1.wav | coordinator | Deathshead? Haven't our sources placed him at the secret rocket base in Catamarandi? | Deathshead? Haven't our sources placed him at the secret rocket base in Katamarunde? |
| scenaric/boss1/en_01.wav | coordinator | This is Eagle's Nest. We read your mother, Ham. What is your status? | This is Eagle's Nest. We read you, Mother Hen. What is your status? |
| scenaric/boss1/mh_01.wav | coordinator | Mother Hand Eagle's Nest. Mother Hand Eagle's Nest. Come in Eagle's Nest. | Mother Hen Eagle's Nest. Mother Hen Eagle's Nest. Come in Eagle's Nest. |
| scenaric/cs6/cs06_jac_04_2.wav | coordinator | Well, there are two things that still bother me. Exactly what is this dark night they all seem to be so interested in? | Well, there are two things that still bother me. Exactly what is this Dark Knight they all seem to be so interested in? |
| scenaric/boss2/dh_only_delaying.wav | coordinator | Your only delay is inevitable. | You're only delaying the inevitable. |
| scenaric/boss2/dh_winning_how.wav | coordinator | H-H-H-H-Hauen! | H-h-h-how? |
| scenaric/rocket/sci_quick_guards.wav | coordinator | The quick gods! | Quick! Guards! |
| scenaric/escape1/axis1_american_is_loose.wav | coordinator | What? Guards! Alarm! They're making it loose! | What? Guards! Alarm! The American is loose! |
| scenaric/escape1/axis1_give_order.wav | coordinator | Sergeant, when I give you an author, I expect an acknowledgement. | Sergeant, when I give you an order, I expect an acknowledgement. |
| scenaric/escape2/axis11_heard.wav | coordinator | Haven't you heard? This is valuable property of the Reich. With all those accusations of pilfering coming from the Reichsmasters' office, the Major isn't taking any chances. | Haven't you heard? This is valuable property of the Reich. With all those accusations of pilfering coming from the Reichsmarschall's office, the Major isn't taking any chances. |
| scenaric/escape2/axis1_doubled_guard.wav | coordinator | That's because the Major just doubled the gather on the dig site again. | That's because the Major just doubled the guard on the dig site again. |
| scenaric/village2/kemph_my_apologies.wav | coordinator | Apologies, Man-General. I will go and investigate the delay. | Apologies, Herr General. I will go and investigate the delay. |
| scenaric/village2/gen_where_is_my_latour.wav | coordinator | Kempf, where is my 38 litre? I sent that idiot down to the wine cellar 20 minutes ago. | Kempf, where is my '38 Latour? I sent that idiot down to the wine cellar 20 minutes ago. |
| scenaric/village2/klugg_no_such_wine.wav | coordinator | 38 Le Tour, 38 Le Tour. There's no such wine down here. | '38 Latour, '38 Latour. There's no such wine down here. |
| scenaric/norway/g3_bad_water.wav | coordinator | The Metics said it was bad water. | The medics said it was bad water. |
| scenaric/dam/1933_reichstag.wav | coordinator | The government of the National Assembly is determined to fulfill its mission taken by the German people. Therefore, today, with the hot desire to find a support in it for the implementation of its mission. | The government of the national uprising is determined to fulfil the task entrusted to it by the German people. It therefore comes before the Reichstag today with the ardent wish to find in it support for carrying out its mission. |
| scenaric/chateau/gen1_did_you_know.wav | coordinator | Did you know Burghalter and von Stauff still haven't shown up? | Did you know Burkhalter and von Stauff still haven't shown up? |
| scenaric/dam/driver_delivery_for_gen.wav | coordinator | But this delivery is for General von Staff. It's six cases of cheese and sausages for the officer's kitchen. Get him on the phone now. I'm sure he'll make an exception. | But this delivery is for General von Stauff. It's six cases of cheese and sausages for the officer's kitchen. Get him on the phone now. I'm sure he'll make an exception. |
| scenaric/dam/driver_ja_ja.wav | coordinator | Yeah, yeah, I know, by order of General Von Staff. Look, I'm not going to be held responsible for this. I absolutely refuse to budge from this spot until you let me through. | Yeah, yeah, I know, by order of General von Stauff. Look, I'm not going to be held responsible for this. I absolutely refuse to budge from this spot until you let me through. |
| scenaric/boss1/hel_04.wav | coordinator | Get out of my way, Zempf! Your feeble threats won't stop me! | Get out of my way, Zemph! Your feeble threats won't stop me! |
| scenaric/church/dispatch.wav | coordinator | Move it, Zempf! Your orders, my noble Fuhrer. Deploy the remaining elite guard. Jawohl! | Move it, Zemph! Your orders, my noble Fuhrer. Deploy the remaining elite guard. Jawohl! |
| scenaric/xlabs/death_i_will_deal.wav | wiki | (empty) | I will deal with him. |
| scenaric/swf/cs10_dh_02.wav | wiki | I don't have time for this nonsense. I have important business to attend to. This boat leaves for the X-Labs within the hour, torpedoes or not. Is that understood, Major? | I don't have time for this nonsense. I have important business to attend to. This boat leaves for the X-Labs within an hour, torpedoes or none. Is that understood, Major? |
| scenaric/boss2/dh_well_agent.wav | wiki | Well, Agent Blazkowicz, is it? You are our most impressive specimen. It will be my pleasure to dissect you piece by piece. Let me introduce you to someone. Do not confuse him with the mere prototypes you have encountered. This is the pinnacle of all my research. Das Supersoldat. The Super Soldier. | Well, Agent Blazkowicz. You are a most impressive specimen. It would be my pleasure to dissect you piece by piece. Let me introduce you to someone. Do not confuse it with the mere prototypes you've encountered. This is the pinnacle of all my research. Das Über-Soldat. The Super Soldier. |
| scenaric/boss2/dh_my_pleasure.wav | wiki | It will be my pleasure to watch him destroy you. | It will be my pleasure to watch it destroy you. |
| scenaric/boss2/dh_thus_we_see.wav | wiki | Thus we see the superiority of the machine of flesh and blood. | Thus we will see the superiority of the machine over flesh and blood! |
| scenaric/boss2/dh_quite_the_toy.wav | wiki | Quite a deadly little toy, isn't he? | Quite a scientific little toy, isn't it? |
| scenaric/boss2/dh_very_good.wav | wiki | Very good! I may learn something after all! | Very good! I might learn something after all! |
| scenaric/boss2/dh_new_armor.wav | wiki | That new armor makes all the difference, don't you agree? | The new armor makes all the difference, don't you agree? |
| scenaric/boss2/dh_make_it_easy.wav | wiki | Why not make it easy on yourself and let him finish you quickly? | Why don't you make it easy on yourself and let it finish you quickly? |
| scenaric/boss2/dh_very_amusing.wav | wiki | This has all been very amusing, but we're running short of time. | This has all been very amusing, but we are running short on time. |
| scenaric/boss2/dh_have_to_do_better.wav | wiki | Or you'll have to do better than that if you expect me to get any useful data. | Oh, you'll have to do better than that if you expect me to get any useful data. |
| scenaric/boss2/dh_see_what_i_mean.wav | wiki | Do you see what I mean about these improved reactions? | Do you see what I mean about its improved reactions? |
| scenaric/boss2/dh_try_harder.wav | wiki | Oh, you really must try harder. This is barely competitive at all. | Oh, you really must try harder than that! This is barely tempting at all. |
| scenaric/boss2/dh_the_results.wav | wiki | The results of this live fire exercise will be invaluable. I thank you again for providing me with this opportunity. | The results of this lifelike exercise will be invaluable. I thank you again for providing me with this opportunity. |
| scenaric/boss2/dh_winning_meet_again.wav | wiki | We shall meet again another day. | We will meet again another day. |
| scenaric/cs6/cs06_dir_05_3.wav | wiki | What did our research come up with? | Well, what did our research come up with? |
| scenaric/cs6/cs06_dir_09.wav | wiki | Yes, his orders are to infiltrate and sabotage the entire V-Weapons complex. With any luck, he might even get his hands on the latest experimental Cobra. | Yes, his orders are to infiltrate and sabotage the entire V-Weapons complex. With any luck, he might even get his hands on the latest experimental Kobra. |
| scenaric/cs6/cs06_hig_04_7.wav | wiki | The Cobra rocket plane. | The Kobra rocket plane. |
| scenaric/cs9/cs09_jac_01_2.wav | wiki | Blazkowicz touched down with the Cobra in Malta about six hours ago. | Blazkowicz touched down with the Kobra in Malta about six hours ago. |
| scenaric/cs9/cs09_dir_04_3.wav | wiki | Excellent. Now, I've read your report, Jack. Tell me what you make of this Operation Resurrection the Jerrys are so hot about. | Excellent. Now, I read your report, Jack. Tell me what you make of this Operation Resurrection the Jerrys are so hot about. |
| scenaric/cs9/cs09_dir_07_2.wav | wiki | I take it you're referring to the secret weapons facility near Kugelsstadt. | I take it you're referring to the secret weapons facility near Kugelstadt. |
| scenaric/cs9/cs09_dir_10_4.wav | wiki | Hmm. What you probably don't know is that our Kreisau friends in the area have recently reported the existence of a high-level scientist from the weapons facility who wishes to defect and is desperately seeking asylum. I imagine he could supply us with some very useful facts. | Hmm. And what you probably don't know is that our Kreisau friends in the area have recently reported the existence of a high-level scientist from the weapons facility who wishes to defect and is desperately seeking asylum. I imagine he could supply us with some very useful facts. |
| scenaric/cs9/cs09_jac_03.wav | wiki | Well, sir, this is the second time that name has cropped up. First at the dig, and then at the rocket base. It is unquestionably the link between Deathshead and the paranormal group. | Well, sir, this is the second time that name has cropped up. First at the dig, and then at the rocket base. It is unquestionably the link to Deathshead and the paranormal group. |
| scenaric/cs14/cs14_dir_01_2.wav | wiki | How is Agent Blazkowicz? | Now, how is Agent Blazkowicz? |
| scenaric/cs14/cs14_dir_05_1.wav | wiki | What have you got there, Jack? | Now, what have you got there, Jack? |
| scenaric/cs19/cs19_dir_02_5.wav | wiki | I just finished reading the last of the reports. It's still hard to believe. | I just finished reading the last of the reports. Still hard to believe. |
| scenaric/cs19/cs19_dir_06_1.wav | wiki | Ah, excellent, excellent. Anything special? | Ha ha ha, excellent, excellent. Anything special? |
| scenaric/cs1/cs01_jac_01.wav | wiki | Yes, sir. We've just received a code of transmission from Kessler, our contact in the Kreisau Circle. | Yes, sir. We just received a coded transmission from Kessler, our contact in the Kreisau Circle. |
| scenaric/cs1/cs01_jac_04.wav | wiki | Well, here's what we know. | Oh, here's what we know. |
| scenaric/cs1/cs01_jac_06.wav | wiki | Now, we've known of the existence of Castle Wolfenstein for some time, but we've only recently heard reports from our Kreisau Circle contacts and the German resistance regarding bizarre occult rituals taking place there. | Now, we've known of the existence of Castle Wolfenstein for some time, but we've only recently heard reports from our Kreisau Circle contacts in the German resistance regarding bizarre occult rituals taking place there. |
| scenaric/cs1/cs01_jac_09.wav | wiki | The kraut with the monocle is one Wilhelm Strasser, also known as Deathshead, a brilliant and ruthless scientist who heads up Himmler's Special Projects Division. | The kraut with the monocle is one Wilhelm Strasse, also known as Deathshead, a brilliant and ruthless scientist who heads up Himmler's Special Projects Division. |
| scenaric/cs6/cs06_jac_02.wav | wiki | Don't get me wrong. We've learned plenty about their capabilities. That alone scares the hell out of me. | Don't get me wrong. We've learned plenty about their capabilities, and that alone scares the hell out of me. |
| scenaric/cs11/cs11_jac_02.wav | wiki | Well, unfortunately, not as much as I'd hoped. He was pretty badly shaken when we got a hold of him, and he still hasn't completely recovered. He kept referring to a Project Uber Soldat. | Well, unfortunately, not as much as I hoped. He was pretty badly shaken when we got a hold of him, and he still hasn't completely recovered. He kept referring to a Project Über-Soldat. |
| scenaric/cs11/cs11_jac_03_6.wav | wiki | Yes. From what I could piece together, it involves some bizarre synthesis of robotic and biological engineering. | Yes. From what I could piece together, it involved some bizarre synthesis of robotic and biological engineering. |
| scenaric/cs11/cs11_jac_05_6.wav | wiki | According to the scientists, this project is Deathshead's baby, the thing most near and dear to his heart, and he's been working on it in one form or another since 1937. | According to the scientist, this project is Deathshead's baby, the thing most near and dear to his heart, and he's been working on it in one form or another since 1937. |
| scenaric/cs14/cs14_jac_05.wav | wiki | Two Dakota dispatches just in from Ultra. The first one is a complete itinerary for Reichsführer SS Heinrich Himmler, covering the next 48 hours. | Two decoded dispatches just in from Ultra. The first one is a complete itinerary for Reichsführer SS Heinrich Himmler, covering the next 48 hours. |
| scenaric/cs14/cs14_jac_06_2.wav | wiki | Wait till you see the next one. A private communique from one Wilhelm Strasser, alias Deathshead, to the same Reichsführer, SS, dated yesterday. Shall I read it? | And wait until you see the next one. A private communique from Wilhelm Strasse, alias Deathshead, to the same Reichsführer, SS, dated yesterday. Shall I read it? |
| scenaric/cs14/cs14_jac_07.wav | wiki | My dear Reichsfuhrer SS, as you are no doubt already aware, my X-Labs lie in complete ruin. Operation Ubersoldat, my life's work, is now a bitter memory. I realize you still have faith in the ultimate success of Operation Resurrection. I wish I could share your confidence, but I feel you have been misled by individuals whose mental competence must be called into question. I leave you now with a word of caution. The Allies have sent a most determined and capable agent to disrupt your ceremony. Do not make the mistake of underestimating him, as I did. Yours faithfully, SS Oberfuhrer Wilhelm Strasser | My dear Reichsführer SS, as you are no doubt already aware, my X-Labs lie in complete ruin. Operation Über-Soldat, my life's work, is now a bitter memory. I realize you still have faith in the ultimate success of Operation Resurrection. I wish I could share your confidence, but I feel you have been misled by individuals whose mental competence must be called into question. I leave you now with a word of caution. The Allies have sent a most determined and capable agent to disrupt your ceremony. Do not make the mistake of underestimating him, as I did. Your faithful SS Oberführer Wilhelm Strasse |
