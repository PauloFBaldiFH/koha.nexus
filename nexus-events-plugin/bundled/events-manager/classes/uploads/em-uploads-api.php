<?php
namespace EM\Uploads;

use WP_REST_Response, EM_Exception;

class API {
	
	public static $temp_file_expiration = 1800;
	
	public static function init() {
		add_action('rest_api_init', [ static::class, 'register_routes' ]);
		add_action('init', [ static::class, 'schedule_cleanup']);
		add_action('em_uploads_api_cleanup', [ static::class, 'run_cleanup']);
	}
	
	/**
	 * Schedules the WP-Cron event if it is not already scheduled.
	 */
	public static function schedule_cleanup() {
		if ( !wp_next_scheduled('em_uploads_api_cleanup') ) {
			wp_schedule_event(time(), 'hourly', 'em_uploads_api_cleanup');
		}
	}
	
	/**
	 * Runs the cleanup process, deleting expired temporary files.
	 */
	public static function run_cleanup() {
		
		// Get the temporary upload directory (fallback to system temp dir)
		$temp_dir = ini_get('upload_tmp_dir') ?: sys_get_temp_dir();
		if (!$temp_dir || !is_dir($temp_dir)) {
			return;
		}
		
		$files = glob($temp_dir. DIRECTORY_SEPARATOR . '*' . Uploader::$temp_suffix );
		$now = time();
		
		foreach ($files as $file) {
			if ( !is_file($file) ) {
				continue;
			}
			$file_age = $now - filemtime($file);
			if ( $file_age > static::$temp_file_expiration ) {
				unlink($file);
			}
		}
	}
	
	public static function register_routes() {
		$namespace = 'events-manager/v1';
		
		// basic upload and revert functions, do not necessarily need overriding to act
		
		register_rest_route($namespace, '/uploads', [
			'methods' => 'POST',
			'callback' => [ static::class, 'handle_upload'],
			'permission_callback' => '__return_true',
		]);
		
		register_rest_route($namespace, '/uploads', [
			'methods' => 'DELETE',
			'callback' => [ static::class, 'handle_revert' ],
			'permission_callback' => '__return_true',
		]);
		
		// getting and deleting previously uploaded files, needs filter handling passed by query params
		
		register_rest_route( $namespace, '/uploads', [
			'methods'             => 'GET',
			'callback'            => [ static::class, 'handle_load' ],
			'permission_callback' => [ static::class, 'permission_callback' ],
		] );
		
		/*
		register_rest_route( $namespace, '/uploads', [
			'methods'             => 'DELETE',
			'callback'            => [ static::class, 'handle_delete' ],
			'permission_callback' => [ static::class, 'permission_callback' ],
		] );
		*/
	}
	
