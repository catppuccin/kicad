#!/usr/bin/env python3
"""Build script for our Catppuccin KiCad theme!"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
import tomllib
from datetime import datetime
from pathlib import Path
from typing import NotRequired, TypedDict, cast
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED

from packaging.version import Version as SemVer


# ============================================================================
# TYPING
# ============================================================================


class VersionEntryBase(TypedDict):
    """Base version fields required for all version entries."""

    version: str
    status: str
    kicad_version: str
    kicad_version_max: NotRequired[str]


class VersionEntry(VersionEntryBase):
    """Version entry with download and installation metadata."""

    platforms: list[str]
    download_url: str
    download_sha256: str
    download_size: int
    install_size: int


class PackageEntry(TypedDict):
    """A package with identifier, name and version history."""

    identifier: str
    name: str
    versions: list[VersionEntry]


class RepositoryPackages(TypedDict):
    """Repository resource metadata with URL, hash, and timestamps."""

    url: str
    sha256: str
    update_timestamp: int
    update_time_utc: str


class Metadata(TypedDict):
    """Container for metadata.json's `versions` list."""

    versions: list[VersionEntryBase]


class Packages(TypedDict):
    """Container for packages.json's `versions` list."""

    packages: list[PackageEntry]


class Repository(TypedDict):
    """Repository metadata with reference to the `packages` entry."""

    packages: RepositoryPackages


# ============================================================================
# HELPERS
# ============================================================================


def _calc_build_hash(p_items: list[str]) -> str:
    """Compute a hash of all source files."""
    l_hash = hashlib.sha256()
    for i_item in sorted(p_items):
        l_path = Path(i_item)
        if l_path.is_file():
            l_hash.update(l_path.read_bytes())
        elif l_path.is_dir():
            for i_file in sorted(l_path.rglob("*")):
                if i_file.is_file():
                    l_hash.update(i_file.read_bytes())
    return l_hash.hexdigest()


def _update_build_hash(p_path: Path, current_hash: str) -> None:
    """Update only the build-hash value, preserving formatting."""
    content = p_path.read_text()
    content = re.sub(
        r'build-hash\s*=\s*"[^"]*"', f'build-hash = "{current_hash}"', content
    )
    p_path.write_text(content)


