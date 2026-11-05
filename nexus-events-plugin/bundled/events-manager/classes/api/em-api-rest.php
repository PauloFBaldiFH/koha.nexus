<?php
namespace EM\API;

class REST {

	const NAMESPACE = 'events-manager/v1';

	public static function init() {
		add_action( 'rest_api_init', array( static::class, 'register_routes' ) );
		// Inbound authentication is handled entirely by the bundled \Pixelite\OAuth_App_Passwords library — its Bearer → Basic translator runs on determine_current_user priority 9, then WP core's native Application Password validator (priority 20) does the actual check. Nothing for EM to wire up here.
	}

	public static function register_routes() {
		register_rest_route( static::NAMESPACE, '/events', array(
			array(
				'methods' => 'GET',
				'callback' => array( static::class, 'list_events' ),
				'permission_callback' => 'is_user_logged_in',
			),
			array(
				'methods' => 'POST',
				'callback' => array( static::class, 'create_event' ),
				'permission_callback' => array( static::class, 'can_edit_events' ),
			),
		) );
		register_rest_route( static::NAMESPACE, '/events/(?P<id>[\d:]+)/availability', array(
			'methods' => 'GET',
			'callback' => array( static::class, 'get_event_availability' ),
			'permission_callback' => 'is_user_logged_in',
		) );
		register_rest_route( static::NAMESPACE, '/events/(?P<id>[\d:]+)/tickets', array(
			array(
				'methods' => 'GET',
				'callback' => array( static::class, 'list_event_tickets' ),
				'permission_callback' => 'is_user_logged_in',
			),
			array(
				'methods' => 'POST',
				'callback' => array( static::class, 'create_event_ticket' ),
				'permission_callback' => array( static::class, 'can_manage_bookings' ),
			),
		) );
		register_rest_route( static::NAMESPACE, '/events/(?P<id>[\d:]+)', array(
			array(
				'methods' => 'GET',
				'callback' => array( static::class, 'get_event' ),
				'permission_callback' => 'is_user_logged_in',
			),
			array(
				'methods' => 'PATCH',
				'callback' => array( static::class, 'update_event' ),
				'permission_callback' => array( static::class, 'can_edit_events' ),
			),
			array(
				'methods' => 'DELETE',
				'callback' => array( static::class, 'delete_event' ),
				'permission_callback' => array( static::class, 'can_delete_events' ),
			),
		) );
		register_rest_route( static::NAMESPACE, '/tickets/(?P<id>\d+)', array(
			array(
				'methods' => 'GET',
				'callback' => array( static::class, 'get_ticket' ),
				'permission_callback' => 'is_user_logged_in',
			),
			array(
				'methods' => 'PATCH',
				'callback' => array( static::class, 'update_ticket' ),
				'permission_callback' => array( static::class, 'can_manage_bookings' ),
			),
			array(
				'methods' => 'DELETE',
				'callback' => array( static::class, 'delete_ticket' ),
				'permission_callback' => array( static::class, 'can_manage_bookings' ),
			),
		) );

		register_rest_route( static::NAMESPACE, '/locations', array(
			array(
				'methods' => 'GET',
				'callback' => array( static::class, 'list_locations' ),
				'permission_callback' => 'is_user_logged_in',
			),
			array(
				'methods' => 'POST',
				'callback' => array( static::class, 'create_location' ),
				'permission_callback' => array( static::class, 'can_edit_locations' ),
			),
		) );
		register_rest_route( static::NAMESPACE, '/locations/countries', array(
			'methods'             => 'GET',
			'callback'            => array( static::class, 'list_location_countries' ),
			'permission_callback' => 'is_user_logged_in',
		) );
		register_rest_route( static::NAMESPACE, '/locations/regions', array(
			'methods'             => 'GET',
			'callback'            => array( static::class, 'list_location_regions' ),
			'permission_callback' => 'is_user_logged_in',
		) );
		register_rest_route( static::NAMESPACE, '/locations/states', array(
			'methods'             => 'GET',
			'callback'            => array( static::class, 'list_location_states' ),
			'permission_callback' => 'is_user_logged_in',
		) );
		register_rest_route( static::NAMESPACE, '/locations/towns', array(
			'methods'             => 'GET',
			'callback'            => array( static::class, 'list_location_towns' ),
			'permission_callback' => 'is_user_logged_in',
		) );
		register_rest_route( static::NAMESPACE, '/locations/(?P<id>\d+)', array(
			array(
				'methods' => 'GET',
				'callback' => array( static::class, 'get_location' ),
				'permission_callback' => 'is_user_logged_in',
			),
			array(
				'methods' => 'PATCH',
				'callback' => array( static::class, 'update_location' ),
				'permission_callback' => array( static::class, 'can_edit_locations' ),
			),
			array(
				'methods' => 'DELETE',
				'callback' => array( static::class, 'delete_location' ),
				'permission_callback' => array( static::class, 'can_delete_locations' ),
			),
		) );

		register_rest_route( static::NAMESPACE, '/bookings', array(
			array(
				'methods' => 'GET',
				'callback' => array( static::class, 'list_bookings' ),
				'permission_callback' => array( static::class, 'can_read_bookings' ),
			),
			array(
				'methods' => 'POST',
				'callback' => array( static::class, 'create_booking' ),
				'permission_callback' => array( static::class, 'can_create_booking' ),
			),
		) );
		register_rest_route( static::NAMESPACE, '/bookings/(?P<id>[\w-]+)', array(
			array(
				'methods' => 'GET',
				'callback' => array( static::class, 'get_booking' ),
				'permission_callback' => array( static::class, 'can_read_bookings' ),
			),
			array(
				'methods' => 'PATCH',
				'callback' => array( static::class, 'update_booking' ),
				'permission_callback' => array( static::class, 'can_manage_bookings' ),
			),
			array(
				'methods' => 'DELETE',
				'callback' => array( static::class, 'delete_booking' ),
				'permission_callback' => array( static::class, 'can_manage_bookings' ),
			),
		) );
		register_rest_route( static::NAMESPACE, '/bookings/(?P<id>[\w-]+)/status', array(
			'methods' => 'POST',
			'callback' => array( static::class, 'set_booking_status' ),
			'permission_callback' => array( static::class, 'can_manage_bookings' ),
		) );

		register_rest_route( static::NAMESPACE, '/media', array(
			'methods'             => 'POST',
			'callback'            => array( static::class, 'upload_media' ),
			'permission_callback' => array( static::class, 'can_upload_files' ),
		) );

		foreach ( static::term_routes() as $route => $taxonomy ) {
			register_rest_route( static::NAMESPACE, '/' . $route, array(
				array(
					'methods' => 'GET',
					'callback' => function( $request ) use ( $taxonomy ) {
						return REST::respond( Service::list_terms( $taxonomy, Utils::get_request_data( $request ) ) );
					},
					'permission_callback' => 'is_user_logged_in',
				),
				array(
					'methods' => 'POST',
					'callback' => function( $request ) use ( $taxonomy ) {
						return REST::respond( Service::save_term( $taxonomy, Utils::get_request_data( $request ) ), 201 );
					},
					'permission_callback' => array( static::class, 'can_manage_terms' ),
				),
			) );
			register_rest_route( static::NAMESPACE, '/' . $route . '/(?P<id>\d+)', array(
				array(
					'methods' => 'GET',
					'callback' => function( $request ) use ( $taxonomy ) {
						return REST::respond( Service::get_term( $taxonomy, $request['id'] ) );
					},
					'permission_callback' => 'is_user_logged_in',
				),
				array(
					'methods' => 'PATCH',
					'callback' => function( $request ) use ( $taxonomy ) {
						return REST::respond( Service::save_term( $taxonomy, Utils::get_request_data( $request ), $request['id'] ) );
					},
					'permission_callback' => array( static::class, 'can_manage_terms' ),
				),
				array(
					'methods' => 'DELETE',
					'callback' => function( $request ) use ( $taxonomy ) {
						return REST::respond( Service::delete_term( $taxonomy, $request['id'] ) );
					},
					'permission_callback' => array( static::class, 'can_delete_terms' ),
				),
			) );
		}
	}

