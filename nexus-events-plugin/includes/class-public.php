<?php
namespace Nexus_Eventos;
defined('ABSPATH') || exit;

final class Public_UI {
    public static function boot() {
        add_shortcode('nexus_eventos', array(__CLASS__, 'agenda'));
        add_shortcode('nexus_minhas_inscricoes', array(__CLASS__, 'my_bookings'));
        add_shortcode('nexus_validar_comprovante', array(__CLASS__, 'verify_form'));
        add_filter('the_content', array(__CLASS__, 'related'), 30);
        add_action('wp_enqueue_scripts', array(__CLASS__, 'assets'));
        add_action('template_redirect', array(__CLASS__, 'route'), 1);
        add_action('template_redirect', function () {
            $post = get_queried_object();
            if ($post instanceof \WP_Post && has_shortcode($post->post_content, 'nexus_minhas_inscricoes')) {
                if (!defined('DONOTCACHEPAGE')) { define('DONOTCACHEPAGE', true); }
                nocache_headers();
                header('Cache-Control: private, no-store, max-age=0');
            }
        }, 0);
    }

    public static function assets() {
        wp_register_style('nxev', plugins_url('assets/events.css', NXEV_FILE), array(), NXEV_VERSION);
        // Small namespaced stylesheet, no replacement of the Tainacan theme.
        wp_enqueue_style('nxev');
    }

    public static function agenda($attributes = array()) {
        $atts = shortcode_atts(array('limite' => 12, 'colecao' => 0), $attributes, 'nexus_eventos');
        $limit = min(48, max(1, (int) $atts['limite']));
        $page = min(1000, max(1, absint(self::get('nxev_page', 1))));
        $search = sanitize_text_field(self::get('nxev_search', ''));
        $period = self::get('nxev_period', 'future') === 'past' ? 'past' : 'future';
        $category = absint(self::get('nxev_category', 0));
        $args = array('scope' => $period, 'limit' => $limit, 'page' => $page, 'pagination' => true,
            'private' => false, 'status' => 1, 'cancelled' => false, 'search' => mb_substr($search, 0, 150),
            'orderby' => 'event_start_date,event_start_time', 'order' => $period === 'past' ? 'DESC' : 'ASC');
        if ($category) {
            $args['category'] = $category;
        }
        // Collection filtering happens in SQL before pagination, not by truncating the results.
        $collection = absint($atts['colecao']);
        if ($collection) {
            if (!Core::collection($collection)) {
                return '<p>' . esc_html__('Coleção pública não encontrada.', 'nexus-eventos') . '</p>';
            }
            $posts = get_posts(array('post_type' => EM_POST_TYPE_EVENT, 'post_status' => 'publish', 'fields' => 'ids',
                'numberposts' => -1, 'meta_key' => '_nxev_collection_' . $collection, 'meta_value' => '1'));
            if (!$posts) {
                return '<p>' . esc_html__('Nenhum evento vinculado a esta coleção.', 'nexus-eventos') . '</p>';
            }
            $args['post_id'] = $posts;
        }
        $events = \EM_Events::get($args);
        $total = (int) \EM_Events::$num_rows_found;
        ob_start(); ?>
        <section class="nxev" aria-label="<?php esc_attr_e('Agenda de eventos', 'nexus-eventos'); ?>">
          <form class="nxev-filters" method="get" action="<?php echo esc_url(get_permalink()); ?>">
            <?php if (!get_option('permalink_structure')): ?><input type="hidden" name="page_id" value="<?php echo (int) get_queried_object_id(); ?>"><?php endif; ?>
            <label><?php esc_html_e('Pesquisar eventos', 'nexus-eventos'); ?><input name="nxev_search" maxlength="150" value="<?php echo esc_attr($search); ?>" type="search"></label>
            <label><?php esc_html_e('Período', 'nexus-eventos'); ?><select name="nxev_period"><option value="future" <?php selected($period, 'future'); ?>><?php esc_html_e('Próximos eventos', 'nexus-eventos'); ?></option><option value="past" <?php selected($period, 'past'); ?>><?php esc_html_e('Eventos anteriores', 'nexus-eventos'); ?></option></select></label>
            <?php if (defined('EM_TAXONOMY_CATEGORY') && taxonomy_exists(EM_TAXONOMY_CATEGORY)): ?>
            <label><?php esc_html_e('Categoria', 'nexus-eventos'); ?><select name="nxev_category"><option value="0"><?php esc_html_e('Todas', 'nexus-eventos'); ?></option>
              <?php foreach (get_terms(array('taxonomy' => EM_TAXONOMY_CATEGORY, 'hide_empty' => true)) as $term): ?>
              <option value="<?php echo (int) $term->term_id; ?>" <?php selected($category, $term->term_id); ?>><?php echo esc_html($term->name); ?></option>
              <?php endforeach; ?></select></label><?php endif; ?>
            <button type="submit"><?php esc_html_e('Filtrar', 'nexus-eventos'); ?></button>
          </form>
          <div class="nxev-grid">
          <?php foreach ($events as $event): if (!Core::public_post($event->post_id)) { continue; } ?>
            <article class="nxev-card">
              <?php echo get_the_post_thumbnail($event->post_id, 'medium_large', array('loading' => 'lazy')); ?>
              <div class="nxev-card-body">
                <time datetime="<?php echo esc_attr($event->start()->format(DATE_ATOM)); ?>"><?php echo esc_html($event->start()->format('d/m/Y H:i') . ' · ' . $event->event_timezone); ?></time>
                <h3><a href="<?php echo esc_url($event->get_permalink()); ?>"><?php echo esc_html($event->event_name); ?></a></h3>
                <p><?php echo esc_html(wp_trim_words(wp_strip_all_tags(strip_shortcodes($event->post_content)), 24)); ?></p>
                <?php $location = $event->get_location(); if ($location && $location->location_name): ?><p><?php echo esc_html($location->location_name); ?></p><?php endif; ?>
                <div class="nxev-actions"><a class="nxev-button" href="<?php echo esc_url($event->get_permalink()); ?>"><?php esc_html_e('Detalhes e inscrição', 'nexus-eventos'); ?></a><a href="<?php echo esc_url($event->get_ical_url()); ?>"><?php esc_html_e('Adicionar à agenda', 'nexus-eventos'); ?></a></div>
              </div>
            </article>
          <?php endforeach; ?>
          </div>
          <?php if (!$events): ?><p role="status"><?php esc_html_e('Nenhum evento encontrado.', 'nexus-eventos'); ?></p><?php endif; ?>
          <nav class="nxev-pagination" aria-label="<?php esc_attr_e('Páginas da agenda', 'nexus-eventos'); ?>">
            <?php if ($page > 1): ?><a href="<?php echo esc_url(add_query_arg('nxev_page', $page - 1)); ?>"><?php esc_html_e('Anterior', 'nexus-eventos'); ?></a><?php endif; ?>
            <?php if ($page * $limit < $total): ?><a href="<?php echo esc_url(add_query_arg('nxev_page', $page + 1)); ?>"><?php esc_html_e('Próxima', 'nexus-eventos'); ?></a><?php endif; ?>
          </nav>
        </section>
        <?php return ob_get_clean();
    }

