from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from bs4 import BeautifulSoup


JsonObject = dict[str, Any]


@dataclass(frozen=True)
class EmbeddedState:
    next_data: JsonObject
    env_scripts: dict[str, JsonObject]


def extract_embedded_state(html: str) -> EmbeddedState:
    soup = BeautifulSoup(html, "html.parser")
    next_data = _load_json_script(soup, "__NEXT_DATA__") or {}
    env_scripts: dict[str, JsonObject] = {}

    for script in soup.find_all("script"):
        script_id = script.get("id")
        if not script_id or not script_id.startswith("env:"):
            continue
        payload = _loads_script_text(script.get_text())
        if payload is not None:
            env_scripts[script_id] = payload

    return EmbeddedState(next_data=next_data, env_scripts=env_scripts)


def _load_json_script(soup: BeautifulSoup, script_id: str) -> JsonObject | None:
    script = soup.find("script", id=script_id)
    if script is None:
        return None
    return _loads_script_text(script.get_text())


def _loads_script_text(raw_text: str) -> JsonObject | None:
    text = raw_text.strip()
    if not text:
        return None
    loaded = json.loads(text)
    if not isinstance(loaded, dict):
        raise ValueError("Expected embedded JSON script to contain an object")
    return loaded
