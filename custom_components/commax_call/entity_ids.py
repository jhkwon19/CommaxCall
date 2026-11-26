"""Stable registry identities for Commax Call."""

from hashlib import sha256

from homeassistant.helpers import entity_registry as er
from homeassistant.util import slugify

from .const import CONF_NAME, CONF_SENSORS, CONF_SWITCHES, DOMAIN


def prepare_entity_ids(hass, entry):
    """Keep canonical entities and clean up legacy copies for this entry."""
    registry = er.async_get(hass)
    registered = er.async_entries_for_config_entry(registry, entry.entry_id)
    identities = {}

    for domain, option in (("binary_sensor", CONF_SENSORS), ("switch", CONF_SWITCHES)):
        names = dict.fromkeys(item[CONF_NAME] for item in (entry.options.get(option) or ()))
        claimed = set()
        for name in names:
            object_id = slugify(f"{DOMAIN}_{name}".lower())
            legacy = f"{DOMAIN}.{object_id}"
            digest = sha256(name.encode("utf-8")).hexdigest()[:12]
            scoped = f"{legacy}_{entry.entry_id}_{digest}"
            owner_id = registry.async_get_entity_id(domain, DOMAIN, legacy)
            owner = registry.async_get(owner_id) if owner_id else None
            scoped_id = registry.async_get_entity_id(domain, DOMAIN, scoped)
            if scoped_id or legacy in claimed or (
                owner and (owner.config_entry_id != entry.entry_id or owner.original_name != name)
            ):
                unique_id, keep_id = scoped, scoped_id
            else:
                unique_id, keep_id = legacy, owner_id

            prefix = legacy + "_"
            copies = [
                item for item in registered
                if item.domain == domain and item.platform == DOMAIN
                and item.original_name == name and item.unique_id.startswith(prefix)
                and item.unique_id.removeprefix(prefix).isascii()
                and item.unique_id.removeprefix(prefix).isdecimal()
            ]
            if keep_id is None and copies:
                # 원본이 지워졌다면 가장 오래된 엔터티 ID를 보존합니다.
                original = min(copies, key=lambda item: (item.created_at, item.entity_id))
                registry.async_update_entity(original.entity_id, new_unique_id=unique_id)
                keep_id = original.entity_id

            for duplicate in copies:
                if duplicate.entity_id != keep_id:
                    registry.async_remove(duplicate.entity_id)

            claimed.add(unique_id)
            identities[(domain, name)] = (f"{domain}.{object_id}", unique_id)
    return identities
