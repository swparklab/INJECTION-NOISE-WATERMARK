"""I/O utilities for reading and writing data."""

import json
import logging
from pathlib import Path
from typing import Any, Iterable, List, Mapping, Optional, Union

from tqdm.auto import tqdm

logger = logging.getLogger(__name__)


def resolve_globs(glob_paths: Union[str, Iterable[str]]) -> List[Path]:
    """Resolve glob patterns to file paths.

    Args:
        glob_paths: Single glob pattern or list of patterns

    Returns:
        List of Path objects matching the patterns
    """
    filepaths = []
    if isinstance(glob_paths, str):
        glob_paths = [glob_paths]

    for path in glob_paths:
        filepaths.extend(Path().glob(path))

    return filepaths


def read_jsonlines(filename: str, show_progress: bool = True) -> Iterable[Mapping[str, Any]]:
    """Read JSONL file line by line.

    Args:
        filename: Path to JSONL file
        show_progress: Whether to show progress bar

    Returns:
        Iterator of dictionaries from JSON lines
    """
    with open(filename) as fp:
        lines = fp.readlines()
        if show_progress:
            lines = tqdm(lines, desc=f"Reading {Path(filename).name}", unit="lines")

        for line in lines:
            try:
                yield json.loads(line)
            except json.JSONDecodeError as ex:
                logger.error(f"Failed to decode line: {line}")
                raise ex


def load_jsonlines(filename: str) -> List[Mapping[str, Any]]:
    """Load entire JSONL file into memory.

    Args:
        filename: Path to JSONL file

    Returns:
        List of dictionaries from JSON lines
    """
    return list(read_jsonlines(filename, show_progress=False))


def write_jsonlines(
    objs: Iterable[Mapping[str, Any]],
    filename: str,
    to_dict: Optional[callable] = None,
) -> None:
    """Write objects as JSONL file.

    Args:
        objs: Iterable of dictionaries to write
        filename: Output file path
        to_dict: Optional function to convert objects to dicts
    """
    to_dict = to_dict or (lambda x: x)

    with open(filename, "w") as fp:
        for obj in tqdm(objs, desc=f"Writing {Path(filename).name}", unit="lines"):
            fp.write(json.dumps(to_dict(obj)))
            fp.write("\n")


def read_json(filename: str) -> Mapping[str, Any]:
    """Read JSON file.

    Args:
        filename: Path to JSON file

    Returns:
        Dictionary from JSON file
    """
    with open(filename) as fp:
        return json.load(fp)


def write_json(
    obj: Mapping[str, Any],
    filename: str,
    indent: Optional[int] = None,
) -> None:
    """Write object as JSON file.

    Args:
        obj: Dictionary to write
        filename: Output file path
        indent: Indentation level (None for compact output)
    """
    with open(filename, "w") as fp:
        json.dump(obj, fp, indent=indent)


def print_json(data: Any, indent: int = 4) -> None:
    """Pretty print object as JSON.

    Args:
        data: Object to print
        indent: Indentation level
    """
    print(json.dumps(data, indent=indent))
