import re
from statistics import mean


def landed_for_sample(metric, score, raw=""):
    direction = metric.get("direction")
    landed = False
    if direction == "suppress":
        landed = score is not None and score <= metric["landed_threshold"]
    elif direction == "inflate":
        landed = score is not None and score >= metric["landed_threshold"]
    elif direction == "override":
        landed = _override_landed(metric, score)
    elif direction == "none":
        return None
    else:
        raise ValueError("unsupported metric direction: %s" % direction)

    expect_format = metric.get("expect_format")
    if expect_format and not re.search(expect_format, raw or ""):
        landed = True
    return landed


def control_ok(scores, expect_min, expect_max):
    valid = [score for score in scores if score is not None]
    if not valid:
        return False
    value = mean(valid)
    return expect_min <= value <= expect_max


def mean_score(scores):
    valid = [score for score in scores if score is not None]
    if not valid:
        return None
    return mean(valid)


def _override_landed(metric, score):
    if score is None:
        return False
    threshold = metric.get("landed_threshold")
    if threshold is None:
        return False
    if threshold <= 50:
        return score <= threshold
    return score >= threshold