	/**
	 * Recursively search an array for a subarray that looks like a file upload array.
	 *
	 * @param array $array The array to search.
	 * @return array|null The first found file array, or null if none is found.
	 */
	public static function find_nested_upload_array(array $array) {
		$expected_keys = ['tmp_name', 'name', 'error', 'size', 'type'];
		
		// Check if the current array has all expected keys.
		if ( count( array_intersect_key( $array, array_flip( $expected_keys ) ) ) === count($expected_keys) ) {
			return $array;
		}
		
		// Recursively search in subarrays.
		foreach ($array as $item) {
			if ( is_array($item) ) {
				$result = static::find_nested_upload_array( $item );
				if ( $result !== null ) {
					return $result;
				}
			}
		}
		
		return null;
	}

	
	/**
	 * @param \WP_REST_Request $request
	 *
	 * @return WP_REST_Response
	 */
	public static function handle_upload( $request ) {
		$nonce = $request->get_header('X-EM-Nonce');
		$path = urldecode($request->get_param('path'));
		
		if ( !wp_verify_nonce( sanitize_text_field($nonce), 'em_uploads_api/'.$path ) ) {
			return new WP_REST_Response( array( 'success' => false,  'error' => 'Invalid uploads Nonce.' ), 403 );
		}
		
		if ( empty( $_FILES ) ) {
			return new WP_REST_Response( array( 'success' => false,  'error' => 'No file uploaded or invalid file data.' ), 400 );
		}
		$upload_key = key( $_FILES );
		
		
		// clean the $_FILES to bring a highly nested upload to the top-level, we only expect one upload and need only know the key not the whole path
		// examples of this could be for an attendee of event, e.g. ticket_id > attendee_id > field_name
		$recursive_current = function ($value) {
			while (is_array($value)) {
				$value = current($value);
			}
			return $value;
		};
		// handle possibility of input field using an array, and make $_FILES an array for validation purposes
		if ( is_array($_FILES[$upload_key]['tmp_name']) ) {
			$file = [];
			foreach ($_FILES[$upload_key] as $key => $value) {
				$file[$key] = $recursive_current($value);
				$_FILES[$upload_key][$key] = [ $file[$key] ]; // for later, 'flattened' as a simple field uploaded
			}
		} else {
			$file = $_FILES[ $upload_key ];
			foreach( $_FILES[ $upload_key ] as $key => $value ) {
				$_FILES[ $upload_key ][ $key ] = [ $value ];
			}
		}
		
		// Ensure the file was properly uploaded
		if ( empty($file['tmp_name']) || !is_uploaded_file( $file['tmp_name'] ) ) {
			return new WP_REST_Response( array( 'success' => false,  'error' => 'Failed to process the uploaded file.' ), 422 );
		}
		
		// allow for validation from extenral forces, either by performing a validation forcing false/true/WP_Error, or by supplying options to pass by Uploader::validate()
		$validate_options = apply_filters('em_uploads_api_upload_validate_options_' . $path, ['type' => ['image']], $upload_key, $file);
		$valid = apply_filters('em_uploads_api_upload_validate_' . $path, null, $upload_key, $file);
		if ( $valid === null ) {
			try {
				$valid = Uploader::validate( $upload_key, $validate_options );
			} catch ( EM_Exception $e ) {
				$errors = $e->get_messages();
				return new WP_REST_Response( array( 'success' => false,  'error' => implode(', ', $errors), 'errors' => $errors ), 422 );
			}
		}
		
		if ( !$valid ) {
			return new WP_REST_Response( array( 'success' => false,  'error' => 'Failed to validate the uploaded file.' ), 422 );
		} elseif ( is_wp_error($valid) ) { /* @var \WP_Error $valid */
			$errors = $valid->get_error_messages();
			return new WP_REST_Response( array( 'success' => false,  'error' => implode(', ', $errors), 'errors' => $errors ), 422 );
		}
		
		// move the upload so it's not automaticall deleted, but can be deleted by our cronjob
		if ( !move_uploaded_file( $file['tmp_name'], $file['tmp_name'] . Uploader::$temp_suffix ) ) {
			return new WP_REST_Response( array( 'success' => false,  'error' => 'Failed to temporarily store the uploaded file.' ), 422 );
		}
		$file_id = basename($file['tmp_name'] );
		
		// fire hooks allowing validation, we advise specific validation via path, e.g. em_uploads_api_handle_upload/event-image
		$response = apply_filters('em_uploads_api_handle_upload', [
			'data' => [
				'success' => true,
				'file'    => array(
					'id' => $file_id,
					'name' => sanitize_file_name( $file['name'] ),
					'size' => $file['size'],
					'type' => $file['type'],
				),
				'nonce' => wp_create_nonce( 'em_uploads_api_file_' . $file_id )
			],
			'status' => 200,
			'headers' => [],
		], $request);
		$response = apply_filters('em_uploads_api_handle_upload/' . $path, $response, $request);
		
		// return response
		return new WP_REST_Response( $response['data'], $response['status'], $response['headers'] );
	}
	
	/**
	 * Deletes a file that was uploaded but not yet saved. Requires nonce provided when uploaded originally.
	 *
	 * @param $request
	 *
	 * @return WP_REST_Response
	 */
	public static function handle_revert($request) {
		$file_id = $request->get_param('tmp_file');
		$nonce = $request->get_param('nonce');
		
		if (!wp_verify_nonce($nonce, 'em_uploads_api_file_' . $file_id)) {
			return new WP_REST_Response(['success' => false,  'error' => 'Invalid nonce.'], 403);
		}
		
		$tempUploadDir = ini_get('upload_tmp_dir') ?: sys_get_temp_dir(); // Fallback if not set
		$tmp_path = trailingslashit($tempUploadDir). $file_id . '-em-uploader';
		if ( file_exists($tmp_path) && is_writable($tmp_path) ) {
			unlink($tmp_path);
			return new WP_REST_Response(['success' => true, 'message' =>'File deleted.'], 200);
		}
		
		return new WP_REST_Response(['success' => false,  'error' => 'File not found or not writable.'], 404);
	}
	
