<?php
/** Run with wp eval-file in a disposable WordPress installation. */
use Nexus_Eventos\Core;
use Nexus_Eventos\Public_UI;
use Nexus_Eventos\Admin;

if (getenv('NXEV_TEST_RUN') !== 'disposable') {
    throw new RuntimeException('Only run on a disposable test site with NXEV_TEST_RUN=disposable');
}

$GLOBALS['nxev_checks'] = 0;
function nx_assert($condition, $message) {
    if (!$condition) { throw new RuntimeException('FAIL: ' . $message); }
    $GLOBALS['nxev_checks']++;
    echo 'PASS: ' . $message . "\n";
}
wp_set_current_user(1);
add_filter('pre_wp_mail', '__return_true');
update_option('dbem_bookings', 1);
update_option('dbem_bookings_approval', 1);
update_option('dbem_bookings_anonymous', 1);
$admin = get_userdata(1);
$admin->add_cap('manage_bookings');
$admin->add_cap('manage_others_bookings');
Core::activate();
Core::activate();
nx_assert(get_option('nxev_schema') === '2', 'schema installation is idempotent');
nx_assert(Nexus_Eventos\Dependency::verify_bundle(), 'unpacked upstream files match integrity manifest');
$unexpected = NXEV_DIR . '/bundled/events-manager/nxev-test-unexpected.txt';
file_put_contents($unexpected, 'unexpected');
nx_assert(!Nexus_Eventos\Dependency::verify_bundle(), 'unexpected bundled file is rejected');
unlink($unexpected);
nx_assert(Nexus_Eventos\Dependency::verify_bundle(), 'bundle verification recovers after cleanup');

function nx_event($name, $offset = -7200, $end_offset = -3600) {
    $event = new EM_Event();
    update_option('dbem_require_location', 0);
    $old_post = $_POST; $old_request = $_REQUEST;
    $_POST = array('event_name' => $name, 'content' => 'Uma oficina de memória e fotografia.',
        'event_start_date' => gmdate('Y-m-d', time() + $offset),
        'event_end_date' => gmdate('Y-m-d', time() + $end_offset),
        'event_timezone' => 'UTC', 'event_type' => 'single', 'event_active_status' => 1,
        'event_rsvp' => 1, 'event_spaces' => 2, 'event_rsvp_spaces' => 1, 'location_id' => 0,
        'event_timeranges' => array(array('start' => gmdate('H:i', time() + $offset), 'end' => gmdate('H:i', time() + $end_offset))));
    $_REQUEST = $_POST;
    $event->get_post(false);
    if (!$event->save()) { throw new RuntimeException('event: ' . implode(';', $event->get_errors())); }
    $_POST = $old_post; $_REQUEST = $old_request;
    update_post_meta($event->post_id, '_nxev_certificate', '1');
    update_post_meta($event->post_id, '_nxev_hours', '2.5');
    return $event;
}
$event = nx_event('Oficina de memória ' . wp_generate_password(5, false));
$future = nx_event('Visita ao museu ' . wp_generate_password(5, false), 172800, 176400);
$subscriber = wp_insert_user(array('user_login' => 'participante_' . wp_generate_password(6, false),
    'user_pass' => wp_generate_password(32), 'user_email' => 'p' . wp_generate_password(6, false) . '@example.invalid',
    'display_name' => 'Érica da Conceição', 'role' => 'subscriber'));
nx_assert(!is_wp_error($subscriber), 'participant account created');

