"""Minimal Cloudflare DNS client for Fitness external profile access.

This module deliberately owns only Cloudflare's generic DNS API contract. Profile
access policy, hostname ownership and Home Assistant routing live in
``access_control`` so Cloudflare details do not leak into dashboard/profile code.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

from aiohttp import ClientError
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

_API_BASE = "https://api.cloudflare.com/client/v4"
_REQUEST_TIMEOUT = 15.0


class CloudflareDNSError(RuntimeError):
    """Raised when a bounded Cloudflare DNS operation fails."""

    def __init__(self, code: str, message: str | None = None) -> None:
        super().__init__(message or code)
        self.code = code


@dataclass(slots=True, frozen=True)
class CloudflareRecord:
    """Small DNS record descriptor used by the access controller."""

    record_id: str
    name: str
    record_type: str
    content: str
    proxied: bool
    comment: str


class CloudflareDNSClient:
    """Use the Cloudflare v4 API without introducing another dependency."""

    def __init__(self, hass: HomeAssistant, token: str) -> None:
        self.hass = hass
        self.token = str(token or "").strip()
        if not self.token:
            raise CloudflareDNSError("cloudflare_token_required")

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

    @staticmethod
    def _error_code(payload: Any, status: int) -> str:
        if isinstance(payload, dict):
            errors = payload.get("errors")
            if isinstance(errors, list) and errors:
                first = errors[0]
                if isinstance(first, dict):
                    code = str(first.get("code") or "").strip()
                    if code:
                        return f"cloudflare_api_{code}"
        if status in {401, 403}:
            return "cloudflare_token_rejected"
        if status == 404:
            return "cloudflare_not_found"
        if status == 429:
            return "cloudflare_rate_limited"
        return "cloudflare_api_error"

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        session = async_get_clientsession(self.hass)
        try:
            async with asyncio.timeout(_REQUEST_TIMEOUT):
                async with session.request(
                    method,
                    f"{_API_BASE}{path}",
                    headers=self._headers,
                    params=params,
                    json=json_body,
                ) as response:
                    try:
                        payload = await response.json(content_type=None)
                    except (TypeError, ValueError):
                        payload = None
                    if (
                        response.status < 200
                        or response.status >= 300
                        or not isinstance(payload, dict)
                        or payload.get("success") is not True
                    ):
                        raise CloudflareDNSError(
                            self._error_code(payload, int(response.status))
                        )
                    return payload
        except TimeoutError as err:
            raise CloudflareDNSError("cloudflare_timeout") from err
        except ClientError as err:
            raise CloudflareDNSError("cloudflare_connection_failed") from err

    async def async_zone_id(self, zone_name: str) -> str:
        """Resolve one exact active Cloudflare zone."""
        zone = str(zone_name or "").strip().lower().rstrip(".")
        payload = await self._request(
            "GET", "/zones", params={"name": zone, "per_page": 50}
        )
        result = payload.get("result")
        if not isinstance(result, list):
            raise CloudflareDNSError("cloudflare_zone_not_found")
        exact = [
            row
            for row in result
            if isinstance(row, dict)
            and str(row.get("name") or "").lower().rstrip(".") == zone
        ]
        if len(exact) != 1:
            raise CloudflareDNSError("cloudflare_zone_not_found")
        zone_id = str(exact[0].get("id") or "").strip()
        if not zone_id:
            raise CloudflareDNSError("cloudflare_zone_not_found")
        return zone_id

    async def async_records(self, zone_id: str, name: str) -> list[CloudflareRecord]:
        """Return exact-name DNS records for conflict/ownership checks."""
        fqdn = str(name or "").strip().lower().rstrip(".")
        payload = await self._request(
            "GET",
            f"/zones/{zone_id}/dns_records",
            params={"name": fqdn, "per_page": 100},
        )
        rows = payload.get("result")
        if not isinstance(rows, list):
            return []
        records: list[CloudflareRecord] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            row_name = str(row.get("name") or "").strip().lower().rstrip(".")
            if row_name != fqdn:
                continue
            records.append(
                CloudflareRecord(
                    record_id=str(row.get("id") or ""),
                    name=row_name,
                    record_type=str(row.get("type") or "").upper(),
                    content=str(row.get("content") or ""),
                    proxied=bool(row.get("proxied", False)),
                    comment=str(row.get("comment") or ""),
                )
            )
        return records

    async def async_ensure_a_record(
        self,
        *,
        zone_id: str,
        name: str,
        target: str,
        comment: str,
        record_id: str = "",
    ) -> str:
        """Create/update one DNS-only A record owned by Fitness.

        Existing unrelated records at the same hostname are never adopted or
        overwritten; that makes disabling external access safe because Fitness
        can only delete records it created and can identify.
        """
        fqdn = str(name or "").strip().lower().rstrip(".")
        body = {
            "type": "A",
            "name": fqdn,
            "content": str(target or "").strip(),
            "ttl": 1,
            "proxied": False,
            "comment": str(comment or "")[:100],
        }
        records = await self.async_records(zone_id, fqdn)
        owned = next(
            (
                row
                for row in records
                if (record_id and row.record_id == record_id)
                or (comment and row.comment == comment)
            ),
            None,
        )
        if owned is not None:
            payload = await self._request(
                "PATCH",
                f"/zones/{zone_id}/dns_records/{owned.record_id}",
                json_body=body,
            )
            result = payload.get("result")
            updated_id = str(result.get("id") or "") if isinstance(result, dict) else ""
            return updated_id or owned.record_id

        # A/CNAME coexistence restrictions make *any* unrelated exact-name
        # record a conflict. Never mutate the user's unrelated DNS record.
        if records:
            raise CloudflareDNSError("cloudflare_dns_name_in_use")

        payload = await self._request(
            "POST", f"/zones/{zone_id}/dns_records", json_body=body
        )
        result = payload.get("result")
        created_id = str(result.get("id") or "") if isinstance(result, dict) else ""
        if not created_id:
            raise CloudflareDNSError("cloudflare_record_create_failed")
        return created_id

    async def async_delete_managed_record(
        self,
        *,
        zone_id: str,
        name: str,
        comment: str,
        record_id: str = "",
    ) -> None:
        """Delete only the A record Fitness can prove it owns."""
        records = await self.async_records(zone_id, name)
        targets = [
            row
            for row in records
            if (record_id and row.record_id == record_id)
            or (comment and row.comment == comment)
        ]
        for row in targets:
            await self._request(
                "DELETE", f"/zones/{zone_id}/dns_records/{row.record_id}"
            )
