<?php
/*
 * Fixture of tests/tainacan_events_system.bats, run inside the throwaway
 * Tainacan of the test machine with WP-CLI:
 *   wp eval-file /work/events-fixture.php MODE [ARGS] --user=knadmin
 * MODE seed           a published collection, a past event (certificate on,
 *                     linked to the collection) and a future one, a
 *                     participant with an approved booking in each (the
 *                     passes), a pending booking (no pass), attendance and a
 *                     certificate for the past one. Prints one JSON line.
 * MODE render ID      the "Nexus" box of the event post ID, as the edit
 *                     screen draws it.
 * MODE delete BOOKING the booking deleted the way Events Manager does it;
 *                     prints what Nexus Eventos keeps of it.
 * MODE pass BOOKING   the pass link of a booking.
 * Never on a real site: it creates users, events and bookings.
 */
use Nexus_Eventos\Core;
use Nexus_Eventos\Admin;

$mode = $args[0] ?? '';
add_filter('pre_wp_mail', '__return_true');

function kn_fail($what) { fwrite(STDERR, $what . "\n"); exit(1); }

if ($mode === 'seed') {
    $admin = wp_get_current_user();
    $admin->add_cap('manage_bookings');
    $admin->add_cap('manage_others_bookings');
    update_option('dbem_bookings', 1);
    update_option('dbem_bookings_approval', 1);
    update_option('dbem_require_location', 0);

    $r = new WP_REST_Request('POST', '/tainacan/v2/collections');
    $r->set_header('content-type', 'application/json');
    $r->set_body(json_encode(array('name' => 'Acervo da oficina', 'status' => 'publish')));
    $res = rest_do_request($r);
    if ($res->get_status() >= 300) { kn_fail('collection: ' . json_encode($res->get_data())); }
    $collection = (int) $res->get_data()['id'];

    $event = function ($name, $offset, $end_offset) {
        $e = new EM_Event();
        $old_post = $_POST; $old_request = $_REQUEST;
        $_POST = array('event_name' => $name, 'content' => 'Oficina de memória.',
            'event_start_date' => gmdate('Y-m-d', time() + $offset), 'event_end_date' => gmdate('Y-m-d', time() + $end_offset),
            'event_timezone' => 'UTC', 'event_type' => 'single', 'event_active_status' => 1,
            'event_rsvp' => 1, 'event_spaces' => 5, 'event_rsvp_spaces' => 1, 'location_id' => 0,
            'event_timeranges' => array(array('start' => gmdate('H:i', time() + $offset), 'end' => gmdate('H:i', time() + $end_offset))));
        $_REQUEST = $_POST;
        $e->get_post(false);
        if (!$e->save()) { kn_fail('event: ' . implode(';', $e->get_errors())); }
        $_POST = $old_post; $_REQUEST = $old_request;
        update_post_meta($e->post_id, '_nxev_certificate', '1');
        update_post_meta($e->post_id, '_nxev_hours', '2.5');
        return $e;
    };
    $booking = function ($e, $person, $status) {
        $t = new EM_Ticket();
        $t->event_id = $e->event_id; $t->ticket_name = 'Inscrição'; $t->ticket_price = 0;
        $t->ticket_spaces = 5; $t->ticket_min = 1; $t->ticket_max = 1;
        if (!$t->save()) { kn_fail('ticket: ' . implode(';', $t->get_errors())); }
        $b = new EM_Booking();
        $b->event_id = $e->event_id; $b->person_id = $person; $b->booking_status = $status;
        $b->booking_spaces = 1; $b->manage_override = true;
        $seat = new EM_Ticket_Booking(array('ticket_id' => $t->ticket_id));
        $seat->booking = $b; $seat->ticket = $t;
        $b->get_tickets_bookings()->add($seat);
        if (!$b->save(false)) { kn_fail('booking: ' . implode(';', $b->get_errors())); }
        return em_get_booking($b->booking_id);
    };
    $past = $event('Oficina de memória', -7200, -3600);
    $future = $event('Visita ao acervo', 172800, 176400);
    update_post_meta($past->post_id, '_nxev_collections', array($collection));
    update_post_meta($past->post_id, '_nxev_collection_' . $collection, '1');
    $person = wp_insert_user(array('user_login' => 'participante', 'user_pass' => wp_generate_password(32),
        'user_email' => 'participante@example.invalid', 'display_name' => 'Érica da Conceição', 'role' => 'subscriber'));
    if (is_wp_error($person)) { kn_fail('user: ' . $person->get_error_message()); }
    $b1 = $booking($past, $person, 1);
    $b2 = $booking($future, $person, 1);
    $b3 = $booking($future, $person, 0);
    if (Core::checkin($b1) !== true) { kn_fail('checkin'); }
    $cert = Core::issue($b1);
    if (is_wp_error($cert)) { kn_fail('issue: ' . $cert->get_error_message()); }
    echo json_encode(array('collection' => $collection, 'collection_title' => 'Acervo da oficina',
        'event_post' => (int) $past->post_id, 'event' => (int) $past->event_id, 'future_post' => (int) $future->post_id,
        'b1' => (int) $b1->booking_id, 'b2' => (int) $b2->booking_id, 'b3' => (int) $b3->booking_id,
        'pass' => Core::pass_url($b1), 'pass_key' => Core::token($b1), 'code' => $cert->code,
        'verify' => add_query_arg('nxev_verify', $cert->code, home_url('/')))), "\n";
    exit(0);
}

if ($mode === 'render') {
    $post = get_post((int) ($args[1] ?? 0));
    if (!$post) { kn_fail('no post'); }
    ob_start();
    Admin::meta_fields($post);
    echo ob_get_clean();
    exit(0);
}

if ($mode === 'delete') {
    global $wpdb;
    $id = (int) ($args[1] ?? 0);
    $b = em_get_booking($id);
    if (!$b->booking_id || !$b->delete()) { kn_fail('delete'); }
    $cert = Core::certificate($id);
    echo json_encode(array(
        'attendance' => (int) $wpdb->get_var($wpdb->prepare('SELECT COUNT(*) FROM ' . Core::table('attendance') . ' WHERE booking_id=%d', $id)),
        'log' => (int) $wpdb->get_var($wpdb->prepare('SELECT COUNT(*) FROM ' . Core::table('log') . ' WHERE booking_id=%d', $id)),
        'certificate' => $cert ? array('participant' => $cert->participant, 'email' => $cert->subject_email, 'revoked' => $cert->revoked_at !== null) : null,
        'log_others' => (int) $wpdb->get_var('SELECT COUNT(*) FROM ' . Core::table('log')),
    )), "\n";
    exit(0);
}

if ($mode === 'pass') {
    echo Core::pass_url(em_get_booking((int) ($args[1] ?? 0))), "\n";
    exit(0);
}

kn_fail('mode?');
