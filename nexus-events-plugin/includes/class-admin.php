<?php
namespace Nexus_Eventos;
defined('ABSPATH') || exit;

final class Admin {
    public static function boot() {
        add_action('admin_menu', array(__CLASS__, 'menu'));
        add_action('add_meta_boxes', array(__CLASS__, 'metabox'));
        add_action('save_post', array(__CLASS__, 'save_meta'), 30, 2);
        add_action('admin_post_nxev_action', array(__CLASS__, 'action'));
        add_action('admin_post_nopriv_nxev_action', array(__CLASS__, 'action'));
        add_action('admin_post_nxev_export', array(__CLASS__, 'export'));
        add_action('admin_post_nxev_settings', array(__CLASS__, 'settings'));
        add_action('admin_enqueue_scripts', function ($hook) {
            if ($hook === 'toplevel_page_nexus-eventos') {
                wp_enqueue_style('nxev-admin', plugins_url('assets/events.css', NXEV_FILE), array(), NXEV_VERSION);
            }
        });
    }

    public static function menu() {
        add_menu_page(__('Nexus Eventos', 'nexus-eventos'), __('Nexus Eventos', 'nexus-eventos'),
            'manage_bookings', 'nexus-eventos', array(__CLASS__, 'page'), 'dashicons-tickets-alt', 27);
    }

    public static function metabox() {
        add_meta_box('nxev-integration', __('Nexus: acervo e participação', 'nexus-eventos'),
            array(__CLASS__, 'meta_fields'), EM_POST_TYPE_EVENT, 'normal');
    }

    public static function meta_fields($post) {
        wp_nonce_field('nxev-meta-' . $post->ID, 'nxev_meta_nonce');
        echo '<p><label><input type="checkbox" name="nxev_certificate" value="1" ' . checked(get_post_meta($post->ID, '_nxev_certificate', true), '1', false) . '> ' . esc_html__('Permitir comprovante após o evento para inscrições individuais com presença confirmada.', 'nexus-eventos') . '</label></p>';
        echo '<p><label>' . esc_html__('Carga horária declarada (opcional)', 'nexus-eventos') . ' <input type="number" name="nxev_hours" min="0" max="9999" step="0.25" value="' . esc_attr(get_post_meta($post->ID, '_nxev_hours', true)) . '"></label></p>';
        echo '<p>' . esc_html__('O comprovante registra a declaração da organização e não equivale a assinatura digital qualificada. Reservas de grupo e horários fracionados não recebem passes individuais nesta versão.', 'nexus-eventos') . '</p>';
        if (!post_type_exists('tainacan-collection')) {
            echo '<p>' . esc_html__('Ative o Tainacan para vincular coleções. Agenda e inscrições continuam disponíveis sem ele.', 'nexus-eventos') . '</p>';
            return;
        }
        $selected = Core::collection_ids($post->ID);
        $collections = get_posts(array('post_type' => 'tainacan-collection', 'post_status' => 'publish', 'numberposts' => 200,
            'orderby' => 'title', 'order' => 'ASC'));
        $rows = iterator_to_array($rows);
        echo '<input type="hidden" name="nxev_collections_present" value="1"><p><label for="nxev-collections">' . esc_html__('Coleções públicas relacionadas (até 200 listadas)', 'nexus-eventos') . '</label></p><select id="nxev-collections" name="nxev_collections[]" multiple size="6" style="width:100%;max-width:600px">';
        foreach ($collections as $collection) {
            if (!Core::collection($collection->ID)) { continue; }
            echo '<option value="' . (int) $collection->ID . '" ' . selected(in_array($collection->ID, $selected, true), true, false) . '>' . esc_html($collection->post_title) . '</option>';
        }
        echo '</select><p>' . esc_html__('Os vínculos apontam ao acervo original. Não são criadas cópias dos itens ou dos arquivos.', 'nexus-eventos') . '</p>';
    }

