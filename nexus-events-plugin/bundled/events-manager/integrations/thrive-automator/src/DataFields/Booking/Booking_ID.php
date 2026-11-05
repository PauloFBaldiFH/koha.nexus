<?php
namespace EM\Thrive\Automator\DataFields\Booking;

if ( ! defined( 'ABSPATH' ) ) {
	exit; // Silence is golden!
}

class Booking_ID extends Booking_Field {

	public static function get_id() {
		return 'booking_id';
	}
	
	public static function get_supported_filters() {
		return [ 'number_comparison' ];
	}

	public static function get_name() {
		return __('Booking ID', 'events-manager-thrive-automator');
	}

	public static function get_description() {
		return __('The ID of the booking.', 'events-manager-thrive-automator');
	}
	
	public static function return_data_from_booking( $EM_Booking ){
		return $EM_Booking->booking_id;
	}
	
	public static function get_field_value_type() {
		return static::TYPE_NUMBER;
	}
}
