<?php
/**
 * Plugin Name: Nexus Eventos para Tainacan
 * Description: Agenda, acervos relacionados, presença e comprovantes de participação sobre o Events Manager gratuito.
 * Version: 0.1.1
 * Requires at least: 6.5
 * Requires PHP: 8.1
 * Author: Koha.Nexus contributors
 * License: GPL-3.0-or-later
 * Text Domain: nexus-eventos
 * Domain Path: /languages
 */
defined('ABSPATH') || exit;
define('NXEV_VERSION', '0.1.1');
define('NXEV_FILE', __FILE__);
define('NXEV_DIR', __DIR__);
require_once __DIR__ . '/includes/class-core.php';
require_once __DIR__ . '/includes/class-dependency.php';
register_activation_hook(__FILE__, array('Nexus_Eventos\Core', 'activate'));
add_action('plugins_loaded', function () {
    load_plugin_textdomain('nexus-eventos', false, dirname(plugin_basename(NXEV_FILE)) . '/languages');
    Nexus_Eventos\Dependency::boot();
    if (!class_exists('EM_Events') || !defined('EM_VERSION') || version_compare(EM_VERSION, '7.4.13', '<')) {
        return;
    }
    // The upstream global-table mode needs cross-site authorization and is not supported.
    if (defined('EM_MS_GLOBAL') && EM_MS_GLOBAL) {
        add_action('admin_notices', function () {
            echo '<div class="notice notice-error"><p>' . esc_html__('Nexus Eventos não suporta tabelas globais do Events Manager em multisite. Use eventos locais de cada site.', 'nexus-eventos') . '</p></div>';
        });
        return;
    }
    require_once __DIR__ . '/includes/class-public.php';
    require_once __DIR__ . '/includes/class-admin.php';
    Nexus_Eventos\Core::boot();
    Nexus_Eventos\Public_UI::boot();
    Nexus_Eventos\Admin::boot();
}, 30);
