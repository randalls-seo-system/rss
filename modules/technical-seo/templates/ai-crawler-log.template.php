<?php
/**
 * RSS Technical SEO Module — ai-crawler-log.php
 * Source: VALN production (pulled 2026-05-03)
 * Status: Template
 *
 * Template variables (replaced at deploy time):
 * - {{SITE_PREFIX}} — function/identifier prefix (lowercase)
 * - {{SITE_PREFIX_UPPER}} — uppercase prefix for class names
 *
 * Render with: ./modules/technical-seo/render.sh <site-config>
 */
if ( ! defined( 'ABSPATH' ) ) exit;

/* ---------- Table creation ---------- */

add_action( 'init', function () {
    $version = get_option( '{{SITE_PREFIX}}_ai_crawler_db_version', '0' );
    if ( $version !== '1.0' ) {
        {{SITE_PREFIX}}_ai_crawler_create_table();
        update_option( '{{SITE_PREFIX}}_ai_crawler_db_version', '1.0', false );
    }
}, 5 );

function {{SITE_PREFIX}}_ai_crawler_create_table() {
    global $wpdb;
    $table   = $wpdb->prefix . '{{SITE_PREFIX}}_ai_crawler_log';
    $charset = $wpdb->get_charset_collate();

    $sql = "CREATE TABLE {$table} (
        id BIGINT AUTO_INCREMENT PRIMARY KEY,
        crawler_name VARCHAR(64),
        user_agent TEXT,
        request_uri VARCHAR(500),
        request_method VARCHAR(10),
        remote_addr VARCHAR(45),
        hit_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_crawler (crawler_name),
        INDEX idx_hit_at (hit_at),
        INDEX idx_uri (request_uri(191))
    ) {$charset};";

    require_once ABSPATH . 'wp-admin/includes/upgrade.php';
    dbDelta( $sql );
}

/* ---------- Crawler detection + logging ---------- */

// Run early, before most WordPress processing
add_action( 'muplugins_loaded', '{{SITE_PREFIX}}_ai_crawler_detect', 1 );

function {{SITE_PREFIX}}_ai_crawler_detect() {
    if ( ! isset( $_SERVER['HTTP_USER_AGENT'] ) ) {
        return;
    }

    $ua = $_SERVER['HTTP_USER_AGENT'];

    $crawlers = [
        'GPTBot'          => 'GPTBot',
        'ChatGPT-User'    => 'ChatGPT-User',
        'ClaudeBot'       => 'ClaudeBot',
        'Claude-Web'      => 'Claude-Web',
        'PerplexityBot'   => 'PerplexityBot',
        'Perplexity-User' => 'Perplexity-User',
        'GoogleOther'     => 'GoogleOther',
        'Google-Extended'  => 'Google-Extended',
        'CCBot'           => 'CCBot',
        'cohere-ai'       => 'cohere-ai',
        'anthropic-ai'    => 'anthropic-ai',
    ];

    $matched = null;
    foreach ( $crawlers as $needle => $name ) {
        if ( stripos( $ua, $needle ) !== false ) {
            $matched = $name;
            break;
        }
    }

    if ( ! $matched ) {
        return;
    }

    global $wpdb;
    $table = $wpdb->prefix . '{{SITE_PREFIX}}_ai_crawler_log';

    // Graceful: skip if table doesn't exist yet (first page load race)
    if ( $wpdb->get_var( "SHOW TABLES LIKE '{$table}'" ) !== $table ) {
        return;
    }

    $wpdb->insert( $table, [
        'crawler_name'   => $matched,
        'user_agent'     => substr( $ua, 0, 1000 ),
        'request_uri'    => substr( $_SERVER['REQUEST_URI'] ?? '', 0, 500 ),
        'request_method' => substr( $_SERVER['REQUEST_METHOD'] ?? '', 0, 10 ),
        'remote_addr'    => substr( $_SERVER['REMOTE_ADDR'] ?? '', 0, 45 ),
    ], [ '%s', '%s', '%s', '%s', '%s' ] );
}

/* ---------- Auto-prune: 90 days ---------- */

add_action( '{{SITE_PREFIX}}_ai_crawler_prune', function () {
    global $wpdb;
    $table = $wpdb->prefix . '{{SITE_PREFIX}}_ai_crawler_log';
    $wpdb->query( "DELETE FROM {$table} WHERE hit_at < DATE_SUB(NOW(), INTERVAL 90 DAY)" );
} );

add_action( 'init', function () {
    if ( ! wp_next_scheduled( '{{SITE_PREFIX}}_ai_crawler_prune' ) ) {
        wp_schedule_event( time(), 'daily', '{{SITE_PREFIX}}_ai_crawler_prune' );
    }
}, 20 );

/* ---------- Admin dashboard widget ---------- */

add_action( 'wp_dashboard_setup', function () {
    wp_add_dashboard_widget(
        '{{SITE_PREFIX}}_ai_crawler_widget',
        'AI Crawler Activity',
        '{{SITE_PREFIX}}_ai_crawler_dashboard_render'
    );
} );

