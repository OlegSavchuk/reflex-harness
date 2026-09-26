"""Seed the four context configurations (SPEC §7) into `configs`. Idempotent upsert.

Usage: python scripts/seed_configs.py [--registry r1]
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from reflex_harness import config  # noqa: E402
from reflex_harness.store import db  # noqa: E402

CONFIGS = config.CONFIGS_R1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--registry", default=config.REGISTRY)
    registry = ap.parse_args().registry
    coll = db()["configs"]
    for c in CONFIGS:
        coll.replace_one({"registry": registry, "config_id": c["config_id"]},
                         {**c, "registry": registry}, upsert=True)
    for c in coll.find({"registry": registry}, {"_id": 0}).sort("order", 1):
        print(f"{c['registry']}  {c['order']}  {c['config_id']:<11} context={c['context']} "
              f"workflow={c['workflow']}")
    n = coll.count_documents({"registry": registry})
    print(f"{n} configs in registry {registry}")
    if n != len(CONFIGS):
        sys.exit(f"expected {len(CONFIGS)}, found {n}")


if __name__ == "__main__":
    main()
