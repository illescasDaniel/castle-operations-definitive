"""Unit tests with a mocked launcher: the game is never started. Run: .venv/bin/python -m unittest discover tests"""
import asyncio
import os
import sys
import tempfile
import unittest
from pathlib import Path

TMP = Path(tempfile.mkdtemp(prefix="rtcwmcp-test-"))
os.environ["RTCW_ROOT"] = str(TMP)
os.environ["XDG_RUNTIME_DIR"] = str(TMP)
(TMP / "run/home/codmod").mkdir(parents=True)
(TMP / "benchmarks").mkdir()
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import rtcw_core as core  # noqa: E402
import server  # noqa: E402
from rtcw_core import RtcwError, Step  # noqa: E402

NORMALCOV = """\
normalcov: will report on the next rendered frame
normalcov: 412 surfaces, 3 shaders
  300  town_wall/town_c22a1burn                  textures/town_wall/town_c22a1burn         parallax
   80  xlab_wall/xconcrete_c54                   textures/xlab_wall/xconcrete_c54          NO NORMAL MAP
   32  sky/foo                                   -                                         not lightall
  not lightall                  32 surfaces
  NO NORMAL MAP                 80 surfaces
  normal map                     0 surfaces
  _nh found, parallax off        0 surfaces
  parallax                     300 surfaces
  normals off (cvars)            0 surfaces
normalcov: 300/380 lightall surfaces have a normal map (78.9%)
"""


def fake_launcher_factory(step_logs, shots=0, hung=False):
    seen = {}

    def launcher(cmd, env, timeout, tick):
        seen["cmd"], seen["env"] = list(cmd), env
        cfg = (core.HOME_CFG / cmd[cmd.index("+exec") + 1]).read_text()
        seen["cfg"] = cfg
        lines = ["some boot noise"]
        for i, body in enumerate(step_logs, 1):
            lines += [f"MCPMARK BEGIN {i}"] + body.splitlines() + [f"MCPMARK END {i}"]
        (core.HOME_CFG / "screenshots").mkdir(exist_ok=True)
        for i in range(1, shots + 1):
            (core.HOME_CFG / "screenshots" / f"codmod_mcp_{i:02d}.tga").write_bytes(b"")
        return core.RunResult(0, 1.0, lines, killed_hung=hung, timed_out=hung)
    launcher.seen = seen
    return launcher


class Patched(unittest.TestCase):
    def setUp(self):
        self._orig = (core.game_processes, core.bake_processes, core.build_processes)
        core.game_processes = lambda: []
        core.bake_processes = lambda: []
        core.build_processes = lambda: []

    def tearDown(self):
        core.game_processes, core.bake_processes, core.build_processes = self._orig


