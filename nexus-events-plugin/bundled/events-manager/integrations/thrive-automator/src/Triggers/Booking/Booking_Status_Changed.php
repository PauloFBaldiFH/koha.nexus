<?php
namespace EM\Thrive\Automator\Triggers\Booking;

if ( ! defined( 'ABSPATH' ) ) {
	exit; // Silence is golden!
}

class Booking_Status_Changed extends Booking_Trigger {

	public static function get_id() {
		return 'events-manager/booking_status_changed';
	}

	public static function get_wp_hook() {
		return 'em_booking_status_changed';
	}

	public static function get_name() {
		return __('Booking Status Change', 'events-manager-thrive-automator');
	}

	public static function get_description() {
		return __('When a previously-made booking status has changed, does not include new bookings.', 'events-manager-thrive-automator');
	}
	
	/**
	 * @param array $data_objects
	 * @param \EM_Booking $EM_Booking
	 *
	 * @return array
	 */
	public function process_booking( $data_objects, $EM_Booking ){
		if( $EM_Booking->previous_status === false ){
			return $data_objects; // return empty array
		}
		return parent::process_booking( $data_objects, $EM_Booking );
	}
}