    public static function save_meta($id, $post) {
        if ($post->post_type !== EM_POST_TYPE_EVENT || wp_is_post_revision($id) || wp_is_post_autosave($id) ||
            !current_user_can('edit_post', $id) || empty($_POST['nxev_meta_nonce']) ||
            !is_string($_POST['nxev_meta_nonce']) || !wp_verify_nonce(sanitize_text_field(wp_unslash($_POST['nxev_meta_nonce'])), 'nxev-meta-' . $id)) {
            return;
        }
        update_post_meta($id, '_nxev_certificate', isset($_POST['nxev_certificate']) ? '1' : '0');
        $hours = isset($_POST['nxev_hours']) && is_scalar($_POST['nxev_hours']) ? (float) $_POST['nxev_hours'] : 0;
        update_post_meta($id, '_nxev_hours', max(0, min(9999, $hours)));
        if (isset($_POST['nxev_collections_present']) && post_type_exists('tainacan-collection')) {
            $ids = isset($_POST['nxev_collections']) && is_array($_POST['nxev_collections']) ?
                array_values(array_unique(array_filter(array_map('absint', array_filter($_POST['nxev_collections'], 'is_scalar')), array('Nexus_Eventos\Core', 'collection')))) : array();
            $ids = array_slice($ids, 0, 200);
            foreach ((array) get_post_meta($id, '_nxev_collections', true) as $old) {
                delete_post_meta($id, '_nxev_collection_' . absint($old));
            }
            update_post_meta($id, '_nxev_collections', $ids);
            foreach ($ids as $collection) {
                update_post_meta($id, '_nxev_collection_' . $collection, '1');
            }
        }
    }

    public static function action() {
        if (($_SERVER['REQUEST_METHOD'] ?? '') !== 'POST') {
            wp_die(esc_html__('Use o formulário de confirmação.', 'nexus-eventos'), '', array('response' => 405));
        }
        $id = isset($_POST['booking_id']) && is_scalar($_POST['booking_id']) ? absint($_POST['booking_id']) : 0;
        $operation = isset($_POST['operation']) && is_string($_POST['operation']) ? sanitize_key($_POST['operation']) : '';
        if (!in_array($operation, array('checkin', 'undo', 'revoke', 'issue'), true)) {
            wp_die(esc_html__('Operação inválida.', 'nexus-eventos'), '', array('response' => 400));
        }
        check_admin_referer('nxev-' . $operation . '-' . $id);
        $booking = em_get_booking($id);
        $token = isset($_POST['pass_key']) && is_string($_POST['pass_key']) ? wp_unslash($_POST['pass_key']) : '';
        if ($operation === 'issue') {
            $result = Core::issue($booking, $token);
        } else {
            if (!Core::manager($booking)) {
                wp_die(esc_html__('Você não pode administrar este evento.', 'nexus-eventos'), '', array('response' => 403));
            }
            if ($operation === 'checkin') {
                $result = Core::checkin($booking);
            } else {
                $result = $operation === 'undo' ? Core::undo($booking) : Core::revoke($id);
            }
        }
        if (is_wp_error($result)) {
            wp_die(esc_html($result->get_error_message()), '', array('response' => 400, 'back_link' => true));
        }
        if ($result === false) {
            wp_die(esc_html__('Não foi possível concluir a operação. Tente novamente.', 'nexus-eventos'), '', array('response' => 500));
        }
        wp_safe_redirect(Core::pass_url($booking));
        exit;
    }

    public static function settings() {
        if (($_SERVER['REQUEST_METHOD'] ?? '') !== 'POST' || !current_user_can('manage_options')) {
            wp_die('', '', array('response' => 403));
        }
        check_admin_referer('nxev-settings');
        $value = isset($_POST['institution']) && is_string($_POST['institution']) ? sanitize_text_field(wp_unslash($_POST['institution'])) : '';
        update_option('nxev_institution', mb_substr($value, 0, 250), false);
        wp_safe_redirect(admin_url('admin.php?page=nexus-eventos'));
        exit;
    }

