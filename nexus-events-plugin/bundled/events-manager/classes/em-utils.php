<?php
namespace EM;

/**
 * Namespaced class for howsing EM utilities, rather than functions
 */
class Utils {
	
	/**
	 * Gets a key from $_REQUEST, but mapped to a specific path in $_request_path, allowing for handling forms stored in arrays.
	 *
	 * For example, $_REQUEST['tickets'][ticket_id][0] = ['some_value' => 123, ...] can be accessed with $_request_path = ['tickets', ticket_id, 0] and then using this method with $key = 'some_value' to access 123.
	 *
	 * @param array $request_path
	 * @param string $key
	 *
	 * @return mixed|null
	 */
	public static function _request( $request_path = [], $key = null ) {
		$REQUEST = $_REQUEST;
		
		// Traverse the request map to get to the correct nested array
		foreach ( $request_path as $mapKey) {
			if (isset($REQUEST[$mapKey])) {
				$REQUEST = $REQUEST[$mapKey];
			} else {
				// If the key is missing in the structure, return null or handle the error
				return [];
			}
		}
		
		// Now check for the final key in the nested array
		if ( $key ) {
			return isset( $REQUEST[ $key ] ) ? $REQUEST[ $key ] : null;
		}
		return $REQUEST;
	}
}