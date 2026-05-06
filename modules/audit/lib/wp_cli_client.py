"""
Shared WP-CLI client for SSH command execution and output parsing.

Reusable across all RSS modules that need WP-CLI access.
Reads SSH credentials from sites/<slug>.conf.

Usage:
    from wp_cli_client import WPCLIClient

    client = WPCLIClient.from_site_config("lrg")
    posts = client.run("post list --post_type=post --format=json")
    client.close()
"""

import csv
import io
import json
import os
import subprocess
import sys
import time


class WPCLIClient:
    """SSH-based WP-CLI client for remote WordPress sites."""

    def __init__(self, ssh_host: str, ssh_user: str, ssh_key_path: str,
                 wp_path: str = "", sleep_between: float = 1.0):
        self.ssh_host = ssh_host
        self.ssh_user = ssh_user
        self.ssh_key_path = os.path.expanduser(ssh_key_path)
        self.wp_path = wp_path
        self.sleep_between = sleep_between
        self._call_count = 0

    @classmethod
    def from_site_config(cls, site_slug: str, sleep_between: float = 1.0) -> "WPCLIClient":
        """Create client from sites/<slug>.conf file."""
        # Search for config relative to common locations
        search_paths = [
            os.path.join(os.path.expanduser("~/randalls-seo-system"), "sites", f"{site_slug}.conf"),
        ]
        # Also check relative to this file
        module_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        root_dir = os.path.dirname(os.path.dirname(module_dir))
        search_paths.append(os.path.join(root_dir, "sites", f"{site_slug}.conf"))

        conf_path = None
        for p in search_paths:
            if os.path.exists(p):
                conf_path = p
                break

        if not conf_path:
            raise FileNotFoundError(f"Site config not found for '{site_slug}'")

        config = {}
        with open(conf_path) as f:
            for line in f:
                line = line.strip()
                if line.startswith("#") or "=" not in line:
                    continue
                key, val = line.split("=", 1)
                config[key.strip()] = val.strip().strip('"')

        return cls(
            ssh_host=config.get("SSH_HOST", ""),
            ssh_user=config.get("SSH_USER", ""),
            ssh_key_path=config.get("SSH_KEY_PATH", ""),
            wp_path=config.get("WP_PATH", ""),
            sleep_between=sleep_between,
        )

    def _ssh_cmd(self) -> list[str]:
        """Build base SSH command."""
        return [
            "ssh",
            "-i", self.ssh_key_path,
            "-o", "IdentitiesOnly=yes",
            "-o", "ConnectTimeout=15",
            "-o", "StrictHostKeyChecking=accept-new",
            f"{self.ssh_user}@{self.ssh_host}",
        ]

    def run(self, wp_command: str, timeout: int = 120) -> str:
        """Execute a WP-CLI command via SSH. Returns stdout."""
        if self._call_count > 0 and self.sleep_between > 0:
            time.sleep(self.sleep_between)
        self._call_count += 1

        full_cmd = f"wp {wp_command}"
        if self.wp_path:
            full_cmd = f"cd {self.wp_path} && {full_cmd}"

        cmd = self._ssh_cmd() + [full_cmd]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)

        if result.returncode != 0:
            raise RuntimeError(f"WP-CLI error (exit {result.returncode}): {result.stderr.strip()}")

        return result.stdout

    def run_json(self, wp_command: str, timeout: int = 120) -> list | dict:
        """Execute WP-CLI command and parse JSON output."""
        if "--format=json" not in wp_command:
            wp_command += " --format=json"
        output = self.run(wp_command, timeout)
        return json.loads(output)

    def run_csv(self, wp_command: str, timeout: int = 120) -> list[dict]:
        """Execute WP-CLI command and parse CSV output."""
        if "--format=csv" not in wp_command:
            wp_command += " --format=csv"
        output = self.run(wp_command, timeout)
        reader = csv.DictReader(io.StringIO(output))
        return list(reader)

    def eval_file(self, php_code: str, timeout: int = 120) -> str:
        """Pipe PHP code to the server and execute via wp eval-file."""
        cmd = self._ssh_cmd()
        full_remote = "cat > /tmp/_rss_audit.php && wp eval-file /tmp/_rss_audit.php && rm -f /tmp/_rss_audit.php"
        if self.wp_path:
            full_remote = f"cd {self.wp_path} && {full_remote}"
        cmd.append(full_remote)

        if self._call_count > 0 and self.sleep_between > 0:
            time.sleep(self.sleep_between)
        self._call_count += 1

        result = subprocess.run(
            cmd, input=php_code, capture_output=True, text=True, timeout=timeout,
        )
        if result.returncode != 0:
            raise RuntimeError(f"eval-file error: {result.stderr.strip()}")
        return result.stdout

    def test_connection(self) -> bool:
        """Test SSH connectivity."""
        try:
            result = self.run("cli version", timeout=15)
            return "WP-CLI" in result
        except Exception:
            return False
