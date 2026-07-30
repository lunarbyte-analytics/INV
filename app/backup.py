"""Eksport / import kopii zapasowej (ZIP) — dane i opcjonalnie kod aplikacji.

Plik ZIP można zapisać w folderze chmury (OneDrive, Google Drive, Dropbox);
synchronizacja odbywa się po stronie klienta chmury.
"""
from __future__ import annotations

import json
import shutil
import sqlite3
import tempfile
import zipfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

BACKUP_FORMAT_VERSION = 1
MANIFEST_NAME = "inv_backup_manifest.json"

DATA_DB_NAMES = ("sqllite3_inv.db", "sqllite3_inv_test.db")
SETTINGS_NAME = "inv_app_settings.json"

APP_ROOT_FILES = (
    "main.py",
    "UruchomINV.bat",
    "UtworzSkrotINV.bat",
    "requirements.txt",
    "inv_app_settings.example.json",
    "README.md",
    "set-ksef-env.ps1",
)

APP_DIRS = ("app", "assets")

SKIP_DIR_NAMES = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    ".idea",
    ".vscode",
    "backups",
    "output",
    "agent-transcripts",
}


@dataclass
class ExportOptions:
    include_app: bool = False
    include_settings: bool = True
    include_reports: bool = False
    include_both_databases: bool = True


@dataclass
class ExportResult:
    path: Path
    files: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass
class ImportResult:
    restored: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def get_project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def get_data_root() -> Path:
    """Katalog danych = CWD (UruchomINV.bat ustawia go na katalog projektu)."""
    return Path.cwd()


def default_backup_filename(*, include_app: bool = False) -> str:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    kind = "app" if include_app else "dane"
    return f"INV_backup_{kind}_{stamp}.zip"


def suggested_cloud_folders() -> list[Path]:
    """Znane lokalne foldery synchronizacji chmury (jeśli istnieją)."""
    home = Path.home()
    candidates = [
        home / "OneDrive",
        home / "OneDrive - Personal",
        home / "Google Drive",
        home / "GoogleDrive",
        home / "Dropbox",
        home / "iCloudDrive",
    ]
    # OneDrive Business / wariant z nazwą firmy
    for p in home.glob("OneDrive*"):
        if p.is_dir() and p not in candidates:
            candidates.append(p)
    return [p for p in candidates if p.is_dir()]


