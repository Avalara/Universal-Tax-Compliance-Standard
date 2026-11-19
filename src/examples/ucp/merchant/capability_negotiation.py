#   Copyright 2026 UCP Authors
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.

"""UCP capability normalization, intersection, and extension pruning.

Implements the business/platform intersection and orphaned-extension pruning
described in the UCP specification (capability names, version intersection,
highest mutual version, repeat prune until stable).
"""

from __future__ import annotations

import json
import pathlib
import re
from typing import Any

import checkout_extension_registry

CHECKOUT_ROOT = "dev.ucp.shopping.checkout"
ORDER_ROOT = "dev.ucp.shopping.order"

_PROFILE_PATH = (
  pathlib.Path(__file__).resolve().parent / "routes" / "discovery_profile.json"
)


def profile_uri_from_ucp_agent(ucp_agent: str) -> str | None:
  """Return the profile URI from a UCP-Agent header, if present."""
  match = re.search(r'profile="([^"]+)"', ucp_agent)
  if not match:
    return None
  return match.group(1)


def extract_webhook_url_from_profile(data: dict[str, Any]) -> str | None:
  """Find ``webhook_url`` under ``ucp.capabilities`` (list or keyed object)."""
  ucp = data.get("ucp")
  if not isinstance(ucp, dict):
    return None
  caps = ucp.get("capabilities")
  if caps is None:
    return None
  if isinstance(caps, list):
    for item in caps:
      if not isinstance(item, dict):
        continue
      cfg = item.get("config")
      if isinstance(cfg, dict):
        wu = cfg.get("webhook_url")
        if wu:
          return str(wu)
  elif isinstance(caps, dict):
    for items in caps.values():
      if not isinstance(items, list):
        continue
      for item in items:
        if not isinstance(item, dict):
          continue
        cfg = item.get("config")
        if isinstance(cfg, dict):
          wu = cfg.get("webhook_url")
          if wu:
            return str(wu)
  return None


def normalize_capabilities_blob(
  raw: list[dict[str, Any]] | dict[str, list[dict[str, Any]]] | None,
) -> dict[str, list[dict[str, Any]]]:
  """Normalize ``ucp.capabilities`` to name -> list of capability dicts."""
  if raw is None:
    return {}
  if isinstance(raw, list):
    out: dict[str, list[dict[str, Any]]] = {}
    for item in raw:
      if not isinstance(item, dict):
        continue
      name = item.get("name")
      if not name:
        continue
      entry = dict(item)
      out.setdefault(str(name), []).append(entry)
    return out
  if isinstance(raw, dict):
    out = {}
    for name, items in raw.items():
      if not isinstance(items, list):
        continue
      cleaned: list[dict[str, Any]] = []
      for item in items:
        if isinstance(item, dict):
          row = dict(item)
          row.setdefault("name", name)
          cleaned.append(row)
      if cleaned:
        out[str(name)] = cleaned
    return out
  return {}


