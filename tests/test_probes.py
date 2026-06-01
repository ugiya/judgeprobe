from pathlib import Path

from judgeprobe.probes import load_probes


ROOT = Path(__file__).resolve().parents[1]


def test_loads_payload_and_control_schemas():
    probes = load_probes([ROOT / "probes"])
    suites = {probe.suite for probe in probes}
    assert suites == {
        "bound_max",
        "bound_min",
        "rubric_override",
        "format_override",
        "criteria_override",
        "controls",
    }

    controls = next(probe for probe in probes if probe.suite == "controls")
    assert controls.is_control
    assert controls.items[0].id == "clean_strong"
    assert controls.items[0].base == "strong"
    assert controls.items[0].expect_min == 80
    assert controls.items[0].expect_max == 100

    bound_max = next(probe for probe in probes if probe.suite == "bound_max")
    assert not bound_max.is_control
    assert bound_max.base == "strong"
    assert set(bound_max.items[0].text) == {"en", "he"}

