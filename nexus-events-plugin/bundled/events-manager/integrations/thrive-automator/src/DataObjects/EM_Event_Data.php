<?php

namespace EM\Thrive\Automator\DataObjects;

use EM\Automation\Triggers\Event_Time;
use Thrive\Automator\Items\Data_Object;

use EM\Thrive\Automator\DataFields\Event\Event_ID;
use EM\Thrive\Automator\DataFields\Event\Event_Name;
use EM\Thrive\Automator\DataFields\Event\Event_Content;
use EM\Thrive\Automator\DataFields\Event\Event_StartDateTime;
use EM\Thrive\Automator\DataFields\Event\Event_EndDateTime;
use EM\Thrive\Automator\DataFields\Event\Event_Timezone;
use EM\Thrive\Automator\DataFields\Event\Event_ContactEmail;
use EM\Thrive\Automator\DataFields\Event\Event_ContactName;
use EM\Thrive\Automator\DataFields\Event\Event_Status;
use EM\Thrive\Automator\DataFields\Event\Event_Spaces;
use EM\Thrive\Automator\DataFields\Event\Event_Location;
use EM\Thrive\Automator\DataFields\Event\Event_Location_Name;
use EM\Thrive\Automator\DataFields\Event\Event_Location_Description;
use EM\Thrive\Automator\DataFields\Event\Event_EventLocation;
use EM\Thrive\Automator\DataFields\Event\Event_API;

if ( ! defined( 'ABSPATH' ) ) {
	exit; // Silence is golden!
}

class EM_Event_Data extends Data_Object {
	
	/**
	 * Get the data-object identifier
	 *
	 * @return string
	 */
	public static function get_id() {
		return 'em_event_data';
	}
	
	public static function get_nice_name() {
		return __( 'Event Data', 'events-manager-thrive-automator' );
	}
	
	/**
	 * Array of field object keys that are contained by this data-object
	 *
	 * @return array
	 */
	public static function get_fields() {
		return [
			Event_ID::get_id(),
			Event_Name::get_id(),
			Event_Content::get_id(),
			Event_StartDateTime::get_id(),
			Event_EndDateTime::get_id(),
			Event_Timezone::get_id(),
			Event_ContactEmail::get_id(),
			Event_ContactName::get_id(),
			Event_Status::get_id(),
			Event_Spaces::get_id(),
			Event_Location::get_id(),
			Event_Location_Name::get_id(),
			Event_Location_Description::get_id(),
			Event_EventLocation::get_id(),
			Event_API::get_id(),
		];
	}
	
	public static function create_object( $param ) {
		
		if ( is_a( $param, 'EM_Event' ) ) {
			$EM_Event = $param;
		} else {
			// can be usually an event id, null if not found or invalid data
			$EM_Event = em_get_event( $param );
		}
		
		if ( !empty($EM_Event) ) {
			/* @var \EM_Event $EM_Event */
			// get name and email
			if( $EM_Event->event_owner_anonymous ) {
				$email = $EM_Event->event_owner_email;
				$name = $EM_Event->event_owner_name;
			}else{
				$user_id = $EM_Event->get_owner();
				$user = new \WP_User($user_id);
				$email = $user->user_email;
				$name = trim($user->first_name . ' ' . $user->last_name);
			}
			$return = [
				'event_id'                => $EM_Event->event_id,
				'event_name'              => $EM_Event->event_name,
				'event_start'             => $EM_Event->start()->getDateTime( true ),
				'event_end'               => $EM_Event->end()->getDateTime( true ),
				'event_timezone'          => $EM_Event->event_timezone,
				'event_contact_name'      => $name,
				'event_contact_email'     => $email,
				'event_spaces'            => $EM_Event->get_spaces(),
				'location'                => null,
				'location_name'           => null,
				'location_content'        => null,
				'event_location'          => null,
				'event_post_status'       => $EM_Event->post_status,
				'event_api'               => $EM_Event->to_api(),
			];
			if( $EM_Event->has_event_location() ){
				$return['event_location'] = $EM_Event->get_event_location()->output();
			}
			if( $EM_Event->has_location() ){
				$return['location']	= $EM_Event->get_location()->get_full_address(true);
				$return['location_name']	= $EM_Event->get_location()->location_name;
				$return['location_content']	= $EM_Event->get_location()->post_content;
			}
			return $return;
		}
		
		return null;
	}
	
	public function can_provide_email() {
		return true;
	}
	
	public function get_provided_email() {
		return $this->get_value( Event_ContactEmail::get_id() );
	}
}
