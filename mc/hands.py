"""The hands: Composio tool execution, raw REST, stdlib only.

GitHub for bounty work (fork, branch, PR), Gmail for anything that needs a
human on the other end. The brain proposes actions by name; only actions on
the allowlist execute. A confused model gets a refusal back in its result,
priced into the cycle like everything else.

No SDK on purpose. The whole runtime is stdlib, and Composio's v3 API is one
POST: /api/v3/tools/execute/{TOOL_SLUG} with a user_id and arguments. The
connected account (OAuth, done once by a human at a Connect Link) lives on
Composio's side, keyed by that user_id.
"""

import json
import os
import urllib.error
import urllib.request

COMPOSIO_BASE = os.environ.get("COMPOSIO_BASE_URL",
                               "https://backend.composio.dev/api/v3")
USER_ID = os.environ.get("MC_COMPOSIO_USER_ID", "mc-agent")

# Prefixes the agent may execute. Submitting work and talking to humans,
# nothing destructive: no deletes, no force pushes, no account mutations.
ALLOWED_PREFIXES = (
    "GITHUB_CREATE",
    "GITHUB_GET",
    "GITHUB_LIST",
    "GITHUB_SEARCH",
    "GITHUB_FORK",
    "GITHUB_ADD",
    "GMAIL_CREATE_EMAIL_DRAFT",
    "GMAIL_SEND_EMAIL",
)


class Hands:
    def __init__(self):
        self.api_key = os.environ.get("COMPOSIO_API_KEY")

    @property
    def live(self):
        return bool(self.api_key)

    @staticmethod
    def allowed(action):
        return isinstance(action, str) and action.upper().startswith(ALLOWED_PREFIXES)

    def execute(self, action, params):
        if not self.allowed(action):
            return {"refused": True, "action": action,
                    "note": "action not on the allowlist; submit work or "
                            "send mail, nothing else"}
        if not self.live:
            return {"simulated": True, "action": action, "params": params,
                    "note": "set COMPOSIO_API_KEY for live tool execution"}
        body = json.dumps({"user_id": USER_ID,
                           "arguments": params or {}}).encode()
        req = urllib.request.Request(
            f"{COMPOSIO_BASE}/tools/execute/{action.upper()}",
            data=body,
            headers={"x-api-key": self.api_key,
                     "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read())
        except urllib.error.HTTPError as e:
            detail = self._error_message(e)
            return {"error": f"HTTP {e.code}: {detail}", "action": action}
        except Exception as e:
            return {"error": f"{type(e).__name__}: {e}", "action": action}
        # Composio reports tool-level failure in-band; surface it as an error
        # so the loop never books revenue for a submission that went nowhere.
        if not data.get("successful", True):
            return {"error": str(data.get("error") or "tool reported failure"),
                    "action": action}
        return data

    @staticmethod
    def _error_message(err):
        try:
            payload = json.loads(err.read())
            return (payload.get("error") or {}).get("message") or str(payload)[:200]
        except Exception:
            return "execution failed"
