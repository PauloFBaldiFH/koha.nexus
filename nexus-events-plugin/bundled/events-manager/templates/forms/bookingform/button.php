<?php
/* @var $EM_Event EM_Event */
/* @var $EM_Booking EM_Booking */

do_action('em_booking_form_before_buttons', $EM_Event); //do not delete
?>
<div class="em-booking-section em-booking-form-buttons em-booking-buttons">
	<?php do_action('em_booking_form_buttons_header', $EM_Event); //do not delete ?>
	<?php if( preg_match('/https?:\/\//',em_get_option('dbem_bookings_submit_button')) ): //Settings have an image url (we assume). Use it here as the button.?>
		<input type="image" src="<?php echo em_get_option('dbem_bookings_submit_button'); ?>" class="em-form-submit em-booking-submit" alt="<?php esc_html__('Booking Submit Button', 'events-manager'); ?>">
	<?php else: //Display normal submit button ?>
		<?php
		// show free or paid button by default
		$button_text = $EM_Booking && $EM_Booking->get_price_base() > 0 ?  str_replace('%s', $EM_Booking->get_price(true), em_get_option('dbem_bookings_submit_button_paid')) : em_get_option('dbem_bookings_submit_button');
		?>
		<input type="submit" class="em-form-submit em-booking-submit em-button em-button-1" value="<?php echo esc_attr($button_text); ?>"
		       data-text-free="<?php echo esc_attr(em_get_option('dbem_bookings_submit_button')); ?>"
		       data-text-payment="<?php echo esc_attr(em_get_option('dbem_bookings_submit_button_paid')); ?>"
		       data-text-processing="<?php echo esc_attr(em_get_option('dbem_bookings_submit_button_processing')); ?>">
	<?php endif; ?>
	<?php do_action('em_booking_form_buttons_footer', $EM_Event); //do not delete ?>
</div>
<?php
do_action('em_booking_form_footer_after_buttons', $EM_Event); //do not delete