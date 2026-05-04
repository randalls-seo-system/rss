<?php
/**
 * RSS Linking Module — link-injector.php
 * Source: VALN production link-injector-v3.php (pulled 2026-05-04)
 * Status: Template
 *
 * Template variables:
 * - {{SITE_URL}} — full site URL (e.g., https://example.com)
 *
 * Contextual link injection with streaming CSV output.
 * Features: restricted zone awareness, word-boundary matching,
 * self-link prevention, already-linked detection, anchor fallback.
 *
 * Usage: Set $PLAN array before including, then wp eval-file.
 * Plan format: array of ['source_id'=>int, 'target_url'=>string, 'anchor_text'=>string]
 */
set_time_limit(600);
global $wpdb;

if (!isset($PLAN) || !is_array($PLAN)) {
    echo "ERROR: No plan loaded\n";
    exit;
}

function rss_link_is_restricted($content, $pos) {
    $zones = [
        ['<div class="bullet-section', '</div>'],
        ['<div class="vlnCallout', '</div>'],
        ['<div class="vlnTableScroll', '</div>'],
        ['<table class="vlnTable', '</table>'],
        ['<div class="vlnFaq', '</div>'],
        ['<details', '</details>'],
        ['<h1', '</h1>'], ['<h2', '</h2>'], ['<h3', '</h3>'],
        ['<h4', '</h4>'], ['<h5', '</h5>'], ['<h6', '</h6>'],
    ];
    foreach ($zones as $z) {
        $s = 0;
        while (($o = stripos($content, $z[0], $s)) !== false) {
            $c = stripos($content, $z[1], $o + strlen($z[0]));
            if ($c === false) $c = strlen($content); else $c += strlen($z[1]);
            if ($pos >= $o && $pos < $c) return true;
            $s = $c;
        }
    }
    return false;
}

function rss_link_try_inject($content, $target_url, $anchor_text) {
    $tn = rtrim($target_url, '/');
    foreach (['href="'.$target_url.'"', 'href="'.$tn.'"', 'href="'.$tn.'/"',
              'href="{{SITE_URL}}'.$target_url.'"',
              'href="{{SITE_URL}}'.$tn.'"'] as $c) {
        if (stripos($content, $c) !== false)
            return ['s'=>'skip','r'=>'already_linked','c'=>$content];
    }

    $anchors = [$anchor_text];
    $sh = preg_replace('/^(VA |the |a |an |your )/i', '', $anchor_text);
    if ($sh !== $anchor_text && strlen($sh) >= 5) $anchors[] = $sh;

    if (!preg_match_all('~<p[^>]*>(.*?)</p>~si', $content, $pm, PREG_OFFSET_CAPTURE)) {
        return ['s'=>'skip','r'=>'no_p_tags','c'=>$content];
    }

    foreach ($anchors as $a) {
        foreach ($pm[0] as $i => $m) {
            $ps = $m[1]; $ph = $m[0]; $pi = $pm[1][$i][0];
            if (rss_link_is_restricted($content, $ps)) continue;
            if (preg_match('~<a\s~i', $pi)) continue;
            // Word-boundary match to prevent sub-word splits
            $pattern = '/\b' . preg_quote($a, '/') . '\b/i';
            if (!preg_match($pattern, $pi, $wm, PREG_OFFSET_CAPTURE)) continue;
            $p = $wm[0][1];
            $ex = $wm[0][0];
            $b = substr($pi, 0, $p);
            if (substr_count($b, '<') > substr_count($b, '>')) continue;
            $lk = '<a href="'.$target_url.'">'.$ex.'</a>';
            $ni = substr($pi, 0, $p).$lk.substr($pi, $p + strlen($a));
            $np = str_replace($pi, $ni, $ph);
            $nc = substr_replace($content, $np, $ps, strlen($ph));
            return ['s'=>'ok','r'=>'injected','a'=>$a,'c'=>$nc];
        }
    }
    return ['s'=>'skip','r'=>'no_anchor','c'=>$content];
}

echo "source_id,source_slug,target_url,anchor_text,status,reason,anchor_used\n";

$modified = [];

foreach ($PLAN as $item) {
    $sid = intval($item['source_id']);
    $tgt = $item['target_url'];
    $anc = $item['anchor_text'];

    $post = get_post($sid);
    if (!$post || $post->post_status !== 'publish') {
        echo "{$sid},,{$tgt},{$anc},error,not_found,\n";
        continue;
    }

    // Self-link check
    $sp = '/'.trim(str_replace(home_url(), '', get_permalink($sid)), '/').'/';
    $tp = '/'.trim($tgt, '/').'/';
    if ($sp === $tp) {
        echo "{$sid},{$post->post_name},{$tgt},{$anc},skip,self_link,\n";
        continue;
    }

    $content = isset($modified[$sid]) ? $modified[$sid] : $post->post_content;
    $r = rss_link_try_inject($content, $tgt, $anc);

    $st = $r['s'] === 'ok' ? 'injected' : 'skipped';
    $au = isset($r['a']) ? $r['a'] : '';
    echo "{$sid},{$post->post_name},{$tgt}," . str_replace(',',';',$anc) . ",{$st},{$r['r']},{$au}\n";

    if ($r['s'] === 'ok') {
        $modified[$sid] = $r['c'];
    }
}

// Save modified posts
$saved = 0;
foreach ($modified as $pid => $nc) {
    $wpdb->update($wpdb->posts, ['post_content' => $nc], ['ID' => $pid]);
    clean_post_cache($pid);
    $saved++;
    if ($saved < count($modified)) sleep(5);
}
echo "# SAVED: {$saved} posts\n";
