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
    "wrong threshold": (" Pickup is free for 5 sarees.", "free pickup/delivery claim outside the approved sentence"),
    "charge without symbol": (" Delivery charge is 100 rupees.", "fixed pickup/delivery charge"),
    "charge in INR": (" Pickup and delivery cost INR 100.", "fixed pickup/delivery charge"),
    "number-less time promise": (" Same-day delivery.", "pickup/delivery time promise"),
    "n-day delivery": (" We offer 2-day delivery.", "pickup/delivery time promise"),
    "guarantee": (" Guaranteed delivery.", "pickup/delivery guarantee"),
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


def _slug(s):
    return s.replace(" ", "_").replace("(", "").replace(")", "").replace(".", "_").replace("-", "_")


for _loc in LOCATIONS:
    for _atk in ATTACKS:
        setattr(PolicyChecks, "test_fails_" + _slug(_atk + "_" + _loc), _make_test(_loc, _atk))


# --- the approved sentence itself must not be weakened in any of its locations ---------------------
SENTENCE_EDITS = {
    "prefix removed": lambda s: s.replace("For saree pre-pleating orders, pickup", "Pickup", 1),
    "threshold 5 or more": lambda s: s.replace("more than 5 sarees", "5 or more sarees", 1),
    "threshold exactly 5 free": lambda s: s.replace("For 5 sarees or fewer, pickup and delivery are chargeable",
                                                   "For 5 sarees or fewer, pickup and delivery are free", 1),
}


def _make_sentence_test(location, edit):
    rel, nth, _ = LOCATIONS[location]

    def test(self):
        root = self.fresh_copy()
        path = root / rel
        text = path.read_text(encoding="utf-8", newline="")
        idx = -1
        for _ in range(nth + 1):
            idx = text.index(POLICY, idx + 1)
        path.write_text(text[:idx] + SENTENCE_EDITS[edit](POLICY) + text[idx + len(POLICY):], encoding="utf-8", newline="")
        code, out = run_validator(root)
        self.assertEqual(code, 1, f"validator should reject '{edit}' in {location}")
        self.assertIn("FAIL", out)
    return test


for _loc in LOCATIONS:
    for _edit in SENTENCE_EDITS:
        setattr(PolicyChecks, "test_rejects_" + _slug(_edit + "_" + _loc), _make_sentence_test(_loc, _edit))


# --- the pre-pleating-only policy must not appear on the homepage or the draping page ----------------
MISPLACED = {
    "draping page (visible)": ("saree-draping/index.html", "<h2>Service areas</h2>", False, "/saree-draping/"),
    "homepage (visible)": ("index.html", '<section class="final-cta">', False, "/"),
    "draping page (JSON-LD)": ("saree-draping/index.html", '"description": "', True, "/saree-draping/"),
    "homepage (JSON-LD)": ("index.html", '"description": "', True, "/"),
}


def _make_misplaced_test(location):
    rel, anchor, in_jsonld, route = MISPLACED[location]

    def test(self):
        root = self.fresh_copy()
        path = root / rel
        text = path.read_text(encoding="utf-8", newline="")
        i = text.index(anchor)
        add = POLICY + " " if in_jsonld else f"<p>{POLICY}</p>"
        path.write_text(text[:i + len(anchor)] + add + text[i + len(anchor):], encoding="utf-8", newline="")
        code, out = run_validator(root)
        self.assertEqual(code, 1, f"validator should reject the policy sentence on the {location}")
        self.assertIn(f"FAIL approved pickup/delivery policy sentence is not present on {route}", out)
    return test


for _loc in MISPLACED:
    setattr(PolicyChecks, "test_rejects_policy_on_" + _slug(_loc), _make_misplaced_test(_loc))

