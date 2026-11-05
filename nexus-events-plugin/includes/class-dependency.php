<?php
namespace Nexus_Eventos;
defined('ABSPATH') || exit;

/**
 * Events Manager is a separate plugin. The production package (built by
 * tools/nexus-eventos-package.py) does not carry a copy of it: it is
 * installed from wordpress.org, checked file by file against the published
 * checksums (Koha.Nexus: config.sh --task tainacan-events enable), or by an
 * administrator in Plugins. A development checkout that still has
 * bundled/events-manager can copy it, only after an administrator's POST.
 */
final class Dependency {
    public static function verify_bundle() {
        $root = NXEV_DIR . '/bundled/events-manager';
        $index = NXEV_DIR . '/bundled/events-manager.sha256.json';
        if (!is_readable($index)) { return false; }
        $manifest = json_decode((string) file_get_contents($index), true);
        if (!is_array($manifest) || !$manifest || !is_dir($root) || is_link($root)) { return false; }
        $actual = array();
        $iterator = new \RecursiveIteratorIterator(new \RecursiveDirectoryIterator($root, \FilesystemIterator::SKIP_DOTS));
        foreach ($iterator as $file) {
            if ($file->isLink()) { return false; }
            if (!$file->isFile()) { continue; }
            $name = str_replace(DIRECTORY_SEPARATOR, '/', substr($file->getPathname(), strlen($root) + 1));
            $actual[$name] = hash_file('sha256', $file->getPathname());
        }
        ksort($actual);
        ksort($manifest);
        return $actual === $manifest;
    }

    public static function has_bundle() {
        return is_dir(NXEV_DIR . '/bundled/events-manager') && is_readable(NXEV_DIR . '/bundled/events-manager.sha256.json');
    }

    public static function boot() {
        add_action('admin_post_nxev_prepare', array(__CLASS__, 'prepare'));
        if (!defined('EM_VERSION') || version_compare(EM_VERSION, '7.4.13', '<')) {
            add_action('admin_notices', array(__CLASS__, 'notice'));
        }
    }

    public static function notice() {
        echo '<div class="notice notice-warning"><p>' . esc_html__('Nexus Eventos usa o Events Manager gratuito (7.4.13 ou mais novo) para agenda e reservas. Nenhuma extensão paga é necessária para os recursos Nexus.', 'nexus-eventos') . '</p>';
        if (defined('EM_VERSION') && version_compare(EM_VERSION, '7.4.13', '<')) {
            echo '<p>' . esc_html__('Atualize o Events Manager pelo procedimento normal do WordPress. Uma instalação existente não será substituída automaticamente.', 'nexus-eventos') . '</p>';
        } elseif (self::has_bundle() && current_user_can('install_plugins') && current_user_can('activate_plugins')) {
            echo '<form method="post" action="' . esc_url(admin_url('admin-post.php')) . '"><input type="hidden" name="action" value="nxev_prepare">';
            wp_nonce_field('nxev-prepare');
            echo '<p><button class="button button-primary">' . esc_html__('Preparar base gratuita: instalar se ausente e ativar Events Manager', 'nexus-eventos') . '</button></p></form>';
        } else {
            echo '<p>' . esc_html__('Instale e ative o Events Manager em Plugins, Adicionar novo, a partir do diretório oficial do WordPress. No Koha.Nexus, a ativação dos eventos do Tainacan baixa o pacote oficial e confere cada arquivo antes de instalar.', 'nexus-eventos') . '</p>';
        }
        echo '<p>' . esc_html__('Os dados existentes são preservados.', 'nexus-eventos') . '</p></div>';
    }

    public static function prepare() {
        if (($_SERVER['REQUEST_METHOD'] ?? '') !== 'POST' || !current_user_can('install_plugins') || !current_user_can('activate_plugins')) {
            wp_die('', '', array('response' => 403));
        }
        check_admin_referer('nxev-prepare');
        require_once ABSPATH . 'wp-admin/includes/plugin.php';
        $main = WP_PLUGIN_DIR . '/events-manager/events-manager.php';
        if (!file_exists($main)) {
            if (!self::has_bundle() || !self::verify_bundle()) {
                wp_die(esc_html__('O pacote incluído não passou na verificação de integridade. Instale Events Manager manualmente.', 'nexus-eventos'), '', array('response' => 400));
            }
            require_once ABSPATH . 'wp-admin/includes/file.php';
            require_once ABSPATH . 'wp-admin/includes/class-wp-upgrader.php';
            if (get_filesystem_method() !== 'direct' || !WP_Filesystem()) {
                wp_die(esc_html__('Este servidor exige instalação manual de plugins pelo administrador. Instale Events Manager em Plugins e ative-o.', 'nexus-eventos'), '', array('response' => 400));
            }
            if (!\WP_Upgrader::create_lock('nxev_dependency', 300)) {
                wp_die(esc_html__('Outra preparação está em andamento. Aguarde e tente novamente.', 'nexus-eventos'), '', array('response' => 409));
            }
            global $wp_filesystem;
            $stage = WP_PLUGIN_DIR . '/.nxev-stage-' . bin2hex(random_bytes(12));
            $failed = false;
            try {
                // Never overwrite a directory owned by another installation, even without a main file.
                if (file_exists(dirname($main)) || is_link(dirname($main)) || !$wp_filesystem->mkdir($stage, FS_CHMOD_DIR)) {
                    $failed = true;
                } else {
                    $result = copy_dir(NXEV_DIR . '/bundled/events-manager', $stage);
                    if (is_wp_error($result) || !$wp_filesystem->move($stage, dirname($main), false)) {
                        $failed = true;
                    }
                }
            } finally {
                if ($wp_filesystem->exists($stage)) { $wp_filesystem->delete($stage, true); }
                \WP_Upgrader::release_lock('nxev_dependency');
            }
            if ($failed) {
                wp_die(esc_html__('Não foi possível preparar a base. Nenhuma instalação existente foi substituída. Instale Events Manager manualmente.', 'nexus-eventos'), '', array('response' => 400));
            }
        }
        $header = get_plugin_data($main, false, false);
        if (empty($header['Version']) || version_compare($header['Version'], '7.4.13', '<')) {
            wp_die(esc_html__('Já existe uma versão antiga. Atualize-a manualmente; seus arquivos não foram substituídos.', 'nexus-eventos'), '', array('response' => 400));
        }
        $result = activate_plugin('events-manager/events-manager.php', '', false);
        if (is_wp_error($result)) {
            wp_die(esc_html($result->get_error_message()), '', array('response' => 400));
        }
        wp_safe_redirect(admin_url('admin.php?page=nexus-eventos'));
        exit;
    }
}
