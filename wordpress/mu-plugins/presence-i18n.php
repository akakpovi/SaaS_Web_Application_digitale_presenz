<?php
/**
 * Plugin Name: Presence Blog — language layer (DE/EN)
 * Description: Minimal, dependency-free multilingual support for the headless blog: a `language` taxonomy, translation links and the REST fields the React frontend needs.
 * Version: 1.0.0
 * License: GPL-2.0-or-later
 *
 * Why not Polylang or WPML?
 *   The blog is consumed headlessly over the REST API; what the frontend needs
 *   is a language code, a translation link and hreflang data. Polylang (GPL,
 *   free) or WPML (paid) would add a full admin language layer we would then
 *   have to map back to these three fields — extra plugins, extra maintenance
 *   and an API surface we cannot verify locally. This file is versioned in the
 *   repository, weighs nothing, and exposes exactly this contract:
 *
 *     GET /wp-json/wp/v2/posts?presence_lang=de
 *     → each post carries presence_lang { code, name } and
 *       presence_translations [{ lang, slug }]
 *
 *   Editors set the language with the "Sprache / Language" box and link the
 *   translation through "Translation of". Nothing else is required.
 */

defined('ABSPATH') || exit;

const PRESENCE_LANGUAGES = ['de', 'en'];
const PRESENCE_DEFAULT_LANGUAGE = 'de';

/**
 * Register the language taxonomy (available in REST so the frontend can filter).
 */
add_action('init', function () {
    register_taxonomy('language', ['post'], [
        'label' => 'Sprache / Language',
        'public' => true,
        'hierarchical' => false,
        'show_in_rest' => true,
        'show_admin_column' => true,
        'rewrite' => ['slug' => 'sprache'],
        'capabilities' => [
            'manage_terms' => 'edit_posts',
            'edit_terms' => 'edit_posts',
            'delete_terms' => 'edit_posts',
            'assign_terms' => 'edit_posts',
        ],
    ]);

    foreach (PRESENCE_LANGUAGES as $code) {
        if (!term_exists($code, 'language')) {
            // Name is the visible label, slug is what the API filters on.
            wp_insert_term(strtoupper($code), 'language', [
                'slug' => $code,
                'description' => $code,
            ]);
        }
    }
});

/** The language assigned to a post, falling back to the site default. */
function presence_post_language(int $post_id): string {
    $terms = wp_get_post_terms($post_id, 'language', ['fields' => 'slugs']);
    if (is_wp_error($terms) || empty($terms)) {
        return PRESENCE_DEFAULT_LANGUAGE;
    }
    return in_array($terms[0], PRESENCE_LANGUAGES, true) ? $terms[0] : PRESENCE_DEFAULT_LANGUAGE;
}

/** The post this one is a translation of (0 when it is an original). */
function presence_translation_source(int $post_id): int {
    return (int) get_post_meta($post_id, '_presence_translation_of', true);
}

/** Every language variant of a post, including the post itself. */
function presence_translation_group(int $post_id): array {
    $source_id = presence_translation_source($post_id) ?: $post_id;
    $ids = [$source_id];
    $siblings = get_posts([
        'post_type' => 'post',
        'post_status' => 'publish',
        'posts_per_page' => 20,
        'meta_key' => '_presence_translation_of',
        'meta_value' => $source_id,
        'fields' => 'ids',
    ]);
    return array_values(array_unique(array_merge($ids, $siblings)));
}

/** Assign the default language on save when the editor did not pick one. */
add_action('save_post_post', function (int $post_id) {
    if (wp_is_post_revision($post_id) || wp_is_post_autosave($post_id)) {
        return;
    }
    $terms = wp_get_post_terms($post_id, 'language', ['fields' => 'slugs']);
    if (is_wp_error($terms) || empty($terms)) {
        wp_set_object_terms($post_id, PRESENCE_DEFAULT_LANGUAGE, 'language');
    }
}, 10, 1);

/**
 * REST: expose language + translations, and allow ?presence_lang=de.
 */
