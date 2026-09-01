"""Olist source-quality entry point."""

from pathlib import Path

from common.validation.runner import ProfilingResult
from common.validation.runner import profile_raw_sources as _profile_raw_sources
from olist.paths import WAREHOUSE_PATH, project_root
from olist.validation.catalog import CHECKS
from olist.validation.staging_types import CANDIDATE_STAGING_TYPES

PROFILING_REPORT_PATH = project_root() / "reports" / "source-profile.md"

__all__ = ["ProfilingResult", "profile_raw_sources"]


def profile_raw_sources(
    warehouse_path: Path = WAREHOUSE_PATH,
    report_path: Path = PROFILING_REPORT_PATH,
) -> ProfilingResult:
    return _profile_raw_sources(
        warehouse_path,
        report_path,
        checks=CHECKS,
        staging_types=CANDIDATE_STAGING_TYPES,
        report_title="Olist raw-source profile",
    )
