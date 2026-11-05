<?php
/**
 * Displays a list of timeslots for booking.
 *
 * Serves two data sources:
 * - Default (single event): fetches Timeslot objects from the event's own timeranges via get_timeslots().
 * - Recurring + timeslot: $recurrences is injected by booking-recurrences.php as an array of EM_Event
 *   objects already scoped to the requested date/timezone via EM_Events::get(). When present, the
 *   get_timeslots() fetch is skipped entirely and the pre-queried items are rendered directly.
 */
/* @var EM_Event $EM_Event */
/* @var EM_Event $recurrences */
$id = $id ?? $EM_Event->event_id;
$scope = $scope ?? $EM_Event->event_start_date;
$timezone = $timezone ?? $EM_Event->event_timezone;
$timeslot_options = $timeslot_options ?? em_booking_timeslots_get_display_options( $EM_Event );
$title = $title ?? false;
$multiday = !empty($multiday) || !preg_match( '/^[0-9]{4}-[0-9]{2}-[0-9]{2}$/', $scope );
$show_no_recurrences = $show_no_recurrences ?? true;
$date_class = $multiday || $timeslot_options['show_dates'] ? 'has-dates' : '';

$use_events = isset( $recurrences );
$items      = $use_events ? $recurrences : $EM_Event->get_timeranges()->get_timeslots();
?>
<div id="em-booking-timeslots-<?php echo $id; ?>" class="em-booking-recurrences em-booking-timeslots <?php echo esc_attr( $date_class ); ?>" data-date="<?php echo esc_attr( $scope ); ?>">
	<?php if ( $title ) : ?><h3><?php echo esc_html( $title ); ?></h3><?php endif; ?>
	<?php if ( !empty( $items ) ) : ?>
		<?php if ( em_get_option('dbem_timezone_enabled') || $EM_Event->event_timezone !== em_get_option('timezone_string') ) : ?>
		<p class="em-timezone">
			<label for="recurrence-timezone-<?php echo $id; ?>"><span class="em-icon em-icon-map"></span>&nbsp;&nbsp;<?php esc_html_e('Timezone', 'events-manager'); ?></label>
			<select id="recurrence-timezone-<?php echo $id; ?>" name="recurrence_timezone" class="em-selectize recurrence_timezone">
				<?php echo wp_timezone_choice( $EM_Event->get_timezone()->getValue(), get_user_locale() ); ?>
			</select>
		</p>
		<?php endif; ?>
		<div class="em-booking-timeslots-list">
		<?php
		if ( $use_events ) {
			foreach ( $items as $EM_Event ) {
				$EM_Event->set_timezone( $timezone, false );
				$template_vars = $EM_Event->get_bookings()->get_booking_vars();
				$template_vars['id'] = $id;
				$template_vars['multiday'] = $multiday;
				$template_vars['scope'] = $scope;
				$template_vars['timeslot_options'] = $timeslot_options;
				em_locate_template( 'forms/bookingform/timeslots/timeslot.php', true, $template_vars );
			}
		} else {
			foreach ( $items as $Timeslot ) {
				if ( $Timeslot->timeslot_status === 0 ) continue;
				$EM_Event = $Timeslot->get_event();
				$template_vars = $EM_Event->get_bookings()->get_booking_vars();
				$template_vars['timeslot_options'] = $timeslot_options;
				em_locate_template( 'forms/bookingform/timeslots/timeslot.php', true, $template_vars );
			}
		}
		?>
		</div>
		<?php if ( $multiday ) : ?>
		<p class="more-recurrenes"><?php esc_html_e('Find more dates from the calendar.', 'events-manager'); ?></p>
		<?php endif; ?>
	<?php elseif ( $show_no_recurrences ) : ?>
		<div class="no-recurrences">
			<?php esc_html_e('No upcoming dates/times.', 'events-manager'); ?>
		</div>
	<?php endif; ?>
</div>
