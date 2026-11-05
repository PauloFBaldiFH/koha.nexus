<?php
namespace EM\API;

class Abilities {

	const CATEGORY_DATA = 'events-manager-data';
	const CATEGORY_MANAGEMENT = 'events-manager-management';

	public static function init() {
		if ( function_exists( 'wp_register_ability' ) && function_exists( 'wp_register_ability_category' ) ) {
			add_action( 'wp_abilities_api_categories_init', array( static::class, 'register_categories' ) );
			add_action( 'wp_abilities_api_init', array( static::class, 'register_abilities' ) );
		}
	}

	public static function register_categories() {
		wp_register_ability_category( static::CATEGORY_DATA, array(
			'label' => __( 'Events Manager Data', 'events-manager' ),
			'description' => __( 'Read-only abilities for retrieving Events Manager events, locations, bookings, categories, and tags.', 'events-manager' ),
		) );
		wp_register_ability_category( static::CATEGORY_MANAGEMENT, array(
			'label' => __( 'Events Manager Management', 'events-manager' ),
			'description' => __( 'Abilities that create, update, delete, or otherwise modify Events Manager data.', 'events-manager' ),
		) );
	}

	public static function register_abilities() {
		static::register_data_ability( 'list-events', __( 'List events', 'events-manager' ), __( 'Retrieves a filtered collection of Events Manager events.', 'events-manager' ), Schemas::collection_input(), array( static::class, 'list_events' ) );
		static::register_data_ability( 'get-event', __( 'Get event', 'events-manager' ), __( 'Retrieves one Events Manager event by ID.', 'events-manager' ), Schemas::id_input( __( 'Event ID or event ID with timeslot suffix.', 'events-manager' ) ), array( static::class, 'get_event' ) );
		static::register_data_ability( 'get-event-availability', __( 'Get event availability', 'events-manager' ), __( 'Retrieves booking availability, spaces, and ticket availability for one event.', 'events-manager' ), Schemas::id_input( __( 'Event ID or event ID with timeslot suffix.', 'events-manager' ) ), array( static::class, 'get_event_availability' ) );
		static::register_data_ability( 'get-booking-requirements', __( 'Get booking requirements', 'events-manager' ), __( 'Returns the exact fields, payload locations, payment options, and a ready-to-submit example payload needed to create a booking for one event. Call this before create-booking.', 'events-manager' ), Schemas::id_input( __( 'Event ID or event ID with timeslot suffix.', 'events-manager' ) ), array( static::class, 'get_booking_requirements' ) );
		static::register_data_ability( 'list-event-tickets', __( 'List event tickets', 'events-manager' ), __( 'Retrieves tickets for one Events Manager event.', 'events-manager' ), Schemas::id_input( __( 'Event ID or event ID with timeslot suffix.', 'events-manager' ) ), array( static::class, 'list_event_tickets' ) );
		static::register_data_ability( 'get-ticket', __( 'Get ticket', 'events-manager' ), __( 'Retrieves one Events Manager ticket by ID.', 'events-manager' ), Schemas::id_input( __( 'Ticket ID.', 'events-manager' ) ), array( static::class, 'get_ticket' ) );
		static::register_management_ability( 'create-event', __( 'Create event', 'events-manager' ), __( 'Creates an Events Manager event.', 'events-manager' ), Schemas::event_input(), array( static::class, 'create_event' ), array( static::class, 'can_edit_events' ), array( 'destructive' => false, 'idempotent' => false ) );
		static::register_management_ability( 'update-event', __( 'Update event', 'events-manager' ), __( 'Updates an Events Manager event.', 'events-manager' ), Schemas::event_input( true ), array( static::class, 'update_event' ), array( static::class, 'can_edit_events' ), array( 'destructive' => true, 'idempotent' => false ) );
		static::register_management_ability( 'delete-event', __( 'Delete event', 'events-manager' ), __( 'Deletes or trashes an Events Manager event.', 'events-manager' ), Schemas::id_input( __( 'Event ID.', 'events-manager' ) ), array( static::class, 'delete_event' ), array( static::class, 'can_delete_events' ), array( 'destructive' => true, 'idempotent' => false ) );
		static::register_management_ability( 'create-event-ticket', __( 'Create event ticket', 'events-manager' ), __( 'Creates a ticket for an Events Manager event.', 'events-manager' ), Schemas::ticket_input( false, true ), array( static::class, 'create_event_ticket' ), array( static::class, 'can_manage_bookings' ), array( 'destructive' => false, 'idempotent' => false ) );
		static::register_management_ability( 'update-ticket', __( 'Update ticket', 'events-manager' ), __( 'Updates an Events Manager ticket.', 'events-manager' ), Schemas::ticket_input( true ), array( static::class, 'update_ticket' ), array( static::class, 'can_manage_bookings' ), array( 'destructive' => true, 'idempotent' => false ) );
		static::register_management_ability( 'delete-ticket', __( 'Delete ticket', 'events-manager' ), __( 'Deletes an Events Manager ticket if it has no bookings.', 'events-manager' ), Schemas::id_input( __( 'Ticket ID.', 'events-manager' ) ), array( static::class, 'delete_ticket' ), array( static::class, 'can_manage_bookings' ), array( 'destructive' => true, 'idempotent' => false ) );

		static::register_data_ability( 'list-locations', __( 'List locations', 'events-manager' ), __( 'Retrieves a filtered collection of Events Manager locations.', 'events-manager' ), Schemas::collection_input(), array( static::class, 'list_locations' ) );
		static::register_data_ability( 'list-location-countries', __( 'List location countries', 'events-manager' ), __( 'Returns countries with their ISO-3166 alpha-2 code and translated display name. By default returns the full ISO list — useful for populating a country picker. Pass `only_available: true` to narrow the result to countries that have at least one stored location row.', 'events-manager' ), Schemas::location_geo_input( array( 'only_available' ) ), array( static::class, 'list_location_countries' ) );
		static::register_data_ability( 'list-location-regions', __( 'List location regions', 'events-manager' ), __( 'Returns the distinct list of region names present in Events Manager locations. Pass `country` to narrow results to one country.', 'events-manager' ), Schemas::location_geo_input( array( 'country' ) ), array( static::class, 'list_location_regions' ) );
		static::register_data_ability( 'list-location-states', __( 'List location states', 'events-manager' ), __( 'Returns the distinct list of state/province names present in Events Manager locations. Pass `country` and/or `region` to narrow results.', 'events-manager' ), Schemas::location_geo_input( array( 'country', 'region' ) ), array( static::class, 'list_location_states' ) );
		static::register_data_ability( 'list-location-towns', __( 'List location towns', 'events-manager' ), __( 'Returns the distinct list of town/city names present in Events Manager locations. Pass `country`, `region`, and/or `state` to narrow results.', 'events-manager' ), Schemas::location_geo_input( array( 'country', 'region', 'state' ) ), array( static::class, 'list_location_towns' ) );
		static::register_data_ability( 'get-location', __( 'Get location', 'events-manager' ), __( 'Retrieves one Events Manager location by ID.', 'events-manager' ), Schemas::id_input( __( 'Location ID.', 'events-manager' ) ), array( static::class, 'get_location' ) );
		static::register_management_ability( 'create-location', __( 'Create location', 'events-manager' ), __( 'Creates an Events Manager location.', 'events-manager' ), Schemas::location_input(), array( static::class, 'create_location' ), array( static::class, 'can_edit_locations' ), array( 'destructive' => false, 'idempotent' => false ) );
		static::register_management_ability( 'update-location', __( 'Update location', 'events-manager' ), __( 'Updates an Events Manager location.', 'events-manager' ), Schemas::location_input( true ), array( static::class, 'update_location' ), array( static::class, 'can_edit_locations' ), array( 'destructive' => true, 'idempotent' => false ) );
		static::register_management_ability( 'delete-location', __( 'Delete location', 'events-manager' ), __( 'Deletes or trashes an Events Manager location.', 'events-manager' ), Schemas::id_input( __( 'Location ID.', 'events-manager' ) ), array( static::class, 'delete_location' ), array( static::class, 'can_delete_locations' ), array( 'destructive' => true, 'idempotent' => false ) );

		static::register_management_ability( 'upload-media', __( 'Upload media', 'events-manager' ), __( 'Uploads an image (or other media) to the WordPress media library and returns its attachment ID. Accepts a `source_url` to sideload a public image, base64-encoded bytes via `content_base64` + `filename`, or an existing `id` to look up an existing attachment. If a public URL blocks server-side fetches (e.g. Unsplash) use `content_base64` instead. To make the upload an event/location featured image in one call, pass `featured_image_for_event` / `featured_image_for_location`; otherwise pass the returned ID as `featured_image` to update-event / update-location, or as `image` to update-category / update-tag. (Note: `post_id` only files the attachment under a post in the library — it does NOT set the featured image.)', 'events-manager' ), Schemas::media_upload_input(), array( static::class, 'upload_media' ), array( static::class, 'can_upload_files' ), array( 'destructive' => false, 'idempotent' => false ) );

		static::register_data_ability( 'list-bookings', __( 'List bookings', 'events-manager' ), __( 'Retrieves bookings visible to the current user.', 'events-manager' ), Schemas::collection_input(), array( static::class, 'list_bookings' ), array( static::class, 'can_read_bookings' ) );
		static::register_data_ability( 'get-booking', __( 'Get booking', 'events-manager' ), __( 'Retrieves one booking by ID if visible to the current user.', 'events-manager' ), Schemas::id_input( __( 'Booking ID.', 'events-manager' ) ), array( static::class, 'get_booking' ), array( static::class, 'can_read_bookings' ) );
		static::register_management_ability( 'create-booking', __( 'Create booking', 'events-manager' ), __( "Creates an Events Manager booking. Call get-booking-requirements first to get this event's required fields, payload locations, and an example payload.", 'events-manager' ), Schemas::booking_input(), array( static::class, 'create_booking' ), array( static::class, 'can_create_booking' ), array( 'destructive' => false, 'idempotent' => false ) );
		static::register_management_ability( 'update-booking', __( 'Update booking', 'events-manager' ), __( 'Updates an Events Manager booking.', 'events-manager' ), Schemas::booking_input( true ), array( static::class, 'update_booking' ), array( static::class, 'can_manage_bookings' ), array( 'destructive' => true, 'idempotent' => false ) );
		static::register_management_ability( 'set-booking-status', __( 'Set booking status', 'events-manager' ), __( 'Changes a booking status, such as approving, rejecting, or cancelling it.', 'events-manager' ), Schemas::booking_status_input(), array( static::class, 'set_booking_status' ), array( static::class, 'can_manage_bookings' ), array( 'destructive' => true, 'idempotent' => true ) );
		static::register_management_ability( 'delete-booking', __( 'Delete booking', 'events-manager' ), __( 'Permanently deletes an Events Manager booking.', 'events-manager' ), Schemas::id_input( __( 'Booking ID.', 'events-manager' ) ), array( static::class, 'delete_booking' ), array( static::class, 'can_manage_bookings' ), array( 'destructive' => true, 'idempotent' => false ) );

		static::register_term_abilities( 'category', 'categories', defined( 'EM_TAXONOMY_CATEGORY' ) ? EM_TAXONOMY_CATEGORY : '' );
		static::register_term_abilities( 'tag', 'tags', defined( 'EM_TAXONOMY_TAG' ) ? EM_TAXONOMY_TAG : '' );
	}

