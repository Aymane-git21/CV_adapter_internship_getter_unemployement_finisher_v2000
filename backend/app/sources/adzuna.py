"""Adzuna France search API adapter (backfill source). INSEE codes mean
nothing to Adzuna, so location falls back to the city name: Toulouse's
code maps to the literal string until saved searches carry a city label."""
import httpx

from ..schemas import JobPostingIn, SavedSearchParams
from . import SourceError

SEARCH_URL = "https://api.adzuna.com/v1/api/jobs/fr/search/1"

_INSEE_TO_CITY = {"31555": "Toulouse"}


class AdzunaSource:
    name = "adzuna"

    def __init__(self, app_id: str, app_key: str):
        self._id = app_id
        self._key = app_key

    async def fetch(
        self, params: SavedSearchParams, client: httpx.AsyncClient
    ) -> list[JobPostingIn]:
        if not self._id or not self._key:
            raise SourceError("Adzuna credentials are not configured (ADZUNA_APP_ID/KEY).")
        query = {
            "app_id": self._id,
            "app_key": self._key,
            "what": params.keywords,
            "where": _INSEE_TO_CITY.get(params.insee, params.insee),
            "distance": str(params.radius_km),
            "results_per_page": "50",
            "content-type": "application/json",
        }
        resp = await client.get(SEARCH_URL, params=query)
        if resp.status_code != 200:
            raise SourceError(f"Adzuna search failed ({resp.status_code})")
        out: list[JobPostingIn] = []
        try:
            data = resp.json()
        except ValueError as exc:
            raise SourceError("Adzuna returned an unreadable response.") from exc
        for item in data.get("results", []):
            out.append(
                JobPostingIn(
                    source=self.name,
                    external_id=str(item.get("id", "")),
                    title=item.get("title", ""),
                    company=(item.get("company") or {}).get("display_name", ""),
                    location=(item.get("location") or {}).get("display_name", ""),
                    contract_type=item.get("contract_type", ""),
                    description=item.get("description", ""),
                    apply_email=None,  # Adzuna never exposes application emails
                    apply_url=item.get("redirect_url") or None,
                    posted_at=item.get("created", ""),
                    raw=item,
                )
            )
        return out
