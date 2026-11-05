<?php
namespace EM\API;

class Utils {

	public static function get_request_data( $request ) {
		$params = is_object( $request ) && method_exists( $request, 'get_params' ) ? $request->get_params() : array();
		$json = is_object( $request ) && method_exists( $request, 'get_json_params' ) ? $request->get_json_params() : array();
		if ( !is_array( $params ) ) $params = array();
		if ( !is_array( $json ) ) $json = array();
		return array_merge( $params, $json );
	}

	public static function error( $code, $message, $status = 400, $extra = array() ) {
		return new \WP_Error( $code, $message, array_merge( array( 'status' => $status ), $extra ) );
	}

	public static function object_error( $code, $object, $fallback, $status = 400 ) {
		$raw = is_object( $object ) && method_exists( $object, 'get_errors' ) ? $object->get_errors() : array();
		$messages = static::flatten_error_messages( $raw );
		$message = !empty( $messages ) ? implode( ' ', $messages ) : $fallback;
		return static::error( $code, $message, $status, array( 'errors' => $messages ) );
	}

	/**
	 * Reduce an arbitrarily-nested error structure to a flat list of non-empty,
	 * tag-stripped strings. EM objects can stash nested arrays (and occasionally
	 * empty strings) inside ->errors; passing those straight to wp_strip_all_tags()
	 * collapses the message to "", which is what made MCP/REST booking failures
	 * surface as {"success":false,"error":""} with no actionable detail.
	 */
	protected static function flatten_error_messages( $errors ) {
		$out = array();
		foreach ( (array) $errors as $item ) {
			if ( is_array( $item ) ) {
				$out = array_merge( $out, static::flatten_error_messages( $item ) );
			} elseif ( is_scalar( $item ) ) {
				$text = trim( wp_strip_all_tags( (string) $item ) );
				if ( $text !== '' ) {
					$out[] = $text;
				}
			}
		}
		return array_values( array_unique( $out ) );
	}

	public static function collection_args( $params, $defaults = array() ) {
		$page = !empty( $params['page'] ) ? absint( $params['page'] ) : 1;
		$per_page = !empty( $params['per_page'] ) ? absint( $params['per_page'] ) : ( !empty( $params['limit'] ) ? absint( $params['limit'] ) : 20 );
		$page = max( 1, $page );
		$per_page = max( 1, min( 100, $per_page ) );
		return array_merge( $defaults, array(
			'limit' => $per_page,
			'page' => $page,
			'pagination' => true,
		) );
	}

	public static function pick_search_args( $params, $accepted ) {
		$args = array();
		foreach ( $accepted as $key ) {
			if ( array_key_exists( $key, $params ) ) {
				$args[ $key ] = $params[ $key ];
			}
		}
		return $args;
	}

	public static function normalize_input( $input ) {
		return is_array( $input ) ? $input : array();
	}

	public static function is_truthy( $value ) {
		return $value === true || $value === 1 || $value === '1' || $value === 'true';
	}

	public static function sanitize_post_status( $status ) {
		$status = sanitize_key( $status );
		$allowed = array( 'publish', 'pending', 'draft', 'private' );
		return in_array( $status, $allowed, true ) ? $status : false;
	}

	public static function with_request_data( $data, $callback ) {
		$old_request = $_REQUEST;
		$old_post = $_POST;
		$_REQUEST = array_merge( $_REQUEST, $data );
		$_POST = array_merge( $_POST, $data );
		try {
			return call_user_func( $callback );
		} finally {
			$_REQUEST = $old_request;
			$_POST = $old_post;
		}
	}

	public static function strip_private_owner_data( $api, $can_manage = false ) {
		if ( !$can_manage && isset( $api['owner'] ) && is_array( $api['owner'] ) ) {
			unset( $api['owner']['email'] );
		}
		return $api;
	}

	public static function pagination( $total, $page, $per_page ) {
		return array(
			'total' => absint( $total ),
			'total_pages' => $per_page ? (int) ceil( absint( $total ) / $per_page ) : 0,
			'page' => absint( $page ),
			'per_page' => absint( $per_page ),
		);
	}
}
