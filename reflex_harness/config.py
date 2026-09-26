"""Environment loading and frozen constants. Secrets come from the environment only."""
import os

from dotenv import load_dotenv

load_dotenv()

MONGODB_URI = os.environ.get("MONGODB_URI", "")
MONGODB_DB = os.environ.get("MONGODB_DB", "reflex")

REGISTRY = "r1"          # config registry version
PROTOCOL = "p1"          # attempt protocol; checkpoints must match to be retrieved
SNAPSHOT_ID = "mem-v1"   # frozen memory snapshot evaluation retrieves from

VECTOR_INDEX = "ckpt_vec"
TEXT_INDEX = "ckpt_text"
EMBED_MODEL = "voyage-4"

# The config each family is designed around (SPEC §12); logged as `designed_config` per run.
DESIGNED_CONFIG = {"oscillation": "caller", "semantic_repetition": "dependency"}

# Registry r1: the four context configurations (SPEC §7). Seeded into `configs`.
CONFIGS_R1 = [
    {"config_id": "focused", "order": 1,
     "context": {"focal": True, "error": True, "callers": False, "deps": False},
     "workflow": {"diagnostic_first": False}},
    {"config_id": "caller", "order": 2,
     "context": {"focal": True, "error": True, "callers": True, "deps": False},
     "workflow": {"diagnostic_first": False}},
    {"config_id": "dependency", "order": 3,
     "context": {"focal": True, "error": True, "callers": False, "deps": True},
     "workflow": {"diagnostic_first": False}},
    {"config_id": "diagnostic", "order": 4,
     "context": {"focal": True, "error": True, "callers": False, "deps": False},
     "workflow": {"diagnostic_first": True}},
]
