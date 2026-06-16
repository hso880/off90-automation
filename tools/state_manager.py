import json
import os
import subprocess
from pathlib import Path

STATE_PATH = Path("pending/state.json")
OFFSET_PATH = Path("pending/last_update_id.txt")


def load():
    if not STATE_PATH.exists():
        return {"status": "idle"}
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"status": "idle"}


def save(state: dict):
    STATE_PATH.parent.mkdir(exist_ok=True)
    STATE_PATH.write_text(
        json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    _git_commit(f"state: {state.get('status', 'update')}")


def clear():
    save({"status": "idle"})


def load_offset():
    if OFFSET_PATH.exists():
        try:
            return int(OFFSET_PATH.read_text().strip())
        except Exception:
            pass
    return None


def save_offset(update_id):
    OFFSET_PATH.parent.mkdir(exist_ok=True)
    OFFSET_PATH.write_text(str(update_id + 1))
    _git_commit("state: update offset")


def _git_commit(message):
    try:
        subprocess.run(["git", "config", "user.email", "actions@github.com"], check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "GitHub Actions"], check=True, capture_output=True)
        subprocess.run(["git", "add", "pending/"], check=True, capture_output=True)
        diff = subprocess.run(["git", "diff", "--cached", "--quiet"], capture_output=True)
        if diff.returncode != 0:
            subprocess.run(["git", "commit", "-m", message], check=True, capture_output=True)
            subprocess.run(["git", "push"], check=True, capture_output=True)
    except subprocess.CalledProcessError as e:
        print(f"[state] git commit 실패: {e}")


def trigger_workflow(workflow_file, inputs=None):
    """같은 레포 workflow_dispatch 트리거"""
    import requests as req
    token = os.environ.get("GITHUB_TOKEN", "")
    repo = os.environ.get("GITHUB_REPOSITORY", "hso880/off90-automation")
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}
    body = {"ref": "main"}
    if inputs:
        body["inputs"] = inputs
    r = req.post(
        f"https://api.github.com/repos/{repo}/actions/workflows/{workflow_file}/dispatches",
        headers=headers, json=body,
    )
    print(f"[workflow] {workflow_file} 트리거: {r.status_code}")
