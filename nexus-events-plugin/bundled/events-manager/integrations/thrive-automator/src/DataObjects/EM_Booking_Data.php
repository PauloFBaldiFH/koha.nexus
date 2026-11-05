<?php

namespace EM\Thrive\Automator\DataObjects;

use Thrive\Automator\Items\Data_Object;

use EM\Thrive\Automator\DataFields\Booking\Booking_ID;
use EM\Thrive\Automator\DataFields\Booking\Booking_Email;
use EM\Thrive\Automator\DataFields\Booking\Booking_Name;
use EM\Thrive\Automator\DataFields\Booking\Booking_FirstName;
use EM\Thrive\Automator\DataFields\Booking\Booking_LastName;
use EM\Thrive\Automator\DataFields\Booking\Booking_Status;
use EM\Thrive\Automator\DataFields\Booking\Booking_Previous_Status;
use EM\Thrive\Automator\DataFields\Booking\Booking_Spaces;
use EM\Thrive\Automator\DataFields\Booking\Booking_Price;
use EM\Thrive\Automator\DataFields\Booking\Booking_API;

if ( ! defined( 'ABSPATH' ) ) {
	exit; // Silence is golden!
}

class EM_Booking_Data extends Data_Object {
	
	/**
	 * Get the data-object identifier
	 *
	 * @return string
	 */
	public static function get_id() {
		return 'em_booking_data';
	}
	
	public static function get_nice_name() {
		return __( 'Booking Data', 'events-manager-thrive-automator' );
	}
	
	/**
	 * Array of field object keys that are contained by this data-object
	 *
	 * @return array
	 */
	public static function get_fields() {
		return [
			Booking_ID::get_id(),
			Booking_Email::get_id(),
			Booking_Name::get_id(),
			Booking_FirstName::get_id(),
			Booking_LastName::get_id(),
			Booking_Status::get_id(),
			Booking_Previous_Status::get_id(),
			Booking_Spaces::get_id(),
			Booking_Price::get_id(),
			Booking_API::get_id(),
		];
	}
	
	public static function create_object( $param ) {
		
		if ( is_a( $param, 'EM_Booking' ) ) {
			$EM_Booking = $param;
		} else {
			// can be usually a booking id or uid, null if not found or invalid data
			$EM_Booking = em_get_booking( $param );
		}
		
		if ( !empty($EM_Booking) ) { /* @var \EM_Booking $EM_Booking */
			return [
				'booking_id'      => $EM_Booking->booking_id,
				'booking_email'   => $EM_Booking->get_person()->user_email,
				'booking_name'   => $EM_Booking->get_person()->get_name(),
				'booking_firstname' => $EM_Booking->get_person()->first_name,
				'booking_lastname' => $EM_Booking->get_person()->last_name,
				'booking_spaces'  => $EM_Booking->booking_spaces,
				'booking_status'  => $EM_Booking->booking_status,
				'booking_previous_status' => $EM_Booking->previous_status,
				'booking_price'   => $EM_Booking->get_price(),
				'booking_api'     => $EM_Booking->to_api(),
			];
		}
		
		return null;
	}
	
	public function can_provide_email() {
		return true;
	}
	
	public function get_provided_email() {
		return $this->get_value( Booking_Email::get_id() );
	}
}