# --- draping classes: unverified fee/duration/schedule/batch/certificate claims must be rejected -------------
CLASS_ANCHOR = "Di Dee Designers offers saree draping classes in Tiruppur."
CLASS_ATTACKS = {
    "fee symbol": (" Class fee is ₹2000.", "class fee or price"),
    "fee in rupees": (" Class fee is 2000 rupees.", "class fee or price"),
    "free class": (" Free demo class.", "class fee or price"),
    "duration": (" The course runs for 4 weeks.", "class duration, schedule or batch claim"),
    "batch": (" Next batch starts soon.", "class duration, schedule or batch claim"),
    "schedule": (" Classes are held on weekends.", "class duration, schedule or batch claim"),
    "certificate": (" A certificate is provided.", "class certificate or qualification claim"),
}
# location -> (file, which occurrence of the anchor sentence, suffix of the failing check name)
CLASS_LOCATIONS = {
    "classes page": ("saree-draping-classes/index.html", 0, "on /saree-draping-classes/"),
    "draping page": ("saree-draping/index.html", 0, "on /saree-draping/"),
    "FAQ page (visible)": ("faq.html", 1, "on /faq"),
    "FAQ page (JSON-LD)": ("faq.html", 0, "in JSON-LD on /faq"),
    "llms.txt": ("llms.txt", 0, "in llms.txt"),
}


class ClassChecks(unittest.TestCase):
    fresh_copy = PolicyChecks.fresh_copy

    def test_classes_page_passes(self):
        code, out = run_validator(ROOT)
        self.assertEqual(code, 0, out[-800:])
        for needle in ("PASS /saree-draping-classes/ exists and is indexable",
                       "PASS /faq links to /saree-draping-classes/",
                       "PASS classes page links back to /saree-draping/",
                       "PASS /saree-draping-classes/ lists no invented price"):
            self.assertIn(needle, out)
        self.assertNotIn("FAIL", out)

    def test_faq_link_removed_fails(self):
        root = self.fresh_copy()
        path = root / "faq.html"
        text = path.read_text(encoding="utf-8", newline="")
        path.write_text(text.replace('href="/saree-draping-classes/"', 'href="/saree-draping/"'), encoding="utf-8", newline="")  # drops every link to the classes page
        code, out = run_validator(root)
        self.assertEqual(code, 1)
        self.assertIn("FAIL /faq links to /saree-draping-classes/", out)

    def test_sitemap_missing_classes_fails(self):
        root = self.fresh_copy()
        path = root / "sitemap.xml"
        text = path.read_text(encoding="utf-8", newline="")
        s = text.index("  <url>\r\n    <loc>https://dideedesigners.in/saree-draping-classes/")
        e = text.index("</url>", s) + len("</url>\r\n")
        path.write_text(text[:s] + text[e:], encoding="utf-8", newline="")
        code, out = run_validator(root)
        self.assertEqual(code, 1)
        self.assertIn("FAIL sitemap URLs == indexable canonicals", out)


def _make_class_test(location, attack):
    rel, nth, where = CLASS_LOCATIONS[location]
    extra, rule = CLASS_ATTACKS[attack]

    def test(self):
        root = self.fresh_copy()
        inject_after(root, rel, CLASS_ANCHOR, nth, extra)
        code, out = run_validator(root)
        self.assertEqual(code, 1, f"validator should exit 1 for {attack} in {location}")
        self.assertIn(f"FAIL no {rule} {where}", out)
    return test


def inject_after(root, rel, anchor, nth, extra):
    path = Path(root) / rel
    text = path.read_text(encoding="utf-8", newline="")
    idx = -1
    for _ in range(nth + 1):
        idx = text.index(anchor, idx + 1)
    end = idx + len(anchor)
    path.write_text(text[:end] + extra + text[end:], encoding="utf-8", newline="")


for _loc in CLASS_LOCATIONS:
    for _atk in CLASS_ATTACKS:
        setattr(ClassChecks, "test_fails_" + _slug(_atk + "_" + _loc), _make_class_test(_loc, _atk))

if __name__ == "__main__":
    unittest.main(verbosity=2)
