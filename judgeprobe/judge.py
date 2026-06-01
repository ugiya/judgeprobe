from pathlib import Path

import yaml

from .defenses import load_boundary_clause


def load_answers(path="content/answers.yaml"):
    path = Path(path)
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        raise ValueError("%s: answers file must be a mapping" % path)
    for key in ("question", "rubric", "answers"):
        if key not in data:
            raise ValueError("%s: missing %s" % (path, key))
    return data


def build_messages(answers, lang, base, payload_text, arm, defenses_dir="defenses"):
    try:
        question = answers["question"][lang].strip()
        rubric = answers["rubric"][lang].strip()
        answer = answers["answers"][base][lang].strip()
    except KeyError as exc:
        raise ValueError("missing answer content for %s" % (exc,))

    if arm not in ("stock", "hardened"):
        raise ValueError("unsupported arm: %s" % arm)

    system = rubric
    if arm == "hardened":
        system = system + "\n\n" + load_boundary_clause(lang, defenses_dir)

    user = (
        "Question:\n%s\n\n"
        "Candidate answer:\n%s%s"
    ) % (question, answer, payload_text)
    return system, user

