from pathlib import Path


BOUNDARY_FILES = {
    "en": "boundary_en.txt",
    "he": "boundary_he.txt",
}


def load_boundary_clause(lang, defenses_dir="defenses"):
    try:
        filename = BOUNDARY_FILES[lang]
    except KeyError:
        raise ValueError("no boundary clause for language: %s" % lang)
    path = Path(defenses_dir) / filename
    with path.open("r", encoding="utf-8") as handle:
        return handle.read().strip()

