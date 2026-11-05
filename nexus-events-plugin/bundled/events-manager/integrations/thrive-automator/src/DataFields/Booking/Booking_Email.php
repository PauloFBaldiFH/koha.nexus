<?php
namespace EM\Thrive\Automator\DataFields\Booking;

if ( ! defined( 'ABSPATH' ) ) {
	exit; // Silence is golden!
}

class Booking_Email extends Booking_Field {

	public static function get_id() {
		return 'booking_email';
	}
	
	public static function get_supported_filters() {
		return [ 'string_equals' ];
	}

	public static function get_name() {
		return __('Booking Email', 'events-manager-thrive-automator');
	}

	public static function get_description() {
		return __('Email associated with the booking.', 'events-manager-thrive-automator');
	}
	
	public static function get_dummy_value() {
		return 'someone@somewhere.com';
	}
	
	public static function get_validators() {
		return [ 'email' ];
	}
	
	public static function return_data_from_booking( $EM_Booking ){
		return $EM_Booking->get_person()->user_email;
	}
}
