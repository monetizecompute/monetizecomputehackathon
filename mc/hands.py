"""The hands: Composio tool execution.

GitHub for bounty work (fork, branch, PR), Gmail for anything that needs a
human on the other end. The brain proposes actions by name; only actions on
the allowlist execute. A confused model gets a refusal back in its result,
priced into the cycle like everything else. Lazy import so demo mode runs
with zero dependencies.
"""

import os

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
        self._toolset = None

    @property
    def live(self):
        return bool(self.api_key)

    @staticmethod
    def allowed(action):
        return isinstance(action, str) and action.upper().startswith(ALLOWED_PREFIXES)

    def _tools(self):
        if self._toolset is None:
            from composio import ComposioToolSet  # requires `pip install composio-core`
            self._toolset = ComposioToolSet(api_key=self.api_key)
        return self._toolset

    def execute(self, action, params):
        if not self.allowed(action):
            return {"refused": True, "action": action,
                    "note": "action not on the allowlist; submit work or "
                            "send mail, nothing else"}
        if not self.live:
            return {"simulated": True, "action": action, "params": params,
                    "note": "set COMPOSIO_API_KEY for live tool execution"}
        try:
            return self._tools().execute_action(action=action, params=params)
        except Exception as e:  # missing package, bad params, API failure
            return {"error": f"{type(e).__name__}: {e}", "action": action}
