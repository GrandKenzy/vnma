"""HTTP client for querying the official PyPI JSON API."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from vnma.core.models import WheelRelease, normalize_package_name


class PyPIClient:
    """Queries PyPI endpoints to inspect package versions and release files."""

    BASE_URL = "https://pypi.org/pypi"

    def __init__(self, user_agent: str = "vnma/0.2.1") -> None:
        """Initialize client with customized user-agent headers."""
        self._user_agent = user_agent

    def fetch_package_data(self, package_name: str, version: str | None = None) -> dict[str, Any]:
        """Retrieve raw package metadata from PyPI JSON endpoint."""
        norm_name = normalize_package_name(package_name)
        endpoint = (
            f"{self.BASE_URL}/{norm_name}/{version}/json"
            if version
            else f"{self.BASE_URL}/{norm_name}/json"
        )
        request = urllib.request.Request(
            endpoint,
            headers={"User-Agent": self._user_agent, "Accept": "application/json"},
        )
        try:
            with urllib.request.urlopen(request) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as err:
            if err.code == 404:
                raise ValueError(f"Package '{package_name}' not found on PyPI") from err
            raise RuntimeError(f"PyPI request failed with HTTP {err.code}: {err.reason}") from err
        except urllib.error.URLError as err:
            raise RuntimeError(f"Network error contacting PyPI: {err.reason}") from err

    def fetch_wheel_releases(
        self, package_name: str, requested_version: str | None = None
    ) -> list[WheelRelease]:
        """Extract and structure all wheel release distributions available for package."""
        data = self.fetch_package_data(package_name, requested_version)
        info = data.get("info", {})
        requires_dist = tuple(info.get("requires_dist") or ())

        releases_map = data.get("releases", {})
        if requested_version and not releases_map and "urls" in data:
            releases_map = {requested_version: data.get("urls", [])}

        results: list[WheelRelease] = []

        target_versions = (
            [requested_version]
            if requested_version and requested_version in releases_map
            else sorted(releases_map.keys())
        )

        for ver in target_versions:
            file_entries = releases_map.get(ver, [])
            for file_info in file_entries:
                if file_info.get("yanked", False):
                    continue

                filename = file_info.get("filename", "")
                packagetype = file_info.get("packagetype", "")
                if packagetype != "bdist_wheel" or not filename.endswith(".whl"):
                    continue

                digests = file_info.get("digests", {})
                sha256 = digests.get("sha256", "")
                url = file_info.get("url", "")
                parts = filename[:-4].split("-")
                py_tag = parts[-3] if len(parts) >= 3 else ""
                abi_tag = parts[-2] if len(parts) >= 2 else ""
                plat_tag = parts[-1] if len(parts) >= 1 else ""

                results.append(
                    WheelRelease(
                        filename=filename,
                        url=url,
                        sha256=sha256,
                        version=ver,
                        python_tag=py_tag,
                        abi_tag=abi_tag,
                        platform_tag=plat_tag,
                        requires_dist=requires_dist,
                    )
                )

        return results