	protected static function register_term_abilities( $singular, $plural, $taxonomy ) {
		if ( !$taxonomy ) return;
		static::register_data_ability( 'list-' . $plural, sprintf( __( 'List %s', 'events-manager' ), $plural ), sprintf( __( 'Retrieves Events Manager %s.', 'events-manager' ), $plural ), Schemas::collection_input(), function( $input ) use ( $taxonomy ) {
			return Service::list_terms( $taxonomy, Utils::normalize_input( $input ) );
		} );
		static::register_data_ability( 'get-' . $singular, sprintf( __( 'Get %s', 'events-manager' ), $singular ), sprintf( __( 'Retrieves one Events Manager %s by ID.', 'events-manager' ), $singular ), Schemas::id_input(), function( $input ) use ( $taxonomy ) {
			$input = Utils::normalize_input( $input );
			return Service::get_term( $taxonomy, $input['id'] ?? 0 );
		} );
		static::register_management_ability( 'create-' . $singular, sprintf( __( 'Create %s', 'events-manager' ), $singular ), sprintf( __( 'Creates an Events Manager %s.', 'events-manager' ), $singular ), Schemas::term_input(), function( $input ) use ( $taxonomy ) {
			return Service::save_term( $taxonomy, Utils::normalize_input( $input ) );
		}, array( static::class, 'can_manage_terms' ), array( 'destructive' => false, 'idempotent' => false ) );
		static::register_management_ability( 'update-' . $singular, sprintf( __( 'Update %s', 'events-manager' ), $singular ), sprintf( __( 'Updates an Events Manager %s.', 'events-manager' ), $singular ), Schemas::term_input( true ), function( $input ) use ( $taxonomy ) {
			$input = Utils::normalize_input( $input );
			return Service::save_term( $taxonomy, $input, $input['id'] ?? 0 );
		}, array( static::class, 'can_manage_terms' ), array( 'destructive' => true, 'idempotent' => false ) );
		static::register_management_ability( 'delete-' . $singular, sprintf( __( 'Delete %s', 'events-manager' ), $singular ), sprintf( __( 'Deletes an Events Manager %s.', 'events-manager' ), $singular ), Schemas::id_input(), function( $input ) use ( $taxonomy ) {
			$input = Utils::normalize_input( $input );
			return Service::delete_term( $taxonomy, $input['id'] ?? 0 );
		}, array( static::class, 'can_delete_terms' ), array( 'destructive' => true, 'idempotent' => false ) );
	}

