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
$id = $EM_Event->event_id;
?>
<section class="em-booking-recurring" data-event="<?php echo $EM_Event->event_id; ?>">
	<?php if ( em_get_option('dbem_recurrence_picker', 'select') === 'select' ) : ?>
		<div class="em-booking-recurrence-picker mode-<?php echo esc_attr( em_get_option('dbem_recurrence_picker' ) ); ?>">
			<select class="em-selectize" name="booking_recurrence_selection">
				<option value="0"><?php esc_html_e('Select a date', 'events-manager'); ?></option>
				<?php foreach( EM_Events::get( ['scope' => 'future', 'recurrence' => $EM_Event->event_id, 'limit' => false ] ) as $event ) : ?>
					<?php $format = $event->event_timezone !== $EM_Event->event_timezone ? '#_EVENTDATES @ #_EVENTTIMES (#_EVENTTIMEZONE)' : '#_EVENTDATES @ #_EVENTTIMES'; ?>
					<option value="<?php echo absint($event->event_id); ?>"><?php echo $event->output( $format ); ?></option>
				<?php endforeach; ?>
			</select>
		</div>
	<?php else: ?>
		<div class="em-booking-recurrence-picker mode-<?php echo esc_attr( em_get_option('dbem_recurrence_picker' ) ); ?>" data-nonce="<?php echo wp_create_nonce('booking_recurrences'); ?>">
			<?php include em_locate_template( 'forms/bookingform/recurring/calendar.php' ); ?>
			<?php include em_locate_template( 'forms/bookingform/recurring/booking-recurrences.php' ); ?>
		</div>
		<?php include em_locate_template( 'forms/bookingform/recurring/booking-recurrences-skeleton.php' ); ?>
	<?php endif; ?>

	<div id="em-booking-recurrence-form-<?php echo $id; ?>" class="em-booking-recurrence-form" data-nonce="<?php echo wp_create_nonce('booking_form'); ?>">
		<!-- booking form will go here -->
	</div>
	<?php include em_locate_template( 'forms/bookingform/summary-skeleton.php' ); ?>
</section>