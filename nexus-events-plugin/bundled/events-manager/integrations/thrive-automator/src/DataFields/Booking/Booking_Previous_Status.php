<?php
namespace EM\Thrive\Automator\DataFields\Booking;

if ( ! defined( 'ABSPATH' ) ) {
	exit; // Silence is golden!
}

class Booking_Previous_Status extends Booking_Field {

	public static function get_id() {
		return 'booking_previous_status';
	}
	
	public static function get_supported_filters() {
		return [ 'number_comparison' ];
	}

	public static function get_name() {
		return __('Booking Previous Status', 'events-manager-thrive-automator');
	}

	public static function get_description() {
		return __('The previous status number of the booking if just changed.', 'events-manager-thrive-automator');
	}
	
	public static function return_data_from_booking( $EM_Booking ){
		return $EM_Booking->previous_status;
	}
	
	public static function get_field_value_type() {
		return static::TYPE_NUMBER;
	}
}
