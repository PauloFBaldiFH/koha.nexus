<?php
namespace EM\Thrive\Automator\DataFields\Booking;

if ( ! defined( 'ABSPATH' ) ) {
	exit; // Silence is golden!
}

use Thrive\Automator\Items\Data_Field;

class Booking_Field extends Data_Field {

	public static function get_id() {
		return 'em_booking';
	}
	
	/**
	 * Array of filters that are supported by the field
	 * @return array
	 */
	public static function get_supported_filters() {
		return [];
	}

	public static function get_name() {
		return 'Booking Data (Generic)';
	}

	public static function get_description() {
		return 'Base Class for booking_data';
	}

	public static function get_placeholder() {
		return static::get_dummy_value();
	}

	public static function get_dummy_value() {
		return '1';
	}
	
	/**
	 * We plan attach this data field to the em_booking_data object
	 * @return string[]
	 */
	public static function get_compatible_data_objects() {
		return [ 'em_booking_data' ];
	}

	/**
	 * Process the data and return the relevant field for the booking.
	 *
	 * @param $data_object
	 * @param $raw_data
	 * @param $data_object_id
	 *
	 * @return mixed
	 */
	public static function process_data_value( $data_object, $raw_data, $data_object_id ) {

		if ( $data_object_id === 'em_booking_data' ) {
			if ( is_a( $raw_data, 'EM_Booking' ) ) {
				$EM_Booking = $raw_data;
			} elseif ( is_numeric( $raw_data ) ) {
				$EM_Booking = \em_get_booking( $raw_data );
			}
			if( !empty($EM_Booking) ){
				$data_object[ static::get_id() ] = static::return_data_from_booking( $EM_Booking );
			}else{
				$data_object[ static::get_id() ] = null;
			}
		}

		return $data_object;
	}
	
	/**
	 * Return data from the booking that this field needs.
	 *
	 * @param \EM_Booking $EM_Booking
	 *
	 * @return mixed
	 */
	public static function return_data_from_booking( $EM_Booking ){
		return $EM_Booking->to_api();
	}
	
	public static function get_field_value_type() {
		return static::TYPE_STRING;
	}
	
	public static function get_validators() {
		return [];
	}
}