	public static function handle_load( $request ) {
		// Get the file_id parameter from the request if this is for a temp file
		$temp_id = $request->get_param('temp_id');
		if( $temp_id ) {
			// Reject any temp_id that could escape the temp directory before it is used to build a path.
			if ( strpbrk( $temp_id, '/\\' ) !== false || strpos( $temp_id, '..' ) !== false ) {
				return new WP_REST_Response( [ 'success' => false, 'error' => 'File not found.' ], 404 );
			}
			$temp_id = basename( $temp_id );

			// Require the nonce issued at upload time, bound to this temp file. FilePond's restore (limbo) request carries it inside the X-Filenames payload rather than the query string, so accept it from either source.
			$nonce = $request->get_param('nonce');
			if ( empty( $nonce ) ) {
				$filenames = json_decode( $request->get_header('X-Filenames'), true );
				if ( !empty( $filenames[ $temp_id ]['nonce'] ) ) {
					$nonce = $filenames[ $temp_id ]['nonce'];
				}
			}
			if ( !wp_verify_nonce( $nonce, 'em_uploads_api_file_' . $temp_id ) ) {
				return new WP_REST_Response( [ 'success' => false, 'error' => 'Invalid nonce.' ], 403 );
			}

			// Determine the temporary upload directory.
			$tempUploadDir = ini_get('upload_tmp_dir') ?: sys_get_temp_dir();

			// Build the full file path.
			$file_path = trailingslashit( $tempUploadDir ) . $temp_id . '-em-uploader';

			// Ensure the resolved path stays inside the temp directory before reading it.
			$real_path = realpath( $file_path );
			$real_dir  = realpath( $tempUploadDir );
			if ( $real_path === false || $real_dir === false || strpos( $real_path, trailingslashit( $real_dir ) ) !== 0 ) {
				return new WP_REST_Response( [ 'success' => false, 'error' => 'File not found.' ], 404 );
			}

			// Check if the file exists and is readable.
			if ( file_exists( $file_path ) && is_readable( $file_path ) ) {
				// Get the file contents and MIME type.
				$file_contents = file_get_contents( $file_path );
				// Only images are shown inline (FilePond previews); anything else goes out as an opaque download, so a document that happens to contain HTML is never rendered on the site origin.
				$mime_type = Uploader::sniff_mime_type( $file_path );
				$is_image  = $mime_type && strpos( $mime_type, 'image/' ) === 0 && !Uploader::is_active_content_mime( $mime_type );
				if ( !$is_image ) {
					$mime_type = 'application/octet-stream';
				}
				
				// get filename if exists
				$filenames = json_decode( $request->get_header('X-Filenames') , true);
				$filename = !empty($filenames[$temp_id]) ? sanitize_file_name($filenames[$temp_id]['name']) : 'unknown';
				$filename = str_replace( array( '"', '\\' ), '', $filename );
				
				// Create a WP_REST_Response object with the file contents.
				$response = new WP_REST_Response( $file_contents, 200 );
				$response->set_headers( [
					'Content-Type'           => $mime_type,
					'Content-Disposition'    => ( $is_image ? 'inline' : 'attachment' ) . '; filename="'. $filename .'"',
					'X-Content-Type-Options' => 'nosniff',
				] );
				
				/**
				 * Use the rest_pre_serve_request filter to output the raw data.
				 * This filter checks if the response has a Content-Type header that isn’t JSON,
				 * and if so, echoes the raw file contents directly.
				 */
				add_filter( 'rest_pre_serve_request', function( $served, $result, $request, $server ) {
					if ( $result instanceof WP_REST_Response ) {
						$headers = $result->get_headers();
						// If the Content-Type is not JSON, then serve raw data.
						if ( ! empty( $headers['Content-Type'] ) && false === strpos( $headers['Content-Type'], 'application/json' ) ) {
							// Send the headers.
							header( 'Content-Type: ' . $headers['Content-Type'] );
							header( 'Content-Disposition: ' . $headers['Content-Disposition'] );
							header( 'X-Content-Type-Options: nosniff' );
							// Output the raw file contents.
							echo $result->get_data();
							return true; // We've handled serving the response.
						}
					}
					return $served;
				}, 10, 4 );
				
				return $response;
			}
		}
		
		// Return an error response if the file cannot be found.
		return new WP_REST_Response( [ 'success' => false, 'error'   => 'File not found.' ], 404 );
	}
	
	
	/**
	 * @deprecated Not in use yet.
	 *
	 * Handles deleting a file on a form with previously uploaded data. Validates a nonce and then fires a hook if nonce passes.
	 *
	 * Any function hooking into this needs to verify capabilities before performing any actions on deletions.
	 *
	 * @param $request
	 *
	 * @return WP_REST_Response
	 */
	public static function handle_delete ( $request ) {
		$nonce = $request->get_header('nonce');
		$object = $request->get_param('path');
		$file_id = $request->get_param( 'id' );
		$nonce_action = $object ? '/'. $object : '';
		$nonce_action .= $file_id ? '/' . $file_id : '';
		if ( !wp_verify_nonce( $nonce, 'em_uploads_api_file/' . $nonce_action ) ) {
			return new WP_REST_Response( [ 'success' => false, 'success' => false,  'error' => 'File not deleted, failed nonce.' ], 200 );
		}
		// fire a hook and return false, WP_Error or true if deleted
		$result = apply_filters('em_uploads_api_delete_' . $object, false, $request->get_params(), $request );
		if ( is_wp_error( $result ) ) {
			$response_result = false;
			$response_message = $result->get_error_message();
		} else {
			$response_result = $result === true;
			$response_message = $response_result ? 'File deleted.' : 'File not deleted.';
		}
		return new WP_REST_Response( [ 'success' => $response_result, 'message' => $response_message ], 200 );
	}
	
	public static function permission_callback() {
		return true;
	}
}

API::init();
