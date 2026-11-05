<?php
namespace EM\Thrive\Automator\Triggers\Event;

if ( ! defined( 'ABSPATH' ) ) {
	exit; // Silence is golden!
}

class Event_Published extends Event_Trigger {
	
	protected $event_param_key = 1;

	public static function get_id() {
		return 'events-manager/event_published';
	}

	public static function get_wp_hook() {
		return 'em_event_save';
	}

	public static function get_name() {
		return __('Event Published', 'events-manager-thrive-automator');
	}

	public static function get_description() {
		return __('When an event has been publisehd.', 'events-manager-thrive-automator');
	}
	
	/**
	 * Override default method so we manually init user data if we can match the form's email with an existing user
	 *
	 * @param array $params
	 *
	 * @return array
	 * @see Automation::start()
	 */
	public function process_params( $params = array() ) {
		$data_objects = array();
		
		if ( ! empty( $params ) ) {
			$EM_Event = $params[$this->event_param_key]; /* @var \EM_Event $EM_Event */
			
			// add to data objects if actually published
			if( $EM_Event->previous_status != $EM_Event->event_status && $EM_Event->event_status == 1 ){
				$data_objects = $this->process_event( $data_objects, $EM_Event );
			}
		}
		
		return $data_objects;
	}
}