def export_backup(dest_zip: Path, options: ExportOptions | None = None) -> ExportResult:
    opts = options or ExportOptions()
    data_root = get_data_root()
    project_root = get_project_root()
    dest_zip = Path(dest_zip)
    dest_zip.parent.mkdir(parents=True, exist_ok=True)

    files: list[str] = []
    warnings: list[str] = []

    with tempfile.TemporaryDirectory(prefix="inv_backup_") as tmp:
        staging = Path(tmp)
        payload = staging / "payload"
        payload.mkdir()

        db_names = DATA_DB_NAMES if opts.include_both_databases else (_active_db_name(),)
        for name in db_names:
            src = data_root / name
            if not src.is_file():
                warnings.append(f"Pominięto brakującą bazę: {name}")
                continue
            dest = payload / name
            try:
                _safe_copy_sqlite(src, dest)
                files.append(name)
            except Exception as exc:  # noqa: BLE001 — zbieramy ostrzeżenia do UI
                warnings.append(f"Nie udało się skopiować {name}: {exc}")

        if opts.include_settings:
            settings = data_root / SETTINGS_NAME
            if settings.is_file():
                shutil.copy2(settings, payload / SETTINGS_NAME)
                files.append(SETTINGS_NAME)
            else:
                warnings.append(f"Brak pliku ustawień: {SETTINGS_NAME}")

        if opts.include_reports:
            reports_src = data_root / "reports"
            if reports_src.is_dir():
                reports_dst = payload / "reports"
                _copy_tree_filtered(reports_src, reports_dst, files, prefix="reports")
            else:
                warnings.append("Brak katalogu reports/")

        if opts.include_app:
            for name in APP_ROOT_FILES:
                src = project_root / name
                if src.is_file():
                    shutil.copy2(src, payload / name)
                    files.append(name)
            for dirname in APP_DIRS:
                src = project_root / dirname
                if src.is_dir():
                    _copy_tree_filtered(src, payload / dirname, files, prefix=dirname)

        manifest = {
            "format_version": BACKUP_FORMAT_VERSION,
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "kind": "app" if opts.include_app else "data",
            "include_settings": opts.include_settings,
            "include_reports": opts.include_reports,
            "include_app": opts.include_app,
            "files": sorted(files),
            "project_root_hint": str(project_root),
        }
        (staging / MANIFEST_NAME).write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        if dest_zip.exists():
            dest_zip.unlink()
        with zipfile.ZipFile(dest_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.write(staging / MANIFEST_NAME, arcname=MANIFEST_NAME)
            for path in sorted(payload.rglob("*")):
                if path.is_file():
                    zf.write(path, arcname=str(path.relative_to(staging)).replace("\\", "/"))

    return ExportResult(path=dest_zip, files=files, warnings=warnings)


def read_backup_manifest(zip_path: Path) -> dict:
    with zipfile.ZipFile(zip_path, "r") as zf:
        if MANIFEST_NAME not in zf.namelist():
            return {"format_version": 0, "files": [], "kind": "unknown"}
        return json.loads(zf.read(MANIFEST_NAME).decode("utf-8"))


def import_backup(
    zip_path: Path,
    *,
    restore_settings: bool = True,
    restore_reports: bool = True,
    restore_app: bool = False,
) -> ImportResult:
    """Przywraca dane (i opcjonalnie kod) z ZIP do katalogu projektu / CWD."""
    zip_path = Path(zip_path)
    data_root = get_data_root()
    project_root = get_project_root()
    restored: list[str] = []
    warnings: list[str] = []

    with tempfile.TemporaryDirectory(prefix="inv_restore_") as tmp:
        extract_dir = Path(tmp)
        with zipfile.ZipFile(zip_path, "r") as zf:
            _safe_extract(zf, extract_dir)

        payload = extract_dir / "payload"
        if not payload.is_dir():
            # starsze / ręczne ZIP-y: pliki w korzeniu archiwum
            payload = extract_dir

        for name in DATA_DB_NAMES:
            src = payload / name
            if src.is_file():
                dest = data_root / name
                shutil.copy2(src, dest)
                restored.append(name)

        settings_src = payload / SETTINGS_NAME
        if settings_src.is_file():
            if restore_settings:
                shutil.copy2(settings_src, data_root / SETTINGS_NAME)
                restored.append(SETTINGS_NAME)
            else:
                warnings.append("Pominięto ustawienia (tokeny) na życzenie użytkownika.")

        reports_src = payload / "reports"
        if reports_src.is_dir() and restore_reports:
            dest = data_root / "reports"
            dest.mkdir(parents=True, exist_ok=True)
            for f in reports_src.rglob("*"):
                if f.is_file():
                    rel = f.relative_to(reports_src)
                    out = dest / rel
                    out.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(f, out)
                    restored.append(f"reports/{rel.as_posix()}")

        if restore_app:
            for name in APP_ROOT_FILES:
                src = payload / name
                if src.is_file():
                    shutil.copy2(src, project_root / name)
                    restored.append(name)
            for dirname in APP_DIRS:
                src = payload / dirname
                if src.is_dir():
                    dest = project_root / dirname
                    _copy_tree_overwrite(src, dest)
                    restored.append(f"{dirname}/")
        elif any((payload / d).is_dir() for d in APP_DIRS):
            warnings.append(
                "Archiwum zawiera kod aplikacji — pominięto "
                "(włącz opcję przywracania aplikacji, jeśli chcesz)."
            )

    if not restored:
        warnings.append("W archiwum nie znaleziono rozpoznanych plików INV.")
    return ImportResult(restored=restored, warnings=warnings)


def _active_db_name() -> str:
    from .app_env import get_database_path

    return get_database_path().name


def _safe_copy_sqlite(src: Path, dest: Path) -> None:
    """Spójna kopia SQLite (nawet gdy baza jest otwarta)."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        dest.unlink()
    src_uri = src.resolve().as_uri() + "?mode=ro"
    src_conn = sqlite3.connect(src_uri, uri=True)
    try:
        dst_conn = sqlite3.connect(dest)
        try:
            src_conn.backup(dst_conn)
            dst_conn.commit()
        finally:
            dst_conn.close()
    finally:
        src_conn.close()


def _copy_tree_filtered(
    src: Path,
    dest: Path,
    files: list[str],
    *,
    prefix: str,
) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    for path in src.rglob("*"):
        if any(part in SKIP_DIR_NAMES for part in path.parts):
            continue
        if path.is_dir():
            continue
        if path.suffix in {".pyc", ".pyo"}:
            continue
        rel = path.relative_to(src)
        out = dest / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, out)
        files.append(f"{prefix}/{rel.as_posix()}")


def _copy_tree_overwrite(src: Path, dest: Path) -> None:
    for path in src.rglob("*"):
        if any(part in SKIP_DIR_NAMES for part in path.parts):
            continue
        if path.is_dir():
            continue
        rel = path.relative_to(src)
        out = dest / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, out)


def _safe_extract(zf: zipfile.ZipFile, dest: Path) -> None:
    """Extract bez path traversal (Zip Slip)."""
    dest = dest.resolve()
    for info in zf.infolist():
        name = info.filename.replace("\\", "/")
        if not name or name.endswith("/"):
            continue
        target = (dest / name).resolve()
        try:
            target.relative_to(dest)
        except ValueError as exc:
            raise ValueError(f"Niebezpieczna ścieżka w ZIP: {info.filename}") from exc
        target.parent.mkdir(parents=True, exist_ok=True)
        with zf.open(info) as src, open(target, "wb") as out:
            shutil.copyfileobj(src, out)


def list_backup_member_summary(zip_path: Path) -> str:
    try:
        m = read_backup_manifest(zip_path)
    except Exception as exc:  # noqa: BLE001
        return f"(nie można odczytać manifestu: {exc})"
    kind = m.get("kind", "?")
    created = m.get("created_at", "?")
    n = len(m.get("files") or [])
    return f"Rodzaj: {kind}, utworzono: {created}, plików: {n}"
