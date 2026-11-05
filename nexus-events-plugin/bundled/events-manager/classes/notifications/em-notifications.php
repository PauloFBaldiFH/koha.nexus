<?php
namespace EM\Notifications;

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

require_once EM_DIR . '/classes/notifications/em-notifications-devices.php';
require_once EM_DIR . '/classes/notifications/em-notifications-expo.php';
require_once EM_DIR . '/classes/notifications/em-notifications-types.php';
require_once EM_DIR . '/classes/notifications/em-notifications-installer.php'; // Provides Installer::install(), wired below to em_install_create_tables so wp_em_app_devices is created the EM way — on install/upgrade, not on every load.

/**
 * Push-notification framework for the Events Manager mobile app. A generic type registry: each type binds an EM lifecycle hook (a new booking, a cancellation, a new event …) to a recipient rule and a payload, and the app drives delivery through Expo. Booking notifications are the first use, but the registry is the point — Pro and add-ons register more types on the em_notifications_register hook without touching this file or shipping an app update (the app's settings screen is built from GET /app/notifications/types at runtime).
 *
 * Topology: each site pushes directly to the devices registered with it (the app talks to every site directly already), so booking data never routes through a central server and nothing breaks when one is down. Recipients are chosen per-user in the app and bounded by WordPress capability — and the capability is always re-checked here at send time, so a stored preference is never an authorisation.
 */
class Notifications {

	/** @var array<string,array> Registered notification types, keyed by type key. */
	protected static $types = array();

	/** @var bool Guard so the default + extension types register exactly once. */
	protected static $registered = false;

	public static function init() {
		add_action( 'rest_api_init', array( __CLASS__, 'register_routes' ) );
		// Register types on init (mirrors EM\API\API::init): by init all add-ons' plugins_loaded hooks have run, so they can still hook em_notifications_register — and unlike plugins_loaded, init is late enough that translating the type labels won't trip WP 6.7's just-in-time textdomain notice.
		add_action( 'init', array( __CLASS__, 'register_types' ), 1 );
		if ( did_action( 'init' ) ) {
			static::register_types();
		}
		// Create the device table only when notifications are enabled — on install/upgrade via em_install(), or immediately when the admin enables the feature (covers git/rsync deploys).
		add_action( 'em_install_create_tables', array( __CLASS__, 'maybe_install_table' ) );
		// Also create the table the moment an admin enables notifications in settings — covers git/rsync deploys where em_install() never runs because the version number didn't change.
		add_action( 'update_option_dbem_app_notifications_enabled', array( __CLASS__, 'on_enabled_option_change' ), 10, 2 );
		add_action( 'add_option_dbem_app_notifications_enabled',    array( __CLASS__, 'on_enabled_option_add' ),    10, 2 );
	}

	public static function maybe_install_table() {
		if ( get_option( 'dbem_app_notifications_enabled' ) ) {
			Installer::install();
		}
	}

	public static function on_enabled_option_change( $old_value, $new_value ) {
		if ( $new_value && ! $old_value ) {
			Installer::install();
		}
	}

	public static function on_enabled_option_add( $option, $value ) {
		if ( $value ) {
			Installer::install();
		}
	}

	/** Returns all registered types (keyed by type key). Used by the settings page so Pro-registered types appear there automatically. Does not apply the site-wide enabled gate. */
	public static function get_types() {
		return static::$types;
	}

	public static function register_types() {
		if ( static::$registered ) {
			return;
		}
		static::$registered = true;
		Types::register_defaults();
		do_action( 'em_notifications_register' ); // Pro / add-ons call Notifications::register_type() here.
	}

	/**
	 * Register a notification type. Required: key, hook (the EM do_action it listens on), resolve (callable mapping the hook args → array('owner_user_id','title','body','data')). Optional: label, group, hook_args (number of args the hook passes), capability (minimum cap for the "own" scope, default manage_bookings), others_capability (cap that unlocks the "others" scope, or null).
	 */
	public static function register_type( array $args ) {
		$type = wp_parse_args( $args, array(
			'key'               => '',
			'label'             => '',
			'group'             => 'general',
			'hook'              => '',
			'hook_args'         => 1,
			'capability'        => 'manage_bookings',
			'others_capability' => null,
			'resolve'           => null,
		) );
		if ( '' === $type['key'] || '' === $type['hook'] || ! is_callable( $type['resolve'] ) ) {
			return false;
		}
		if ( isset( static::$types[ $type['key'] ] ) ) {
			return false; // first registration wins; don't let a later one silently shadow it.
		}
		static::$types[ $type['key'] ] = $type;
		$key = $type['key'];
		// Bind the EM lifecycle hook at priority 20 so core's own handlers (emails etc.) run first. func_get_args() forwards whatever the hook passed to the resolver.
		add_action( $type['hook'], function () use ( $key ) {
			Notifications::handle( $key, func_get_args() );
		}, 20, (int) $type['hook_args'] );
		return true;
	}

