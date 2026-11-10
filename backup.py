"""Create a consistent SQLite snapshot and upload referenced files over SFTP."""
import json
import os
import sqlite3
import tarfile
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import paramiko

DATA = Path(os.getenv("DATA_DIR", "/data"))

def backup():
    host = os.environ["SFTP_HOST"]
    user = os.environ["SFTP_USER"]
    password = os.environ["SFTP_PASSWORD"]
    remote_dir = os.environ.get("SFTP_DIRECTORY", ".")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    with tempfile.TemporaryDirectory(prefix="site-backup-") as tmp:
        root = Path(tmp); snapshot = root / "app.db"
        with sqlite3.connect(f"file:{DATA / 'app.db'}?mode=ro", uri=True) as source, sqlite3.connect(snapshot) as target:
            source.backup(target)
        with sqlite3.connect(snapshot) as db:
            attachment_ids = [row[0] for row in db.execute("SELECT id FROM attachments")]
        archive = root / f"site-delivery-{stamp}.tar.gz"
        with tarfile.open(archive, "w:gz") as tar:
            tar.add(snapshot, arcname="database/app.db")
            for file_id in attachment_ids:
                file = DATA / "uploads" / file_id
                if not file.is_file(): raise RuntimeError(f"Missing attachment: {file_id}")
                tar.add(file, arcname=f"uploads/{file_id}")
        client = paramiko.SSHClient()
        client.load_host_keys(os.environ["SFTP_KNOWN_HOSTS"])
        client.set_missing_host_key_policy(paramiko.RejectPolicy())
        client.connect(host, port=int(os.environ.get("SFTP_PORT", "22")), username=user, password=password, timeout=20)
        try:
            with client.open_sftp() as sftp:
                destination = remote_dir.rstrip("/") + "/" + archive.name
                temporary = destination + ".uploading"
                sftp.put(str(archive), temporary)
                if sftp.stat(temporary).st_size != archive.stat().st_size: raise RuntimeError("Uploaded size mismatch")
                sftp.rename(temporary, destination)
        finally:
            client.close()
        print(json.dumps({"status":"ok", "file":archive.name, "bytes":archive.stat().st_size}), flush=True)

if __name__ == "__main__":
    backup()
