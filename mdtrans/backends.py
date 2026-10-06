"""LLM backends. Each exposes complete(system, user) -> str. probe() reports what is usable now."""
import json
import os
import shlex
import shutil
import subprocess
import time
import urllib.request
from pathlib import Path


class BackendError(RuntimeError):
    pass


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        k, sep, v = line.strip().partition("=")
        if sep and k.startswith("MDTRANS_"):
            os.environ.setdefault(k.strip(), v.strip().strip("'\""))


def with_retry(fn, tries: int = 3):
    base = float(os.environ.get("MDTRANS_RETRY_SLEEP", "5"))
    for i in range(tries):
        try:
            return fn()
        except BackendError:
            if i == tries - 1:
                raise
            time.sleep(base * 2**i)


class OpenAI:
    def __init__(self, base_url: str, model: str, api_key: str = ""):
        self.name, self.base_url, self.model, self.api_key = "openai", base_url.rstrip("/"), model, api_key

    def complete(self, system: str, user: str) -> str:
        body = json.dumps({"model": self.model, "temperature": 0.2, "messages": [
            {"role": "system", "content": system}, {"role": "user", "content": user}]}).encode()
        req = urllib.request.Request(f"{self.base_url}/chat/completions", data=body, headers={
            "Content-Type": "application/json", **({"Authorization": f"Bearer {self.api_key}"} if self.api_key else {})})
        try:
            with urllib.request.urlopen(req, timeout=900) as r:
                return json.load(r)["choices"][0]["message"]["content"]
        except Exception as e:  # network, HTTP, malformed JSON: all retryable
            raise BackendError(f"openai {self.base_url}: {e}") from e


class ClaudeCLI:
    """`claude -p` locally, or on an SSH host when host is set."""

    def __init__(self, model: str | None = None, host: str | None = None):
        self.name = f"ssh:{host}" if host else "claude-cli"
        self.model, self.host = model, host

    def complete(self, system: str, user: str) -> str:
        cmd = ["claude", "-p", "--tools", "", "--system-prompt", system]
        if self.model:
            cmd += ["--model", self.model]
        if self.host:
            cmd = ["ssh", "-o", "BatchMode=yes", self.host, "bash -lc " + shlex.quote(shlex.join(cmd))]
        try:
            r = subprocess.run(cmd, input=user, capture_output=True, text=True, timeout=900, check=False)
        except subprocess.TimeoutExpired as e:
            raise BackendError(f"{self.name}: timeout") from e
        if r.returncode != 0 or not r.stdout.strip():
            raise BackendError(f"{self.name}: exit {r.returncode}: {(r.stderr or r.stdout)[:300]}")
        return r.stdout


def _ssh_hosts() -> list[tuple[str, str | None]]:
    out = []
    for item in filter(None, (s.strip() for s in os.environ.get("MDTRANS_SSH_HOSTS", "").split(","))):
        host, _, model = item.partition("=")
        out.append((host, model or None))
    return out


def _http_ok(url: str, key: str = "") -> bool:
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {key}"} if key else {})
    try:
        with urllib.request.urlopen(req, timeout=5):
            return True
    except Exception:
        return False


def probe() -> list[dict]:
    """Candidates in recommendation order (remote/dedicated first); 'ok' says if usable now."""
    found = []
    for host, model in _ssh_hosts():
        r = subprocess.run(["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=5", host,
                            "bash -lc 'command -v claude'"], capture_output=True, text=True, check=False)
        found.append({"spec": f"ssh:{host}", "model": model, "ok": r.returncode == 0,
                      "detail": "claude on remote host" if r.returncode == 0 else (r.stderr.strip() or "no claude")[:120]})
    base, key = os.environ.get("MDTRANS_BASE_URL", ""), os.environ.get("MDTRANS_API_KEY", "")
    if base:
        found.append({"spec": f"openai:{base}", "model": os.environ.get("MDTRANS_MODEL"),
                      "ok": _http_ok(base.rstrip("/") + "/models", key), "detail": "OpenAI-compatible endpoint"})
    local = "http://127.0.0.1:8080/v1"
    if base.rstrip("/") != local:
        found.append({"spec": f"openai:{local}", "model": "local", "ok": _http_ok(local + "/models"),
                      "detail": "llama-server"})
    found.append({"spec": "claude-cli", "model": os.environ.get("MDTRANS_MODEL"),
                  "ok": bool(shutil.which("claude")), "detail": "local claude -p"})
    return found


def make(spec: str, model: str | None = None):
    kind, _, target = spec.partition(":")
    if kind == "ssh":
        return ClaudeCLI(model, host=target)
    if kind == "claude-cli":
        return ClaudeCLI(model or os.environ.get("MDTRANS_MODEL"))
    if kind == "openai":
        base = target or os.environ.get("MDTRANS_BASE_URL") or ""
        m = model or os.environ.get("MDTRANS_MODEL") or "local"
        if not base:
            raise BackendError("openai backend needs MDTRANS_BASE_URL or openai:<url>")
        return OpenAI(base, m, os.environ.get("MDTRANS_API_KEY", ""))
    raise BackendError(f"unknown backend {spec!r} (use ssh:<host>, openai[:<url>], claude-cli)")
