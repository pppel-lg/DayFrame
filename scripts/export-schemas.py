"""Generate portable JSON Schemas from the validation models, without opening an archive."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.dayframe.models import ArchiveMetadata, Entry, Letter, Settings


def main():
    destination = ROOT / "schemas"
    destination.mkdir(exist_ok=True)
    for filename, model in {"archive": ArchiveMetadata, "entry": Entry, "letter": Letter, "settings": Settings}.items():
        schema = {"$schema": "https://json-schema.org/draft/2020-12/schema", **model.model_json_schema()}
        (destination / f"{filename}.schema.json").write_text(json.dumps(schema, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Exported four JSON schemas to schemas/")


if __name__ == "__main__":
    main()
