"""Configuration and owned filesystem locations for the local backend."""

from dataclasses import dataclass
from pathlib import Path
import os


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    max_upload_bytes: int = 2 * 1024 * 1024 * 1024

    @classmethod
    def from_env(cls) -> "Settings":
        raw = os.environ.get("APP_DATA_DIR")
        if not raw:
            raise RuntimeError("APP_DATA_DIR must be set to an absolute directory")
        path = Path(raw).expanduser()
        if not path.is_absolute():
            raise RuntimeError("APP_DATA_DIR must be an absolute directory")
        resolved = path.resolve()
        repository = Path(__file__).resolve().parents[2]
        if resolved == repository or repository in resolved.parents:
            raise RuntimeError("APP_DATA_DIR must be outside the repository")
        try:
            max_bytes = int(os.environ.get("APP_MAX_UPLOAD_BYTES", str(cls.max_upload_bytes)))
        except ValueError as exc:
            raise RuntimeError("APP_MAX_UPLOAD_BYTES must be an integer") from exc
        if max_bytes <= 0:
            raise RuntimeError("APP_MAX_UPLOAD_BYTES must be positive")
        return cls(data_dir=resolved, max_upload_bytes=max_bytes)

    @property
    def database_path(self) -> Path:
        return self.data_dir / "gecko.sqlite3"

    def prepare(self) -> None:
        repository = Path(__file__).resolve().parents[2]
        resolved = self.data_dir.resolve()
        if not self.data_dir.is_absolute() or resolved == repository or repository in resolved.parents:
            raise RuntimeError("APP_DATA_DIR must be absolute and outside the repository")
        self.data_dir.mkdir(parents=True, exist_ok=True)
        (self.data_dir / "staging").mkdir(exist_ok=True)
        (self.data_dir / "videos").mkdir(exist_ok=True)
