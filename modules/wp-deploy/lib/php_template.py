"""PHP script generator for WordPress write operations.

Builds wp eval-file scripts dynamically using the proven heredoc pattern.
These templates are the canonical safe-write layer — centralizing them
prevents copy-paste drift across tools.

CRITICAL: Never use wp db query for post_content updates. It fails silently
on WP Engine staging with 60KB+ inline SQL. Always use wp_update_post()
via wp eval-file with file-based content read.
"""


def generate_post_update_script(post_id, content_path, status='draft',
                                 verify_greps=None, forbid_greps=None):
    """Generate PHP for post_content update via wp eval-file.

    Args:
        post_id: WordPress post ID
        content_path: Remote path to the HTML content file
        status: Target post_status
        verify_greps: List of strings that MUST be present in content after write
        forbid_greps: List of strings that must NOT be present after write

    Returns:
        Full PHP source as string (ready to write to /tmp/ and eval-file)
    """
    verify_greps = verify_greps or []
    forbid_greps = forbid_greps or []

    verify_block = ''
    for i, grep in enumerate(verify_greps):
        safe = grep.replace("'", "\\'")
        verify_block += f"""
if (strpos($after->post_content, '{safe}') === false) {{
    echo "VERIFY_FAIL={safe}|";
}}"""

    forbid_block = ''
    for i, grep in enumerate(forbid_greps):
        safe = grep.replace("'", "\\'")
        forbid_block += f"""
if (strpos($after->post_content, '{safe}') !== false) {{
    echo "FORBID_FAIL={safe}|";
}}"""

    return f"""<?php
$content = file_get_contents('{content_path}');
if (!$content) {{
    echo "ERROR=Could not read content file|";
    exit(1);
}}

$result = wp_update_post([
    'ID' => {post_id},
    'post_content' => $content,
    'post_status' => '{status}',
], true);

if (is_wp_error($result)) {{
    echo "ERROR=" . $result->get_error_message() . "|";
    exit(1);
}}

$after = get_post({post_id});
echo "STATUS=" . $after->post_status . "|";
echo "LEN=" . strlen($after->post_content) . "|";
echo "MODIFIED=" . $after->post_modified . "|";
{verify_block}
{forbid_block}
echo "OK=1|";
"""


def generate_meta_update_script(post_id, meta_key, meta_value):
    """Generate PHP for post meta update."""
    safe_value = meta_value.replace("'", "\\'")
    safe_key = meta_key.replace("'", "\\'")
    return f"""<?php
$old = get_post_meta({post_id}, '{safe_key}', true);
echo "OLD_VALUE=" . substr($old, 0, 200) . "|";

update_post_meta({post_id}, '{safe_key}', '{safe_value}');

$new = get_post_meta({post_id}, '{safe_key}', true);
echo "NEW_VALUE=" . substr($new, 0, 200) . "|";

if ($new === '{safe_value}') {{
    echo "OK=1|";
}} else {{
    echo "ERROR=Meta value mismatch after update|";
}}
"""


def generate_status_update_script(post_id, target_status):
    """Generate PHP for post_status update."""
    return f"""<?php
$before = get_post({post_id});
echo "OLD_STATUS=" . $before->post_status . "|";

$result = wp_update_post([
    'ID' => {post_id},
    'post_status' => '{target_status}',
], true);

if (is_wp_error($result)) {{
    echo "ERROR=" . $result->get_error_message() . "|";
    exit(1);
}}

$after = get_post({post_id});
echo "NEW_STATUS=" . $after->post_status . "|";
echo "OK=1|";
"""