    public static function related($content) {
        if (!is_singular() || !in_the_loop() || !is_main_query() || is_feed() || !Core::public_post(get_the_ID())) {
            return $content;
        }
        $id = get_the_ID();
        $type = get_post_type($id);
        if ($type === EM_POST_TYPE_EVENT) {
            $ids = Core::collection_ids($id);
            if (!$ids) { return $content; }
            $html = '<aside class="nxev nxev-related"><h2>' . esc_html__('Conheça o acervo relacionado', 'nexus-eventos') . '</h2><ul>';
            foreach ($ids as $collection) {
                $html .= '<li><a href="' . esc_url(get_permalink($collection)) . '">' . esc_html(get_the_title($collection)) . '</a></li>';
            }
            return $content . $html . '</ul></aside>';
        }
        if ($type === 'tainacan-collection') {
            return $content . '<aside class="nxev"><h2>' . esc_html__('Eventos desta coleção', 'nexus-eventos') . '</h2>' . self::agenda(array('colecao' => $id, 'limite' => 6)) . '</aside>';
        }
        return $content;
    }

    public static function my_bookings() {
        if (!is_user_logged_in()) {
            return '<p><a href="' . esc_url(wp_login_url(get_permalink())) . '">' . esc_html__('Entre para consultar suas inscrições.', 'nexus-eventos') . '</a></p>';
        }
        $page = max(1, absint(self::get('nxev_bookings_page', 1)));
        $rows = \EM_Bookings::get(array('person' => get_current_user_id(), 'owner' => false, 'status' => false,
            'scope' => 'all', 'limit' => 20, 'offset' => ($page - 1) * 20, 'orderby' => 'booking_id', 'order' => 'DESC'));
        $rows = iterator_to_array($rows);
        $html = '<div class="nxev"><ul class="nxev-bookings">';
        foreach ($rows as $booking) {
            $html .= '<li><strong>' . esc_html($booking->get_event()->event_name) . '</strong> · ' . esc_html($booking->get_status());
            if (Core::approved($booking) && Core::single_booking($booking)) {
                $html .= ' <a href="' . esc_url(Core::pass_url($booking)) . '">' . esc_html__('Passe e comprovante', 'nexus-eventos') . '</a>';
            }
            $html .= '</li>';
        }
        $html .= '</ul><p>' . esc_html__('Alterações e cancelamentos são feitos na área de reservas do Events Manager.', 'nexus-eventos') . '</p>';
        if ($page > 1) { $html .= '<a href="' . esc_url(add_query_arg('nxev_bookings_page', $page - 1)) . '">' . esc_html__('Anterior', 'nexus-eventos') . '</a> '; }
        if (count($rows) === 20) { $html .= '<a href="' . esc_url(add_query_arg('nxev_bookings_page', $page + 1)) . '">' . esc_html__('Próxima', 'nexus-eventos') . '</a>'; }
        return $html . '</div>';
    }

