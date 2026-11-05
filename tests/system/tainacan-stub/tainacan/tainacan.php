<?php
/*
 * Plugin Name: Tainacan
 * Description: TEST DOUBLE used only by tests/tainacan_system.bats where wordpress.org cannot be reached. It answers the few REST routes the tests use, the way the real plugin does. CI installs the real plugin.
 * Version: 1.4.1
 */
if (!defined('ABSPATH')) { exit; }

add_action('init', function () {
    register_post_type('tainacan-collection', ['public' => true, 'label' => 'Collections', 'supports' => ['title']]);
    foreach (get_posts(['post_type' => 'tainacan-collection', 'post_status' => 'any', 'numberposts' => -1, 'fields' => 'ids']) as $id) {
        register_post_type('tnc_col_' . $id . '_item', ['public' => true, 'label' => 'Items', 'supports' => ['title']]);
    }
});

add_action('rest_api_init', function () {
    register_rest_route('tainacan/v2', '/collections', [
        ['methods' => 'GET', 'permission_callback' => '__return_true', 'callback' => function () {
            $out = [];
            foreach (get_posts(['post_type' => 'tainacan-collection', 'post_status' => 'publish', 'numberposts' => -1]) as $p) {
                $out[] = ['id' => $p->ID, 'name' => $p->post_title, 'status' => $p->post_status];
            }
            return $out;
        }],
        ['methods' => 'POST', 'permission_callback' => function () { return current_user_can('edit_posts'); }, 'callback' => function ($r) {
            $id = wp_insert_post(['post_type' => 'tainacan-collection', 'post_title' => $r['name'], 'post_status' => $r['status'] ?: 'publish']);
            register_post_type('tnc_col_' . $id . '_item', ['public' => true]);
            return ['id' => $id, 'name' => $r['name']];
        }],
    ]);
    register_rest_route('tainacan/v2', '/collection/(?P<collection_id>\d+)/items', [
        'methods' => 'POST', 'permission_callback' => function () { return current_user_can('edit_posts'); }, 'callback' => function ($r) {
            $id = wp_insert_post(['post_type' => 'tnc_col_' . (int) $r['collection_id'] . '_item', 'post_title' => $r['title'], 'post_status' => $r['status'] ?: 'publish']);
            return ['id' => $id, 'title' => $r['title']];
        },
    ]);
});
