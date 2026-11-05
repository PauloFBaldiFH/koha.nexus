<?php
namespace EM\Thrive\Automator\Actions\Events_Manager;

use EM\Thrive\Automator\Apps\Events_Manager;
use Thrive\Automator\Items\Action;

if ( ! defined( 'ABSPATH' ) ) {
	exit; // Silence is golden!
}

class Event_Add extends Action {

	public static function get_id() {
		return 'events-manager/event-add';
	}

	public static function get_name() {
		return 'Create Event';
	}

	public static function get_description() {
		return 'Create an event with the provided data.';
	}

	public static function get_image() {
		return Events_Manager::get_logo();
	}

	public static function get_app_id() {
		return Events_Manager::get_id();
	}

	/**
	 * This action requires only one action field for setup
	 *
	 * @return array
	 */
	public static function get_required_action_fields() {
		return [
			'events-manager/event_status',
			'events-manager/event_name',
			'events-manager/post_content',
			'events-manager/event_start',
			'events-manager/event_end',
			'events-manager/event_timezone',
		];
	}

	/**
	 * Get an array of keys with the required data-objects
	 *
	 * @return array
	 */
	public static function get_required_data_objects() {
		return [];
	}

	/**
	 * To implement actual action operation
	 */
	public function do_action( $data ) {
		$event_name = $this->get_automation_data_value( 'events-manager/event_name' );
		$event_description = $this->get_automation_data_value( 'events-manager/post_content' );
		$event_start = $this->get_automation_data_value( 'events-manager/event_start' );
		$event_end = $this->get_automation_data_value( 'events-manager/event_end' );
		$event_timezone = $this->get_automation_data_value( 'events-manager/event_timezone' );
		$event_status = $this->get_automation_data_value( 'events-manager/event_status' );

		$EM_Event = new \EM_Event();
		$EM_Event->event_name = sanitize_text_field($event_name);
		$EM_Event->post_content = wp_kses_post($event_description);
		$start = new \EM_DateTime($event_start, $event_timezone);
		$EM_Event->event_start_date = $start->getDate();
		$EM_Event->event_start_time = $start->getTime();
		$EM_Event->event_timezone = $start->getTimezone()->getName();
		$end = new \EM_DateTime($event_end, $event_timezone);
		$EM_Event->event_end_date = $end->getDate();
		$EM_Event->event_end_time = $end->getTime();
		// disable privacy consent
		remove_action('em_event_validate', ['\EM\Consent\Privacy', 'cpt_validate'], 10);
		remove_action('em_event_validate', ['\EM\Consent\Comms', 'cpt_validate'], 10);
		// validate and publish
		if( $EM_Event->validate() ){
			$event_status_map = [
				'publish' => 1,
				'pending' => 0,
				'draft' => null,
			];
			if( isset($event_status_map[$event_status]) ){
				$EM_Event->post_status = $event_status;
				$EM_Event->event_status = $event_status_map[$event_status];
			}
			$EM_Event->save();
		}
	}
}
