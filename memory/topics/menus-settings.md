# menus settings

Imported dated observations. Configuration and implementation may have changed; check code at HEAD. Each entry retains its jevmem source ID.

## Notes

- [2026-11-05 rtcw-cod bug cause  user's running game died with SIGBUS (Misaligned address) on opening the ESC me](../notes/jev-306-bug-cause-user-s-running-game-died.md) 2026-11-05
- [On 2026-10-12, an audit of rtcw-cod found RTCW on Steam ships English-only data (only text/EnglishUSA, English](../notes/jev-227-an-audit-of-rtcw-cod-found-rtcw.md) 2026-10-12
- [On 2026-10-12, rtcw-cod menu deltas moved to format v2 (scripts/menus.py)  any run of lines present in an RTCW](../notes/jev-226-menu-deltas-moved-to-format-v2-scripts.md) 2026-10-12
- [On 2026-10-12, rtcw-cod stopped tracking RTCW-derived .menu files and menu/hud pk3s (id game data, not GPL). G](../notes/jev-225-stopped-tracking-rtcw-derived-menu-files-and.md) 2026-10-12
- [On 2026-10-12, rtcw-cod tried a global bass boost (s_alBass  low-shelf biquad at 200 Hz applied to PCM before](../notes/jev-223-tried-a-global-bass-boost-s-albass.md) 2026-10-12
- [On 2026-10-12, rtcw-cod added a global bass boost (cvar s_alBass, dB, low-shelf biquad at 200 Hz) in iortcw/SP](../notes/jev-222-added-a-global-bass-boost-cvar-s.md) 2026-10-12 (superseded)
- [On 2026-10-11, rtcw-cod lost the in-game HUD and the visible pause menu because a rend2 perf edit made RB_Post](../notes/jev-216-lost-the-in-game-hud-and-the.md) 2026-10-11
- [From 2026-10-09 onward, codmod ships CoD-style left vertical menu lists by overriding ui/*.menu files inside c](../notes/jev-183-ships-cod-style-left-vertical-menu-lists.md) 2026-10-09
- [On 2026-10-09, codmod menu hover hints were fixed by placing yesno_message, slider_message, keyBindStatus, and](../notes/jev-181-menu-hover-hints-were-fixed-by-placing.md) 2026-10-09
- [On 2026-10-09, the Controls MISC tab showed an empty page because its action used show miscellaneous while eve](../notes/jev-179-the-controls-misc-tab-showed-an-empty.md) 2026-10-09
- [On 2026-10-09, codmod replaced all menu ITEM_TYPE_SLIDER controls with ITEM_TYPE_EDITFIELD plus cvar and maxCh](../notes/jev-178-replaced-all-menu-item-type-slider-controls.md) 2026-10-09
- [On 2026-10-09, pause settings BACK/Esc must run close ingame_* ; open ingame because Menus_CloseByName does no](../notes/jev-177-pause-settings-back-esc-must-run-close.md) 2026-10-09
- [On 2026-10-09, codmod merged System and Game Options into one Options menu (options_menu / ingame_options) wit](../notes/jev-176-merged-system-and-game-options-into-one.md) 2026-10-09
- [On 2026-10-09, codmod default sound levels are s_volume 0.489583 (Effects) and s_musicvolume 0.510417 (Music),](../notes/jev-175-default-sound-levels-are-s-volume-0.md) 2026-10-09
- [On 2026-10-09, codmod Main OPTIONS opens setup_menu (hub), settings value pages and ui/mods.menu use setup-sty](../notes/jev-174-main-options-opens-setup-menu-hub-settings.md) 2026-10-09
- [On 2026-10-09, codmod settings value menus (system/options/controls and ingame_*) became CoD-style fullscreen](../notes/jev-173-settings-value-menus-system-options-controls-and.md) 2026-10-09
- [On 2026-10-09, ioRTCW under game_run.sh (MangoHud + gamemode, SDL Wayland) SIGSEGV'd on fullscreen Apply becau](../notes/jev-172-iortcw-under-game-run-sh-mangohud-gamemode.md) 2026-10-09
- [On 2026-10-09, E14 extended r_vidModes through mode 41 in ui_shared.c and both SP renderers, and the r_mode me](../notes/jev-170-e14-extended-r-vidmodes-through-mode-41.md) 2026-10-09
- [On 2026-10-09, after confirming the CoD-style vertical main menu, codmod also overrides ui/ingame.menu in codm](../notes/jev-169-after-confirming-the-cod-style-vertical-main.md) 2026-10-09
- [On 2026-10-09, codmod ships the CoD-style startup main menu as ui/main.menu inside codmod_menus.pk3 (not zz_*)](../notes/jev-168-ships-the-cod-style-startup-main-menu.md) 2026-10-09
- [On 2026-10-09, rtcw-cod ADS iron-sight bake uses absolute per-weapon cg_codAdsView rows while cod_adsTune is o](../notes/jev-166-ads-iron-sight-bake-uses-absolute-per.md) 2026-10-09
- [On 2026-10-09, rtcw-cod defaults r_dlightMode to 1 (ForwardDlight) in codmod.cfg and scripts/run.sh because fl](../notes/jev-156-defaults-r-dlightmode-to-1-forwarddlight-in.md) 2026-10-09
- [On 2026-10-09, hd-textures dual-model batch was chosen for RTCW HD pack  world textures use general-wdn at 2x](../notes/jev-154-hd-textures-dual-model-batch-was-chosen.md) 2026-10-09 (superseded)
- [On 2026-10-09, rtcw-cod defaults ioRTCW rend2 screen-space AO with r_ssao 1 in mod/codmod/codmod.cfg and early](../notes/jev-151-defaults-iortcw-rend2-screen-space-ao-with.md) 2026-10-09
- [On 2026-10-09, rtcw-cod wall POM smoke test uses ioRTCW rend2 (not opengl1)  offline tools/pom-bake builds RGB](../notes/jev-146-wall-pom-smoke-test-uses-iortcw-rend2.md) 2026-10-09
- [codmod Phase 3 (ADS, iortcw codmod branch, implemented 2026-10-08)  BG_COD_MAX_CVARS was bumped from 32 to 64](../notes/jev-95-phase-3-ads-iortcw-codmod-branch-implemented.md) 2026-10-08
- [On 2026-10-08 the rtcw-cod mod plan decided not to change the g_speed cvar, because g_speed also drives every](../notes/jev-92-the-rtcw-cod-mod-plan-decided-not.md) 2026-10-08