	protected static function register_data_ability( $name, $label, $description, $input_schema, $execute_callback, $permission_callback = '__return_true' ) {
		static::register_ability( $name, array(
			'label' => $label,
			'description' => $description,
			'category' => static::CATEGORY_DATA,
			'input_schema' => $input_schema,
			'output_schema' => static::is_collection_ability( $name ) ? Schemas::collection_output() : Schemas::object_output(),
			'execute_callback' => $execute_callback,
			'permission_callback' => $permission_callback,
			'meta' => static::meta( array( 'readonly' => true, 'destructive' => false, 'idempotent' => true ), $name, static::CATEGORY_DATA ),
		) );
	}

	protected static function register_management_ability( $name, $label, $description, $input_schema, $execute_callback, $permission_callback, $annotations ) {
		static::register_ability( $name, array(
			'label' => $label,
			'description' => $description,
			'category' => static::CATEGORY_MANAGEMENT,
			'input_schema' => $input_schema,
			'output_schema' => Schemas::object_output(),
			'execute_callback' => $execute_callback,
			'permission_callback' => $permission_callback,
			'meta' => static::meta( array_merge( array( 'readonly' => false ), $annotations ), $name, static::CATEGORY_MANAGEMENT ),
		) );
	}

	protected static function register_ability( $name, $args ) {
		wp_register_ability( 'events-manager/' . $name, $args );
	}