    public static function verify_form() {
        return '<form class="nxev nxev-filters" method="get" action="' . esc_url(home_url('/')) . '"><label>' .
            esc_html__('Código do comprovante', 'nexus-eventos') . '<input name="nxev_verify" pattern="[a-f0-9]{64}" maxlength="64" required></label><button>' .
            esc_html__('Verificar', 'nexus-eventos') . '</button></form>';
    }

    public static function get($key, $default = '') {
        return isset($_GET[$key]) && is_scalar($_GET[$key]) ? wp_unslash($_GET[$key]) : $default;
    }

    public static function private_headers() {
        nocache_headers();
        header('Cache-Control: private, no-store, max-age=0');
        header('Referrer-Policy: no-referrer');
        header('X-Robots-Tag: noindex, nofollow, noarchive');
        header('X-Content-Type-Options: nosniff');
        header("Content-Security-Policy: default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' data:; base-uri 'none'; form-action 'self'; frame-ancestors 'none'");
        header('Content-Type: text/html; charset=UTF-8');
    }

    private static function document_start($title) {
        self::private_headers();
        echo '<!doctype html><html ' . get_language_attributes() . '><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>' . esc_html($title) . '</title><link rel="stylesheet" href="' . esc_url(plugins_url('assets/events.css', NXEV_FILE)) . '"></head><body class="nxev-document"><main class="nxev">';
    }

    private static function document_end() {
        echo '</main><script src="' . esc_url(plugins_url('assets/vendor/qrcode.js', NXEV_FILE)) . '"></script><script src="' . esc_url(plugins_url('assets/documents.js', NXEV_FILE)) . '"></script></body></html>';
    }

    public static function route() {
        if (isset($_GET['nxev_verify'])) {
            self::verify_document(self::get('nxev_verify'));
            exit;
        }
        if (!isset($_GET['nxev_pass'])) { return; }
        $booking = em_get_booking(absint(self::get('nxev_pass')));
        $token = (string) self::get('nxev_key');
        if (!Core::single_booking($booking) || !Core::viewer($booking, $token) || !Core::approved($booking)) {
            self::private_headers();
            status_header(404);
            wp_die(esc_html__('Passe indisponível. Confira a inscrição ou entre com uma conta autorizada.', 'nexus-eventos'), '', array('response' => 404));
        }
        $cert = Core::certificate($booking->booking_id);
        if (self::get('nxev_document') === '1' && $cert && !$cert->revoked_at) {
            self::certificate_document($cert);
            exit;
        }
        self::document_start(__('Passe de participação', 'nexus-eventos'));
        echo '<h1>' . esc_html($booking->get_event()->event_name) . '</h1><p>' . esc_html($booking->get_person()->get_name()) . '</p><p>' .
            esc_html($booking->get_event()->start()->format('d/m/Y H:i') . ' · ' . $booking->get_event()->event_timezone) . '</p>';
        echo '<p>' . esc_html__('Inscrição aprovada. A leitura do QR não registra presença automaticamente; a equipe confirma após autenticar.', 'nexus-eventos') . '</p>';
        echo '<div class="nxev-qr" data-qr="' . esc_attr(Core::pass_url($booking)) . '"></div><p>' . esc_html__('Não compartilhe este endereço ou QR: ele dá acesso ao seu passe.', 'nexus-eventos') . '</p>';
        echo '<p>' . esc_html(Core::attendance($booking->booking_id) ? __('Presença registrada.', 'nexus-eventos') : __('Presença ainda não registrada.', 'nexus-eventos')) . '</p>';
        if (Core::manager($booking)) {
            self::action_form($booking, 'checkin', __('Confirmar presença', 'nexus-eventos'), $token);
            self::action_form($booking, 'undo', __('Desfazer presença e revogar comprovante', 'nexus-eventos'), $token);
        } else {
            echo '<p><a href="' . esc_url(wp_login_url(Core::pass_url($booking))) . '">' . esc_html__('Acesso da equipe', 'nexus-eventos') . '</a></p>';
        }
        if ($cert && !$cert->revoked_at) {
            echo '<p><a class="nxev-button" href="' . esc_url(add_query_arg('nxev_document', '1', Core::pass_url($booking))) . '">' . esc_html__('Abrir comprovante', 'nexus-eventos') . '</a></p>';
        } elseif (!$cert) {
            self::action_form($booking, 'issue', __('Emitir comprovante após o evento', 'nexus-eventos'), $token);
        } else {
            echo '<p>' . esc_html__('Comprovante revogado. Procure a organização.', 'nexus-eventos') . '</p>';
        }
        echo '<p><button type="button" data-print>' . esc_html__('Imprimir ou salvar como PDF', 'nexus-eventos') . '</button></p>';
        self::document_end();
        exit;
    }

