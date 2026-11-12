"""Disable unrelated standalone MCPs without reading or copying authentication."""

import json
import re
import subprocess
import sys


def scan_overrides(codex_bin):
    # Listing resolves Codex's config layers but does not connect to the servers.
    servers = json.loads(subprocess.check_output(
        [codex_bin, 'mcp', 'list', '--json', '--disable', 'plugins'],
        text=True, timeout=20))
    overrides = []
    for server in servers:
        name = server['name']
        # CLI override paths split on dots and treat quotes as literal key characters.
        if not re.fullmatch(r'[A-Za-z0-9_-]+', name):
            raise ValueError('MCP name cannot be safely used in a CLI override')
        if name not in ('node_repl', 'playwright'):
            overrides.append(f'mcp_servers.{name}.enabled=false')
    return overrides


if __name__ == '__main__':
    for override in scan_overrides(sys.argv[1]):
        print(override)
