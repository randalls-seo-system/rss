"""Shared SSH execution helper for WordPress deployments.

Centralizes SSH command construction, heredoc-safe execution, timeout
handling, output parsing, sleep enforcement, and logging.

Usage:
    from ssh_session import SSHSession
    ssh = SSHSession('lrg')
    result = ssh.run('wp post get 1234 --field=post_status')
    ssh.upload_content('/tmp/content.html', '/tmp/post-1234.html')
    ssh.run('wp eval-file /tmp/push-1234.php')
"""

import configparser
import os
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
LOG_DIR = Path('/tmp')


def load_site_ssh_config(site_slug):
    """Load SSH config from sites/<slug>.conf."""
    conf_path = REPO_ROOT / 'sites' / f'{site_slug}.conf'
    if not conf_path.exists():
        raise FileNotFoundError(f"Site config not found: {conf_path}")

    conf = {}
    with open(conf_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and not line.startswith('[') and '=' in line:
                key, val = line.split('=', 1)
                conf[key.strip()] = val.strip().strip('"')
    return conf


class SSHSession:
    """Manages SSH operations to a WP Engine site."""

    def __init__(self, site_slug, sleep_between=5):
        self.site_slug = site_slug
        self.sleep_between = sleep_between
        self.conf = load_site_ssh_config(site_slug)
        self.ssh_host = f"{self.conf['SSH_USER']}@{self.conf['SSH_HOST']}"
        self.ssh_key = os.path.expanduser(self.conf['SSH_KEY_PATH'])
        self.log_path = LOG_DIR / f'{site_slug}-wp-deploy.log'
        self._last_op_time = 0

    def _ssh_base_cmd(self):
        return ['ssh', '-i', self.ssh_key, '-o', 'IdentitiesOnly=yes', self.ssh_host]

    def _enforce_sleep(self):
        """Ensure minimum sleep between operations."""
        elapsed = time.time() - self._last_op_time
        if elapsed < self.sleep_between and self._last_op_time > 0:
            time.sleep(self.sleep_between - elapsed)
        self._last_op_time = time.time()

    def log(self, message):
        """Append to session log."""
        timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
        line = f"{timestamp} [{self.site_slug}] {message}\n"
        with open(self.log_path, 'a') as f:
            f.write(line)

    def run(self, command, timeout=30, check=True):
        """Execute a remote command via SSH.

        Returns subprocess.CompletedProcess.
        Raises subprocess.CalledProcessError if check=True and exit!=0.
        """
        self._enforce_sleep()
        cmd = self._ssh_base_cmd() + [command]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if check and result.returncode != 0:
            self.log(f"FAIL: {command[:80]} → exit {result.returncode}")
            raise subprocess.CalledProcessError(
                result.returncode, cmd, result.stdout, result.stderr)
        return result

    def upload_content(self, local_path, remote_path):
        """Upload a file to the remote server via stdin pipe.

        WP Engine doesn't support SCP subsystem, so we use:
        ssh host 'cat > /remote/path' < local_file
        """
        self._enforce_sleep()
        cmd = self._ssh_base_cmd() + [f'cat > {remote_path}']
        with open(local_path, 'rb') as f:
            result = subprocess.run(cmd, stdin=f, capture_output=True, timeout=45)
        if result.returncode != 0:
            self.log(f"UPLOAD FAIL: {local_path} → {remote_path}")
            raise RuntimeError(
                f"Upload failed: {result.stderr.decode()[:200]}")
        self.log(f"UPLOAD OK: {local_path} → {remote_path}")
        return True

    def upload_string(self, content, remote_path):
        """Upload a string as a file to the remote server."""
        self._enforce_sleep()
        cmd = self._ssh_base_cmd() + [f'cat > {remote_path}']
        result = subprocess.run(
            cmd, input=content.encode('utf-8'), capture_output=True, timeout=45)
        if result.returncode != 0:
            raise RuntimeError(
                f"Upload failed: {result.stderr.decode()[:200]}")
        return True

    def upload_and_eval(self, php_content, remote_path=None, timeout=90):
        """Upload a PHP file then execute it.

        WP Engine /tmp/ is session-ephemeral. This method writes to the
        persistent WP install path (under wp-content/) so the file survives
        across SSH sessions, then executes it and cleans up.
        """
        wp_path = self.conf.get('WP_PATH', '').rstrip('/')
        if not remote_path:
            remote_path = f'{wp_path}/wp-content/rss-exec.php'
        elif remote_path.startswith('/tmp/'):
            # Rewrite /tmp/ paths to persistent location
            filename = os.path.basename(remote_path)
            remote_path = f'{wp_path}/wp-content/{filename}'

        # Step 1: Upload PHP file
        self._enforce_sleep()
        input_bytes = php_content.encode('utf-8') if isinstance(php_content, str) else php_content
        cmd_upload = self._ssh_base_cmd() + [f'cat > {remote_path}']
        result = subprocess.run(cmd_upload, input=input_bytes, capture_output=True, timeout=45)
        if result.returncode != 0:
            raise RuntimeError(f"Upload failed: {result.stderr.decode('utf-8', errors='replace')[:200]}")

        # Step 2: Execute PHP file
        self._enforce_sleep()
        cmd_exec = self._ssh_base_cmd() + [f'wp eval-file {remote_path} && rm -f {remote_path}']
        result = subprocess.run(cmd_exec, capture_output=True, timeout=timeout)
        if result.returncode != 0:
            self.log(f"EVAL FAIL: {remote_path} → exit {result.returncode}")
            # Try cleanup
            subprocess.run(self._ssh_base_cmd() + [f'rm -f {remote_path}'],
                          capture_output=True, timeout=30)
            raise RuntimeError(
                f"Eval failed (exit {result.returncode}): "
                f"{result.stderr.decode('utf-8', errors='replace')[:200]}")
        return result.stdout.decode('utf-8', errors='replace').strip()

    def download_content(self, remote_path):
        """Download file content from remote. Returns string."""
        result = self.run(f'cat {remote_path}', timeout=30, check=False)
        return result.stdout if result.returncode == 0 else ''

    def wp_get_field(self, post_id, field):
        """Get a single post field via wp post get."""
        result = self.run(f'wp post get {post_id} --field={field}', timeout=30)
        return result.stdout.strip()

    def wp_eval_file(self, remote_php_path, timeout=45):
        """Execute a PHP file via wp eval-file. Returns stdout.

        WARNING: This only works if the file at remote_php_path persists
        across SSH sessions. On WP Engine, /tmp/ is session-local — files
        written in one SSH session are invisible to the next. For /tmp paths,
        use upload_and_eval() instead which handles persistence automatically.
        """
        if remote_php_path.startswith('/tmp/'):
            raise RuntimeError(
                f"wp_eval_file() called with /tmp path '{remote_php_path}'. "
                f"WP Engine /tmp is session-local — file won't exist in this session. "
                f"Use upload_and_eval() instead."
            )
        result = self.run(f'wp eval-file {remote_php_path}', timeout=timeout)
        return result.stdout.strip()

    def parse_pipe_output(self, output):
        """Parse STATUS=x|LEN=y|... pipe-delimited PHP output.

        Returns dict of key-value pairs.
        """
        pairs = {}
        for segment in output.split('|'):
            segment = segment.strip()
            if '=' in segment:
                key, val = segment.split('=', 1)
                pairs[key.strip()] = val.strip()
        return pairs