class TestParsing(unittest.TestCase):
    def test_spot_formats(self):
        self.assertEqual(core.parse_spot("setviewpos -737,3 469,2 107,4 -86,7 15,8"), "-737.3 469.2 107.4 -86.7 15.8")
        self.assertEqual(core.parse_spot([1, 2, 3, 4, 5]), "1 2 3 4 5")
        self.assertEqual(core.parse_spot("1 2 3 4"), "1 2 3 4 0")
        with self.assertRaises(RtcwError):
            core.parse_spot("1 2 3")
        with self.assertRaises(RtcwError):
            core.parse_spot("a b c d e")

    def test_validation(self):
        with self.assertRaises(RtcwError):
            core.check_map("../x")
        with self.assertRaises(RtcwError):
            core.check_cvars({"r_x": "1; quit"})
        with self.assertRaises(RtcwError):
            core.check_cvars({f"c{i}": "1" for i in range(9)})
        for bad in ("quit", "bind a b", "vid_restart", "a; b"):
            with self.assertRaises(RtcwError):
                core.check_console_cmd(bad)
        self.assertEqual(core.check_console_cmd(" viewpos "), "viewpos")

    def test_normalcov(self):
        c = core.parse_normalcov(NORMALCOV.splitlines())
        self.assertTrue(c["parsed"])
        self.assertEqual((c["surfaces"], c["shaders"], c["covered"], c["lightall"]), (412, 3, 300, 380))
        self.assertAlmostEqual(c["covered_pct"], 78.9)
        e = c["entries"]
        self.assertEqual(e[0], {"count": 300, "shader": "town_wall/town_c22a1burn",
                                "image": "textures/town_wall/town_c22a1burn", "status": "parallax"})
        self.assertIsNone(e[2]["image"])
        self.assertEqual(c["totals"]["parallax"], 300)

    def test_cfg(self):
        cfg = core.build_cfg([Step(spot="1 2 3 4 5", commands=["normalcov"], screenshot="s1")], skip_intro=True)
        self.assertIn("cmd cameraInterrupt", cfg)
        self.assertTrue(cfg.endswith("wait 5; quit"))
        self.assertLess(cfg.index("cameraInterrupt"), cfg.index("setviewpos"))
        self.assertIn("set cg_draw2D 0", cfg)
        self.assertNotIn("\n", cfg)

    def test_split_marks(self):
        lines = ["x", "MCPMARK BEGIN 1", "a", "MCPMARK END 1", "junk", "MCPMARK BEGIN 2", "b"]
        self.assertEqual(core.split_by_marks(lines, 2), [["a"], ["b"]])

    def test_load_and_bench_parsers(self):
        lt = (">> escape1\n   map        why           total  frames       maxgap@stage     p95 over33\n"
              "   escape1    load       4300.5ms     180 55.1ms@world_bsp   23.0ms      2  FAIL\n"
              "      gap    41.2 ms @ world_bsp  t=1200.0 ms  hint=img\n\nload-test: FAIL\n")
        r = server.parse_load_test(lt)
        self.assertEqual(r["maps"][0]["loads"][0]["over33"], 2)
        self.assertEqual(r["maps"][0]["loads"][0]["gaps"][0]["hint"], "img")
        self.assertFalse(r["passed"])
        b = ("   frames=900  20.1s  avg 165.2 fps  1%low 120.0 fps  P99 9.1 ms  max 20.0 ms  hitches 1\n"
             "   avg 165.2 fps | 1% low 120.0 fps | P99 9.1 ms\n   cfg: foo\n")
        self.assertEqual(server.parse_bench(b)["median"]["avg_fps"], 165.2)
        pr = server.parse_bench(b.replace("hitches 1\n", "hitches 1\n   pace: mode=2 q=1 T=8333 miss%=0.4 tag=x\n", 1))["runs"]
        self.assertEqual(pr[0]["pace"], {"mode": 2.0, "q": 1.0, "T": 8333.0, "miss%": 0.4, "tag": "x"})
        self.assertNotIn("pace", server.parse_bench(b)["runs"][0])
        g = ("   gpu: frames=900 gpu_avg_ms=3.410 gpu_max_ms=6.100\n"
             "   gpu: sunshadow        avg_ms= 1.300  pct= 38.1  max_ms= 2.000  hit= 99.0%\n")
        gp = server.parse_bench(b + g)["gpu_passes_last_run"]
        self.assertEqual((gp["frames"], gp["passes"][0]["pass"], gp["passes"][0]["pct"]), (900, "sunshadow", 38.1))
        self.assertEqual(server.parse_spin("STILL     GPU   3.10 ms  x1.00\nYAW_700   GPU   5.00 ms  x1.61  <-- FAIL\n")
                         ["rows"]["YAW_700"]["fail"], True)

    def test_build_summary(self):
        s = server.summarize_build("a.c:12:5: warning: unused x [-Wunused]\nb.c:3: error: boom\nok\n")
        self.assertEqual((s["warning_count"], s["error_count"]), (1, 1))


