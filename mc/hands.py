"""The hands: Composio tool execution.

GitHub for bounty work (fork, branch, PR), Gmail for anything that needs a
human on the other end. Lazy import so demo mode runs with zero dependencies.
"""

import os


class Hands:
    def __init__(self):
        self.api_key = os.environ.get("COMPOSIO_API_KEY")
        self._toolset = None

    @property
    def live(self):
        return bool(self.api_key)

    def _tools(self):
        if self._toolset is None:
            from composio import ComposioToolSet  # requires `pip install composio-core`
            self._toolset = ComposioToolSet(api_key=self.api_key)
        return self._toolset

    def execute(self, action, params):
        if not self.live:
            return {"simulated": True, "action": action, "params": params,
                    "note": "set COMPOSIO_API_KEY for live tool execution"}
        return self._tools().execute_action(action=action, params=params)
