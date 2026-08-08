"""France Travail (ex-Pôle emploi) Offres d'emploi v2 adapter.

Auth: OAuth2 client-credentials against the francetravail.io partner realm.
The token is cached on the instance and refreshed when expired. Endpoint
constants are the documented values; confirm at kickoff (spec open item)."""
import time

import httpx

from ..schemas import JobPostingIn, SavedSearchParams
from . import SourceError

TOKEN_URL = "https://entreprise.francetravail.fr/connexion/oauth2/access_token"
SEARCH_URL = "https://api.francetravail.io/partenaire/offresdemploi/v2/offres/search"
SCOPE = "api_offresdemploiv2 o2dsoffre"


class FranceTravailSource:
    name = "ft"

    def __init__(self, client_id: str, client_secret: str):
        self._id = client_id
        self._secret = client_secret
        self._token: str | None = None
        self._token_exp: float = 0.0

    async def _ensure_token(self, client: httpx.AsyncClient) -> str:
        if self._token and time.monotonic() < self._token_exp - 60:
            return self._token
        resp = await client.post(
            TOKEN_URL,
            params={"realm": "/partenaire"},
            data={
                "grant_type": "client_credentials",
                "client_id": self._id,
                "client_secret": self._secret,
                "scope": SCOPE,
            },
        )
        if resp.status_code != 200:
            raise SourceError(f"France Travail token request failed ({resp.status_code})")
        body = resp.json()
        self._token = body["access_token"]
        self._token_exp = time.monotonic() + float(body.get("expires_in", 1200))
        return self._token

    async def fetch(
        self, params: SavedSearchParams, client: httpx.AsyncClient
    ) -> list[JobPostingIn]:
        if not self._id or not self._secret:
            raise SourceError("France Travail credentials are not configured (FT_CLIENT_ID/SECRET).")
        token = await self._ensure_token(client)
        query: dict[str, str] = {"motsCles": params.keywords}
        if params.insee:
            query["commune"] = params.insee
            query["distance"] = str(params.radius_km)
        if params.contract_type:
            query["typeContrat"] = params.contract_type
        resp = await client.get(SEARCH_URL, params=query, headers={"Authorization": f"Bearer {token}"})
        if resp.status_code == 429:
            raise SourceError("France Travail rate limit hit; the next poll will retry.")
        if resp.status_code not in (200, 206):  # 206 = partial content, documented for paging
            raise SourceError(f"France Travail search failed ({resp.status_code})")
        out: list[JobPostingIn] = []
        for offer in resp.json().get("resultats", []):
            contact = offer.get("contact") or {}
            out.append(
                JobPostingIn(
                    source=self.name,
                    external_id=str(offer.get("id", "")),
                    title=offer.get("intitule", ""),
                    company=(offer.get("entreprise") or {}).get("nom", ""),
                    location=(offer.get("lieuTravail") or {}).get("libelle", ""),
                    contract_type=offer.get("typeContrat", ""),
                    description=offer.get("description", ""),
                    apply_email=contact.get("courriel") or None,
                    apply_url=(offer.get("origineOffre") or {}).get("urlOrigine") or None,
                    posted_at=offer.get("dateCreation", ""),
                    raw=offer,
                )
            )
        return out
