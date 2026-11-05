<?php
namespace EM\Thrive\Automator\DataFields\Booking;

if ( ! defined( 'ABSPATH' ) ) {
	exit; // Silence is golden!
}

class Booking_Name extends Booking_Field {

	public static function get_id() {
		return 'booking_name';
	}
	
	public static function get_supported_filters() {
		return [ 'string_equals' ];
	}

	public static function get_name() {
		return __('Full Name', 'events-manager-thrive-automator');
	}

	public static function get_description() {
		return __('Full name of person who made the booking.', 'events-manager-thrive-automator');
	}
	
	public static function get_dummy_value() {
		return 'John Doe';
	}
	
	public static function return_data_from_booking( $EM_Booking ){
		return $EM_Booking->get_person()->get_name();
	}
}
