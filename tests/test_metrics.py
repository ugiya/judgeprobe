from pathlib import Path

from judgeprobe.judge import build_messages, load_answers
from judgeprobe.metrics import control_ok, landed_for_sample
from judgeprobe.probes import load_probe_file
from judgeprobe.providers import MockProvider


ROOT = Path(__file__).resolve().parents[1]


def test_suppress_and_inflate_landing_rules():
    assert landed_for_sample({"direction": "suppress", "landed_threshold": 17}, 15, "{}")
    assert not landed_for_sample({"direction": "suppress", "landed_threshold": 17}, 96, "{}")
    assert landed_for_sample({"direction": "inflate", "landed_threshold": 85}, 95, "{}")
    assert not landed_for_sample({"direction": "inflate", "landed_threshold": 85}, 12, "{}")


def test_format_override_checks_raw_shape():
    metric = {"direction": "inflate", "landed_threshold": 85, "expect_format": '"score"'}
    assert landed_for_sample(metric, 12, "100")
    assert landed_for_sample(metric, 100, '{"score": 100}')
    assert not landed_for_sample(metric, 12, '{"score": 12}')


def test_control_mean_band():
    assert control_ok([94, 96, 99], 80, 100)
    assert not control_ok([60, 62, 64], 80, 100)


def test_mock_bound_max_lands_on_stock_and_blocks_on_hardened():
    answers = load_answers(ROOT / "content" / "answers.yaml")
    probe = load_probe_file(ROOT / "probes" / "bound_max.yaml")
    item = probe.items[0]

    stock_system, stock_user = build_messages(
        answers, "en", probe.base, item.text["en"], "stock", ROOT / "defenses"
    )
    hardened_system, hardened_user = build_messages(
        answers, "en", probe.base, item.text["en"], "hardened", ROOT / "defenses"
    )

    provider = MockProvider(seed=0)
    stock = provider.score(stock_system, stock_user)
    hardened = provider.score(hardened_system, hardened_user)

    assert stock["score"] == 15
    assert landed_for_sample(probe.metric, stock["score"], stock["raw"])
    assert hardened["score"] >= 90
    assert not landed_for_sample(probe.metric, hardened["score"], hardened["raw"])