    private static function selected_event() {
        $id = absint(Public_UI::get('event_id', 0));
        $event = $id ? em_get_event($id) : null;
        return $event && $event->event_id && $event->can_manage('manage_bookings', 'manage_others_bookings') ? $event : null;
    }

    public static function page() {
        if (!current_user_can('manage_bookings')) { return; }
        $event = self::selected_event();
        echo '<div class="wrap nxev"><h1>' . esc_html__('Nexus Eventos', 'nexus-eventos') . '</h1><p>' . esc_html__('Agenda e inscrições usam o Events Manager. Aqui você integra coleções, confirma presença e acompanha comprovantes.', 'nexus-eventos') . '</p><div class="nxev-actions">';
        echo '<a class="button" href="' . esc_url(admin_url('post-new.php?post_type=' . EM_POST_TYPE_EVENT)) . '">' . esc_html__('Criar evento', 'nexus-eventos') . '</a><a class="button" href="' . esc_url(admin_url('edit.php?post_type=' . EM_POST_TYPE_EVENT)) . '">' . esc_html__('Gerenciar eventos e reservas', 'nexus-eventos') . '</a></div>';
        echo '<p><code>[nexus_eventos]</code> ' . esc_html__('Agenda pública com filtros.', 'nexus-eventos') . '<br><code>[nexus_eventos colecao="123"]</code> ' . esc_html__('Agenda de uma coleção.', 'nexus-eventos') . '<br><code>[nexus_minhas_inscricoes]</code> ' . esc_html__('Área do participante autenticado.', 'nexus-eventos') . '<br><code>[nexus_validar_comprovante]</code> ' . esc_html__('Consulta pública pelo código.', 'nexus-eventos') . '</p>';
        if (!defined('TAINACAN_VERSION')) {
            echo '<div class="notice notice-info inline"><p>' . esc_html__('Tainacan não está ativo. Você pode usar a agenda, mas os vínculos com acervos ficam indisponíveis.', 'nexus-eventos') . '</p></div>';
        }
        if (current_user_can('manage_options')) {
            echo '<details><summary>' . esc_html__('Identificação da instituição', 'nexus-eventos') . '</summary><form method="post" action="' . esc_url(admin_url('admin-post.php')) . '"><input type="hidden" name="action" value="nxev_settings">';
            wp_nonce_field('nxev-settings');
            echo '<label>' . esc_html__('Nome que aparecerá nos novos comprovantes', 'nexus-eventos') . ' <input type="text" name="institution" maxlength="250" value="' . esc_attr(get_option('nxev_institution', get_bloginfo('name'))) . '"></label><button class="button">' . esc_html__('Salvar', 'nexus-eventos') . '</button></form></details>';
        }
        echo '<h2>' . esc_html__('Presença e comprovantes', 'nexus-eventos') . '</h2><form method="get"><input type="hidden" name="page" value="nexus-eventos"><label>' . esc_html__('ID do evento no Events Manager', 'nexus-eventos') . ' <input type="number" name="event_id" min="1" value="' . ($event ? (int) $event->event_id : '') . '"></label><button class="button">' . esc_html__('Abrir participantes', 'nexus-eventos') . '</button></form>';
        if (!$event) {
            echo '<p>' . esc_html__('Informe um evento que você pode gerenciar. O ID aparece na listagem do Events Manager.', 'nexus-eventos') . '</p></div>';
            return;
        }
        echo '<h3>' . esc_html($event->event_name) . '</h3><p><a class="button" href="' . esc_url(wp_nonce_url(admin_url('admin-post.php?action=nxev_export&event_id=' . $event->event_id), 'nxev-export-' . $event->event_id)) . '">' . esc_html__('Exportar participantes e presença (CSV)', 'nexus-eventos') . '</a></p>';
        $page = max(1, absint(Public_UI::get('nxev_page', 1)));
        $rows = \EM_Bookings::get(array('event' => $event->event_id, 'owner' => false, 'status' => false,
            'scope' => 'all', 'limit' => 50, 'offset' => ($page - 1) * 50, 'orderby' => 'booking_id', 'order' => 'ASC'));
        $rows = iterator_to_array($rows);
        echo '<div class="nxev-table-wrap"><table class="widefat striped"><thead><tr><th>' . esc_html__('Inscrição', 'nexus-eventos') . '</th><th>' . esc_html__('Participante', 'nexus-eventos') . '</th><th>' . esc_html__('Estado', 'nexus-eventos') . '</th><th>' . esc_html__('Ações', 'nexus-eventos') . '</th></tr></thead><tbody>';
        foreach ($rows as $booking) {
            $attendance = Core::attendance($booking->booking_id);
            echo '<tr><td>' . (int) $booking->booking_id . '</td><td>' . esc_html($booking->get_person()->get_name()) . '</td><td>' . esc_html($booking->get_status()) . '<br>' . esc_html($attendance ? __('Presença registrada', 'nexus-eventos') : __('Sem presença', 'nexus-eventos')) . '</td><td>';
            if (Core::single_booking($booking) && Core::approved($booking)) {
                echo '<a href="' . esc_url(Core::pass_url($booking)) . '">' . esc_html__('Abrir passe', 'nexus-eventos') . '</a>';
                Public_UI::action_form($booking, 'checkin', __('Confirmar presença', 'nexus-eventos'));
            } else {
                echo esc_html__('Passe exige reserva aprovada de uma pessoa e sem horário fracionado.', 'nexus-eventos');
            }
            if ($attendance) { Public_UI::action_form($booking, 'undo', __('Desfazer presença', 'nexus-eventos')); }
            if (Core::certificate($booking->booking_id)) { Public_UI::action_form($booking, 'revoke', __('Revogar comprovante', 'nexus-eventos')); }
            echo '</td></tr>';
        }
        echo '</tbody></table></div><p>';
        if ($page > 1) { echo '<a href="' . esc_url(add_query_arg('nxev_page', $page - 1)) . '">' . esc_html__('Anterior', 'nexus-eventos') . '</a> '; }
        if (count($rows) === 50) { echo '<a href="' . esc_url(add_query_arg('nxev_page', $page + 1)) . '">' . esc_html__('Próxima', 'nexus-eventos') . '</a>'; }
        echo '</p></div>';
    }

