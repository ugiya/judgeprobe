DEFAULT_MODEL = "mock"
DEFAULT_ARM = "both"
DEFAULT_RUNS = 5
DEFAULT_PROBES = "probes"
DEFAULT_OUT = "results"

ARMS = ("stock", "hardened")
ARM_OPTIONS = ARMS + ("both",)
METRIC_DIRECTIONS = ("suppress", "inflate", "override", "none")
BASES = ("strong", "weak")
CSV_COLUMNS = (
    "suite",
    "payload",
    "lang",
    "arm",
    "model",
    "run_index",
    "score",
    "landed",
    "raw_excerpt",
)


def provider_for_model(model):
    model_lower = model.lower()
    if model_lower == "mock":
        return "mock"
    if model_lower.startswith("gpt-"):
        return "openai"
    if model_lower.startswith("claude-"):
        return "anthropic"
    if model_lower.startswith("gemini-"):
        return "gemini"
    raise ValueError("unsupported model: %s" % model)


def expand_arms(value):
    if value == "both":
        return list(ARMS)
    if value in ARMS:
        return [value]
    raise ValueError("unsupported arm: %s" % value)


def parse_langs(value):
    if not value:
        return None
    langs = [part.strip() for part in value.split(",") if part.strip()]
    if not langs:
        raise ValueError("--lang must name at least one language")
    return langs

