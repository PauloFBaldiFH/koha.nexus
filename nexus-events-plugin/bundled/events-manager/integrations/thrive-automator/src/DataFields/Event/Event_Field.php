<?php
namespace EM\Thrive\Automator\DataFields\Event;

if ( ! defined( 'ABSPATH' ) ) {
	exit; // Silence is golden!
}

use Thrive\Automator\Items\Data_Field;

class Event_Field extends Data_Field {

	public static function get_id() {
		return 'EM_Event';
	}
	
	/**
	 * Array of filters that are supported by the field
	 * @return array
	 */
	public static function get_supported_filters() {
		return [];
	}

	public static function get_name() {
		return 'event Data (Generic)';
	}

	public static function get_description() {
		return 'Base Class for event_data';
	}

	public static function get_placeholder() {
		return static::get_dummy_value();
	}

	public static function get_dummy_value() {
		return '1';
	}
	
	/**
	 * We plan attach this data field to the em_event_data object
	 * @return string[]
	 */
	public static function get_compatible_data_objects() {
		return [ 'em_event_data' ];
	}

	/**
	 * Process the data and return the relevant field for the event.
	 *
	 * @param $data_object
	 * @param $raw_data
	 * @param $data_object_id
	 *
	 * @return mixed
	 */
	public static function process_data_value( $data_object, $raw_data, $data_object_id ) {

		if ( $data_object_id === 'em_event_data' ) {
			if ( is_a( $raw_data, 'EM_Event' ) ) {
				$EM_Event = $raw_data;
			} elseif ( is_numeric( $raw_data ) ) {
				$EM_Event = \em_get_event( $raw_data );
			}
			if( !empty($EM_Event) ){
				$data_object[ static::get_id() ] = static::return_data_from_event( $EM_Event );
			}else{
				$data_object[ static::get_id() ] = null;
			}
		}

		return $data_object;
	}
	
	/**
	 * Return data from the event that this field needs.
	 *
	 * @param \EM_Event $EM_Event
	 *
	 * @return mixed
	 */
	public static function return_data_from_event( $EM_Event ){
		return $EM_Event->to_api();
	}
	
	public static function get_field_value_type() {
		return static::TYPE_STRING;
	}
	
	public static function get_validators() {
		return [];
	}
}
