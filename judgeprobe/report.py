import csv
import hashlib
import json
from pathlib import Path

from .config import CSV_COLUMNS
from .metrics import mean_score


def raw_excerpt(raw, limit=160):
    text = " ".join((raw or "").split())
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def write_run(rows, out_dir, timestamp, runid, model, provider, runs, langs, arms, probe_files, version):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    csv_path = out / ("%s-%s.csv" % (timestamp, runid))
    meta_path = out / ("%s-%s.meta.json" % (timestamp, runid))

    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in CSV_COLUMNS})

    meta = {
        "model": model,
        "provider": provider,
        "runs": runs,
        "langs": list(langs),
        "arms": list(arms),
        "probe_files": probe_file_hashes(probe_files),
        "version": version,
        "timestamp": timestamp,
    }
    with meta_path.open("w", encoding="utf-8") as handle:
        json.dump(meta, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
    return csv_path, meta_path


def probe_file_hashes(paths):
    records = []
    for raw in paths:
        path = Path(raw)
        records.append({"path": str(path), "sha256": sha256_file(path)})
    return records


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_csv(path):
    with Path(path).open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def format_matrix(path_or_rows):
    rows = read_csv(path_or_rows) if isinstance(path_or_rows, (str, Path)) else list(path_or_rows)
    if not rows:
        return "No rows."

    suite_order = _ordered_unique(row["suite"] for row in rows)
    arm_order = _ordered_unique(row["arm"] for row in rows)
    lang_order = _ordered_unique(row["lang"] for row in rows)
    payload_order = {}
    for row in rows:
        payload_order.setdefault(row["suite"], [])
        if row["payload"] not in payload_order[row["suite"]]:
            payload_order[row["suite"]].append(row["payload"])

    columns = [(arm, lang) for arm in arm_order for lang in lang_order]
    lines = []
    for suite in suite_order:
        lines.append("Suite: %s" % suite)
        headers = ["payload"] + ["%s/%s" % (arm, lang) for arm, lang in columns]
        body = []
        for payload in payload_order[suite]:
            record = [payload]
            for arm, lang in columns:
                cell_rows = [
                    row for row in rows
                    if row["suite"] == suite
                    and row["payload"] == payload
                    and row["arm"] == arm
                    and row["lang"] == lang
                ]
                record.append(_format_cell(cell_rows))
            body.append(record)
        lines.extend(_render_table(headers, body))
        lines.append("")
    return "\n".join(lines).rstrip()


def _format_cell(rows):
    if not rows:
        return "-"
    scores = [_parse_score(row.get("score")) for row in rows]
    value = mean_score(scores)
    landed = sum(1 for row in rows if _parse_landed(row.get("landed")))
    if value is None:
        return "NA (%d/%d)" % (landed, len(rows))
    return "%.1f (%d/%d)" % (value, landed, len(rows))


def _render_table(headers, rows):
    widths = [len(header) for header in headers]
    for row in rows:
        for index, cell in enumerate(row):
            widths[index] = max(widths[index], len(cell))
    rendered = []
    rendered.append("  " + "  ".join(header.ljust(widths[index]) for index, header in enumerate(headers)))
    rendered.append("  " + "  ".join("-" * width for width in widths))
    for row in rows:
        rendered.append("  " + "  ".join(cell.ljust(widths[index]) for index, cell in enumerate(row)))
    return rendered


def _ordered_unique(values):
    result = []
    for value in values:
        if value not in result:
            result.append(value)
    return result


def _parse_score(value):
    if value in (None, ""):
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _parse_landed(value):
    return str(value).lower() in ("1", "true", "yes", "ok")

