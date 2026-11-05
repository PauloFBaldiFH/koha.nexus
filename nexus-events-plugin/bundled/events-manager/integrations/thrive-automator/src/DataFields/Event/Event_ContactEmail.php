<?php
namespace EM\Thrive\Automator\DataFields\Event;

if ( ! defined( 'ABSPATH' ) ) {
	exit; // Silence is golden!
}

class Event_ContactEmail extends Event_Field {

	public static function get_id() {
		return 'event_contact_email';
	}
	
	public static function get_supported_filters() {
		return [ 'string_equals' ];
	}

	public static function get_name() {
		return __('event Email', 'events-manager-thrive-automator');
	}

	public static function get_description() {
		return __('Email associated with the event.', 'events-manager-thrive-automator');
	}
	
	public static function get_dummy_value() {
		return 'someone@somewhere.com';
	}
	
	public static function get_validators() {
		return [ 'email' ];
	}
	
	public static function return_data_from_event( $EM_Event ){
		// get name and email
		if( $EM_Event->event_owner_anonymous ) {
			$email = $EM_Event->event_owner_email;
		}else{
			$user_id = $EM_Event->get_owner();
			$user = new \WP_User($user_id);
			$email = $user->user_email;
		}
		return $email;
	}
}
