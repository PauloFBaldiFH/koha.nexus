<?php
/**
 * Plugin Name: Events Manager for Thrive Automator
 * Plugin URI: https://wp-events-plugin.com
 * Description: Adds triggers, actions and filters to the Thrive Automator
 * Author URI: https://pixelite.com
 * Version: 1.0
 * Author: <a href="https://pixelite.com">Pixelite</a>
 */

use EM\Thrive\Automator\Apps\Events_Manager;

use EM\Thrive\Automator\DataObjects\EM_Booking_Data;
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

use EM\Thrive\Automator\DataObjects\EM_Event_Data;
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

use EM\Thrive\Automator\Triggers\Booking\Booking_Added;
use EM\Thrive\Automator\Triggers\Booking\Booking_Status_Changed;
use EM\Thrive\Automator\Triggers\Event\Event_Published;
use EM\Thrive\Automator\Triggers\Event\Event_Added;
use EM\Thrive\Automator\Triggers\Event\Event_Status_Changed;

if ( ! defined( 'ABSPATH' ) ) {
	exit; // Silence is golden!
}

add_action( 'thrive_automator_init', static function () {
	
	// include everything, we'll be needing it down here anyway
	include('src/ActionFields/Events_Manager/Booking/Booking_Action_Field.php');
	include('src/ActionFields/Events_Manager/Booking/Booking_Ignore_Capacity.php');
	include('src/ActionFields/Events_Manager/Booking/Booking_Scope.php');
	include('src/ActionFields/Events_Manager/Booking/Booking_Send_Email.php');
	include('src/ActionFields/Events_Manager/Booking/Booking_Status.php');
	include('src/ActionFields/Events_Manager/Event/Event_Action_Field.php');
	include('src/ActionFields/Events_Manager/Event/Event_Content.php');
	include('src/ActionFields/Events_Manager/Event/Event_End.php');
	include('src/ActionFields/Events_Manager/Event/Event_Name.php');
	include('src/ActionFields/Events_Manager/Event/Event_Start.php');
	include('src/ActionFields/Events_Manager/Event/Event_Status.php');
	include('src/ActionFields/Events_Manager/Event/Event_Timezone.php');
	include('src/Actions/Events_Manager/Booking_User_Status.php');
	include('src/Actions/Events_Manager/Event_Add.php');
	include('src/Apps/Events_Manager.php');
	include('src/DataFields/Booking/Booking_Field.php');
	include('src/DataFields/Booking/Booking_API.php');
	include('src/DataFields/Booking/Booking_Email.php');
	include('src/DataFields/Booking/Booking_FirstName.php');
	include('src/DataFields/Booking/Booking_ID.php');
	include('src/DataFields/Booking/Booking_LastName.php');
	include('src/DataFields/Booking/Booking_Name.php');
	include('src/DataFields/Booking/Booking_Previous_Status.php');
	include('src/DataFields/Booking/Booking_Price.php');
	include('src/DataFields/Booking/Booking_Spaces.php');
	include('src/DataFields/Booking/Booking_Status.php');
	include('src/DataFields/Event/Event_Field.php');
	include('src/DataFields/Event/Event_API.php');
	include('src/DataFields/Event/Event_ContactEmail.php');
	include('src/DataFields/Event/Event_ContactName.php');
	include('src/DataFields/Event/Event_Content.php');
	include('src/DataFields/Event/Event_EndDateTime.php');
	include('src/DataFields/Event/Event_EventLocation.php');
	include('src/DataFields/Event/Event_ID.php');
	include('src/DataFields/Event/Event_Location.php');
	include('src/DataFields/Event/Event_Location_Description.php');
	include('src/DataFields/Event/Event_Location_Name.php');
	include('src/DataFields/Event/Event_Name.php');
	include('src/DataFields/Event/Event_Spaces.php');
	include('src/DataFields/Event/Event_StartDateTime.php');
	include('src/DataFields/Event/Event_Status.php');
	include('src/DataFields/Event/Event_Timezone.php');
	include('src/DataObjects/EM_Booking_Data.php');
	include('src/DataObjects/EM_Event_Data.php');
	include('src/Triggers/Booking/Booking_Trigger.php');
	include('src/Triggers/Booking/Booking_Added.php');
	include('src/Triggers/Booking/Booking_Status_Changed.php');
	include('src/Triggers/Event/Event_Trigger.php');
	include('src/Triggers/Event/Event_Added.php');
	include('src/Triggers/Event/Event_Published.php');
	include('src/Triggers/Event/Event_Status_Changed.php');
	
	thrive_automator_register_app( Events_Manager::class );
	
	thrive_automator_register_data_object( EM_Booking_Data::class );
	thrive_automator_register_data_field( Booking_ID::class );
	thrive_automator_register_data_field( Booking_Email::class );
	thrive_automator_register_data_field( Booking_Name::class );
	thrive_automator_register_data_field( Booking_FirstName::class );
	thrive_automator_register_data_field( Booking_LastName::class );
	thrive_automator_register_data_field( Booking_Status::class );
	thrive_automator_register_data_field( Booking_Previous_Status::class );
	thrive_automator_register_data_field( Booking_Spaces::class );
	thrive_automator_register_data_field( Booking_Price::class );
	thrive_automator_register_data_field( Booking_API::class );
	
	thrive_automator_register_data_object( EM_Event_Data::class );
	thrive_automator_register_data_field( Event_ID::class );
	thrive_automator_register_data_field( Event_Name::class );
	thrive_automator_register_data_field( Event_Content::class );
	thrive_automator_register_data_field( Event_StartDateTime::class );
	thrive_automator_register_data_field( Event_EndDateTime::class );
	thrive_automator_register_data_field( Event_Timezone::class );
	thrive_automator_register_data_field( Event_ContactEmail::class );
	thrive_automator_register_data_field( Event_ContactName::class );
	thrive_automator_register_data_field( Event_Status::class );
	thrive_automator_register_data_field( Event_Spaces::class );
	thrive_automator_register_data_field( Event_Location::class );
	thrive_automator_register_data_field( Event_Location_Name::class );
	thrive_automator_register_data_field( Event_Location_Description::class );
	thrive_automator_register_data_field( Event_EventLocation::class );
	thrive_automator_register_data_field( Event_API::class );
	
	thrive_automator_register_trigger( Booking_Added::class );
	thrive_automator_register_trigger( Booking_Status_Changed::class );
	thrive_automator_register_trigger( Event_Published::class );
	thrive_automator_register_trigger( Event_Added::class );
	thrive_automator_register_trigger( Event_Status_Changed::class );
	
	/* "Webhook" action registration */
	thrive_automator_register_action_field( \EM\Thrive\Automator\ActionFields\Events_Manager\Event\Event_Name::class );
	thrive_automator_register_action_field( \EM\Thrive\Automator\ActionFields\Events_Manager\Event\Event_Status::class );
	thrive_automator_register_action_field( \EM\Thrive\Automator\ActionFields\Events_Manager\Event\Event_Content::class );
	thrive_automator_register_action_field( \EM\Thrive\Automator\ActionFields\Events_Manager\Event\Event_Start::class );
	thrive_automator_register_action_field( \EM\Thrive\Automator\ActionFields\Events_Manager\Event\Event_End::class );
	thrive_automator_register_action_field( \EM\Thrive\Automator\ActionFields\Events_Manager\Event\Event_Timezone::class );
	thrive_automator_register_action( \EM\Thrive\Automator\Actions\Events_Manager\Event_Add::class );
	thrive_automator_register_action_field( \EM\Thrive\Automator\ActionFields\Events_Manager\Booking\Booking_Status::class );
	thrive_automator_register_action_field( \EM\Thrive\Automator\ActionFields\Events_Manager\Booking\Booking_Scope::class );
	thrive_automator_register_action_field( \EM\Thrive\Automator\ActionFields\Events_Manager\Booking\Booking_Send_Email::class );
	thrive_automator_register_action_field( \EM\Thrive\Automator\ActionFields\Events_Manager\Booking\Booking_Ignore_Capacity::class );
	thrive_automator_register_action( \EM\Thrive\Automator\Actions\Events_Manager\Booking_User_Status::class );
	/* end "Webhook" action registration */
} );