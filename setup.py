from collections import defaultdict
from pathlib import Path

from setuptools import setup


ROOT = Path(__file__).parent
ARTIFACT_ROOTS = ("benchmark", "docs", "oracle", "scripts", "tasks")
ROOT_FILES = ("CITATION.cff", "CONTRIBUTING.md", "LICENSE", "NOTICE", "README.md")


def artifact_data_files() -> list[tuple[str, list[str]]]:
    grouped: dict[Path, list[str]] = defaultdict(list)
    for root_name in ARTIFACT_ROOTS:
        for path in (ROOT / root_name).rglob("*"):
            if not path.is_file() or "__pycache__" in path.parts or path.suffix in {".pyc", ".pyo"}:
                continue
            grouped[path.parent.relative_to(ROOT)].append(str(path.relative_to(ROOT)))

    data_files = [
        (
            str(Path("share") / "backendforge" / relative_dir),
            sorted(paths),
        )
        for relative_dir, paths in sorted(grouped.items(), key=lambda item: str(item[0]))
    ]
    data_files.append(
        (
            str(Path("share") / "backendforge"),
            [name for name in ROOT_FILES if (ROOT / name).is_file()],
        )
    )
    return data_files


setup(data_files=artifact_data_files())
