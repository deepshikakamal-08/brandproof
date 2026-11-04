"""Offline tests: no API keys or network needed (uses SQLite and the mock AI provider)."""
import os
import sys
import tempfile

os.environ.setdefault("LLM_PROVIDER", "mock")
os.environ["SQLITE_PATH"] = os.path.join(tempfile.mkdtemp(), "test.db")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "api"))

from _core import engine, workspace  # noqa: E402
from _core.samples import SAMPLES  # noqa: E402

org, _ = workspace.create_guest_workspace("Test", "creator")
brand = workspace.brand_for(org)


def check(text, channel="social", image=None, alt=None):
    return engine.run_check(org, brand, {"text": text, "image_b64": image, "alt_text": alt}, channel, use_cache=False)


def quotes(r):
    return [f["quote"] for f in r["findings"]]


def test_rules():
    r = check("Neem and Nila serum is clinically proven to remove acne!!! #NeemAndNila")
    q = quotes(r)
    assert "Neem and Nila" in q and "clinically proven" in q and "remove acne" in q and "!!!" in q
    assert all(f["cite_code"] for f in r["findings"]), "every finding must cite a source"


def test_compliant_samples_are_clean():
    for sid in ("s06", "s11"):
        s = next(x for x in SAMPLES if x["id"] == sid)
        r = check(s["text"], s["channel"])
        assert not [f for f in r["findings"] if f["source"] == "rule"], (sid, quotes(r))


def test_citation_gate_drops_uncited():
    r = check("Hurry, only a few left. Glow Ritual Vitamin C Serum at ₹599. #NeemAndNila")
    assert r["dropped_uncited"] >= 1
    ai = [f for f in r["findings"] if f["source"] == "ai"]
    assert any(f["claim_status"] == "outdated" and f["cite_code"] == "F2" for f in ai)
    for f in ai:
        assert f["quote"].lower() in r["findings"][0]["quote"].lower() or f["start"] is not None


def test_fixes_apply():
    text = "Neem and Nila is HERE!!! #NeemAndNila"
    r = check(text)
    for f in r["findings"]:
        f["decision"] = "accepted"
    out = engine.apply_fixes(text, r["findings"])
    assert "Neem & Nila" in out and "HERE" not in out and "!!!" not in out, out


def test_image_checks():
    img = workspace.asset_b64("banner_offbrand.png")
    r = check("Festive glow #NeemAndNila", image=img, alt="")
    cats = {f["category"] for f in r["findings"]}
    assert "accessibility" in cats and "visual" in cats
    on = check("Festive glow #NeemAndNila", image=workspace.asset_b64("banner_onbrand.png"), alt="Serum on sand")
    assert not [f for f in on["findings"] if f["rule"] == "palette"]


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok ", name)
    print("all tests passed")
