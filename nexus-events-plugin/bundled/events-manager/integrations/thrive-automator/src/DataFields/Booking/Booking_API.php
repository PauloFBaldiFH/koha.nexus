<?php
namespace EM\Thrive\Automator\DataFields\Booking;

if ( ! defined( 'ABSPATH' ) ) {
	exit; // Silence is golden!
}

class Booking_API extends Booking_Field {

	public static function get_id() {
		return 'booking_api';
	}
	
	public static function get_supported_filters() {
		return [];
	}

	public static function get_name() {
		return __('API Data', 'events-manager-thrive-automator');
	}

	public static function get_description() {
		return __('A JSON-encodable array of data which would be supplied by the Events Manager API for the booking.', 'events-manager-thrive-automator');
	}
	
	public static function get_dummy_value() {
		return "{'booking_id':123, 'spaces':5, ... 'tickets': [...] ...}";
	}
	
	public static function return_data_from_booking( $EM_Booking ){
		return $EM_Booking->to_api();
	}
	
	public static function get_field_value_type() {
		return static::TYPE_ARRAY;
	}
}