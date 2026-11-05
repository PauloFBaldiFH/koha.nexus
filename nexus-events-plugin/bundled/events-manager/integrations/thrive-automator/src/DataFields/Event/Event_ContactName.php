<?php
namespace EM\Thrive\Automator\DataFields\Event;

if ( ! defined( 'ABSPATH' ) ) {
	exit; // Silence is golden!
}

class Event_ContactName extends Event_Field {

	public static function get_id() {
		return 'event_contact_name';
	}
	
	public static function get_supported_filters() {
		return [ 'string_equals' ];
	}

	public static function get_name() {
		return __('Contact Name', 'events-manager-thrive-automator');
	}

	public static function get_description() {
		return __('Contact Name associated with the event.', 'events-manager-thrive-automator');
	}
	
	public static function get_dummy_value() {
		return 'John Doe';
	}
	
	public static function get_validators() {
		return [];
	}
	
	public static function return_data_from_event( $EM_Event ){
		// get name and email
		if( $EM_Event->event_owner_anonymous ) {
			$name = $EM_Event->event_owner_name;
		}else{
			$user_id = $EM_Event->get_owner();
			$user = new \WP_User($user_id);
			$name = trim($user->first_name . ' ' . $user->last_name);
		}
		return $name;
	}
}
