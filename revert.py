"""Revert the LeetCode Problem card template to the v2 backup.

Usage: Close Anki, then run: python3 revert.py
"""

import sqlite3
import os

BACKUP = os.path.join(os.path.dirname(__file__), "template-backup-v2.blob")
DB = os.path.expanduser(
    "~/Library/Application Support/Anki2/User 1/collection.anki2"
)

with open(BACKUP, "rb") as f:
    blob = f.read()

db = sqlite3.connect(DB)
db.execute(
    "UPDATE templates SET config = ? WHERE ntid = 1774621368457 AND ord = 0",
    (blob,),
)
db.commit()
db.close()
print("Reverted to v2 template. Open Anki to verify.")
