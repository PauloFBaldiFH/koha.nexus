<?php
namespace EM\Thrive\Automator\ActionFields\Events_Manager\Booking;

use Thrive\Automator\Utils;


if ( ! defined( 'ABSPATH' ) ) {
	exit; // Silence is golden!
}

/**
 * Class Url - representation of the URL field needed for the `Webhook` action
 *
 * @package EM\Thrive\Automator\Fields
 */
class Booking_Ignore_Capacity extends Booking_Action_Field {

	/**
	 * Field name/label
	 */
	public static function get_name() {
		return __('Ignore Capacity If Fully Booked?', 'events-manager-thrive-automator');
	}
	
	/**
	 * Field description
	 */
	public static function get_description() {
		return __('If an event is fully booked and you are confirming a booking, unless capacity is ignored the booking will not be approved or confirmed.', 'events-manager-thrive-automator');
	}
	
	
	public static function get_id() {
		return 'events-manager/booking_ignore_capacity';
	}
	
	/**
	 * Campaigns will be displayed in a dropdown select
	 */
	public static function get_type() {
		return Utils::FIELD_TYPE_RADIO;
	}
	
	/**
	 * Function that returns an array with campaigns (id/name) that will be used in the select
	 *
	 * @return array|array[]
	 */
	public static function get_options_callback( $action_id, $action_data ) {
		$options = array();
		$scopes = array(
			1 => __('Yes'),
			0 => __('No'),
		);
		foreach( $scopes as $id => $label ){
			$options[] = [
				'id' => $id,
				'label' => $label,
			];
		}
		return $options;
	}
	
	public static function get_default_value(): string{
		return '0';
	}
}
