<?php
/**
 * Plugin Name: Presence Site Health
 * Plugin URI:  https://monsaas.com
 * Description: Affiche le score de santé de votre site web directement dans le tableau de bord WordPress, propulsé par Presence SaaS.
 * Version:     1.0.0
 * Author:      Presence SaaS
 * Author URI:  https://monsaas.com
 * License:     GPL-2.0-or-later
 * Text Domain: presence-site-health
 */

if ( ! defined( 'ABSPATH' ) ) {
    exit;
}

/**
 * ============================================================
 * CONFIGURATION
 * ============================================================
 * URL de l'API Presence SaaS.
 * En production, remplacez par votre domaine réel :
 *   define( 'PRESENCE_API_URL', 'https://api.monsaas.com/api/v1' );
 *
 * CORS : L'API Presence SaaS doit autoriser les requêtes
 * depuis votre domaine WordPress dans ses settings CORS :
 *   CORS_ALLOWED_ORIGINS = ["https://votre-site-wordpress.com"]
 * ============================================================
 */
if ( ! defined( 'PRESENCE_API_URL' ) ) {
    define( 'PRESENCE_API_URL', 'https://api.monsaas.com/api/v1' );
}

/**
 * ============================================================
 * WIDGET DASHBOARD
 * ============================================================
 */
add_action( 'wp_dashboard_setup', 'presence_register_dashboard_widget' );

function presence_register_dashboard_widget() {
    wp_add_dashboard_widget(
        'presence_site_health_widget',
        '🛡️ Presence — Santé du Site',
        'presence_render_dashboard_widget'
    );
}

function presence_render_dashboard_widget() {
    $site_url   = get_site_url();
    $domain     = wp_parse_url( $site_url, PHP_URL_HOST );
    $cache_key  = 'presence_score_' . md5( $domain );
    $cached     = get_transient( $cache_key );

    if ( false !== $cached ) {
        $data = $cached;
    } else {
        $data = presence_fetch_score( $domain );
        if ( $data && isset( $data['score'] ) ) {
            // Cache pendant 1 heure pour éviter de surcharger l'API
            set_transient( $cache_key, $data, HOUR_IN_SECONDS );
        }
    }

    if ( ! $data || ! isset( $data['score'] ) ) {
        echo '<p style="color:#64748b;">Impossible de récupérer le score pour le moment. ';
        echo '<a href="#" onclick="location.reload();">Réessayer</a></p>';
        return;
    }

    $score  = intval( $data['score'] );
    $color  = $score >= 80 ? '#16a34a' : ( $score >= 50 ? '#d97706' : '#dc2626' );
    $label  = $score >= 80 ? 'Excellent' : ( $score >= 50 ? 'À améliorer' : 'Critique' );
    $report = PRESENCE_API_URL . '/../scan/' . ( $data['scan_id'] ?? '' ) . '?utm_source=wp_plugin&utm_medium=dashboard&utm_campaign=presence_health';

    ?>
    <div style="text-align:center; padding:12px 0;">
        <div style="position:relative; width:120px; height:120px; margin:0 auto;">
            <svg viewBox="0 0 36 36" style="width:120px; height:120px; transform:rotate(-90deg);">
                <path d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                      fill="none" stroke="#e2e8f0" stroke-width="3"/>
                <path d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                      fill="none" stroke="<?php echo esc_attr( $color ); ?>" stroke-width="3"
                      stroke-dasharray="<?php echo esc_attr( $score ); ?>, 100"
                      stroke-linecap="round"/>
            </svg>
            <div style="position:absolute; top:50%; left:50%; transform:translate(-50%,-50%); text-align:center;">
                <div style="font-size:28px; font-weight:800; color:<?php echo esc_attr( $color ); ?>;">
                    <?php echo esc_html( $score ); ?>
                </div>
                <div style="font-size:10px; color:#94a3b8;">/100</div>
            </div>
        </div>
        <p style="margin:8px 0 4px; font-size:13px; font-weight:600; color:<?php echo esc_attr( $color ); ?>;">
            <?php echo esc_html( $label ); ?>
        </p>
        <p style="font-size:11px; color:#94a3b8; margin:0 0 12px;">
            <?php echo esc_html( $domain ); ?>
        </p>
        <a href="<?php echo esc_url( $report ); ?>" target="_blank"
           style="display:inline-block; background:#2563eb; color:#fff; padding:8px 16px; border-radius:6px; text-decoration:none; font-size:12px; font-weight:600;">
            Voir le rapport détaillé →
        </a>
    </div>
    <?php
}

/**
 * ============================================================
 * APPEL API (avec wp_remote_get)
 * ============================================================
 * CORS : L'API Presence doit inclure dans ses headers :
 *   Access-Control-Allow-Origin: https://votre-domaine-wp.com
 *   Access-Control-Allow-Methods: POST, GET, OPTIONS
 *   Access-Control-Allow-Headers: Content-Type
 * ============================================================
 */
function presence_fetch_score( $domain ) {
    $api_url = PRESENCE_API_URL . '/public/scan/';

    $response = wp_remote_post(
        $api_url,
        array(
            'timeout' => 30,
            'headers' => array(
                'Content-Type'  => 'application/json',
                'Accept'        => 'application/json',
            ),
            'body' => wp_json_encode( array( 'url' => 'https://' . $domain ) ),
        )
    );

    if ( is_wp_error( $response ) ) {
        error_log( 'Presence API Error: ' . $response->get_error_message() );
        return null;
    }

    $code = wp_remote_retrieve_response_code( $response );
    if ( $code !== 200 && $code !== 202 ) {
        error_log( 'Presence API HTTP ' . $code );
        return null;
    }

    $body = json_decode( wp_remote_retrieve_body( $response ), true );
    return $body;
}