	/** A registered type fired — resolve it to a recipient owner + payload, then dispatch. */
	public static function handle( $type_key, array $hook_args ) {
		if ( ! get_option( 'dbem_app_notifications_enabled' ) ) {
			return;
		}
		if ( ! isset( static::$types[ $type_key ] ) ) {
			return;
		}
		// Per-type admin toggle; default 1 so types are on for existing installs that predate this option.
		if ( ! get_option( 'dbem_app_notification_' . $type_key, 1 ) ) {
			return;
		}
		$type     = static::$types[ $type_key ];
		$resolved = call_user_func_array( $type['resolve'], $hook_args );
		if ( empty( $resolved ) || empty( $resolved['owner_user_id'] ) ) {
			return; // the resolver opted out (e.g. a status change that wasn't a cancellation).
		}
		static::dispatch( $type, $resolved );
	}

	public static function dispatch( array $type, array $resolved ) {
		$tokens = static::resolve_recipient_tokens( $type, (int) $resolved['owner_user_id'] );
		if ( empty( $tokens ) ) {
			return;
		}
		$title = isset( $resolved['title'] ) && '' !== $resolved['title'] ? (string) $resolved['title'] : get_bloginfo( 'name' );
		$body  = isset( $resolved['body'] ) ? (string) $resolved['body'] : '';
		$data  = isset( $resolved['data'] ) && is_array( $resolved['data'] ) ? $resolved['data'] : array();

		$messages = array();
		foreach ( $tokens as $token ) {
			$messages[] = array(
				'to'       => $token,
				'title'    => $title,
				'body'     => $body,
				'data'     => $data,
				'sound'    => 'default',
				'priority' => 'high',
			);
		}
		// Last hook before the wire — lets a site coalesce, apply quiet hours, or suppress entirely.
		$messages = apply_filters( 'em_notifications_messages', $messages, $type, $resolved );
		if ( ! empty( $messages ) ) {
			Expo::send( $messages );
		}
	}

	/**
	 * The push tokens that should receive this type for an item owned by $owner_user_id. Two scopes, deduped by token:
	 *  - own:    the owner's own devices, if they opted in and still hold the base capability;
	 *  - others: any manager's devices, if they opted into other people's items and still hold the elevated capability.
	 * Capabilities are checked with user_can() against each recipient — never current_user_can(), which here is the booking-maker, not the recipient.
	 */
	protected static function resolve_recipient_tokens( array $type, $owner_user_id ) {
		$tokens = array();
		foreach ( Devices::all() as $device ) {
			$uid     = (int) $device['user_id'];
			$include = false;
			if ( $uid === (int) $owner_user_id && Devices::pref_enabled( $device, $type['key'], 'own' ) && user_can( $uid, $type['capability'] ) ) {
				$include = true;
			} elseif ( ! empty( $type['others_capability'] ) && Devices::pref_enabled( $device, $type['key'], 'others' ) && user_can( $uid, $type['others_capability'] ) ) {
				$include = true;
			}
			if ( $include ) {
				$tokens[ $device['token'] ] = true; // key by token to dedupe a user with several matching scopes.
			}
		}
		return array_keys( $tokens );
	}

	/** The types a given user is allowed to receive, with whether they can opt into the "others" scope. Drives the app's settings screen, so a Pro-registered type appears automatically. Returns empty when push notifications are disabled site-wide so the app hides the options. */
	public static function types_for_user( $user_id ) {
		if ( ! get_option( 'dbem_app_notifications_enabled' ) ) {
			return array();
		}
		$out = array();
		foreach ( static::$types as $key => $type ) {
			// Per-type admin toggle; default 1 so types are on for existing installs that predate this option.
			if ( ! get_option( 'dbem_app_notification_' . $key, 1 ) ) {
				continue;
			}
			$can_own    = user_can( $user_id, $type['capability'] );
			$can_others = ! empty( $type['others_capability'] ) && user_can( $user_id, $type['others_capability'] );
			if ( ! $can_own && ! $can_others ) {
				continue;
			}
			$out[] = array(
				'key'                => $key,
				'label'              => $type['label'],
				'group'              => $type['group'],
				'can_receive_others' => (bool) $can_others,
			);
		}
		return $out;
	}

