from dataclasses import dataclass
from pathlib import Path
import re

import yaml

from .config import BASES, METRIC_DIRECTIONS


class ProbeValidationError(Exception):
    def __init__(self, errors):
        self.errors = list(errors)
        super().__init__("\n".join(self.errors))


@dataclass(frozen=True)
class ProbeItem:
    id: str
    text: dict
    note: str = ""
    base: str = None
    expect_min: int = None
    expect_max: int = None


@dataclass(frozen=True)
class Probe:
    suite: str
    description: str
    metric: dict
    languages: list
    items: list
    path: Path
    base: str = None

    @property
    def is_control(self):
        return self.metric.get("direction") == "none"


def collect_probe_files(paths):
    files = []
    for raw in paths:
        path = Path(raw)
        if path.is_dir():
            files.extend(sorted(path.glob("*.yaml")))
            files.extend(sorted(path.glob("*.yml")))
        else:
            files.append(path)
    return sorted(dict.fromkeys(files))


def load_probes(paths):
    files = collect_probe_files(paths)
    errors = []
    probes = []
    seen = {}
    if not files:
        raise ProbeValidationError(["no probe YAML files found"])

    for path in files:
        try:
            probe = load_probe_file(path)
        except ProbeValidationError as exc:
            errors.extend(exc.errors)
            continue
        if probe.suite in seen:
            errors.append(
                "%s: duplicate suite id %r already declared in %s"
                % (path, probe.suite, seen[probe.suite])
            )
        else:
            seen[probe.suite] = path
            probes.append(probe)

    if errors:
        raise ProbeValidationError(errors)
    return probes


def load_probe_file(path):
    path = Path(path)
    errors = []
    if not path.exists():
        raise ProbeValidationError(["%s: file not found" % path])
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle)
    except yaml.YAMLError as exc:
        raise ProbeValidationError(["%s: invalid YAML: %s" % (path, exc)])

    if not isinstance(data, dict):
        raise ProbeValidationError(["%s: top-level YAML must be a mapping" % path])

    suite = _require_str(data, "suite", path, errors)
    if suite and not re.match(r"^[A-Za-z0-9_-]+$", suite):
        errors.append("%s: suite must contain only letters, digits, '_' or '-'" % path)
    description = _require_str(data, "description", path, errors)
    languages = _require_list_of_str(data, "languages", path, errors)
    metric = _require_mapping(data, "metric", path, errors)
    direction = None
    if metric is not None:
        direction = _require_str(metric, "direction", path, errors, prefix="metric.")
        if direction and direction not in METRIC_DIRECTIONS:
            errors.append("%s: metric.direction must be one of %s" % (path, METRIC_DIRECTIONS))
        if direction in ("suppress", "inflate", "override"):
            _require_int(metric, "landed_threshold", path, errors, prefix="metric.")
        if "expect_format" in metric and not isinstance(metric.get("expect_format"), str):
            errors.append("%s: metric.expect_format must be a string" % path)

    if direction == "none":
        items = _validate_control_cases(data, languages, path, errors, metric or {})
        base = data.get("base")
        if base is not None and base not in BASES:
            errors.append("%s: base must be one of %s" % (path, BASES))
    else:
        base = _require_str(data, "base", path, errors)
        if base and base not in BASES:
            errors.append("%s: base must be one of %s" % (path, BASES))
        items = _validate_payloads(data, languages, path, errors)

    if errors:
        raise ProbeValidationError(errors)

    return Probe(
        suite=suite,
        description=description,
        base=base,
        metric=dict(metric),
        languages=list(languages),
        items=items,
        path=path,
    )


