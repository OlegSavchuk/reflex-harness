"""Gate 0: confirm the Atlas sandbox is reachable and report what it supports."""
import os
import sys

from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.errors import PyMongoError

load_dotenv()
uri = os.environ.get("MONGODB_URI", "")
if not uri or "<db_password>" in uri:
    sys.exit("MONGODB_URI missing or still has <db_password> in .env")

try:
    client = MongoClient(uri, serverSelectionTimeoutMS=8000)
    client.admin.command("ping")
    info = client.server_info()
except PyMongoError as e:
    msg = str(e)
    hint = ""
    if "bad auth" in msg or "Authentication failed" in msg:
        hint = "-> wrong password, or it needs URL-encoding."
    elif "timed out" in msg.lower() or "ServerSelectionTimeout" in type(e).__name__:
        hint = "-> add your current IP in Atlas: Security > Network Access."
    sys.exit(f"Connection failed: {type(e).__name__}: {msg[:200]}\n{hint}")

version = info["version"]
major, minor = (int(x) for x in version.split(".")[:2])
print(f"Connected. MongoDB {version}")
print(f"  $rankFusion (8.0+): {'yes' if (major, minor) >= (8, 0) else 'NO'}")
print(f"  $scoreFusion (8.2+): {'yes' if (major, minor) >= (8, 2) else 'no'}")
db = client[os.environ.get("MONGODB_DB", "reflex")]
print(f"  database '{db.name}' collections: {db.list_collection_names() or 'none yet'}")
