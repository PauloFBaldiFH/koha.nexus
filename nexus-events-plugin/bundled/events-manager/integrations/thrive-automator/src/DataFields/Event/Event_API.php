<?php
namespace EM\Thrive\Automator\DataFields\Event;

if ( ! defined( 'ABSPATH' ) ) {
	exit; // Silence is golden!
}

class Event_API extends Event_Field {

	public static function get_id() {
		return 'event_api';
	}
	
	public static function get_supported_filters() {
		return [];
	}

	public static function get_name() {
		return __('API Data', 'events-manager-thrive-automator');
	}

	public static function get_description() {
		return __('A JSON-encodable array of data which would be supplied by the Events Manager API for the event.', 'events-manager-thrive-automator');
	}
	
	public static function get_dummy_value() {
		return "{'event_id':123, 'spaces':5, ... 'tickets': [...] ...}";
	}
	
	public static function return_data_from_event( $EM_Event ){
		return $EM_Event->to_api();
	}
	
	public static function get_field_value_type() {
		return static::TYPE_ARRAY;
	}
}