def _fetch_last_commit_date() -> tuple[int, int, int, int, int, int]:
    """Get the date of the last commit that touched theme files."""
    try:
        l_result = subprocess.run(
            [
                "git",
                "log",
                "-1",
                "--format=%ct",
                "--",
                "colors",
                "resources",
                "LICENSE",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        l_timestamp = int(l_result.stdout.strip())
        l_dt = datetime.fromtimestamp(l_timestamp)
        return (
            l_dt.year,
            l_dt.month,
            l_dt.day,
            l_dt.hour,
            l_dt.minute,
            l_dt.second,
        )
    except (subprocess.CalledProcessError, ValueError):
        return 2024, 1, 1, 0, 0, 0


def _fetch_semver() -> SemVer:
    """Extract version from pyproject.toml."""
    l_proj = Path("pyproject.toml")
    l_content = l_proj.read_text()
    l_match = re.search(r'version\s*=\s*"([^"]+)"', l_content)
    if not l_match:
        raise ValueError("Version not found in pyproject.toml")
    return SemVer(l_match.group(1))


def _calc_checksum(p_file: Path) -> str:
    """Compute SHA256 checksum of a file."""
    l_hash = hashlib.sha256()
    with open(p_file, "rb") as f:
        for i_chunk in iter(lambda: f.read(4096), b""):
            l_hash.update(i_chunk)
    return l_hash.hexdigest()


def _calc_archive_size(p_zip: Path) -> int:
    """Get the total uncompressed size of zip contents."""
    with ZipFile(p_zip, "r") as l_zip:
        return sum(info.file_size for info in l_zip.infolist())


def _build_archive(p_zip: Path) -> None:
    """Create an archive with a deterministic timestamp."""
    l_lcdate = _fetch_last_commit_date()
    with ZipFile(p_zip, "w", ZIP_DEFLATED) as l_zip:
        for i_item in ["colors", "resources", "metadata.json", "LICENSE"]:
            l_path = Path(i_item)
            if l_path.is_file():
                l_info = ZipInfo(l_path.name, date_time=l_lcdate)
                l_zip.writestr(l_info, l_path.read_bytes())
            elif l_path.is_dir():
                for i_file in sorted(l_path.rglob("*")):
                    if i_file.is_file():
                        l_archive = i_file.relative_to(".").as_posix()
                        l_info = ZipInfo(l_archive, date_time=l_lcdate)
                        l_zip.writestr(l_info, i_file.read_bytes())


def _load_json(
    p_files: dict[str, Path],
) -> tuple[Metadata, Packages, Repository]:
    """Load JSON files."""
    l_result: dict[str, dict[str, object]] = {}
    for i_key, i_file in p_files.items():
        if not i_file.exists():
            raise FileNotFoundError(f"Missing: {i_file}")
        l_result[i_key] = json.loads(i_file.read_text())

    return (
        cast(Metadata, cast(object, l_result["metadata"])),
        cast(Packages, cast(object, l_result["packages"])),
        cast(Repository, cast(object, l_result["repo"])),
    )


def _save_json(p_files: dict[Path, Metadata | Packages | Repository]) -> None:
    """Save JSON files."""
    for i_file, i_data in p_files.items():
        i_file.write_text(json.dumps(i_data, indent=2) + "\n")


# ============================================================================
# MAIN
# ============================================================================


def main() -> int:
    version = _fetch_semver()
    zip_filename = Path(f"catppuccin-kicad-v{version}.zip")

    config_path = Path("pyproject.toml")
    config = tomllib.loads(config_path.read_text())

    try:
        tool_config = config["tool"]["catppuccin-kicad"]
    except KeyError:
        print(
            "Error: [tool.catppuccin-kicad] section not found in pyproject.toml",
            file=sys.stderr,
        )
        return 1

    source_items = [
        "colors",
        "resources",
        "LICENSE",
        "metadata.json",
        "packages.json",
        "repository.json",
    ]
    current_hash = _calc_build_hash(source_items)

    if tool_config.get("build-hash") == current_hash:
        print(f"v{version} sources unchanged, skipping rebuild")
        return 0

    mdata, pdata, rdata = _load_json(
        {
            "metadata": Path("metadata.json"),
            "packages": Path("packages.json"),
            "repo": Path("repository.json"),
        }
    )

    old_packages_hash = hashlib.sha256(
        Path("packages.json").read_bytes()
    ).hexdigest()
    old_repo_str = Path("repository.json").read_text()

    print("Running whiskers...")
    if (
        subprocess.run(
            ["whiskers", "scripts/kicad.tera"], check=False
        ).returncode
        != 0
    ):
        print("Error: whiskers command failed", file=sys.stderr)
        return 1

    print(f"Creating {zip_filename}...")
    _build_archive(zip_filename)

    if not pdata.get("packages") or not pdata["packages"]:
        print("Error: packages.json has no packages", file=sys.stderr)
        return 1

    l_checksum = _calc_checksum(zip_filename)
    version_str = str(version)
    l_timestamp = datetime.now()

    entry: VersionEntry = {
        "version": version_str,
        "status": "stable",
        "kicad_version": "7.0",
        "platforms": ["windows", "macos", "linux"],
        "download_url": f"https://github.com/catppuccin/kicad/releases/download/v{version}/{zip_filename.name}",
        "download_sha256": l_checksum,
        "download_size": zip_filename.stat().st_size,
        "install_size": _calc_archive_size(zip_filename),
    }

    mdata["versions"] = [
        v for v in mdata["versions"] if v["version"] != version_str
    ]
    mdata["versions"].insert(
        0,
        cast(
            VersionEntryBase,
            cast(
                object,
                {
                    "version": entry["version"],
                    "status": entry["status"],
                    "kicad_version": entry["kicad_version"],
                },
            ),
        ),
    )

    pdata["packages"][0]["versions"] = [
        v
        for v in pdata["packages"][0]["versions"]
        if v["version"] != version_str
    ]
    pdata["packages"][0]["versions"].insert(0, entry)

    _save_json({Path("packages.json"): pdata})
    new_packages_hash = hashlib.sha256(
        Path("packages.json").read_bytes()
    ).hexdigest()

    try:
        old_repo_data = json.loads(old_repo_str)
        timestamp = old_repo_data["packages"]["update_timestamp"]
        utc_time = old_repo_data["packages"]["update_time_utc"]
    except (KeyError, json.JSONDecodeError):
        timestamp = int(l_timestamp.timestamp())
        utc_time = l_timestamp.strftime("%Y-%m-%d %H:%M:%S")

    if old_packages_hash != new_packages_hash:
        timestamp = int(l_timestamp.timestamp())
        utc_time = l_timestamp.strftime("%Y-%m-%d %H:%M:%S")

    rdata["packages"] = cast(
        RepositoryPackages,
        cast(
            object,
            {
                "url": "https://raw.githubusercontent.com/catppuccin/kicad/main/packages.json",
                "sha256": new_packages_hash,
                "update_timestamp": timestamp,
                "update_time_utc": utc_time,
            },
        ),
    )

    _save_json(
        {
            Path("metadata.json"): mdata,
            Path("repository.json"): rdata,
        }
    )

    _update_build_hash(config_path, current_hash)

    print(f":3 Updated metadata for v{version}")
    print(f"  Archive SHA256: {entry['download_sha256']}")
    print(f"  Archive size: {entry['download_size']:,} bytes")
    print(f"  Unpacked size: {entry['install_size']:,} bytes")

    return 0


if __name__ == "__main__":
    sys.exit(main())
