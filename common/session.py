import tomllib
from pathlib import Path

from cryptography.hazmat.primitives.serialization import load_pem_private_key
from snowflake.snowpark import Session


def get_session(connection_name: str = "analytics") -> Session:
    toml_path = Path.home() / ".snowflake" / "connections.toml"
    with open(toml_path, "rb") as f:
        conns = tomllib.load(f)

    cfg = conns[connection_name]
    key_path = cfg.get("private_key_path") or cfg.get("private_key_file")
    with open(key_path, "rb") as f:
        private_key = load_pem_private_key(f.read(), password=None)

    return Session.builder.configs({
        "account": cfg["account"],
        "user": cfg["user"],
        "private_key": private_key,
        "role": cfg.get("role"),
        "warehouse": cfg.get("warehouse"),
        "database": cfg.get("database"),
        "schema": cfg.get("schema"),
    }).create()
