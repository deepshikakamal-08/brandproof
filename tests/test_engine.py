"""Offline tests: no API keys or network needed (uses SQLite and the mock AI provider)."""
import os
import sys
import tempfile

os.environ.setdefault("LLM_PROVIDER", "mock")
os.environ["SQLITE_PATH"] = os.path.join(tempfile.mkdtemp(), "test.db")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "api"))

from _core import engine, evaluation, lang, learning, workspace  # noqa: E402
from _core.regional import REGIONAL  # noqa: E402
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


def test_learning_mutes_and_softens():
    """Improvement 1: disputed AI flags are muted, disputed rule flags only softened."""
    learning.clear(org, brand["id"])
    text = "Hurry, only a few left. Glow Ritual Vitamin C Serum at ₹599. #NeemAndNila"
    ai = next(f for f in check(text)["findings"] if f["source"] == "ai" and f["category"] == "tone")
    for i in range(3):
        learning.record(org, brand["id"], {**ai, "id": f"t{i}", "quote": f"other text {i}"}, "disputed", "fine for us")
    r = check(text)
    assert not [f for f in r["findings"] if f["cite_code"] == ai["cite_code"] and f["source"] == "ai"]
    assert any(h["cite_code"] == ai["cite_code"] for h in r["hidden"]), "muted finding must be listed as hidden"
    rule = next(f for f in check("Neem and Nila glow")["findings"] if f["source"] == "rule")
    for i in range(3):
        learning.record(org, brand["id"], {**rule, "id": f"r{i}"}, "disputed", "ok")
    r2 = check("Neem and Nila glow")
    kept = [f for f in r2["findings"] if f["cite_code"] == rule["cite_code"]]
    assert kept and kept[0]["severity"] == "low" and kept[0]["learning"], "rule findings are softened, never hidden"
    # switching learning off restores everything
    learning.set_enabled(org, brand["id"], "*", False)
    assert any(f["cite_code"] == ai["cite_code"] for f in check(text)["findings"])
    learning.set_enabled(org, brand["id"], "*", True)
    learning.clear(org, brand["id"])


def test_learning_threshold_and_prompt():
    learning.clear(org, brand["id"])
    base = {"source": "ai", "category": "tone", "cite_code": "2.1", "quote": "x"}
    for i, (conf, dec) in enumerate([(0.9, "accepted"), (0.85, "accepted"), (0.8, "accepted"),
                                     (0.6, "disputed"), (0.55, "disputed"), (0.6, "disputed"), (0.95, "accepted")]):
        learning.record(org, brand["id"], {**base, "id": f"c{i}", "confidence": conf, "quote": f"q{i}"}, dec, "")
    pol = learning.policy(org, brand["id"])
    assert pol["ai_threshold"] and 0.6 < pol["ai_threshold"] <= 0.8, pol["ai_threshold"]
    block = learning.prompt_block(pol, [{"_id": "C1", "code": "2.1"}])
    assert "REVIEWER HISTORY" in block and "C1" in block
    learning.clear(org, brand["id"])


def test_training_replay_records_calibration():
    learning.clear(org, brand["id"])
    r = evaluation.score_case(org, brand, evaluation.TRAIN_IDS[0], learn=False, train=True)
    pol = learning.policy(org, brand["id"])
    assert pol["calibration_decisions"] == len(r["predicted"]) > 0
    learning.clear(org, brand["id"])


def test_language_detection():
    want = {"Tamil": "ta", "Hindi": "hi", "Tanglish": "ta-en", "Hinglish": "hi-en"}
    for r in REGIONAL:
        assert lang.detect(r["text"])["code"] == want[r["lang"]], r["id"]
    for s in SAMPLES:
        assert lang.detect(s["text"])["code"] == "en", s["id"]


def test_indic_rules_catch_labelled_issues():
    """Every labelled terminology issue and medical/absolute claim in the Indian-language set is
    caught by exact rules; compliant drafts get no rule findings."""
    for r in REGIONAL:
        found = check(r["text"], r["channel"])["findings"]
        rules_ = [f for f in found if f["source"] == "rule"]
        if not r["expected"]:
            assert not rules_, (r["id"], [f["quote"] for f in rules_])
        for cat, q in r["expected"]:
            if cat == "terminology":
                assert any(q.lower() in f["quote"].lower() for f in rules_), (r["id"], q)


def test_brand_name_script_fix():
    f = check("நீம் அண்ட் நிலா Calm Neem Face Wash", "whatsapp")["findings"]
    assert any(x["fix_text"] == "Neem & Nila" for x in f)


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok ", name)
    print("all tests passed")
