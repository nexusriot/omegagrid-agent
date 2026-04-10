from __future__ import annotations

import uuid
from typing import Any, Dict

from skills.base import BaseSkill


_NAMESPACES = {
    "dns": uuid.NAMESPACE_DNS,
    "url": uuid.NAMESPACE_URL,
    "oid": uuid.NAMESPACE_OID,
    "x500": uuid.NAMESPACE_X500,
}


class UuidGenSkill(BaseSkill):
    """Generate UUIDs (v1, v3, v4, v5)."""

    name = "uuid_gen"
    description = (
        "Generate one or more UUIDs. Versions: 1 (time-based), 3 (md5 namespace+name), "
        "4 (random, default), 5 (sha1 namespace+name). For v3/v5 you must supply 'name' "
        "and optionally 'namespace' (dns, url, oid, x500 — default dns)."
    )
    parameters = {
        "version": {
            "type": "integer",
            "description": "UUID version: 1, 3, 4, or 5 (default 4)",
            "required": False,
        },
        "count": {
            "type": "integer",
            "description": "How many UUIDs to generate (1-50, default 1)",
            "required": False,
        },
        "namespace": {
            "type": "string",
            "description": "Namespace for v3/v5: dns, url, oid, x500 (default dns)",
            "required": False,
        },
        "name": {
            "type": "string",
            "description": "Name string for v3/v5 (required for those versions)",
            "required": False,
        },
    }

    def execute(
        self,
        version: int = 4,
        count: int = 1,
        namespace: str = "dns",
        name: str = "",
        **kwargs,
    ) -> Dict[str, Any]:
        try:
            version = int(version)
        except (TypeError, ValueError):
            return {"error": "version must be an integer"}
        if version not in (1, 3, 4, 5):
            return {"error": f"unsupported UUID version: {version}"}

        try:
            count = int(count)
        except (TypeError, ValueError):
            return {"error": "count must be an integer"}
        if count < 1 or count > 50:
            return {"error": "count must be between 1 and 50"}

        ns_key = (namespace or "dns").strip().lower()
        if version in (3, 5):
            if not name:
                return {"error": f"'name' is required for UUID v{version}"}
            if ns_key not in _NAMESPACES:
                return {"error": f"unknown namespace: {namespace}. Use one of {sorted(_NAMESPACES)}"}

        uuids = []
        for _ in range(count):
            if version == 1:
                uuids.append(str(uuid.uuid1()))
            elif version == 3:
                uuids.append(str(uuid.uuid3(_NAMESPACES[ns_key], name)))
            elif version == 4:
                uuids.append(str(uuid.uuid4()))
            elif version == 5:
                uuids.append(str(uuid.uuid5(_NAMESPACES[ns_key], name)))

        result: Dict[str, Any] = {
            "version": version,
            "count": count,
            "uuids": uuids,
        }
        if version in (3, 5):
            result["namespace"] = ns_key
            result["name"] = name
        return result