class TestRunner(Patched):
    def test_run_steps_and_guard(self):
        cfgfile = core.HOME_CFG / "wolfconfig.cfg"
        cfgfile.write_text("seta bind x\n")
        launcher = fake_launcher_factory([NORMALCOV])

        def mutating(cmd, env, timeout, tick):
            cfgfile.write_text("CLOBBERED")
            return launcher(cmd, env, timeout, tick)

        r = core.run_steps("trainyard", [Step(spot="1 2 3 4 5", commands=["normalcov"])], cvars={"r_picmip": 0},
                           launcher=mutating)
        self.assertTrue(r["completed"])
        self.assertEqual(cfgfile.read_text(), "seta bind x\n")  # restored
        cmd = launcher.seen["cmd"]
        self.assertEqual(cmd[:6], ["gamescope", "--backend", "headless", "-W", "1920", "-H"])
        self.assertIn("+spdevmap", cmd)
        self.assertEqual(launcher.seen["env"]["RTCW_STARTUP_SETS"], "r_picmip=0")
        self.assertFalse(list(core.HOME_CFG.glob("rtcwmcp-*.cfg")))  # temp cfg removed
        self.assertNotIn("cameraInterrupt", launcher.seen["cfg"])

    def test_auto_intro_skip(self):
        for m, want in (("escape1", True), ("crypt1", True), ("trainyard", False)):
            launcher = fake_launcher_factory([""])
            core.run_steps(m, [Step(spot="1 2 3 4 5")], launcher=launcher)
            self.assertEqual("cameraInterrupt" in launcher.seen["cfg"], want, m)

    def test_refuse_when_game_running(self):
        core.game_processes = lambda: ["123 ./iowolfsp.x86_64 +set fs_game codmod"]
        with self.assertRaisesRegex(RtcwError, "already running"):
            core.run_steps("trainyard", [Step(spot="1 2 3 4 5")], launcher=fake_launcher_factory([""]))

    def test_lock_is_exclusive(self):
        with core.exclusive("a"):
            with self.assertRaisesRegex(RtcwError, "already running a game"):
                with core.exclusive("b"):
                    pass

    def test_hung_reported(self):
        r = core.run_steps("trainyard", [Step(spot="1 2 3 4 5")], launcher=fake_launcher_factory([""], hung=True))
        self.assertTrue(any("HUNG" in w for w in r["warnings"]))


class TestTools(Patched):
    def test_texture_coverage_tool(self):
        launcher = fake_launcher_factory([NORMALCOV])
        orig = core.real_launcher
        core.run_steps.__kwdefaults__["launcher"] = launcher
        try:
            res = asyncio.run(server.texture_coverage("trainyard", ["-1012.1 481.6 88.1 -143.3 9.5"],
                                                      shader_filter="town_wall"))
        finally:
            core.run_steps.__kwdefaults__["launcher"] = orig
        self.assertTrue(res["ok"], res)
        ent = res["spots"][0]["entries"]
        self.assertEqual([e["status"] for e in ent], ["parallax"])

    def test_screenshot_tool(self):
        from PIL import Image
        launcher = fake_launcher_factory([""], shots=0)

        def with_shot(cmd, env, timeout, tick):
            r = launcher(cmd, env, timeout, tick)
            Image.new("RGB", (64, 40), (10, 20, 30)).save(core.HOME_CFG / "screenshots" / "codmod_mcp_01.tga")
            return r
        orig = core.real_launcher
        core.run_steps.__kwdefaults__["launcher"] = with_shot
        try:
            out = asyncio.run(server.screenshot("trainyard", ["1 2 3 4 5"], label="t1", max_width=32,
                                                return_images=False))
        finally:
            core.run_steps.__kwdefaults__["launcher"] = orig
        import json
        res = json.loads(out[0])
        self.assertTrue(res["ok"], res)
        self.assertTrue(Path(res["shots"][0]["small_png"]).is_file())
        self.assertEqual(Image.open(res["shots"][0]["small_png"]).width, 32)

    def test_compare(self):
        from PIL import Image
        d = core.SHOTS_DIR
        for lab, col in (("a", 10), ("b", 12)):
            (d / lab).mkdir(parents=True, exist_ok=True)
            Image.new("RGB", (16, 16), (col, col, col)).save(d / lab / "spot01.tga")
        res = server._do_compare("a", "b", 1920)
        self.assertEqual(res["pairs"][0]["max_diff"], 2)
        self.assertEqual(res["pairs"][0]["differing_px_pct"], 100.0)


if __name__ == "__main__":
    unittest.main()
