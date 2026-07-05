from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Runtime configuration. Everything swappable lives here so adapters can be
    exchanged (NFR-07: onboarding/config-only, no code changes per kantoor)."""

    app_name: str = "BoekVastAI"
    database_url: str = "sqlite:///./var/boekvast.db"
    storage_dir: Path = Path("./var/storage")

    # Which org the (auth-less, pilot-phase) UI is scoped to.
    demo_org_slug: str = "kantoor-van-loon"

    # FR-13/FR-14: default threshold; per-org override lives on Organization.
    default_confidence_threshold: float = 0.85

    # FR-50: pilot heuristic for time-saved reporting, minutes per auto-processed doc.
    minutes_saved_per_auto_doc: float = 3.0

    model_config = {"env_prefix": "BOEKVAST_", "env_file": ".env", "extra": "ignore"}