add_action('rest_api_init', function () {
    register_rest_field('post', 'presence_lang', [
        'get_callback' => function (array $post) {
            $code = presence_post_language((int) $post['id']);
            return ['code' => $code, 'name' => strtoupper($code)];
        },
        'schema' => null,
    ]);

    register_rest_field('post', 'presence_translations', [
        'get_callback' => function (array $post) {
            $out = [];
            foreach (presence_translation_group((int) $post['id']) as $id) {
                if ($id === (int) $post['id'] || get_post_status($id) !== 'publish') {
                    continue;
                }
                $out[] = [
                    'lang' => presence_post_language((int) $id),
                    'slug' => get_post_field('post_name', $id),
                    'title' => get_the_title($id),
                ];
            }
            return $out;
        },
        'schema' => null,
    ]);

    // Filtering by language through a query parameter.
    add_filter('rest_post_query', function (array $args, WP_REST_Request $request) {
        $lang = $request->get_param('presence_lang');
        if (!$lang || !in_array($lang, PRESENCE_LANGUAGES, true)) {
            return $args;
        }
        $args['tax_query'] = array_merge($args['tax_query'] ?? [], [[
            'taxonomy' => 'language',
            'field' => 'slug',
            'terms' => $lang,
        ]]);
        return $args;
    }, 10, 2);
});

/**
 * Editor UI: language selector and the "translation of" field.
 */
add_action('add_meta_boxes', function () {
    add_meta_box('presence-i18n', 'Sprache / Language', function (WP_Post $post) {
        wp_nonce_field('presence_i18n', 'presence_i18n_nonce');
        $current = presence_post_language($post->ID);
        $source = presence_translation_source($post->ID);

        echo '<p><label for="presence_lang_select"><strong>Sprache</strong></label><br />';
        echo '<select name="presence_lang_select" id="presence_lang_select">';
        foreach (PRESENCE_LANGUAGES as $code) {
            printf(
                '<option value="%s"%s>%s</option>',
                esc_attr($code),
                selected($current, $code, false),
                esc_html(strtoupper($code))
            );
        }
        echo '</select></p>';

        echo '<p><label for="presence_translation_of"><strong>Übersetzung von (ID)</strong></label><br />';
        printf(
            '<input type="number" name="presence_translation_of" id="presence_translation_of" value="%d" min="0" class="small-text" />',
            (int) $source
        );
        echo '<br /><small>Leer lassen, wenn dieser Beitrag das Original ist.</small></p>';

        $siblings = [];
        foreach (presence_translation_group($post->ID) as $id) {
            if ($id === $post->ID) {
                continue;
            }
            $siblings[] = sprintf(
                '%s: #%d %s',
                strtoupper(presence_post_language((int) $id)),
                $id,
                get_the_title($id)
            );
        }
        if ($siblings) {
            echo '<p><strong>Verknüpfte Sprachen</strong><br /><small>'
                . esc_html(implode(' · ', $siblings)) . '</small></p>';
        }
    }, 'post', 'side', 'high');
});

add_action('save_post_post', function (int $post_id) {
    if (!isset($_POST['presence_i18n_nonce'])
        || !wp_verify_nonce(sanitize_text_field(wp_unslash($_POST['presence_i18n_nonce'])), 'presence_i18n')
        || !current_user_can('edit_post', $post_id)) {
        return;
    }

    $lang = isset($_POST['presence_lang_select'])
        ? sanitize_key(wp_unslash($_POST['presence_lang_select']))
        : '';
    if (in_array($lang, PRESENCE_LANGUAGES, true)) {
        wp_set_object_terms($post_id, $lang, 'language');
    }

    $source = isset($_POST['presence_translation_of'])
        ? (int) $_POST['presence_translation_of']
        : 0;
    if ($source > 0 && $source !== $post_id) {
        update_post_meta($post_id, '_presence_translation_of', $source);
    } else {
        delete_post_meta($post_id, '_presence_translation_of');
    }
}, 10, 1);
