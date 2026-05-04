<?php
/**
 * RSS Technical SEO Module — dashboard-ai-crawlers.php
 * Source: VALN production (pulled 2026-05-03)
 * Status: Template
 *
 * Template variables (replaced at deploy time):
 * - {{SITE_PREFIX}} — function/identifier prefix (lowercase)
 *
 * Render with: ./modules/technical-seo/render.sh <site-config>
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

add_action( 'admin_menu', function () {
	add_menu_page(
		'AI Crawlers',
		'AI Crawlers',
		'manage_options',
		'{{SITE_PREFIX}}-ai-crawlers',
		'{{SITE_PREFIX}}_ai_crawlers_render',
		'dashicons-visibility',
		81
	);
} );

function {{SITE_PREFIX}}_ai_crawlers_render() {
	global $wpdb;
	$table = $wpdb->prefix . '{{SITE_PREFIX}}_ai_crawler_log';

	// Check table exists
	$exists = $wpdb->get_var( "SHOW TABLES LIKE '$table'" );
	if ( ! $exists ) {
		echo '<div class="wrap"><h1>AI Crawler Activity</h1><p>Crawler log table not found.</p></div>';
		return;
	}

	// Bust cache on demand
	if ( isset( $_GET['refresh'] ) && wp_verify_nonce( $_GET['_wpnonce'] ?? '', '{{SITE_PREFIX}}_ai_refresh' ) ) {
		delete_transient( '{{SITE_PREFIX}}_ai_crawler_stats' );
	}

	$stats = get_transient( '{{SITE_PREFIX}}_ai_crawler_stats' );
	if ( false === $stats ) {
		$stats = {{SITE_PREFIX}}_ai_crawlers_query( $wpdb, $table );
		set_transient( '{{SITE_PREFIX}}_ai_crawler_stats', $stats, 300 );
	}

	$refresh_url = wp_nonce_url( admin_url( 'admin.php?page={{SITE_PREFIX}}-ai-crawlers&refresh=1' ), '{{SITE_PREFIX}}_ai_refresh' );

	echo '<div class="wrap">';
	echo '<h1 style="display:flex;align-items:center;gap:12px;">AI Crawler Activity';
	echo '<a href="' . esc_url( $refresh_url ) . '" class="button button-small" style="margin-left:8px;">Refresh</a></h1>';

	{{SITE_PREFIX}}_ai_crawlers_css();
	{{SITE_PREFIX}}_ai_crawlers_cards( $stats );
	{{SITE_PREFIX}}_ai_crawlers_two_col( $stats );
	{{SITE_PREFIX}}_ai_crawlers_chart( $stats );
	{{SITE_PREFIX}}_ai_crawlers_recent( $stats );

	echo '</div>';
}

function {{SITE_PREFIX}}_ai_crawlers_query( $wpdb, $table ) {
	$now = current_time( 'mysql' );

	$cnt_24h = (int) $wpdb->get_var( "SELECT COUNT(*) FROM $table WHERE hit_at >= DATE_SUB('$now', INTERVAL 24 HOUR)" );
	$cnt_7d  = (int) $wpdb->get_var( "SELECT COUNT(*) FROM $table WHERE hit_at >= DATE_SUB('$now', INTERVAL 7 DAY)" );
	$cnt_30d = (int) $wpdb->get_var( "SELECT COUNT(*) FROM $table WHERE hit_at >= DATE_SUB('$now', INTERVAL 30 DAY)" );
	$cnt_all = (int) $wpdb->get_var( "SELECT COUNT(*) FROM $table" );

	$top_crawlers = $wpdb->get_results(
		"SELECT crawler_name, COUNT(*) as cnt FROM $table
		 WHERE hit_at >= DATE_SUB('$now', INTERVAL 30 DAY)
		 GROUP BY crawler_name ORDER BY cnt DESC LIMIT 8"
	);

	$top_urls = $wpdb->get_results(
		"SELECT request_uri, COUNT(*) as cnt FROM $table
		 WHERE hit_at >= DATE_SUB('$now', INTERVAL 30 DAY)
		 GROUP BY request_uri ORDER BY cnt DESC LIMIT 10"
	);

	$daily = $wpdb->get_results(
		"SELECT DATE(hit_at) as day, COUNT(*) as cnt FROM $table
		 WHERE hit_at >= DATE_SUB('$now', INTERVAL 30 DAY)
		 GROUP BY DATE(hit_at) ORDER BY day ASC"
	);

	$recent = $wpdb->get_results(
		"SELECT crawler_name, request_uri, hit_at FROM $table
		 ORDER BY hit_at DESC LIMIT 50"
	);

	return compact( 'cnt_24h', 'cnt_7d', 'cnt_30d', 'cnt_all', 'top_crawlers', 'top_urls', 'daily', 'recent' );
}

function {{SITE_PREFIX}}_ai_crawlers_css() {
	?>
	<style>
	.vac-cards{display:flex;gap:16px;margin:20px 0;flex-wrap:wrap}
	.vac-card{flex:1;min-width:140px;background:#fff;border:1px solid #e2e8f0;border-radius:10px;padding:18px 20px;text-align:center}
	.vac-card-num{font-size:32px;font-weight:800;color:#1e3a8a;line-height:1.1}
	.vac-card-label{font-size:12px;font-weight:600;color:#64748b;text-transform:uppercase;letter-spacing:.5px;margin-top:4px}
	.vac-cols{display:flex;gap:20px;margin:20px 0;flex-wrap:wrap}
	.vac-col{flex:1;min-width:300px;background:#fff;border:1px solid #e2e8f0;border-radius:10px;padding:18px 20px}
	.vac-col h3{margin:0 0 12px;font-size:14px;font-weight:700;color:#0f172a}
	.vac-tbl{width:100%;border-collapse:collapse}
	.vac-tbl td,.vac-tbl th{padding:6px 8px;text-align:left;font-size:13px;border-bottom:1px solid #f1f5f9}
	.vac-tbl th{font-weight:700;color:#475569;font-size:11px;text-transform:uppercase;letter-spacing:.4px}
	.vac-tbl td:last-child{text-align:right;font-weight:700;color:#1e3a8a}
	.vac-url{max-width:340px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;display:inline-block;vertical-align:middle;color:#334155}
	.vac-chart-wrap{background:#fff;border:1px solid #e2e8f0;border-radius:10px;padding:18px 20px;margin:20px 0}
	.vac-chart-wrap h3{margin:0 0 12px;font-size:14px;font-weight:700;color:#0f172a}
	.vac-chart{display:flex;align-items:flex-end;gap:3px;height:120px}
	.vac-bar{flex:1;background:#3b82f6;border-radius:3px 3px 0 0;min-width:6px;position:relative;transition:background .15s}
	.vac-bar:hover{background:#1e40af}
	.vac-bar:hover .vac-tip{display:block}
	.vac-tip{display:none;position:absolute;bottom:100%;left:50%;transform:translateX(-50%);background:#0f172a;color:#fff;font-size:10px;padding:3px 6px;border-radius:4px;white-space:nowrap;margin-bottom:4px;pointer-events:none}
	.vac-recent{background:#fff;border:1px solid #e2e8f0;border-radius:10px;padding:18px 20px;margin:20px 0}
	.vac-recent h3{margin:0 0 12px;font-size:14px;font-weight:700;color:#0f172a}
	.vac-pill{display:inline-block;padding:2px 8px;border-radius:999px;font-size:11px;font-weight:700}
	.vac-pill-chatgpt{background:#dcfce7;color:#15803d}
	.vac-pill-perplexity{background:#dbeafe;color:#1e40af}
	.vac-pill-claude{background:#fce7f3;color:#be185d}
	.vac-pill-google{background:#fef9c3;color:#a16207}
	.vac-pill-other{background:#f1f5f9;color:#475569}
	.vac-time{color:#94a3b8;font-size:12px;white-space:nowrap}
	</style>
	<?php
}

function {{SITE_PREFIX}}_ai_crawlers_cards( $stats ) {
	$cards = array(
		array( 'num' => $stats['cnt_24h'], 'label' => 'Last 24 Hours' ),
		array( 'num' => $stats['cnt_7d'],  'label' => 'Last 7 Days' ),
		array( 'num' => $stats['cnt_30d'], 'label' => 'Last 30 Days' ),
		array( 'num' => $stats['cnt_all'], 'label' => 'All Time' ),
	);
	echo '<div class="vac-cards">';
	foreach ( $cards as $c ) {
		echo '<div class="vac-card"><div class="vac-card-num">' . number_format( $c['num'] ) . '</div>';
		echo '<div class="vac-card-label">' . esc_html( $c['label'] ) . '</div></div>';
	}
	echo '</div>';
}

function {{SITE_PREFIX}}_ai_crawlers_two_col( $stats ) {
	echo '<div class="vac-cols">';

	// Top Crawlers
	echo '<div class="vac-col"><h3>Top Crawlers (30d)</h3>';
	if ( empty( $stats['top_crawlers'] ) ) {
		echo '<p style="color:#94a3b8">No data yet.</p>';
	} else {
		echo '<table class="vac-tbl"><tr><th>Crawler</th><th style="text-align:right">Hits</th></tr>';
		foreach ( $stats['top_crawlers'] as $r ) {
			$name = esc_html( $r->crawler_name ?: 'Unknown' );
			echo "<tr><td>{$name}</td><td>" . number_format( $r->cnt ) . '</td></tr>';
		}
		echo '</table>';
	}
	echo '</div>';

	// Top URLs
	echo '<div class="vac-col"><h3>Top Crawled URLs (30d)</h3>';
	if ( empty( $stats['top_urls'] ) ) {
		echo '<p style="color:#94a3b8">No data yet.</p>';
	} else {
		echo '<table class="vac-tbl"><tr><th>URL</th><th style="text-align:right">Hits</th></tr>';
		foreach ( $stats['top_urls'] as $r ) {
			$uri = esc_html( $r->request_uri );
			echo '<tr><td><span class="vac-url" title="' . $uri . '">' . $uri . '</span></td>';
			echo '<td>' . number_format( $r->cnt ) . '</td></tr>';
		}
		echo '</table>';
	}
	echo '</div>';

	echo '</div>';
}

function {{SITE_PREFIX}}_ai_crawlers_chart( $stats ) {
	echo '<div class="vac-chart-wrap"><h3>Daily Volume (30d)</h3>';
	if ( empty( $stats['daily'] ) ) {
		echo '<p style="color:#94a3b8">No data yet.</p></div>';
		return;
	}

	$max = 1;
	foreach ( $stats['daily'] as $d ) {
		if ( (int) $d->cnt > $max ) $max = (int) $d->cnt;
	}

	echo '<div class="vac-chart">';
	foreach ( $stats['daily'] as $d ) {
		$pct = round( ( (int) $d->cnt / $max ) * 100 );
		$pct = max( $pct, 2 );
		$day_label = date( 'M j', strtotime( $d->day ) );
		echo '<div class="vac-bar" style="height:' . $pct . '%">';
		echo '<span class="vac-tip">' . $day_label . ': ' . (int) $d->cnt . '</span>';
		echo '</div>';
	}
	echo '</div></div>';
}

function {{SITE_PREFIX}}_ai_crawlers_recent( $stats ) {
	echo '<div class="vac-recent"><h3>Recent Hits (Last 50)</h3>';
	if ( empty( $stats['recent'] ) ) {
		echo '<p style="color:#94a3b8">No data yet.</p></div>';
		return;
	}

	echo '<table class="vac-tbl"><tr><th>Crawler</th><th>URL</th><th style="text-align:right">Time</th></tr>';
	foreach ( $stats['recent'] as $r ) {
		$pill_class = 'vac-pill-other';
		$name = $r->crawler_name ?: 'Unknown';
		$lower = strtolower( $name );
		if ( strpos( $lower, 'chatgpt' ) !== false ) $pill_class = 'vac-pill-chatgpt';
		elseif ( strpos( $lower, 'perplexity' ) !== false ) $pill_class = 'vac-pill-perplexity';
		elseif ( strpos( $lower, 'claude' ) !== false ) $pill_class = 'vac-pill-claude';
		elseif ( strpos( $lower, 'google' ) !== false ) $pill_class = 'vac-pill-google';

		$uri = esc_html( $r->request_uri );
		$ago = human_time_diff( strtotime( $r->hit_at ), current_time( 'timestamp' ) ) . ' ago';

		echo '<tr>';
		echo '<td><span class="vac-pill ' . $pill_class . '">' . esc_html( $name ) . '</span></td>';
		echo '<td><span class="vac-url" title="' . $uri . '">' . $uri . '</span></td>';
		echo '<td class="vac-time">' . esc_html( $ago ) . '</td>';
		echo '</tr>';
	}
	echo '</table></div>';
}
