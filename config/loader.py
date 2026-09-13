import json
import os
import re
from pathlib import Path

def get_default_config_path() -> Path:
    return Path.home() / ".mybot" / "config.json"

def load_json_config(path: Path | None = None) -> dict:
    if path is None:
        path = get_default_config_path()
    if not path.exists():
        return {}
    with open(path, "r", encoding = "utf-8") as f:
        return json.load(f)

def resolve_env_vars(data: dict) -> dict:
    pattern = re.compile(r"\$\{(\w+)(?:\:-([^}]*))?\}")
    def _resolve(value):
        if isinstance(value, str):
            def _replacer(match):
                var_name = match.group(1)
                default = match.group(2)
                return os.environ.get(var_name, default or "")
            # FIX: 原来缺这行——定义了 _replacer 却没调用，导致字符串的 ${VAR} 永远不被替换
            return pattern.sub(_replacer, value)
        elif isinstance(value, dict):
            return {k: _resolve(v) for k, v in value.items()}
        elif isinstance(value, list):
            return [_resolve(item) for item in value]
        return value
    return _resolve(data)

def load_config(path: Path | None = None) -> "Config": #type: ignore
    from mybot.config.schema import Config
    raw = load_json_config(path)
    resolved = resolve_env_vars(raw)
    return Config(**resolved)