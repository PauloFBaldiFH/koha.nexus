<?php
namespace EM\Thrive\Automator\DataFields\Event;

if ( ! defined( 'ABSPATH' ) ) {
	exit; // Silence is golden!
}

class Event_Location extends Event_Field {

	public static function get_id() {
		return 'location';
	}
	
	public static function get_supported_filters() {
		return [ 'string_equals' ];
	}

	public static function get_name() {
		return __('Location Address', 'events-manager-thrive-automator');
	}

	public static function get_description() {
		return __('Full address of event location.', 'events-manager-thrive-automator');
	}

	public static function get_dummy_value() {
		return '123 Some Street, Sometown, United States';
	}
	
	public static function return_data_from_event( $EM_Event ){
		if( $EM_Event->has_location() ){
			return $EM_Event->get_location()->get_full_address(true);
		}
		return null;
	}
}
