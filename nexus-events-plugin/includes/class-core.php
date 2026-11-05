<?php
namespace Nexus_Eventos;
defined('ABSPATH') || exit;

final class Core {
    public static function table($name) {
        global $wpdb;
        return $wpdb->prefix . 'nxev_' . $name;
    }

    public static function activate($network_wide = false) {
        if ($network_wide) {
            wp_die(esc_html__('Ative Nexus Eventos individualmente em cada site, não para toda a rede.', 'nexus-eventos'));
        }
        global $wpdb;
        require_once ABSPATH . 'wp-admin/includes/upgrade.php';
        $charset = $wpdb->get_charset_collate();
        $attendance = self::table('attendance');
        $certificates = self::table('certificates');
        $log = self::table('log');
        dbDelta("CREATE TABLE $attendance (
            booking_id bigint(20) unsigned NOT NULL,
            event_id bigint(20) unsigned NOT NULL,
            checked_at datetime NOT NULL,
            checked_by bigint(20) unsigned NOT NULL,
            subject_email varchar(254) NOT NULL DEFAULT '',
            PRIMARY KEY  (booking_id),
            KEY event_id (event_id)
        ) $charset;");
        dbDelta("CREATE TABLE $certificates (
            booking_id bigint(20) unsigned NOT NULL,
            code varchar(64) NOT NULL,
            participant varchar(250) NOT NULL,
            subject_email varchar(254) NOT NULL DEFAULT '',
            event_title varchar(250) NOT NULL,
            institution varchar(250) NOT NULL,
            event_date varchar(100) NOT NULL,
            hours decimal(6,2) NOT NULL DEFAULT 0,
            issued_at datetime NOT NULL,
            revoked_at datetime DEFAULT NULL,
            PRIMARY KEY  (booking_id),
            UNIQUE KEY code (code)
        ) $charset;");
        dbDelta("CREATE TABLE $log (
            id bigint(20) unsigned NOT NULL AUTO_INCREMENT,
            booking_id bigint(20) unsigned NOT NULL,
            actor bigint(20) unsigned NOT NULL,
            operation varchar(30) NOT NULL,
            created_at datetime NOT NULL,
            PRIMARY KEY  (id),
            KEY booking_id (booking_id)
        ) $charset;");
        update_option('nxev_schema', '2', false);
    }

    public static function boot() {
        if (get_option('nxev_schema') !== '2') {
            self::activate();
        }
        add_filter('em_booking_email_messages', array(__CLASS__, 'email_pass'), 20, 2);
        add_action('em_booking_deleted', array(__CLASS__, 'booking_deleted'));
        add_action('em_bookings_deleted', function ($result, $ids) {
            if ($result) {
                foreach ($ids as $id) { self::booking_deleted((object) array('booking_id' => (int) $id)); }
            }
        }, 10, 2);
        add_filter('wp_privacy_personal_data_exporters', array(__CLASS__, 'privacy_exporter'));
        add_filter('wp_privacy_personal_data_erasers', array(__CLASS__, 'privacy_eraser'));
    }

    public static function public_post($id) {
        $post = get_post($id);
        return $post && is_post_publicly_viewable($post) && !post_password_required($post) && $post->post_password === '';
    }

    public static function single_booking($booking) {
        return $booking && !empty($booking->booking_id) && (int) $booking->booking_spaces === 1 && empty($booking->timeslot_id);
    }

    public static function approved($booking) {
        if (!$booking || empty($booking->booking_id) || (int) $booking->booking_status !== 1) {
            return false;
        }
        $event = $booking->get_event();
        return $event && $event->event_id && (int) $event->event_status === 1 && (int) $event->event_active_status === 1;
    }

    public static function manager($booking) {
        return is_user_logged_in() && $booking && $booking->booking_id &&
            $booking->get_event()->can_manage('manage_bookings', 'manage_others_bookings');
    }

    public static function token($booking) {
        // Existing random upstream UUID plus site secret; no sequential-ID-only access.
        return hash_hmac('sha256', 'nxev-pass-v1|' . get_current_blog_id() . '|' . $booking->booking_id . '|' . $booking->booking_uuid, wp_salt('auth'));
    }

    public static function pass_url($booking) {
        return add_query_arg(array('nxev_pass' => (int) $booking->booking_id, 'nxev_key' => self::token($booking)), home_url('/'));
    }

    public static function viewer($booking, $token = '') {
        if (!$booking || !$booking->booking_id) {
            return false;
        }
        if (self::manager($booking) || (is_user_logged_in() && (int) $booking->person_id === get_current_user_id())) {
            return true;
        }
        return is_string($token) && preg_match('/^[a-f0-9]{64}$/D', $token) && hash_equals(self::token($booking), $token);
    }

    public static function email_pass($messages, $booking) {
        if (self::approved($booking) && self::single_booking($booking)) {
            $messages['user']['body'] .= "\n\n" . __('Seu passe e comprovante de participação:', 'nexus-eventos') . "\n" . self::pass_url($booking);
        }
        return $messages;
    }

