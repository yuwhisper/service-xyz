#!/usr/bin/env python3
"""Apply Service XYZ nginx snippet to /etc/nginx/sites-available/ruoyi on server."""
import re
import sys
from pathlib import Path

import paramiko

HOST = "121.43.75.44"
USER = "root"
PASSWORD = __import__("os").environ.get("SERVICE_ZYX_SSH_PASSWORD", "18905795607@A")
RUOYI = "/etc/nginx/sites-available/ruoyi"
SNIPPET = (Path(__file__).resolve().parent.parent / "deploy" / "nginx-domain-service-zyx.conf").read_text(
    encoding="utf-8"
)
# strip comment-only first line for insertion
lines = SNIPPET.splitlines()
if lines and lines[0].startswith("#"):
    body_lines = lines[1:]
else:
    body_lines = lines
NEW_BLOCK = "\n".join(body_lines).strip() + "\n"


def main():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PASSWORD, timeout=30)

    sftp = client.open_sftp()
    with sftp.file(RUOYI, "r") as f:
        content = f.read().decode("utf-8")

    pattern = re.compile(
        r"\n\s*# Service XYZ API.*?\n\s*location = /service/zyx \{[^}]+\}\n",
        re.DOTALL,
    )
    if not pattern.search(content):
        print("ERROR: could not find Service XYZ block in ruoyi config")
        return 1

    updated = pattern.sub("\n" + NEW_BLOCK, content, count=1)
    if updated == content:
        print("No change needed")
        return 0

    backup = RUOYI + ".bak-service-zyx"
    client.exec_command(f"cp {RUOYI} {backup}")
    with sftp.file(RUOYI, "w") as f:
        f.write(updated)

    for cmd in ("nginx -t", "systemctl reload nginx"):
        print(">>>", cmd)
        _, stdout, stderr = client.exec_command(cmd)
        out = stdout.read().decode()
        err = stderr.read().decode()
        code = stdout.channel.recv_exit_status()
        if out.strip():
            print(out.strip())
        if err.strip():
            print(err.strip())
        if code != 0:
            print("FAILED, restoring backup")
            client.exec_command(f"cp {backup} {RUOYI}")
            return 1

    print("Nginx updated: ozon proxy_read_timeout=1800s")
    client.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
