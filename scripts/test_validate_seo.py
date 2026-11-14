#!/usr/bin/env python3
"""Negative/positive tests for scripts/validate_seo.py (stdlib only).

Each test copies the site to a temporary directory, injects one unsupported pickup/delivery
claim next to the approved policy sentence in one content location, runs the validator on the
copy and asserts that the specific check for that location FAILS. The repository files are
never modified.

Usage: python scripts/test_validate_seo.py
"""
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VALIDATOR = ROOT / "scripts" / "validate_seo.py"
POLICY = ("For saree pre-pleating orders, pickup and delivery are free for orders of more than 5 sarees from one customer. "
          "For 5 sarees or fewer, pickup and delivery are chargeable and the charge depends on your location.")

# attack name -> (text appended right after the policy sentence, name of the check that must fail)
ATTACKS = {
    "time promise": (" Delivery within 2 days.", "pickup/delivery time promise"),
    "fixed charge": (" Pickup and delivery cost ₹50.", "fixed pickup/delivery charge"),
    "free claim": (" Free delivery on all orders.", "free pickup/delivery claim outside the approved sentence"),
}

# location -> (file, which occurrence of the policy sentence to alter, suffix of the failing check name)
LOCATIONS = {
    "pre-pleating page (visible)": ("saree-pre-pleating/index.html", 0, "on /saree-pre-pleating/"),
    "FAQ page (visible text)": ("faq.html", 1, "on /faq"),         # 2nd occurrence in the file = visible answer
    "FAQ page (JSON-LD)": ("faq.html", 0, "in JSON-LD on /faq"),   # 1st occurrence in the file = FAQPage schema
    "terms.html": ("terms.html", 0, "in terms.html"),
    "llms.txt": ("llms.txt", 0, "in llms.txt"),
}


def run_validator(root):
    r = subprocess.run([sys.executable, str(VALIDATOR), str(root)], capture_output=True, text=True, encoding="utf-8")
    return r.returncode, r.stdout


def inject(root, rel, nth, extra):
    path = Path(root) / rel
    text = path.read_text(encoding="utf-8", newline="")
    idx = -1
    for _ in range(nth + 1):
        idx = text.index(POLICY, idx + 1)
    end = idx + len(POLICY)
    path.write_text(text[:end] + extra + text[end:], encoding="utf-8", newline="")


class PolicyChecks(unittest.TestCase):
    def fresh_copy(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        dst = Path(tmp.name) / "site"
        shutil.copytree(ROOT, dst, ignore=shutil.ignore_patterns(".git", "__pycache__"))
        return dst

    def test_approved_sentence_passes(self):
        code, out = run_validator(ROOT)
        self.assertEqual(code, 0, out[-800:])
        for needle in ("PASS approved pickup/delivery policy sentence is visible on /saree-pre-pleating/",
                       "PASS approved pickup/delivery policy sentence is visible on /faq",
                       "PASS approved pickup/delivery policy sentence is in the FAQPage JSON-LD",
                       "PASS approved pickup/delivery policy sentence is present in terms.html",
                       "PASS approved pickup/delivery policy sentence is present in llms.txt"):
            self.assertIn(needle, out)
        self.assertNotIn("FAIL", out)


def _make_test(location, attack):
    rel, nth, where = LOCATIONS[location]
    extra, rule = ATTACKS[attack]
    expected = f"FAIL no {rule} {where}"

    def test(self):
        root = self.fresh_copy()
        inject(root, rel, nth, extra)
        code, out = run_validator(root)
        self.assertEqual(code, 1, f"validator should exit 1 for {attack} in {location}")
        self.assertIn(expected, out)
    return test


for _loc in LOCATIONS:
    for _atk in ATTACKS:
        _name = "test_fails_" + (_atk + "_" + _loc).replace(" ", "_").replace("(", "").replace(")", "").replace(".", "_").replace("-", "_")
        setattr(PolicyChecks, _name, _make_test(_loc, _atk))

if __name__ == "__main__":
    unittest.main(verbosity=2)
