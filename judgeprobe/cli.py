import argparse
from collections import defaultdict
from datetime import datetime, timezone
import sys
import uuid

from . import __version__
from .config import DEFAULT_ARM, DEFAULT_MODEL, DEFAULT_OUT, DEFAULT_PROBES, DEFAULT_RUNS, expand_arms, parse_langs, provider_for_model
from .judge import build_messages, load_answers
from .metrics import control_ok, landed_for_sample
from .probes import ProbeValidationError, collect_probe_files, load_probes
from .providers import ProviderAuthError, create_provider
from .report import format_matrix, raw_excerpt, write_run


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "validate":
            return cmd_validate(args)
        if args.command == "run":
            return cmd_run(args)
        if args.command == "report":
            return cmd_report(args)
    except ProbeValidationError as exc:
        for error in exc.errors:
            print(error, file=sys.stderr)
        return 2
    except ProviderAuthError as exc:
        print(str(exc), file=sys.stderr)
        return 3
    except (ValueError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    parser.print_help()
    return 2


def build_parser():
    parser = argparse.ArgumentParser(prog="judgeprobe")
    sub = parser.add_subparsers(dest="command", required=True)

    validate = sub.add_parser("validate", help="schema-check probe YAML")
    validate.add_argument("probes", nargs="*", default=[DEFAULT_PROBES])

    run = sub.add_parser("run", help="run probes")
    run.add_argument("--probes", nargs="+", default=[DEFAULT_PROBES])
    run.add_argument("--arm", choices=("stock", "hardened", "both"), default=DEFAULT_ARM)
    run.add_argument("--model", default=DEFAULT_MODEL)
    run.add_argument("--lang", default=None)
    run.add_argument("--runs", type=int, default=DEFAULT_RUNS)
    run.add_argument("--out", default=DEFAULT_OUT)
    run.add_argument("--seed", type=int, default=0)

    report = sub.add_parser("report", help="print a matrix from a run CSV")
    report.add_argument("csv")
    return parser


def cmd_validate(args):
    probes = load_probes(args.probes)
    print("Validated %d probe file(s)." % len(probes))
    return 0


def cmd_run(args):
    if args.runs <= 0:
        raise ValueError("--runs must be positive")
    probes = load_probes(args.probes)
    answers = load_answers()
    arms = expand_arms(args.arm)
    requested_langs = parse_langs(args.lang)
    provider_name = provider_for_model(args.model)
    provider = create_provider(args.model, seed=args.seed)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    runid = uuid.uuid4().hex[:8]
    rows = []
    control_groups = defaultdict(list)
    used_langs = []

    for probe in probes:
        langs = requested_langs or probe.languages
        unsupported = [lang for lang in langs if lang not in probe.languages]
        if unsupported:
            raise ValueError("%s: unsupported language(s): %s" % (probe.suite, ",".join(unsupported)))
        for lang in langs:
            if lang not in used_langs:
                used_langs.append(lang)
            for arm in arms:
                for item in probe.items:
                    base = item.base or probe.base
                    payload_text = item.text[lang]
                    for run_index in range(1, args.runs + 1):
                        system, user = build_messages(answers, lang, base, payload_text, arm)
                        result = provider.score(system, user)
                        score = result.get("score")
                        raw = result.get("raw", "")
                        landed = landed_for_sample(probe.metric, score, raw)
                        row = {
                            "suite": probe.suite,
                            "payload": item.id,
                            "lang": lang,
                            "arm": arm,
                            "model": args.model,
                            "run_index": str(run_index),
                            "score": "" if score is None else str(score),
                            "landed": "" if landed is None else ("1" if landed else "0"),
                            "raw_excerpt": raw_excerpt(raw),
                        }
                        rows.append(row)
                        if probe.is_control:
                            key = (probe.suite, item.id, lang, arm)
                            control_groups[key].append((row, item))

    _mark_control_rows(control_groups)
    probe_files = collect_probe_files(args.probes)
    csv_path, meta_path = write_run(
        rows=rows,
        out_dir=args.out,
        timestamp=timestamp,
        runid=runid,
        model=args.model,
        provider=provider_name,
        runs=args.runs,
        langs=used_langs,
        arms=arms,
        probe_files=probe_files,
        version=__version__,
    )
    print("CSV: %s" % csv_path)
    print("META: %s" % meta_path)
    return 0


def cmd_report(args):
    print(format_matrix(args.csv))
    return 0


def _mark_control_rows(groups):
    for pairs in groups.values():
        rows = [pair[0] for pair in pairs]
        item = pairs[0][1]
        scores = []
        for row in rows:
            try:
                scores.append(int(row["score"]))
            except (TypeError, ValueError):
                scores.append(None)
        ok = control_ok(scores, item.expect_min, item.expect_max)
        for row in rows:
            row["landed"] = "1" if ok else "0"


if __name__ == "__main__":
    raise SystemExit(main())

