from __future__ import annotations

import csv
import io
import re
import zipfile
from pathlib import Path
from typing import Iterable, Iterator, List, Optional, Sequence, Tuple, Union

from flask import Response, send_file

BytesLike = Union[bytes, bytearray, memoryview]
TextLike = Union[str, bytes]


_SAFE_NAME_RE = re.compile(r"[^a-zA-Z0-9._-]+")


def safe_filename(name: str, default: str = "download") -> str:
    """
    Makes a safe filename for Content-Disposition.
    """
    name = (name or "").strip() or default
    name = name.replace("\\", "_").replace("/", "_")
    name = _SAFE_NAME_RE.sub("_", name)
    return name[:180]  # keep it reasonable


def to_bytes(data: TextLike, encoding: str = "utf-8") -> bytes:
    if isinstance(data, (bytes, bytearray, memoryview)):
        return bytes(data)
    return str(data).encode(encoding, errors="replace")


def send_text_download(filename: str, text: str, mimetype: str = "text/plain; charset=utf-8") -> Response:
    filename = safe_filename(filename)
    bio = io.BytesIO(to_bytes(text))
    bio.seek(0)
    return send_file(
        bio,
        mimetype=mimetype,
        as_attachment=True,
        download_name=filename,
    )


def send_bytes_download(filename: str, data: BytesLike, mimetype: str = "application/octet-stream") -> Response:
    filename = safe_filename(filename)
    bio = io.BytesIO(bytes(data))
    bio.seek(0)
    return send_file(
        bio,
        mimetype=mimetype,
        as_attachment=True,
        download_name=filename,
    )


def csv_bytes(rows: Sequence[dict], fieldnames: Optional[List[str]] = None, delimiter: str = ";") -> bytes:
    """
    Creates CSV bytes (UTF-8 with BOM for Excel friendliness).
    - delimiter defaults to ';' (BE/Excel)
    """
    if not rows:
        fieldnames = fieldnames or []
    else:
        if fieldnames is None:
            # union of keys preserving first row order
            seen = []
            for k in rows[0].keys():
                seen.append(k)
            for r in rows[1:]:
                for k in r.keys():
                    if k not in seen:
                        seen.append(k)
            fieldnames = seen

    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=fieldnames, delimiter=delimiter, lineterminator="\n")
    writer.writeheader()
    for r in rows:
        writer.writerow({k: r.get(k, "") for k in fieldnames})

    # BOM for Excel
    return ("\ufeff" + out.getvalue()).encode("utf-8", errors="replace")


def send_csv_download(filename: str, rows: Sequence[dict], fieldnames: Optional[List[str]] = None, delimiter: str = ";") -> Response:
    filename = safe_filename(filename)
    if not filename.lower().endswith(".csv"):
        filename += ".csv"
    data = csv_bytes(rows, fieldnames=fieldnames, delimiter=delimiter)
    return send_bytes_download(filename, data, mimetype="text/csv; charset=utf-8")


def zip_from_files(files: Iterable[Tuple[str, BytesLike]]) -> bytes:
    """
    files: iterable of (path_inside_zip, bytes)
    """
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for name, content in files:
            name = name.replace("\\", "/").lstrip("/")
            z.writestr(name, bytes(content))
    return buf.getvalue()


def zip_from_folder(
    folder: Path,
    include_globs: Optional[List[str]] = None,
    exclude_globs: Optional[List[str]] = None,
) -> bytes:
    """
    Zips a folder recursively.
    include_globs: patterns like ["*.txt", "*.csv"] (if None => include all)
    exclude_globs: patterns like ["*.log", "__pycache__/*"]
    """
    folder = folder.resolve()
    include_globs = include_globs or []
    exclude_globs = exclude_globs or []

    def is_excluded(rel: str) -> bool:
        rel_norm = rel.replace("\\", "/")
        for pat in exclude_globs:
            if Path(rel_norm).match(pat) or Path(rel_norm).as_posix().startswith(pat.rstrip("*")):
                return True
        return False

    def is_included(p: Path) -> bool:
        if not include_globs:
            return True
        rel = p.relative_to(folder).as_posix()
        for pat in include_globs:
            if Path(rel).match(pat) or p.name.lower() == pat.lower():
                return True
        return False

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for p in folder.rglob("*"):
            if p.is_dir():
                continue
            rel = p.relative_to(folder).as_posix()
            if is_excluded(rel):
                continue
            if not is_included(p):
                continue
            z.write(p, arcname=rel)
    return buf.getvalue()


def send_zip_download(filename: str, zipped: bytes) -> Response:
    filename = safe_filename(filename)
    if not filename.lower().endswith(".zip"):
        filename += ".zip"
    return send_bytes_download(filename, zipped, mimetype="application/zip")


def read_file_bytes(path: Path, max_mb: int = 25) -> bytes:
    """
    Safe-ish file read with size cap.
    """
    path = path.resolve()
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(str(path))
    size = path.stat().st_size
    if size > max_mb * 1024 * 1024:
        raise ValueError(f"File too large ({size} bytes), limit is {max_mb} MB")
    return path.read_bytes()
