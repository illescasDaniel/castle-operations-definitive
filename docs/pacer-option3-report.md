# Option 3 report: fence pipeline pacer (com_maxfpsGpuSync 2)

Implemented and built, NOT committed. Headless 1920x1200 bench, median of 3 runs, `r_vsync 3`.

| Cap | gsync 1 (old) avg / 1% low / hitches | gsync 2 (new) avg / 1% low / hitches |
|---|---|---|
| uncapped | 201.9 / 113.4 / 0 | not run |
| 170 | 162.0 / 110.6 / 0 | 162.2 / 114.8 / 0 |
| 237 | 194.2 / 103.5 / 2-3 | 194.8 / 114.5 / 0-1 |
| 120 | 119.9 / 93.2 / 0 | 119.7 / 94.1 / 0 |

Verdict: no average-FPS gain. Better 1% lows (+4% at 170, +11% at 237) and fewer hitches at the unholdable cap.
A 237 cap still gives ~194 vs 202 uncapped. 170 is held at 162 by both (the GPU downclock / CPU+GPU gap is not fixed).
Needs your in-game A/B: `set com_maxfpsGpuSync 2`, `pacestats reset`, play 60 s, `pacestats`. codmod.cfg still pins 1.
Next: option 2 (logic/render split) to the architect.