    public static function attendance($id) {
        global $wpdb;
        return $wpdb->get_row($wpdb->prepare('SELECT * FROM ' . self::table('attendance') . ' WHERE booking_id=%d', $id));
    }

    public static function certificate($id) {
        global $wpdb;
        return $wpdb->get_row($wpdb->prepare('SELECT * FROM ' . self::table('certificates') . ' WHERE booking_id=%d', $id));
    }

    public static function log($id, $operation) {
        global $wpdb;
        return $wpdb->insert(self::table('log'), array('booking_id' => $id, 'actor' => get_current_user_id(),
            'operation' => $operation, 'created_at' => gmdate('Y-m-d H:i:s')));
    }

    public static function checkin($booking) {
        return self::locked($booking->booking_id, function () use ($booking) { return self::checkin_locked($booking); });
    }

    private static function locked($id, $operation) {
        global $wpdb;
        $key = 'nxev_' . substr(hash('sha256', DB_NAME . $wpdb->prefix . ':' . (int) $id), 0, 50);
        if ((int) $wpdb->get_var($wpdb->prepare('SELECT GET_LOCK(%s,5)', $key)) !== 1) {
            return new \WP_Error('busy', __('Esta inscrição está sendo atualizada. Tente novamente.', 'nexus-eventos'));
        }
        try { return $operation(); } finally { $wpdb->get_var($wpdb->prepare('SELECT RELEASE_LOCK(%s)', $key)); }
    }

    private static function checkin_locked($booking) {
        if (!self::manager($booking) || !self::approved($booking) || !self::single_booking($booking)) {
            return new \WP_Error('forbidden', __('É necessário gerenciar o evento e ter uma reserva individual aprovada, sem horário fracionado.', 'nexus-eventos'));
        }
        $now = time();
        $start = $booking->get_event()->start(true)->getTimestamp();
        if ($now < $start - DAY_IN_SECONDS) {
            return new \WP_Error('early', __('A presença pode ser registrada a partir de 24 horas antes do evento.', 'nexus-eventos'));
        }
        global $wpdb;
        // A unique booking key makes retries and simultaneous scans idempotent.
        $result = $wpdb->query($wpdb->prepare('INSERT IGNORE INTO ' . self::table('attendance') .
            ' (booking_id,event_id,checked_at,checked_by,subject_email) VALUES (%d,%d,%s,%d,%s)',
            $booking->booking_id, $booking->get_event()->event_id, gmdate('Y-m-d H:i:s'), get_current_user_id(), sanitize_email($booking->get_person()->user_email)));
        if ($result === false) {
            return new \WP_Error('storage', __('Não foi possível gravar a presença.', 'nexus-eventos'));
        }
        if ($result) {
            self::log($booking->booking_id, 'checkin');
        }
        return true;
    }

    public static function revoke($id) {
        return self::locked($id, function () use ($id) { return self::revoke_locked($id); });
    }

    private static function revoke_locked($id) {
        global $wpdb;
        $result = $wpdb->query($wpdb->prepare('UPDATE ' . self::table('certificates') .
            ' SET revoked_at=%s WHERE booking_id=%d AND revoked_at IS NULL', gmdate('Y-m-d H:i:s'), $id));
        if ($result) {
            self::log($id, 'revoke');
        }
        return $result !== false;
    }

    public static function issue($booking, $token = '') {
        return self::locked($booking->booking_id, function () use ($booking, $token) { return self::issue_locked($booking, $token); });
    }

    public static function undo($booking) {
        if (!self::manager($booking)) { return new \WP_Error('forbidden', __('Acesso negado.', 'nexus-eventos')); }
        return self::locked($booking->booking_id, function () use ($booking) {
            global $wpdb;
            if (!self::revoke_locked($booking->booking_id)) { return false; }
            $result = $wpdb->delete(self::table('attendance'), array('booking_id' => $booking->booking_id)) !== false;
            if ($result) { self::log($booking->booking_id, 'undo'); }
            return $result;
        });
    }

    private static function issue_locked($booking, $token = '') {
        if (!self::viewer($booking, $token) || !self::approved($booking) || !self::single_booking($booking) || !self::attendance($booking->booking_id)) {
            return new \WP_Error('ineligible', __('A emissão exige inscrição individual aprovada e presença registrada.', 'nexus-eventos'));
        }
        $event = $booking->get_event();
        if (!get_post_meta($event->post_id, '_nxev_certificate', true) || time() < $event->end(true)->getTimestamp()) {
            return new \WP_Error('not_ready', __('A emissão precisa estar habilitada e o evento deve ter terminado.', 'nexus-eventos'));
        }
        $existing = self::certificate($booking->booking_id);
        if ($existing) {
            return $existing->revoked_at ? new \WP_Error('revoked', __('Comprovante revogado. Procure a organização.', 'nexus-eventos')) : $existing;
        }
        global $wpdb;
        $data = array('booking_id' => $booking->booking_id, 'code' => bin2hex(random_bytes(32)),
            'participant' => mb_substr(sanitize_text_field($booking->get_person()->get_name()), 0, 250),
            'subject_email' => sanitize_email($booking->get_person()->user_email),
            'event_title' => mb_substr(sanitize_text_field($event->event_name), 0, 250),
            'institution' => mb_substr(sanitize_text_field(get_option('nxev_institution', get_bloginfo('name'))), 0, 250),
            'event_date' => $event->start()->format('d/m/Y'),
            'hours' => (float) get_post_meta($event->post_id, '_nxev_hours', true),
            'issued_at' => gmdate('Y-m-d H:i:s'));
        // Do not overwrite the original snapshot if two requests issue concurrently.
        $result = $wpdb->query($wpdb->prepare('INSERT IGNORE INTO ' . self::table('certificates') .
            ' (booking_id,code,participant,subject_email,event_title,institution,event_date,hours,issued_at) VALUES (%d,%s,%s,%s,%s,%s,%s,%f,%s)', array_values($data)));
        if ($result === false) {
            return new \WP_Error('storage', __('Não foi possível emitir o comprovante.', 'nexus-eventos'));
        }
        if ($result) {
            self::log($booking->booking_id, 'issue');
        }
        return self::certificate($booking->booking_id);
    }