	public static function list_events( $request ) {
		return static::respond( Service::list_events( Utils::get_request_data( $request ) ) );
	}

	public static function get_event( $request ) {
		return static::respond( Service::get_event( $request['id'], $request->get_param( 'context' ) ?: 'view' ) );
	}

	public static function get_event_availability( $request ) {
		return static::respond( Service::get_event_availability( $request['id'] ) );
	}

	public static function list_event_tickets( $request ) {
		return static::respond( Service::list_event_tickets( $request['id'], Utils::get_request_data( $request ) ) );
	}

	public static function get_ticket( $request ) {
		return static::respond( Service::get_ticket( $request['id'], $request->get_param( 'context' ) ?: 'view' ) );
	}

	public static function create_event_ticket( $request ) {
		return static::respond( Service::create_event_ticket( $request['id'], Utils::get_request_data( $request ) ), 201 );
	}

	public static function update_ticket( $request ) {
		return static::respond( Service::update_ticket( $request['id'], Utils::get_request_data( $request ) ) );
	}

	public static function delete_ticket( $request ) {
		return static::respond( Service::delete_ticket( $request['id'], $request->get_param( 'force' ) ) );
	}

	public static function create_event( $request ) {
		return static::respond( Service::create_event( Utils::get_request_data( $request ) ), 201 );
	}