    public static function export() {
        $event = self::selected_event();
        if (!$event) { wp_die('', '', array('response' => 403)); }
        check_admin_referer('nxev-export-' . $event->event_id);
        nocache_headers();
        header('Content-Type: text/csv; charset=UTF-8');
        header('Content-Disposition: attachment; filename="participantes-' . (int) $event->event_id . '.csv"');
        $stream = fopen('php://output', 'w');
        fwrite($stream, "\xEF\xBB\xBF");
        fputcsv($stream, array('Inscrição', 'Nome', 'E-mail', 'Vagas', 'Estado', 'Presença UTC', 'Comprovante'), ';', '"', '');
        for ($offset = 0; ; $offset += 100) {
            $rows = \EM_Bookings::get(array('event' => $event->event_id, 'owner' => false, 'status' => false,
                'scope' => 'all', 'limit' => 100, 'offset' => $offset, 'orderby' => 'booking_id', 'order' => 'ASC'));
        $rows = iterator_to_array($rows);
            foreach ($rows as $booking) {
                $attendance = Core::attendance($booking->booking_id);
                $cert = Core::certificate($booking->booking_id);
                $values = array($booking->booking_id, $booking->get_person()->get_name(), $booking->get_person()->user_email,
                    $booking->booking_spaces, $booking->get_status(), $attendance ? $attendance->checked_at : '',
                    $cert ? ($cert->revoked_at ? 'Revogado' : 'Emitido') : '');
                fputcsv($stream, array_map(array('Nexus_Eventos\Core', 'csv_cell'), $values), ';', '"', '');
            }
            if (count($rows) < 100) { break; }
        }
        fclose($stream);
        exit;
    }
}
