<?php
/**
 * Fetches the timeslot/recurrence list for a given scope and timezone, then delegates all
 * rendering to forms/bookingform/timeslots/timeslots.php, which is the canonical template for
 * displaying a list of bookable timeslots. Override that template (not this one) to customise output.
 */
/* @var EM_Event $EM_Event */
$id = $id ?? $EM_Event->event_id;
$scope = $scope ?? 'future';
$timezone = $timezone ?? $EM_Event->event_timezone;
$timeslot_options = em_booking_timeslots_get_display_options( $EM_Event );
$multiday = preg_match( '/^[0-9]{4}-[0-9]{2}-[0-9]{2}$/', $scope ) ? false : 'has-dates';
$show_no_recurrences = true;
if ( $multiday ) {
	$title = esc_html( sprintf( __('Upcoming %s', 'events-manager'), esc_html__('Events', 'events-manager') ) );
	if ( $scope == 'future' && !$timeslot_options['show_upcoming'] ) {
		$recurrences         = array();
		$show_no_recurrences = false;
	} else {
		$limit       = $scope == 'future' ? $timeslot_options['upcoming_limit'] : false;
		$recurrences = EM_Events::get( [ 'recurrence' => $EM_Event->event_id, 'scope' => $scope, 'timezone_scope' => $timezone, 'limit' => $limit ?: false, 'timeslots' => $EM_Event->has_timeslots() ] );
	}
} else {
	// specific date selected — output the date as heading
	$title       = date( em_get_date_format(), strtotime( $scope ) );
	if ( $EM_Event->is_recurring() ) {
		$recurrences = EM_Events::get( [ 'recurrence' => $EM_Event->event_id, 'scope' => $scope, 'timezone_scope' => $timezone, 'limit' => false, 'timeslots' => $EM_Event->has_timeslots() ] );
	} else {
		$recurrences = EM_Events::get( [ 'event' => $EM_Event->event_id, 'scope' => $scope, 'timezone_scope' => $timezone, 'limit' => false, 'timeslots' => $EM_Event->has_timeslots() ] );
	}
}
$template_vars = compact( 'id', 'scope', 'timezone', 'timeslot_options', 'title', 'multiday', 'show_no_recurrences', 'recurrences' );
$template_vars['EM_Event'] = $EM_Event;
em_locate_template( 'forms/bookingform/timeslots/timeslots.php', true, $template_vars );