	public static function update_event( $request ) {
		return static::respond( Service::update_event( $request['id'], Utils::get_request_data( $request ) ) );
	}

	public static function delete_event( $request ) {
		return static::respond( Service::delete_event( $request['id'], $request->get_param( 'force' ) ) );
	}

	public static function list_locations( $request ) {
		return static::respond( Service::list_locations( Utils::get_request_data( $request ) ) );
	}

	public static function get_location( $request ) {
		return static::respond( Service::get_location( $request['id'], $request->get_param( 'context' ) ?: 'view' ) );
	}

	public static function create_location( $request ) {
		return static::respond( Service::create_location( Utils::get_request_data( $request ) ), 201 );
	}

	public static function update_location( $request ) {
		return static::respond( Service::update_location( $request['id'], Utils::get_request_data( $request ) ) );
	}

	public static function delete_location( $request ) {
		return static::respond( Service::delete_location( $request['id'], $request->get_param( 'force' ) ) );
	}

	public static function list_location_countries( $request ) {
		return static::respond( Service::list_location_countries( Utils::get_request_data( $request ) ) );
	}

	public static function list_location_regions( $request ) {
		return static::respond( Service::list_location_regions( Utils::get_request_data( $request ) ) );
	}

	public static function list_location_states( $request ) {
		return static::respond( Service::list_location_states( Utils::get_request_data( $request ) ) );
	}

	public static function list_location_towns( $request ) {
		return static::respond( Service::list_location_towns( Utils::get_request_data( $request ) ) );
	}

	public static function upload_media( $request ) {
		$data = Utils::get_request_data( $request );
		unset( $data['_files_file'] );
		// Multipart file uploads come through $_FILES, not the parsed body.
		if ( !empty( $_FILES['file'] ) && is_array( $_FILES['file'] ) ) {
			$data['_files_file'] = $_FILES['file'];
		}
		return static::respond( Service::upload_media( $data ), 201 );
	}

	public static function list_bookings( $request ) {
		return static::respond( Service::list_bookings( Utils::get_request_data( $request ) ) );
	}

	public static function get_booking( $request ) {
		return static::respond( Service::get_booking( $request['id'], $request->get_param( 'context' ) ?: 'view' ) );
	}

	public static function create_booking( $request ) {
		return static::respond( Service::create_booking( Utils::get_request_data( $request ) ), 201 );
	}

	public static function update_booking( $request ) {
		return static::respond( Service::update_booking( $request['id'], Utils::get_request_data( $request ) ) );
	}

	public static function delete_booking( $request ) {
		return static::respond( Service::delete_booking( $request['id'] ) );
	}

	public static function set_booking_status( $request ) {
		$data = Utils::get_request_data( $request );
		return static::respond( Service::set_booking_status( $request['id'], $data['status'] ?? null, $data['send_email'] ?? true, $data['ignore_spaces'] ?? false ) );
	}

	public static function respond( $result, $status = 200 ) {
		if ( is_wp_error( $result ) ) return $result;
		$response = new \WP_REST_Response( $result, $status );
		if ( isset( $result['pagination'] ) && is_array( $result['pagination'] ) ) {
			$response->header( 'X-WP-Total', $result['pagination']['total'] );
			$response->header( 'X-WP-TotalPages', $result['pagination']['total_pages'] );
		}
		return $response;
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

	public static function can_upload_files() {
		return current_user_can( 'upload_files' );
	}

	protected static function term_routes() {
		$routes = array();
		if ( defined( 'EM_TAXONOMY_CATEGORY' ) ) {
			$routes['categories'] = EM_TAXONOMY_CATEGORY;
		}
		if ( defined( 'EM_TAXONOMY_TAG' ) ) {
			$routes['tags'] = EM_TAXONOMY_TAG;
		}
		return $routes;
	}
}