function {{SITE_PREFIX}}_ai_crawler_dashboard_render() {
    global $wpdb;
    $table = $wpdb->prefix . '{{SITE_PREFIX}}_ai_crawler_log';

    // Check table exists
    if ( $wpdb->get_var( "SHOW TABLES LIKE '{$table}'" ) !== $table ) {
        echo '<p>Crawler log table not initialized yet.</p>';
        return;
    }

    // Last 7 days by crawler
    $seven = $wpdb->get_results(
        "SELECT crawler_name, COUNT(*) as hits
         FROM {$table}
         WHERE hit_at >= DATE_SUB(NOW(), INTERVAL 7 DAY)
         GROUP BY crawler_name
         ORDER BY hits DESC"
    );

    // Last 30 days by crawler
    $thirty = $wpdb->get_results(
        "SELECT crawler_name, COUNT(*) as hits
         FROM {$table}
         WHERE hit_at >= DATE_SUB(NOW(), INTERVAL 30 DAY)
         GROUP BY crawler_name
         ORDER BY hits DESC"
    );

    // Top URLs (30 days)
    $top_urls = $wpdb->get_results(
        "SELECT request_uri, COUNT(*) as hits
         FROM {$table}
         WHERE hit_at >= DATE_SUB(NOW(), INTERVAL 30 DAY)
         GROUP BY request_uri
         ORDER BY hits DESC
         LIMIT 10"
    );

    // llms.txt + llms-full.txt hits
    $llms_hits = $wpdb->get_var(
        "SELECT COUNT(*) FROM {$table}
         WHERE hit_at >= DATE_SUB(NOW(), INTERVAL 30 DAY)
           AND (request_uri LIKE '%llms.txt%' OR request_uri LIKE '%llms-full.txt%')"
    );

    echo '<h4>Last 7 Days</h4>';
    if ( $seven ) {
        echo '<table style="width:100%"><tr><th style="text-align:left">Crawler</th><th style="text-align:right">Hits</th></tr>';
        foreach ( $seven as $r ) {
            echo '<tr><td>' . esc_html( $r->crawler_name ) . '</td><td style="text-align:right">' . (int) $r->hits . '</td></tr>';
        }
        echo '</table>';
    } else {
        echo '<p>No hits recorded.</p>';
    }

    echo '<h4>Last 30 Days</h4>';
    if ( $thirty ) {
        echo '<table style="width:100%"><tr><th style="text-align:left">Crawler</th><th style="text-align:right">Hits</th></tr>';
        foreach ( $thirty as $r ) {
            echo '<tr><td>' . esc_html( $r->crawler_name ) . '</td><td style="text-align:right">' . (int) $r->hits . '</td></tr>';
        }
        echo '</table>';
    }

    echo '<h4>Top URLs (30d)</h4>';
    if ( $top_urls ) {
        echo '<table style="width:100%"><tr><th style="text-align:left">URL</th><th style="text-align:right">Hits</th></tr>';
        foreach ( $top_urls as $r ) {
            echo '<tr><td style="word-break:break-all;font-size:12px">' . esc_html( $r->request_uri ) . '</td><td style="text-align:right">' . (int) $r->hits . '</td></tr>';
        }
        echo '</table>';
    }

    echo '<p><strong>llms.txt + llms-full.txt hits (30d):</strong> ' . (int) $llms_hits . '</p>';
}

/* ---------- WP-CLI command ---------- */

if ( defined( 'WP_CLI' ) && WP_CLI ) {
    WP_CLI::add_command( '{{SITE_PREFIX}} ai-crawler', '{{SITE_PREFIX_UPPER}}_AI_Crawler_CLI' );
}

class {{SITE_PREFIX_UPPER}}_AI_Crawler_CLI {

    /**
     * Show AI crawler stats.
     *
     * ## OPTIONS
     *
     * [--days=<days>]
     * : Number of days to look back. Default: 30
     *
     * ## EXAMPLES
     *
     *     wp {{SITE_PREFIX}} ai-crawler stats
     *     wp {{SITE_PREFIX}} ai-crawler stats --days=7
     *
     * @subcommand stats
     */
    public function stats( $args, $assoc_args ) {
        global $wpdb;
        $table = $wpdb->prefix . '{{SITE_PREFIX}}_ai_crawler_log';
        $days  = isset( $assoc_args['days'] ) ? (int) $assoc_args['days'] : 30;

        $total = $wpdb->get_var( $wpdb->prepare(
            "SELECT COUNT(*) FROM {$table} WHERE hit_at >= DATE_SUB(NOW(), INTERVAL %d DAY)",
            $days
        ) );

        WP_CLI::line( "AI Crawler Stats — Last {$days} days" );
        WP_CLI::line( str_repeat( '─', 50 ) );
        WP_CLI::line( "Total hits: {$total}" );
        WP_CLI::line( '' );

        // By crawler
        $by_crawler = $wpdb->get_results( $wpdb->prepare(
            "SELECT crawler_name, COUNT(*) as hits
             FROM {$table}
             WHERE hit_at >= DATE_SUB(NOW(), INTERVAL %d DAY)
             GROUP BY crawler_name
             ORDER BY hits DESC",
            $days
        ) );

        if ( $by_crawler ) {
            WP_CLI::line( 'Hits by crawler:' );
            $rows = [];
            foreach ( $by_crawler as $r ) {
                $rows[] = [ 'Crawler' => $r->crawler_name, 'Hits' => $r->hits ];
            }
            WP_CLI\Utils\format_items( 'table', $rows, [ 'Crawler', 'Hits' ] );
        }

        WP_CLI::line( '' );

        // Top URLs
        $top_urls = $wpdb->get_results( $wpdb->prepare(
            "SELECT request_uri, COUNT(*) as hits
             FROM {$table}
             WHERE hit_at >= DATE_SUB(NOW(), INTERVAL %d DAY)
             GROUP BY request_uri
             ORDER BY hits DESC
             LIMIT 15",
            $days
        ) );

        if ( $top_urls ) {
            WP_CLI::line( 'Top URLs:' );
            $rows = [];
            foreach ( $top_urls as $r ) {
                $rows[] = [ 'URL' => $r->request_uri, 'Hits' => $r->hits ];
            }
            WP_CLI\Utils\format_items( 'table', $rows, [ 'URL', 'Hits' ] );
        }
    }
}