function nx_booking($event, $person, $registration = array()) {
    $ticket = new EM_Ticket();
    $ticket->event_id = $event->event_id;
    $ticket->ticket_name = 'Inscrição gratuita';
    $ticket->ticket_price = 0;
    $ticket->ticket_spaces = 2;
    $ticket->ticket_min = 1;
    $ticket->ticket_max = 1;
    if (!$ticket->save()) { throw new RuntimeException('ticket: ' . implode(';', $ticket->get_errors())); }
    $booking = new EM_Booking();
    $booking->event_id = $event->event_id;
    $booking->person_id = $person;
    $booking->booking_status = 1;
    if ($registration) { $booking->booking_meta['registration'] = $registration; }
    $booking->booking_spaces = 1;
    $booking->manage_override = true;
    $seat = new EM_Ticket_Booking(array('ticket_id' => $ticket->ticket_id));
    $seat->booking = $booking;
    $seat->ticket = $ticket;
    $booking->get_tickets_bookings()->add($seat);
    if (!$booking->save(false)) { throw new RuntimeException('booking: ' . implode(';', $booking->get_errors())); }
    return $booking;
}
$booking = nx_booking($event, $subscriber);
$upcoming_booking = nx_booking($future, $subscriber);
nx_assert(Core::approved($booking), 'approved booking detected using real Events Manager');
nx_assert(Core::single_booking($booking), 'individual reservation detected');
$original_token = Core::token($booking);
nx_assert(strlen($original_token) === 64, 'pass token has expected entropy representation');
nx_assert(Core::viewer($booking), 'event administrator can view booking');
nx_assert(Core::checkin($booking) === true, 'administrator records attendance');
nx_assert(Core::checkin($booking) === true, 'repeated check-in is idempotent');
global $wpdb;
nx_assert((int) $wpdb->get_var($wpdb->prepare('SELECT COUNT(*) FROM ' . Core::table('attendance') . ' WHERE booking_id=%d', $booking->booking_id)) === 1, 'one attendance row per booking');
nx_assert(is_wp_error(Core::checkin($upcoming_booking)), 'check-in too early rejected');
nx_assert(is_wp_error(Core::issue($upcoming_booking)), 'future event cannot issue certificate');
$cert = Core::issue($booking);
nx_assert(!is_wp_error($cert) && strlen($cert->code) === 64, 'certificate created after attendance and end');
nx_assert(Core::issue($booking)->code === $cert->code, 'certificate issuance idempotent');
nx_assert($cert->participant === 'Érica da Conceição', 'accents preserved in snapshot');
update_post_meta($event->post_id, '_nxev_hours', 99);
nx_assert((float) Core::issue($booking)->hours === 2.5, 'issued certificate immutable when settings change');
$messages = Core::email_pass(array('user' => array('body' => 'Obrigado')), $booking);
nx_assert(strpos($messages['user']['body'], 'nxev_pass=') !== false, 'confirmation email gets pass link');

wp_set_current_user($subscriber);
nx_assert(Core::viewer($booking), 'participant can view own reservation');
nx_assert(!Core::manager($booking), 'participant is not event manager');
nx_assert(is_wp_error(Core::checkin($booking)), 'participant cannot mark own attendance');
nx_assert(strpos(Public_UI::my_bookings(), $event->event_name) !== false, 'my registrations uses native participant ownership');
wp_set_current_user(0);
nx_assert(!Core::viewer($booking), 'anonymous access without token denied');
nx_assert(!Core::viewer($booking, str_repeat('0', 64)), 'wrong bearer token denied');
nx_assert(Core::viewer($booking, $original_token), 'valid guest pass token accepted');
nx_assert(Core::issue($booking, $original_token)->code === $cert->code, 'guest with pass can recover own certificate');
$booking->booking_spaces = 2;
nx_assert(!Core::single_booking($booking), 'group reservation not treated as named individual');
$booking->booking_spaces = 1;
$booking->booking_status = 3;
nx_assert(!Core::approved($booking), 'cancelled reservation no longer accepted');
nx_assert(is_wp_error(Core::issue($booking, $original_token)), 'cancelled reservation cannot issue certificate');
$booking->booking_status = 1;
nx_assert(Core::csv_cell(' =HYPERLINK("x")')[0] === "'", 'CSV formula with whitespace neutralized');
nx_assert(Core::csv_cell('Érica') === 'Érica', 'CSV keeps ordinary Unicode text');

