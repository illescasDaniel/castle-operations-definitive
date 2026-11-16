---
name: jev-228-added-dualsense-gyro-aiming-cod-padgyro-0
description: "On 2026-10-13, rtcw-cod added DualSense gyro aiming  cod_padGyro 0/1/2 (Off/ADS only default/Always), gyro rea"
type: decision
date: 2026-10-13
status: current
supersedes: 
superseded_by: 
source:
---

Historical jevmem entry 228, imported 2026-11-16. Statements about configuration and work status describe the date recorded; check current code before relying on them.

On 2026-10-13, rtcw-cod added DualSense gyro aiming: cod_padGyro 0/1/2 (Off/ADS only default/Always), gyro read via SDL_GameControllerGetSensorData in sdl_input.c and added to cl.viewangles in CL_GyroMove (cl_input.c), bypassing the stick pipeline. ADS is detected from cl.snap.ps.stats[8] (STAT_COD_ADS) rather than the +ads button so toggled ADS works. Playtested OK.

