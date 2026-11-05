<?php
namespace EM\Thrive\Automator\DataFields\Booking;

if ( ! defined( 'ABSPATH' ) ) {
	exit; // Silence is golden!
}

class Booking_LastName extends Booking_Field {

	public static function get_id() {
		return 'booking_lastname';
	}
	
	public static function get_supported_filters() {
		return [ 'string_equals' ];
	}

	public static function get_name() {
		return __('Last Name', 'events-manager-thrive-automator');
	}

	public static function get_description() {
		return __('Last name of person who made the booking.', 'events-manager-thrive-automator');
	}
	
	public static function get_dummy_value() {
		return 'Doe';
	}
	
	public static function return_data_from_booking( $EM_Booking ){
		return $EM_Booking->get_person()->user_lastname;
	}
}
