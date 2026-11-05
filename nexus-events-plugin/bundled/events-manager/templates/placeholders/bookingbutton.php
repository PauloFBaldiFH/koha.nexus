<?php
/*
 * You can override this by copying this file to wp-content/themesyourthemefolder/plugins/events-manager/placeholders/ and modifying it however you need.
 * There are a few variables made available to you:
 * 
 * $EM_Event - EM_Event object 
 */
$notice_full = em_get_option('dbem_booking_button_msg_full');
$button_text = em_get_option('dbem_booking_button_msg_book');
$button_already_booked = em_get_option('dbem_booking_button_msg_already_booked');
$button_closed = em_get_option('dbem_booking_button_msg_closed');
$button_cancel = em_get_option('dbem_booking_button_msg_cancel');
/* @var $EM_Event EM_Event */
?>
<?php 
if( is_user_logged_in() ){ //only show this to logged in users
	ob_start();
	if ( $EM_Event->event_active_status === 0 ) {
		$notice_cancelled = em_get_option('dbem_booking_button_msg_event_cancelled');
		$status = 'event-cancelled'
		?><span class="em-closed-button"><?php echo $notice_cancelled ?></span><?php
	} else {
		$EM_Booking = $EM_Event->get_bookings()->has_booking();
		if( is_object($EM_Booking) && $EM_Booking->booking_status != 3 && em_get_option('dbem_bookings_user_cancellation') ){
			$status = 'cancel';
			$booking_id = $EM_Booking->booking_id;
			$nonce = wp_create_nonce('booking_cancel');
			?><a id="em-cancel-button_<?php echo $booking_id . '_' . $nonce; ?>" class="button em-cancel-button" href="#" data-booking_id="<?php echo $booking_id; ?>" data-_wpnonce="<?php echo $nonce; ?>" data-action="booking_cancel"><?php echo $button_cancel; ?></a><?php
		}elseif( $EM_Event->get_bookings()->is_open() ){
			if( !is_object($EM_Booking) ){
				$status = 'open';
				$event_id = absint($EM_Event->event_id);
				$nonce = wp_create_nonce('booking_add_one');
				?><a id="em-booking-button_<?php echo $event_id .'_'. $nonce; ?>" class="button em-booking-button" href="#"  data-event_id="<?php echo $event_id; ?>" data-_wpnonce="<?php echo $nonce; ?>" data-action="booking_add_one"><?php echo $button_text; ?></a><?php
			}else{
				$status = 'booked';
				?><span class="em-booked-button"><?php echo $button_already_booked ?></span><?php
			}
		}elseif( $EM_Event->get_bookings()->get_available_spaces() <= 0 ){
			$status = 'full'
			?><span class="em-full-button"><?php echo $notice_full ?></span><?php
		}else{
			$status = 'closed'
			?><span class="em-closed-button"><?php echo $button_closed ?></span><?php
		}
	}
	echo apply_filters( 'em_booking_button', ob_get_clean(), $EM_Event, $status, $EM_Booking ?? new EM_Booking() );
}; 
?>