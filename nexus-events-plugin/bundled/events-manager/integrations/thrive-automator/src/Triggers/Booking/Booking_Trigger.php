<?php
namespace EM\Thrive\Automator\Triggers\Booking;

if ( ! defined( 'ABSPATH' ) ) {
	exit; // Silence is golden!
}

use EM\Thrive\Automator\Apps\Events_Manager;
use Thrive\Automator\Items\Data_Object;
use Thrive\Automator\Items\Trigger;

class Booking_Trigger extends Trigger {
	
	/**
	 * The EM_Booking arg number for the trigger's hook, for example if it's the first arg passed then it'd be 0, such as with em_booking_added and em_status_changed actions
	 *
	 * @var int
	 */
	protected $booking_param_key = 0;
	
	/* START Required Extendable Methods */
	public static function get_id() {
		return 'events-manager/booking_trigger';
	}
	
	public static function get_wp_hook() {
		return 'em_some_wo_hook';
	}
	
	public static function get_name() {
		return 'Extendable Booking Trigger';
	}
	
	public static function get_description() {
		return 'Extendable booking trigger for any booking trigger type.';
	}
	/* END Required Extendable Methods */

	public static function get_provided_data_objects() {
		return [ 'em_booking_data', 'user_data', 'email_data' ];
	}

	public static function get_hook_params_number() {
		return 2;
	}

	public static function get_app_id() {
		return Events_Manager::get_id();
	}

	public static function get_image() {
		return Events_Manager::get_logo();
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
			$EM_Booking = $params[$this->booking_param_key]; /* @var \EM_Booking $EM_Booking */
			$data_objects = $this->process_booking( $data_objects, $EM_Booking );
		}
		
		return $data_objects;
	}
	
	public function process_booking( $data_objects, $EM_Booking ){
		/* get all registered data objects and see which ones we use for this trigger */
		$data_object_classes = Data_Object::get();
		
		if( $EM_Booking->person_id !== 0 ) {
			if ( empty( $data_object_classes['user_data'] ) ) {
				/* if we don't have a class that parses the current param, we just leave the value as it is */
				$data_objects['user_data'] = $EM_Booking->get_person();
			} else {
				/* when a data object is available for the current parameter key, we create an instance that will handle the data */
				$data_objects['user_data'] = new $data_object_classes['user_data']( $EM_Booking->get_person(), $this->get_automation_id() );
			}
		}else{
			$data_objects['user_data'] = null;
		}
		
		$email = $EM_Booking->get_person()->user_email;
		if ( empty( $data_object_classes['email_data'] ) ) {
			/* if we don't have a class that parses the current param, we just leave the value as it is */
			$data_objects['email_data'] = $email;
		} else {
			/* when a data object is available for the current parameter key, we create an instance that will handle the data */
			$data_objects['email_data'] = new $data_object_classes['email_data']( $email, $this->get_automation_id() );
		}
		
		if ( empty( $data_object_classes['em_booking_data'] ) ) {
			/* if we don't have a class that parses the current param, we just leave the value as it is */
			$data_objects['em_booking_data'] = $EM_Booking;
		} else {
			/* when a data object is available for the current parameter key, we create an instance that will handle the data */
			$data_objects['em_booking_data'] = new $data_object_classes['em_booking_data']( $EM_Booking, $this->get_automation_id() );
		}
		return $data_objects;
	}
}