def _capability_defs_by_name(
  merged: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
  return {c["name"]: c for c in merged if "name" in c}


def intersect_capability_versions(
  business: dict[str, list[dict[str, Any]]],
  platform: dict[str, list[dict[str, Any]]],
) -> dict[str, str]:
  """Return capability name -> chosen version (highest mutual YYYY-MM-DD)."""
  selected: dict[str, str] = {}
  for name, b_items in business.items():
    if name not in platform:
      continue
    b_vers = {str(x["version"]) for x in b_items if "version" in x}
    p_vers = {str(x["version"]) for x in platform[name] if "version" in x}
    common = b_vers & p_vers
    if not common:
      continue
    selected[name] = max(common)
  return selected


def prune_orphaned_extensions(
  selected: dict[str, str],
  defs_by_name: dict[str, dict[str, Any]],
) -> None:
  """Drop extensions with no parent in ``selected``; repeat until stable."""
  while True:
    removed_any = False
    for name in list(selected):
      cap = defs_by_name.get(name, {})
      ext = cap.get("extends")
      if ext is None:
        continue
      parents = [ext] if isinstance(ext, str) else list(ext)
      if not any(p in selected for p in parents):
        del selected[name]
        removed_any = True
    if not removed_any:
      break


def negotiate_capabilities(
  merged_business_capabilities: list[dict[str, Any]],
  platform_profile: dict[str, Any] | None,
) -> dict[str, str]:
  """Intersect capabilities with platform and prune orphaned extensions."""
  defs_by_name = _capability_defs_by_name(merged_business_capabilities)

  def _full_business_versions() -> dict[str, str]:
    return {
      name: str(defs_by_name[name]["version"])
      for name in defs_by_name
      if "version" in defs_by_name[name]
    }

  if platform_profile is None:
    return _full_business_versions()
  ucp = platform_profile.get("ucp")
  if not isinstance(ucp, dict):
    return _full_business_versions()
  platform_blob = normalize_capabilities_blob(ucp.get("capabilities"))
  if not platform_blob:
    return _full_business_versions()
  business_blob = normalize_capabilities_blob(
    [dict(x) for x in merged_business_capabilities]
  )
  selected = intersect_capability_versions(business_blob, platform_blob)
  prune_orphaned_extensions(selected, defs_by_name)
  return selected


def load_template_capability_list() -> list[dict[str, Any]]:
  """Load capabilities from ``discovery_profile.json``.

  The current profile stores ``ucp.capabilities`` as a name-keyed object.
  Older documents used a list of objects that each carry ``name``. Both
  shapes are returned as a flat list of declarations that include ``name``.
  """
  with _PROFILE_PATH.open(encoding="utf-8") as f:
    data = json.load(f)
  raw = data.get("ucp", {}).get("capabilities", [])
  if isinstance(raw, dict):
    out: list[dict[str, Any]] = []
    for name, items in raw.items():
      if not isinstance(items, list):
        continue
      for item in items:
        if isinstance(item, dict):
          row = dict(item)
          row["name"] = str(name)
          out.append(row)
    return out
  if isinstance(raw, list):
    return [dict(x) for x in raw if isinstance(x, dict)]
  return []


def load_merged_business_capabilities() -> list[dict[str, Any]]:
  """Template capabilities merged with :mod:`checkout_extension_registry`."""
  template = load_template_capability_list()
  return checkout_extension_registry.merge_discovery_capabilities_list(template)


def merged_capability_definitions_by_name() -> dict[str, dict[str, Any]]:
  """``name`` -> capability declaration for merged business capabilities."""
  return _capability_defs_by_name(load_merged_business_capabilities())


def filter_for_checkout_response(
  negotiated: dict[str, str],
  defs_by_name: dict[str, dict[str, Any]],
) -> dict[str, str]:
  """Checkout root plus extensions that extend checkout."""
  out: dict[str, str] = {}
  for name, ver in negotiated.items():
    cap = defs_by_name.get(name, {})
    if name == CHECKOUT_ROOT:
      out[name] = ver
      continue
    ext = cap.get("extends")
    if ext is None:
      continue
    parents = [ext] if isinstance(ext, str) else list(ext)
    if CHECKOUT_ROOT in parents:
      out[name] = ver
  return out


def filter_for_order_response(
  negotiated: dict[str, str],
  defs_by_name: dict[str, dict[str, Any]],
) -> dict[str, str]:
  """Order root plus extensions that extend order."""
  out: dict[str, str] = {}
  for name, ver in negotiated.items():
    cap = defs_by_name.get(name, {})
    if name == ORDER_ROOT:
      out[name] = ver
      continue
    ext = cap.get("extends")
    if ext is None:
      continue
    parents = [ext] if isinstance(ext, str) else list(ext)
    if ORDER_ROOT in parents:
      out[name] = ver
  return out
