# Gyro aiming (DualSense)

`cod_padGyro`: 0 Off, **1 Aiming (default, only while ADS)**, 2 Always. `cod_padGyroSens` (multiplier, default 1),
`cod_padGyroDeadzone` (deg/s noise gate, default 0.3). Menu: CONTROLS > CONTROLLER > Gyro Aiming / Gyro Sensitivity.

- `sdl_input.c`: `IN_InitJoystick` enables `SDL_SENSOR_GYRO` (SDL >= 2.0.14); `IN_GyroSample` (per frame, from
  `IN_GamepadMove`) converts rad/s to deg/s, learns a slow resting bias, applies the deadzone; `IN_GetGyroRates` exports it.
- `cl_input.c` `CL_GyroMove` (after `CL_JoystickMove`): adds `rate * sens * frametime` to `cl.viewangles`. ADS is read
  from `cl.snap.ps.stats[8]` (`STAT_COD_ADS`, x1000), so toggled ADS counts too.
- Axis mapping: yaw = SDL gyro y, pitch = -x. Signs unverified on hardware: if a direction is inverted, flip it in `IN_GyroSample`.
