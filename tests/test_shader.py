"""Config/reference checks only; these do NOT compile or execute ReShadeFX."""
import configparser
import math
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
FX = ROOT / "shaders" / "NFSUCFoundation.fx"


def read_profile(name):
    # ReShade stores its root keys without an INI section.
    config = configparser.ConfigParser()
    config.optionxform = str
    config.read_string("[ROOT]\n" + (ROOT / "profiles" / (name + ".ini")).read_text(encoding="utf-8"))
    return config


def grade_reference(rgb, p):
    """Independent scalar reference, no GPU/compiler equivalence is claimed."""
    weights = (0.2126, 0.7152, 0.0722)
    c = [max(0.0, min(1.0, v)) ** 2.2 * 2 ** p["ExposureEV"] for v in rgb]
    y = sum(v * w for v, w in zip(c, weights))
    contrast_gain = ((y + 0.02) / 0.20) ** p["LightContrast"]
    c = [v * contrast_gain for v in c]
    y = max(0.0, min(1.0, sum(v * w for v, w in zip(c, weights))))
    lift = p["ShadowLift"] * 4 * math.sqrt(y) * (1 - y) ** 4
    gains = (1 + 0.08 * p["Warmth"], 1, 1 - 0.08 * p["Warmth"])
    c = [(v + lift) * g for v, g in zip(c, gains)]
    y = sum(v * w for v, w in zip(c, weights))
    c = [max(0.0, y + p["Saturation"] * (v - y)) for v in c]
    peak = max(c)
    t = max(peak - 0.65, 0.0) / 0.35
    shoulder = 0.65 + 0.35 * t / (1 + p["HighlightCompression"] * t)
    scale = 1.0 - (peak - min(peak, shoulder)) / max(peak, 0.000001)
    c = [v * scale for v in c]
    gamut = max(1.0, *c)
    c = [max(0.0, min(1.0, v / gamut)) ** (1 / 2.2) for v in c]
    return tuple(a + p["EffectStrength"] * (b - a) for a, b in zip(rgb, c))


class ShaderConfigTests(unittest.TestCase):
    def test_presets_resolve_all_techniques_and_uniforms(self):
        fx = FX.read_text(encoding="utf-8")
        techniques = set(re.findall(r"^technique\s+(\w+)", fx, re.M))
        uniforms = dict((name, (float(lo), float(hi))) for name, lo, hi in re.findall(
            r"uniform float (\w+)\s*<.*?ui_min = ([\d.-]+); ui_max = ([\d.-]+);.*?>", fx, re.S))
        self.assertEqual(techniques, {"NFSUC_Grade", "NFSUC_Bloom"})
        self.assertEqual(len(uniforms), 10)
        for name in ("Hybrid", "Clean", "Cinematic"):
            config = read_profile(name)
            params = config[FX.name]
            self.assertEqual(set(params), set(uniforms), name)
            for key, raw in params.items():
                lo, hi = uniforms[key]
                self.assertTrue(math.isfinite(float(raw)))
                self.assertLessEqual(lo, float(raw), key)
                self.assertLessEqual(float(raw), hi, key)
            active = config["ROOT"]["Techniques"].split(",")
            order = config["ROOT"]["TechniqueSorting"].split(",")
            for token in active + order:
                tech, filename = token.split("@")
                self.assertEqual(filename, FX.name)
                self.assertIn(tech, techniques)
            self.assertTrue(set(active).issubset(order))
            self.assertEqual(active[0], "NFSUC_Grade@" + FX.name)
            self.assertEqual(len(active), 1 if name == "Clean" else 2)

    def test_source_is_self_contained_and_has_no_depth_or_simulation_access(self):
        fx = FX.read_text(encoding="utf-8")
        self.assertNotRegex(fx, r'#\s*include|:\s*DEPTH|source\s*=\s*"')
        self.assertIn("texture NFSUC_Color : COLOR;", fx)
        self.assertEqual(len(re.findall(r"Format = RGBA16F", fx)), 3)
        self.assertNotIn("SimRate", fx)

    def test_reference_all_profile_sdr_outputs_are_finite_bounded_and_black_preserved(self):
        for name in ("Hybrid", "Clean", "Cinematic"):
            p = {key: float(value) for key, value in read_profile(name)[FX.name].items()}
            self.assertEqual(grade_reference((0, 0, 0), p), (0, 0, 0))
            for r in range(9):
                for g in range(9):
                    for b in range(9):
                        result = grade_reference((r / 8, g / 8, b / 8), p)
                        self.assertTrue(all(math.isfinite(v) and 0 <= v <= 1 for v in result), (name, result))

    def test_reference_gray_ramp_has_no_inversions(self):
        for name in ("Hybrid", "Clean", "Cinematic"):
            p = {key: float(value) for key, value in read_profile(name)[FX.name].items()}
            previous = (0, 0, 0)
            for n in range(1, 1025):
                current = grade_reference((n / 1024,) * 3, p)
                self.assertTrue(all(c >= old - 1e-12 for c, old in zip(current, previous)), name)
                previous = current

    def test_neutral_reference_roundtrip_and_bloom_kernel(self):
        p = {key: float(value) for key, value in read_profile("Clean")[FX.name].items()}
        for key in ("ExposureEV", "LightContrast", "Warmth", "ShadowLift", "HighlightCompression"):
            p[key] = 0.0
        for rgb in ((0.1, 0.2, 0.3), (0.9, 0.5, 0.01), (1, 1, 1),
                    (1e-9, 2e-9, 3e-9), (1e-5, 2e-5, 3e-5)):
            for value, reference in zip(grade_reference(rgb, p), rgb):
                self.assertAlmostEqual(value, reference, places=12)
        weights = (0.2270270270, 0.1945945946, 0.1216216216, 0.0540540541, 0.0162162162)
        self.assertAlmostEqual(weights[0] + 2 * sum(weights[1:]), 1.0, places=9)
        self.assertTrue(all(w >= 0 for w in weights))


if __name__ == "__main__":
    unittest.main()
