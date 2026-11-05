<?php
namespace EM\Thrive\Automator\DataFields\Event;

if ( ! defined( 'ABSPATH' ) ) {
	exit; // Silence is golden!
}

class Event_Location_Name extends Event_Field {

	public static function get_id() {
		return 'location_name';
	}
	
	public static function get_supported_filters() {
		return [ 'string_equals' ];
	}

	public static function get_name() {
		return __('Location Name', 'events-manager-thrive-automator');
	}

	public static function get_description() {
		return __('Name of the event location.', 'events-manager-thrive-automator');
	}

	public static function get_dummy_value() {
		return 'Downtown Concert Hall';
	}
	
	public static function return_data_from_event( $EM_Event ){
		if( $EM_Event->has_location() ){
			return $EM_Event->get_location()->location_name;
		}
		return null;
	}
}