	public static function user_can_receive_any( $user_id ) {
		foreach ( static::$types as $type ) {
			if ( user_can( $user_id, $type['capability'] ) ) {
				return true;
			}
			if ( ! empty( $type['others_capability'] ) && user_can( $user_id, $type['others_capability'] ) ) {
				return true;
			}
		}
		return false;
	}

	// --- REST ---------------------------------------------------------------
	// Routes live under the same events-manager/v1 namespace as the rest of the app API, registered here so the feature stays self-contained (no edit to em-api-rest.php; Pro extends it via the registry).

	public static function register_routes() {
		$ns = 'events-manager/v1'; // matches EM\API\REST::NAMESPACE.
		register_rest_route( $ns, '/app/notifications/types', array(
			'methods'             => 'GET',
			'callback'            => array( __CLASS__, 'rest_get_types' ),
			'permission_callback' => array( __CLASS__, 'rest_permission' ),
		) );
		register_rest_route( $ns, '/app/devices', array(
			array(
				'methods'             => 'POST',
				'callback'            => array( __CLASS__, 'rest_register_device' ),
				'permission_callback' => array( __CLASS__, 'rest_permission' ),
			),
			array(
				'methods'             => 'DELETE',
				'callback'            => array( __CLASS__, 'rest_unregister_device' ),
				'permission_callback' => 'is_user_logged_in',
			),
		) );
	}

	public static function rest_permission() {
		return is_user_logged_in() && static::user_can_receive_any( get_current_user_id() );
	}

	public static function rest_get_types( $request ) {
		return static::respond( array( 'types' => static::types_for_user( get_current_user_id() ) ) );
	}

	public static function rest_register_device( $request ) {
		$token = sanitize_text_field( (string) $request->get_param( 'token' ) );
		if ( ! Expo::is_expo_token( $token ) ) {
			return new \WP_Error( 'em_invalid_token', __( 'A valid Expo push token is required.', 'events-manager' ), array( 'status' => 400 ) );
		}
		$platform = in_array( $request->get_param( 'platform' ), array( 'ios', 'android' ), true ) ? $request->get_param( 'platform' ) : '';
		$label    = sanitize_text_field( (string) $request->get_param( 'label' ) );
		$prefs    = static::sanitize_prefs( $request->get_param( 'prefs' ) );
		Devices::register( get_current_user_id(), $token, $platform, $label, $prefs );
		return static::respond( array( 'registered' => true, 'types' => static::types_for_user( get_current_user_id() ) ) );
	}

	public static function rest_unregister_device( $request ) {
		$token = sanitize_text_field( (string) $request->get_param( 'token' ) );
		if ( '' === $token ) {
			return new \WP_Error( 'em_invalid_token', __( 'A token is required.', 'events-manager' ), array( 'status' => 400 ) );
		}
		Devices::unregister( get_current_user_id(), $token );
		return static::respond( array( 'unregistered' => true ) );
	}

	/** Keep only known type keys; coerce own/others to bool; and only accept others=true if the user actually holds that type's elevated capability (dispatch re-checks too, but don't even store a claim we know is false). */
	protected static function sanitize_prefs( $raw ) {
		$out = array();
		if ( ! is_array( $raw ) ) {
			return $out;
		}
		$uid = get_current_user_id();
		foreach ( static::$types as $key => $type ) {
			if ( ! isset( $raw[ $key ] ) || ! is_array( $raw[ $key ] ) ) {
				continue;
			}
			$out[ $key ] = array(
				'own'    => ! empty( $raw[ $key ]['own'] ),
				'others' => ! empty( $raw[ $key ]['others'] ) && ! empty( $type['others_capability'] ) && user_can( $uid, $type['others_capability'] ),
			);
		}
		return $out;
	}

	protected static function respond( $result, $status = 200 ) {
		if ( is_wp_error( $result ) ) {
			return $result;
		}
		return new \WP_REST_Response( $result, $status );
	}
}

Notifications::init();