wp_set_current_user(1);
if (class_exists('Tainacan\Entities\Collection')) {
    $entity = new Tainacan\Entities\Collection();
    $entity->set_name('Coleção Memória');
    $entity->set_status('publish');
    if (!$entity->validate()) { throw new RuntimeException('collection validate'); }
    $entity = Tainacan\Repositories\Collections::get_instance()->insert($entity);
    $collection_id = $entity->get_id();
} else {
    throw new RuntimeException('Real Tainacan must be active for this test suite');
}
nx_assert(Core::collection($collection_id), 'real Tainacan public collection accepted');
$upload = wp_upload_bits('nxev-acervo-teste.png', null, base64_decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+a1ioAAAAASUVORK5CYII='));
nx_assert(empty($upload['error']), 'real image uploaded to WordPress');
$attachment = wp_insert_attachment(array('post_title' => 'Imagem do acervo', 'post_mime_type' => 'image/png', 'post_status' => 'inherit'), $upload['file']);
$item = new Tainacan\Entities\Item();
$item->set_collection($entity);
$item->set_title('Memória visual');
$item->set_document_type('attachment');
$item->set_document($attachment);
$item->set_status('draft');
if (!$item->validate()) { throw new RuntimeException('item validate'); }
$item = Tainacan\Repositories\Items::get_instance()->insert($item);
$original_file_hash = hash_file('sha256', $upload['file']);
nx_assert($item->get_id() > 0 && (int) $item->get_document() === $attachment, 'real Tainacan item references uploaded document');
$private_collection = wp_insert_post(array('post_type' => 'tainacan-collection', 'post_status' => 'private', 'post_title' => 'Acervo sigiloso'));
nx_assert(!Core::collection($private_collection), 'private collection rejected');
$_POST = array('nxev_meta_nonce' => wp_create_nonce('nxev-meta-' . $event->post_id), 'nxev_certificate' => 1,
    'nxev_hours' => '2.5', 'nxev_collections_present' => 1, 'nxev_collections' => array($collection_id, $private_collection));
Admin::save_meta($event->post_id, get_post($event->post_id));
$_POST = array();
nx_assert(Core::collection_ids($event->post_id) === array($collection_id), 'metabox stores public collections only');
nx_assert(hash_file('sha256', $upload['file']) === $original_file_hash &&
    (int) (new Tainacan\Entities\Item($item->get_id()))->get_document() === $attachment, 'event linking preserves Tainacan item and original file');
$_GET = array('nxev_period' => 'past');
$agenda = Public_UI::agenda(array('colecao' => $collection_id));
nx_assert(strpos($agenda, $event->event_name) !== false, 'collection-filtered agenda finds its event');
nx_assert(strpos($agenda, 'Acervo sigiloso') === false, 'private collection not leaked');
$_GET = array();
$_GET['nxev_search'] = $future->event_name;
nx_assert(strpos(Public_UI::agenda(), $future->event_name) !== false, 'future agenda renders real event');
$_GET = array();
$private_event = nx_event('Segredo nunca público', 172800, 176400);
wp_update_post(array('ID' => $private_event->post_id, 'post_status' => 'private'));
nx_assert(strpos(Public_UI::agenda(), 'Segredo nunca público') === false, 'private event not leaked to anonymous agenda');

$export = Core::export_personal(get_userdata($subscriber)->user_email);
nx_assert(count($export['data']) >= 1, 'WordPress personal-data export includes attendance and certificate');
Core::revoke($booking->booking_id);
nx_assert((bool) Core::certificate($booking->booking_id)->revoked_at, 'certificate revoked');
nx_assert(is_wp_error(Core::issue($booking)), 'revoked certificate not silently reissued');
$erase = Core::erase_personal(get_userdata($subscriber)->user_email);
nx_assert($erase['items_removed'], 'WordPress privacy eraser removes personal addon data');
nx_assert(Core::certificate($booking->booking_id)->participant === '', 'name removed from certificate snapshot');
nx_assert(!Core::attendance($booking->booking_id), 'attendance erased');

$guest = nx_booking($event, 0, array('user_name' => 'Visitante de teste', 'user_email' => 'convidado@example.invalid'));
nx_assert(Core::checkin($guest) === true, 'guest reservation can have attendance');
nx_assert(!is_wp_error(Core::issue($guest)), 'guest reservation can receive named document');
nx_assert(count(Core::export_personal('convidado@example.invalid')['data']) >= 1, 'privacy export covers guest without WordPress account');
nx_assert(Core::erase_personal('convidado@example.invalid')['items_removed'], 'privacy erasure covers guest without WordPress account');
nx_assert(Core::certificate($guest->booking_id)->subject_email === '', 'guest email removed from addon data');

$undo_booking = nx_booking($event, $subscriber);
Core::checkin($undo_booking);
Core::issue($undo_booking);
nx_assert(Core::undo($undo_booking) === true && !Core::attendance($undo_booking->booking_id) &&
    Core::certificate($undo_booking->booking_id)->revoked_at, 'serialized undo removes presence and revokes proof');

// A fresh active pass remains available for browser security tests.
$browser_booking = nx_booking($event, $subscriber);
Core::checkin($browser_booking);
$browser_cert = Core::issue($browser_booking);
$agenda_page = wp_insert_post(array('post_type' => 'page', 'post_status' => 'publish', 'post_title' => 'Agenda cultural', 'post_content' => '[nexus_eventos]'));
$member_page = wp_insert_post(array('post_type' => 'page', 'post_status' => 'publish', 'post_title' => 'Minhas inscrições', 'post_content' => '[nexus_minhas_inscricoes]'));
$session = WP_Session_Tokens::get_instance(1)->create(time() + HOUR_IN_SECONDS);
file_put_contents('/tmp/nxev-fixtures.json', wp_json_encode(array('booking_id' => $browser_booking->booking_id,
    'pass_url' => Core::pass_url($browser_booking), 'cert_code' => $browser_cert->code,
    'event_id' => $event->event_id, 'future_post' => $future->post_id,
    'agenda_url' => get_permalink($agenda_page), 'member_url' => get_permalink($member_page), 'participant' => $subscriber,
    'auth_cookie_name' => AUTH_COOKIE, 'auth_cookie' => wp_generate_auth_cookie(1, time() + HOUR_IN_SECONDS, 'auth', $session),
    'login_cookie_name' => LOGGED_IN_COOKIE, 'login_cookie' => wp_generate_auth_cookie(1, time() + HOUR_IN_SECONDS, 'logged_in', $session))));
echo 'INTEGRATION: ' . $GLOBALS['nxev_checks'] . " checks passed\n";