def _validate_payloads(data, languages, path, errors):
    payloads = data.get("payloads")
    if not isinstance(payloads, list) or not payloads:
        errors.append("%s: payloads must be a non-empty list" % path)
        return []
    items = []
    seen = set()
    for index, payload in enumerate(payloads):
        label = "payloads[%d]" % index
        if not isinstance(payload, dict):
            errors.append("%s: %s must be a mapping" % (path, label))
            continue
        item_id = _require_str(payload, "id", path, errors, prefix=label + ".")
        if item_id in seen:
            errors.append("%s: duplicate payload id %r" % (path, item_id))
        seen.add(item_id)
        text = _validate_text_map(payload, languages, path, errors, label)
        note = payload.get("note", "")
        if note is not None and not isinstance(note, str):
            errors.append("%s: %s.note must be a string" % (path, label))
            note = ""
        if item_id and text is not None:
            items.append(ProbeItem(id=item_id, note=note or "", text=text))
    return items


def _validate_control_cases(data, languages, path, errors, metric):
    cases = data.get("cases")
    if not isinstance(cases, list) or not cases:
        errors.append("%s: cases must be a non-empty list for metric.direction=none" % path)
        return []
    items = []
    seen = set()
    for index, case in enumerate(cases):
        label = "cases[%d]" % index
        if not isinstance(case, dict):
            errors.append("%s: %s must be a mapping" % (path, label))
            continue
        item_id = _require_str(case, "id", path, errors, prefix=label + ".")
        if item_id in seen:
            errors.append("%s: duplicate case id %r" % (path, item_id))
        seen.add(item_id)
        base = _require_str(case, "base", path, errors, prefix=label + ".")
        if base and base not in BASES:
            errors.append("%s: %s.base must be one of %s" % (path, label, BASES))
        expect_min = case.get("expect_min", metric.get("expect_min"))
        expect_max = case.get("expect_max", metric.get("expect_max"))
        if not isinstance(expect_min, int):
            errors.append("%s: %s.expect_min must be an integer" % (path, label))
        if not isinstance(expect_max, int):
            errors.append("%s: %s.expect_max must be an integer" % (path, label))
        if isinstance(expect_min, int) and isinstance(expect_max, int) and expect_min > expect_max:
            errors.append("%s: %s.expect_min must be <= expect_max" % (path, label))
        text = _validate_text_map(case, languages, path, errors, label)
        note = case.get("note", "")
        if note is not None and not isinstance(note, str):
            errors.append("%s: %s.note must be a string" % (path, label))
            note = ""
        if item_id and base and text is not None and isinstance(expect_min, int) and isinstance(expect_max, int):
            items.append(
                ProbeItem(
                    id=item_id,
                    note=note or "",
                    text=text,
                    base=base,
                    expect_min=expect_min,
                    expect_max=expect_max,
                )
            )
    return items


def _validate_text_map(item, languages, path, errors, label):
    text = item.get("text")
    if not isinstance(text, dict):
        errors.append("%s: %s.text must be a mapping of language to string" % (path, label))
        return None
    cleaned = {}
    for lang in languages:
        value = text.get(lang)
        if not isinstance(value, str):
            errors.append("%s: %s.text.%s must be a string" % (path, label, lang))
        else:
            cleaned[lang] = value
    for lang in text:
        if lang not in languages:
            errors.append("%s: %s.text.%s is not declared in languages" % (path, label, lang))
    return cleaned if len(cleaned) == len(languages) else None


def _require_mapping(data, key, path, errors):
    value = data.get(key)
    if not isinstance(value, dict):
        errors.append("%s: %s must be a mapping" % (path, key))
        return None
    return value


def _require_str(data, key, path, errors, prefix=""):
    value = data.get(key)
    if not isinstance(value, str) or not value:
        errors.append("%s: %s%s must be a non-empty string" % (path, prefix, key))
        return None
    return value


def _require_int(data, key, path, errors, prefix=""):
    value = data.get(key)
    if not isinstance(value, int):
        errors.append("%s: %s%s must be an integer" % (path, prefix, key))
        return None
    return value


def _require_list_of_str(data, key, path, errors):
    value = data.get(key)
    if not isinstance(value, list) or not value:
        errors.append("%s: %s must be a non-empty list" % (path, key))
        return []
    if not all(isinstance(item, str) and item for item in value):
        errors.append("%s: %s must contain only non-empty strings" % (path, key))
        return []
    return value