    public static function booking_deleted($booking) {
        global $wpdb;
        $id = (int) $booking->booking_id;
        if ($id < 1) { return; }
        self::revoke($id);
        $wpdb->update(self::table('certificates'), array('participant' => '', 'subject_email' => ''), array('booking_id' => $id));
        $wpdb->delete(self::table('attendance'), array('booking_id' => $id));
        // The history of a deleted booking goes with it (who checked it in,
        // issued, undid or revoked). The anonymous, revoked certificate row
        // stays, so its public code keeps answering "revoked".
        $wpdb->delete(self::table('log'), array('booking_id' => $id));
    }

    public static function csv_cell($value) {
        $value = (string) $value;
        // Defend against spreadsheet formulas, including hidden leading whitespace.
        return preg_match('/^[\s\x00-\x1f]*[=+@-]/u', $value) ? "'" . $value : $value;
    }

    public static function collection($id) {
        return post_type_exists('tainacan-collection') && get_post_type($id) === 'tainacan-collection' && self::public_post($id);
    }

    public static function collection_ids($post_id) {
        return array_values(array_filter(array_map('absint', (array) get_post_meta($post_id, '_nxev_collections', true)), array(__CLASS__, 'collection')));
    }

    public static function privacy_exporter($exporters) {
        $exporters['nexus-eventos'] = array('exporter_friendly_name' => 'Nexus Eventos', 'callback' => array(__CLASS__, 'export_personal'));
        return $exporters;
    }

    public static function privacy_eraser($erasers) {
        $erasers['nexus-eventos'] = array('eraser_friendly_name' => 'Nexus Eventos', 'callback' => array(__CLASS__, 'erase_personal'));
        return $erasers;
    }

    private static function personal_bookings($email, $page) {
        global $wpdb;
        // Own email index also covers guest reservations and works after upstream erasure.
        return $wpdb->get_results($wpdb->prepare('SELECT booking_id FROM ' . self::table('attendance') .
            ' WHERE subject_email=%s UNION SELECT booking_id FROM ' . self::table('certificates') .
            ' WHERE subject_email=%s ORDER BY booking_id LIMIT 50 OFFSET %d',
            sanitize_email($email), sanitize_email($email), (max(1, (int) $page) - 1) * 50), ARRAY_A);
    }

    public static function export_personal($email, $page = 1) {
        $rows = self::personal_bookings($email, $page);
        $data = array();
        foreach ($rows as $row) {
            $id = (int) $row['booking_id'];
            $attendance = self::attendance($id);
            $cert = self::certificate($id);
            if ($attendance || $cert) {
                $fields = array(array('name' => 'Inscrição', 'value' => $id));
                if ($attendance) {
                    $fields[] = array('name' => 'Presença (UTC)', 'value' => $attendance->checked_at);
                }
                if ($cert) {
                    $fields[] = array('name' => 'Comprovante', 'value' => $cert->code);
                    $fields[] = array('name' => 'Participante', 'value' => $cert->participant);
                }
                $data[] = array('group_id' => 'nexus-eventos', 'group_label' => 'Nexus Eventos', 'item_id' => 'nxev-' . $id, 'data' => $fields);
            }
        }
        return array('data' => $data, 'done' => count($rows) < 50);
    }

    public static function erase_personal($email, $page = 1) {
        global $wpdb;
        // Erasing removes entries from this index; always take the first remaining batch.
        $rows = self::personal_bookings($email, 1);
        $removed = false;
        foreach ($rows as $row) {
            $id = (int) $row['booking_id'];
            self::revoke($id);
            $removed = (bool) $wpdb->update(self::table('certificates'), array('participant' => '', 'subject_email' => ''), array('booking_id' => $id)) || $removed;
            $removed = (bool) $wpdb->delete(self::table('attendance'), array('booking_id' => $id)) || $removed;
            $removed = (bool) $wpdb->delete(self::table('log'), array('booking_id' => $id)) || $removed;
        }
        return array('items_removed' => $removed, 'items_retained' => false, 'messages' => array(), 'done' => count($rows) < 50);
    }
}