	protected static function is_collection_ability( $name ) {
		return in_array( $name, array( 'list-events', 'list-locations', 'list-bookings' ), true ) || strpos( $name, 'list-' ) === 0;
	}

	protected static function meta( $annotations, $name = '', $category = '' ) {
		return array(
			'annotations' => $annotations,
			'show_in_rest' => true,
			'mcp' => array(
				'public' => (bool) apply_filters( 'em_api_ability_mcp_public', true, $name, $annotations, $category ),
			),
		);
	}

	public static function list_events( $input ) {
		return Service::list_events( Utils::normalize_input( $input ) );
	}

	public static function get_event( $input ) {
		$input = Utils::normalize_input( $input );
		return Service::get_event( $input['id'] ?? 0, $input['context'] ?? 'view' );
	}

	public static function get_event_availability( $input ) {
		$input = Utils::normalize_input( $input );
		return Service::get_event_availability( $input['id'] ?? 0 );
	}

	public static function get_booking_requirements( $input ) {
		$input = Utils::normalize_input( $input );
		return Service::get_booking_requirements( $input['id'] ?? $input['event_id'] ?? 0 );
	}

	public static function list_event_tickets( $input ) {
		$input = Utils::normalize_input( $input );
		return Service::list_event_tickets( $input['id'] ?? 0, $input );
	}

	public static function get_ticket( $input ) {
		$input = Utils::normalize_input( $input );
		return Service::get_ticket( $input['id'] ?? 0, $input['context'] ?? 'view' );
	}