    public static function action_form($booking, $operation, $label, $token = '') {
        echo '<form method="post" action="' . esc_url(admin_url('admin-post.php')) . '" class="nxev-action"><input type="hidden" name="action" value="nxev_action"><input type="hidden" name="booking_id" value="' . (int) $booking->booking_id . '"><input type="hidden" name="operation" value="' . esc_attr($operation) . '"><input type="hidden" name="pass_key" value="' . esc_attr($token) . '">';
        wp_nonce_field('nxev-' . $operation . '-' . $booking->booking_id);
        echo '<button type="submit">' . esc_html($label) . '</button></form>';
    }

    private static function verify_document($code) {
        global $wpdb;
        self::document_start(__('Verificação de comprovante', 'nexus-eventos'));
        $cert = is_string($code) && preg_match('/^[a-f0-9]{64}$/D', $code) ?
            $wpdb->get_row($wpdb->prepare('SELECT * FROM ' . Core::table('certificates') . ' WHERE code=%s', $code)) : null;
        $booking = $cert ? em_get_booking((int) $cert->booking_id) : null;
        $valid = $cert && !$cert->revoked_at && Core::approved($booking) && Core::attendance($cert->booking_id);
        echo '<h1>' . esc_html($valid ? __('Comprovante válido', 'nexus-eventos') : __('Comprovante não encontrado ou inválido', 'nexus-eventos')) . '</h1>';
        if ($valid) {
            echo '<p>' . esc_html($cert->institution) . '</p>';
            if (Core::public_post($booking->get_event()->post_id)) {
                echo '<p>' . esc_html($cert->event_title . ' · ' . $cert->event_date) . '</p>';
            }
            echo '<p>' . esc_html__('A identidade do participante não é publicada nesta consulta. Confira o documento apresentado com a organização.', 'nexus-eventos') . '</p>';
        }
        echo '<p>' . esc_html__('Esta verificação não equivale a assinatura digital qualificada.', 'nexus-eventos') . '</p>';
        self::document_end();
    }

    private static function certificate_document($cert) {
        self::document_start(__('Comprovante de participação', 'nexus-eventos'));
        $verify = add_query_arg('nxev_verify', $cert->code, home_url('/'));
        echo '<article class="nxev-certificate"><p>' . esc_html($cert->institution) . '</p><h1>' . esc_html__('Comprovante de participação', 'nexus-eventos') . '</h1><p>' . esc_html__('Certificamos a participação de', 'nexus-eventos') . '</p><h2>' . esc_html($cert->participant) . '</h2><p>' . esc_html($cert->event_title) . '</p><p>' . esc_html($cert->event_date) . '</p>';
        if ((float) $cert->hours > 0) {
            /* translators: %s: hours declared by the event organizer, formatted in the site locale. */
            echo '<p>' . esc_html(sprintf(__('Carga horária declarada pela organização: %s horas.', 'nexus-eventos'), number_format_i18n($cert->hours, 2))) . '</p>';
        }
        echo '<div class="nxev-qr" data-qr="' . esc_attr($verify) . '"></div><p class="nxev-code">' . esc_html($cert->code) . '</p><p><a href="' . esc_url($verify) . '">' . esc_html__('Verificar autenticidade', 'nexus-eventos') . '</a></p><p>' . esc_html__('Emitido em (UTC): ', 'nexus-eventos') . esc_html($cert->issued_at) . '</p></article><button type="button" data-print>' . esc_html__('Imprimir ou salvar como PDF', 'nexus-eventos') . '</button>';
        self::document_end();
    }
}
