<?php
namespace EM\Thrive\Automator\ActionFields\Events_Manager\Event;

use Thrive\Automator\Utils;


if ( ! defined( 'ABSPATH' ) ) {
	exit; // Silence is golden!
}

/**
 * Class Url - representation of the URL field needed for the `Webhook` action
 *
 * @package EM\Thrive\Automator\Fields
 */
class Event_Status extends Event_Action_Field {

	/**
	 * Field name/label
	 */
	public static function get_name() {
		return __('Event Publish Status', 'events-manager-thrive-automator');
	}
	
	/**
	 * Field description
	 */
	public static function get_description() {
		return __('The publish status of the event', 'events-manager-thrive-automator');
	}
	
	
	public static function get_id() {
		return 'events-manager/event_status';
	}
	
	/**
	 * Campaigns will be displayed in a dropdown select
	 */
	public static function get_type() {
		return Utils::FIELD_TYPE_SELECT;
	}
	
	/**
	 * Function that returns an array with campaigns (id/name) that will be used in the select
	 *
	 * @return array|array[]
	 */
	public static function get_options_callback( $action_id, $action_data ) {
		return [
			[
				'id' => 'publish',
				'label' => __('Published'),
			],
			[
				'id' => 'pending',
				'label' => __('Pending Review'),
			],
			[
				'id' => 'draft',
				'label' => __('Draft'),
			],
		];
	}
}