	public static function create_event( $input ) {
		return Service::create_event( Utils::normalize_input( $input ) );
	}

	public static function update_event( $input ) {
		$input = Utils::normalize_input( $input );
		return Service::update_event( $input['id'] ?? 0, $input );
	}

	public static function delete_event( $input ) {
		$input = Utils::normalize_input( $input );
		return Service::delete_event( $input['id'] ?? 0, $input['force'] ?? false );
	}

	public static function create_event_ticket( $input ) {
		$input = Utils::normalize_input( $input );
		return Service::create_event_ticket( $input['event_id'] ?? 0, $input );
	}

	public static function update_ticket( $input ) {
		$input = Utils::normalize_input( $input );
		return Service::update_ticket( $input['id'] ?? $input['ticket_id'] ?? 0, $input );
	}

	public static function delete_ticket( $input ) {
		$input = Utils::normalize_input( $input );
		return Service::delete_ticket( $input['id'] ?? $input['ticket_id'] ?? 0, $input['force'] ?? false );
	}

	public static function list_locations( $input ) {
		return Service::list_locations( Utils::normalize_input( $input ) );
	}

	public static function list_location_countries( $input ) {
		return Service::list_location_countries( Utils::normalize_input( $input ) );
	}

	public static function list_location_regions( $input ) {
		return Service::list_location_regions( Utils::normalize_input( $input ) );
	}

	public static function list_location_states( $input ) {
		return Service::list_location_states( Utils::normalize_input( $input ) );
	}

	public static function list_location_towns( $input ) {
		return Service::list_location_towns( Utils::normalize_input( $input ) );
	}

	public static function get_location( $input ) {
		$input = Utils::normalize_input( $input );
		return Service::get_location( $input['id'] ?? 0, $input['context'] ?? 'view' );
	}

	public static function create_location( $input ) {
		return Service::create_location( Utils::normalize_input( $input ) );
	}

	public static function update_location( $input ) {
		$input = Utils::normalize_input( $input );
		return Service::update_location( $input['id'] ?? 0, $input );
	}

	public static function delete_location( $input ) {
		$input = Utils::normalize_input( $input );
		return Service::delete_location( $input['id'] ?? 0, $input['force'] ?? false );
	}

	public static function list_bookings( $input ) {
		return Service::list_bookings( Utils::normalize_input( $input ) );
	}

	public static function upload_media( $input ) {
		return Service::upload_media( Utils::normalize_input( $input ) );
	}

	public static function can_upload_files() {
		return current_user_can( 'upload_files' );
	}

	public static function get_booking( $input ) {
		$input = Utils::normalize_input( $input );
		return Service::get_booking( $input['id'] ?? 0, $input['context'] ?? 'view' );
	}

	public static function create_booking( $input ) {
		return Service::create_booking( Utils::normalize_input( $input ) );
	}

	public static function update_booking( $input ) {
		$input = Utils::normalize_input( $input );
		return Service::update_booking( $input['id'] ?? 0, $input );
	}

	public static function set_booking_status( $input ) {
		$input = Utils::normalize_input( $input );
		return Service::set_booking_status( $input['id'] ?? 0, $input['status'] ?? null, $input['send_email'] ?? true, $input['ignore_spaces'] ?? false );
	}

	public static function delete_booking( $input ) {
		$input = Utils::normalize_input( $input );
		return Service::delete_booking( $input['id'] ?? 0 );
	}

	public static function can_edit_events() {
		return current_user_can( 'edit_events' );
	}

	public static function can_delete_events() {
		return current_user_can( 'delete_events' ) || current_user_can( 'delete_others_events' );
	}

	public static function can_edit_locations() {
		return current_user_can( 'edit_locations' );
	}

	public static function can_delete_locations() {
		return current_user_can( 'delete_locations' ) || current_user_can( 'delete_others_locations' );
	}

	public static function can_read_bookings() {
		return is_user_logged_in();
	}

	public static function can_create_booking() {
		return Service::can_create_booking();
	}

	public static function can_manage_bookings() {
		return current_user_can( 'manage_bookings' ) || current_user_can( 'manage_others_bookings' );
	}

	public static function can_manage_terms() {
		return Service::can_manage_terms();
	}

	public static function can_delete_terms() {
		return current_user_can( 'delete_event_categories' );
	}
}
