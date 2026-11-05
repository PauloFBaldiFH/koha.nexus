<?php
namespace EM\Thrive\Automator\DataFields\Booking;

if ( ! defined( 'ABSPATH' ) ) {
	exit; // Silence is golden!
}

class Booking_Price extends Booking_Field {

	public static function get_id() {
		return 'booking_price';
	}
	
	public static function get_supported_filters() {
		return [ 'number_comparison' ];
	}

	public static function get_name() {
		return __('Booking Price', 'events-manager-thrive-automator');
	}

	public static function get_description() {
		return __('The total price of the booking, including taxes, as a number.', 'events-manager-thrive-automator');
	}

	public static function get_dummy_value() {
		return '189.99';
	}
	
	public static function return_data_from_booking( $EM_Booking ){
		return $EM_Booking->get_price();
	}
	
	public static function get_field_value_type() {
		return static::TYPE_NUMBER;
	}
}
