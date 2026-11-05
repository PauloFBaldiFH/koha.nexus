<?php
/**
 * This template will display bookings for a reurring event, by showing a list or calendar
 */
/* @var EM_Event $EM_Event */
/* @var EM_Booking $EM_Booking booking intent */
/* @var bool $tickets_count */
/* @var bool $available_tickets_count */
/* @var bool $can_book */
/* @var bool $is_open whether there are any available tickets right now */
/* @var bool $is_free */
/* @var bool $show_tickets */
/* @var bool $id */
/* @var bool $already_booked */
/* @var mixed $scope */
/* @var mixed $scope */
/* @var bool $multiday */
$can_book = $EM_Event->get_bookings()->is_open();
$timeslot_options = $timeslot_options ?? em_booking_timeslots_get_display_options( $EM_Event );
$available_spaces = $EM_Event->get_bookings()->get_available_spaces();
$is_fully_booked = $available_spaces <= 0 && !EM_Bookings::$disable_restrictions;
// a full occurrence may still be selectable, e.g. to join a waitlist, which can only be reached by loading its booking form
$can_book = apply_filters( 'em_booking_timeslot_can_book', $can_book, $EM_Event, $is_fully_booked );
if ( $is_fully_booked && !$timeslot_options['show_unavailable'] ) {
	return;
}
$event_id = $EM_Event->event_id;
?>
<a href="#<?php echo esc_attr( $EM_Event->start()->getDate() . '@' . $EM_Event->start()->getTime() ); ?>" class="em-booking-recurrence em-booking-timeslot em-item em-button button-secondary" <?php if ( !$can_book ) echo 'disabled'; ?> data-event="<?php echo esc_attr( $event_id ); ?>">
	<?php if ( $multiday ?? $timeslot_options['show_dates'] ): ?>
	<div class="em-booking-recurrence-date em-booking-timeslot-date">
		<span class="em-icon em-icon-calendar"></span><span><?php echo esc_html( $EM_Event->output_dates( $timeslot_options['date_format'] ?: false ) ); ?></span>
	</div>
	<?php endif; ?>
	<div class="em-booking-recurrence-time em-booking-timeslot-time">
		<span class="em-icon em-icon-clock"></span><span><?php echo esc_html( $EM_Event->output_times( $timeslot_options['time_format'] ?: false ) ); ?></span>
	</div>
	<?php if ( $timeslot_options['show_spaces'] || $is_fully_booked ) : ?>
	<div class="em-booking-recurrence-spaces em-booking-timeslot-spaces">
		<?php if( $already_booked && !em_get_option('dbem_bookings_double') ): //Double bookings not allowed ?>
			<?php do_action('em_booking_form_status_already_booked', $EM_Event); // do not delete ?>
		<?php elseif( !$EM_Event->event_rsvp ): //bookings not enabled ?>
			<?php do_action('em_booking_form_status_disabled', $EM_Event); // do not delete ?>
		<?php elseif( $EM_Event->event_active_status === 0 ): //event is cancelled ?>
			<?php do_action('em_booking_form_status_cancelled', $EM_Event); // do not delete ?>
		<?php elseif( $is_fully_booked ): ?>
			<?php echo esc_html( apply_filters( 'em_booking_timeslot_fully_booked_label', __('Fully Booked', 'events-manager'), $EM_Event ) ); ?>
		<?php elseif( !$is_open ): //event has started ?>
			<?php do_action('em_booking_form_status_closed', $EM_Event); // do not delete ?>
		<?php else : ?>
			<?php printf( _n('%d space', '%d spaces', $available_spaces, 'events-manager'), $available_spaces ); ?>
		<?php endif; ?>
	</div>
	<?php endif; ?>
</a>
