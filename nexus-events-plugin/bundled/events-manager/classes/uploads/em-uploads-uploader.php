<?php
namespace EM\Uploads;

use EM_Exception, EM\Utils;

class Uploader {
	
	/**
	 * If uploading files via AJAX before form submission, files should be saved with this suffix to preserve between stript runs.
	 * @var string
	 */
	public static $temp_suffix = '-em-uploader';
	/**
	 * If set, the upload() function will set the upload directory to the following directory within the wp-uploads directory during the moving of an upload file.
	 * @var string
	 */
	public static $temp_uploads_dir;
	/**
	 * Array of validated file keys, so that upload can cross-check before proceeding.
	 * @var array
	 */
	public static $validated = [];
	
	/**
	 * Default options for handling file uploads. Some values are initialized dynamically in init().
	 *
	 * @var array<string, int|null> $default_options {
	 *     Array of default upload validation constraints.
	 *
	 *     @type bool $allow_multiple Whether multiple files can be uploaded.
	 *     @type int $max_files Maximum number of files allowed per upload.
	 *     @type bool $required Whether the upload field is mandatory.
	 *     @type int $max_file_size Maximum file size allowed (in bytes).
	 *     @type string[] $type Allowed file types (e.g., ['image']).
	 *     @type string[] $extensions Allowed file extensions (e.g., ['jpg', 'png', 'pdf']).
	 *     @type int $image_min_width Minimum width of uploaded images (in pixels).
	 *     @type int $image_max_width Maximum width of uploaded images (in pixels).
	 *     @type int $image_min_height Minimum height of uploaded images (in pixels).
	 *     @type int $image_max_height Maximum height of uploaded images (in pixels).
	 *     @type bool $disabled Initializes the uploader input as disabled if true.
	 * }
	 */
	public static $default_options = [
		'allow_multiple' => false,
		'max_files' => null,
		'max_file_size' => null,
		'required' => false,
		'type' => ['image'],
		'extensions' => [],
		'image_min_width' => 0,
		'image_max_width' => 0,
		'image_min_height' => 0,
		'image_max_height' => 0,
		'disabled' => false,
	];

	/**
	 * Supported filetypes by the uploader, add to these by hooking into em_uploads_uploader_init, restrict allowed types case-by-case in supplied $options when validating.
	 * @var array
	 */
	public static $supported_file_types = array(
		// Images
		'gif'  => array('exif_type' => 1, 'mime' => ['image/gif'], 'type' => 'image'),
		'jpg'  => array('exif_type' => 2, 'mime' => ['image/jpeg'], 'type' => 'image'),
		'jpeg' => array('exif_type' => 2, 'mime' => ['image/jpeg'], 'type' => 'image'),
		'png'  => array('exif_type' => 3, 'mime' => ['image/png'], 'type' => 'image'),
		'webp' => array('exif_type' => null, 'mime' => ['image/webp'], 'type' => 'image'),
		'heic' => array('exif_type' => null, 'mime' => ['image/heic'], 'type' => 'image'),

		// Documents
		'pdf'  => array('mime' => ['application/pdf'], 'type' => 'document'),
		'doc'  => array('mime' => ['application/msword', 'application/x-msword'], 'type' => 'document'),
		'docx' => array('mime' => ['application/vnd.openxmlformats-officedocument.wordprocessingml.document'], 'type' => 'document'),
		'rtf'  => array('mime' => ['text/rtf', 'application/rtf', 'application/x-rtf'], 'type' => 'document'),
		'odt'  => array('mime' => ['application/vnd.oasis.opendocument.text'], 'type' => 'document'),
		'txt'  => array('mime' => ['text/plain'], 'type' => 'document'),

		// Spreadsheets
		'xls'  => array('mime' => ['application/vnd.ms-excel', 'application/xls'], 'type' => 'spreadsheet'),
		'xlsx' => array('mime' => ['application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'], 'type' => 'spreadsheet'),
		'csv'  => array('mime' => ['text/csv', 'application/csv', 'text/plain'], 'type' => 'spreadsheet'),
		'ods'  => array('mime' => ['application/vnd.oasis.opendocument.spreadsheet'], 'type' => 'spreadsheet'),

		// Presentations
		'ppt'  => array('mime' => ['application/vnd.ms-powerpoint', 'application/mspowerpoint'], 'type' => 'presentation'),
		'pptx' => array('mime' => ['application/vnd.openxmlformats-officedocument.presentationml.presentation'], 'type' => 'presentation'),
		'odp'  => array('mime' => ['application/vnd.oasis.opendocument.presentation'], 'type' => 'presentation'),
	);

	public static function init() {
		static::$default_options['max_file_size'] = em_get_option('dbem_uploads_max_file_size');
		if ( static::$default_options['max_file_size'] > wp_max_upload_size() ) {
			static::$default_options['max_file_size'] = wp_max_upload_size();
		}
		static::$default_options['max_files'] = em_get_option('dbem_uploads_max_files');
		static::$default_options['allow_multiple'] = em_get_option('dbem_uploads_allow_multiple');
		static::$default_options['type'] = em_get_option('dbem_uploads_type');
		$extensions = str_replace( ' ', '', em_get_option('dbem_uploads_extensions') );
		static::$default_options['extensions'] = !empty($extensions) ? explode(',', $extensions) : [];

		static::$default_options['image_min_width'] = em_get_option('dbem_image_min_width');
		static::$default_options['image_max_width'] = em_get_option('dbem_image_max_width');
		static::$default_options['image_min_height'] = em_get_option('dbem_image_min_height');
		static::$default_options['image_max_height'] = em_get_option('dbem_image_max_height');

		do_action('em_uploads_uploader_init');
	}

	/**
	 * Server-side MIME detection of a file's actual bytes, independent of its name or of the type the browser claimed.
	 *
	 * @param string $path
	 * @return string Lower-cased MIME type, or '' when nothing could detect it.
	 */
	public static function sniff_mime_type( $path ) {
		$mime = '';
		if ( class_exists( 'finfo' ) ) {
			$mime = (string) ( new \finfo( FILEINFO_MIME_TYPE ) )->file( $path );
		}
		if ( ! $mime && function_exists( 'mime_content_type' ) ) {
			$mime = (string) mime_content_type( $path );
		}
		$mime = explode( ';', $mime );
		return strtolower( trim( $mime[0] ) );
	}

	/**
	 * Whether a MIME type is something a browser would render or execute if it were served from the site origin, which no document upload should ever be.
	 *
	 * @param string $mime
	 * @return bool
	 */
	public static function is_active_content_mime( $mime ) {
		$active = array( 'text/html', 'application/xhtml+xml', 'image/svg+xml', 'application/javascript', 'application/x-javascript', 'text/javascript', 'application/ecmascript', 'text/ecmascript', 'application/x-httpd-php', 'application/x-php', 'text/x-php', 'application/x-sh', 'text/x-shellscript' );
		return in_array( strtolower( (string) $mime ), apply_filters( 'em_uploads_active_content_mime_types', $active ), true );
	}

	
	/**
	 * Merges provided options with default options.
	 *
	 * Ensures that certain falsy values (image_* options and max_file_size) do not override defaults.
	 *
	 * @since 4.0.0
	 *
	 * @param array $options Custom options provided for the upload field.
	 * @return array Merged options with defaults.
	 */
	public static function get_options(array $options = []) {
		$merged_options = array_merge(self::$default_options, $options);
		
		// Preserve default values for specific options if the provided values are falsy
		$preserve_keys = ['max_file_size', 'image_max_width', 'image_max_height', 'image_min_width', 'image_min_height'];
		
		foreach ($preserve_keys as $key) {
			if (empty($options[$key]) && isset(self::$default_options[$key])) {
				$merged_options[$key] = self::$default_options[$key];
			}
		}
		$merged_options['extensions'] = $merged_options['extensions'] ?: [];
		if ( !is_array($merged_options['extensions']) ) $merged_options['extensions'] = explode(',', str_replace(' ', '', $merged_options['extensions']) );
		$merged_options['extensions'] = array_map('strtolower', $merged_options['extensions']);
		$merged_options['type'] = $merged_options['type'] ?: [];
		if ( !is_array($merged_options['type']) ) $merged_options['type'] = explode(',', str_replace(' ', '', $merged_options['type']) );
		$merged_options['type'] = array_map('strtolower', $merged_options['type']);

		// max filesize is always at most wp_max_upload_size();
		if ( empty($merged_options['max_file_size']) || $merged_options['max_file_size'] > wp_max_upload_size() ) {
			$merged_options['max_file_size'] = wp_max_upload_size();
		}
		return $merged_options;
	}
	
	/**
	 * Returns an array of accepted MIME types based on supplied options.
	 *
	 * This method uses the supplied options to filter the supported file types.
	 * If 'extensions' is provided and non-empty, only the MIME types for those extensions are returned.
	 * Otherwise, the MIME types are filtered by the allowed file 'type' values.
	 *
	 * @param array $options Options containing 'extensions' and/or 'type' keys.
	 * @return array Array of accepted MIME types.
	 */
	public static function get_accepted_mime_types( $options = [] ) {
		$options = static::get_options( $options );
		$accepted = array();
		if ( !empty($options['extensions']) && is_array($options['extensions'])) {
			foreach ( static::$supported_file_types as $ext => $data) {
				if (in_array($ext, $options['extensions'])) {
					$accepted = array_merge(  $accepted, $data['mime'] );
				}
			}
		} elseif ( !empty($options['type']) && is_array($options['type'])) {
			foreach ( static::$supported_file_types as $data) {
				if (in_array(strtolower($data['type']), $options['type'])) {
					$accepted = array_merge(  $accepted, $data['mime'] );
				}
			}
		} else {
			foreach ( static::$supported_file_types as $data) {
				$accepted = array_merge(  $accepted, $data['mime'] );
			}
		}
		
		return array_unique($accepted);
	}
	
	/**
	 * Prepare the $_FILES array for a file that was previously uploaded via EM_Upload_API before actually submitting a form. We assume all files uploaded are an array of items in $_FILES, allowing for multiple uploads.
	 *
	 * This function is somewhat equivalent to get_post() functions in Evesnt Manager, such as EM_Events->get_post(), whereas it gets uploaded files.
	 *
	 * Locates the file (saved earlier with a custom suffix), reads its properties (size, mime type, etc.), and populates $_FILES so that further processing works just like a normal upload.
	 *
	 * @param array|string  $file_key  The form field key to assign in $_FILES, which would match a submitted $_REQUEST array item with corresponding file IDs. If an array is supplied then it can match the path of a nested variable.
	 * @param array         $data      Data that can override the $_REQUEST variables, expects fields matching $file_key, such as ['field_key' => ['tmp_file_id'], 'field_key--names' => ['tmp_file_id' => 'temp-file-upload.jpg']]
	 *
	 * @return bool            True on success, false if no file uploaded
	 *@throws EM_Exception    If there are missing files, an exception is thrown.
	 */
	public static function prepare( $file_key, $data = [] ) {
		// contain the $_REQUEST if we need to
		if ( is_array($file_key) ) {
			$request_path = $file_key;
			$files_key = implode('-', $request_path);
			$file_key = array_pop( $request_path );
			$REQUEST = !empty($data) ? $data : Utils::_request( $request_path );
			// go throught $the $_FILES array and check if we have this path available, if so, we rename it to the new $files_key so it's not so multi-dimensional
			if ( empty( $_FILES[$file_key] ) ) {
				// handle possibility of input field using an array, and make $_FILES an array for validation purposes
				$first_path = array_shift($request_path);
				$file = [];
				if ( !empty($_FILES[$first_path]) ) {
					foreach ( $_FILES[$first_path] as $key => $file_array ) {
						$the_request_path = $request_path;
						$path_key = array_shift($the_request_path);
						$current_file = $file_array[ $path_key ];
						while ( $path_key ) {
							$path_key = array_shift( $the_request_path );
							if ( $path_key ) {
								if ( !empty( $current_file[ $path_key ] ) ) {
									$current_file = $current_file[ $path_key ];
								} else {
									break; // not right... bail
								}
							} elseif ( !empty( $current_file[ $file_key ] ) ) {
								// add the value to $file, whether empty or not
								$file[$key] = $current_file[ $file_key ];
							}
						}
					}
					if ( !empty( $file ) ) {
						$_FILES[$files_key] = $file;
						unset($_FILES[$first_path]);
					}
				}
			}
		} else {
			$files_key = $file_key;
			$REQUEST = !empty($data) ? $data : Utils::_request();
		}
		// check fallback or already prepared
		if ( !empty($_FILES[ $files_key ]) ) {
			// break out flattened files, we assume it's all multiple uploads for simplicity
			if ( !is_array($_FILES[ $files_key ]['name']) ) {
				foreach( $_FILES[ $files_key ] as $key => $val ) {
					$_FILES[ $files_key ][ $key ] = [$val];
				}
			}
			return true;
		}
		// For example, assume you saved it in the system temporary directory with a custom suffix.
		if( !empty( $REQUEST[ $file_key ] ) ) {
			if ( !is_array($REQUEST[ $file_key ]) ) {
				$REQUEST[ $file_key ] = [ $REQUEST[ $file_key ] ];
			}
			
			$_FILES[ $files_key ] = [
				'name'     => [],
				'type'     => [],
				'tmp_name' => [],
				'error'    => [],
				'size'     => [],
			];
			foreach( $REQUEST[ $file_key ] as $file_id ) {
				// Ignore already-uploaded URL items and empty placeholders. An empty value here (e.g. an existing file the uploader UI could not render, which submits a blank) must not abort the whole batch and discard the valid uploads sent alongside it.
				if ( $file_id === '' || $file_id === null || preg_match('/^https?:\/\//', $file_id) ) continue;
				$tmp_dir = ini_get('upload_tmp_dir') ?: sys_get_temp_dir(); // Fallback if not set
				$stored_file = trailingslashit($tmp_dir) . $file_id . static::$temp_suffix;

				// Make sure the file exists, the suffix ensures we uploaded it via the API
				if ( !file_exists( $stored_file ) ) {
					if ( count( $REQUEST[ $file_key ] ) > 1 ) {
						throw new EM_Exception('Missing pre-uploaded files.', 'em_upload_uploader_prepare_file');
					} else {
						return false;
					}
				}
				
				// Determine file properties.
				$file_size = filesize( $stored_file );
				// Use mime_content_type to guess the MIME type; you may use other libraries for more reliability.
				$file_type = mime_content_type( $stored_file );
				
				// the display name comes from the submitter and is shown to admins, so it is stored as plain text
				$file_name = !empty($REQUEST[$file_key.'--names'][$file_id]) && is_string($REQUEST[$file_key.'--names'][$file_id]) ? sanitize_text_field( $REQUEST[$file_key.'--names'][$file_id] ) : '';
				if ( $file_name === '' ) {
					$file_name = $file_id;
				}
				
				// Build the $_FILES array for this file.
				$_FILES[ $files_key ]['name'][] = $file_name;
				$_FILES[ $files_key ]['type'][] = $file_type;
				$_FILES[ $files_key ]['tmp_name'][] = $stored_file;
				$_FILES[ $files_key ]['error'][] = 0;
				$_FILES[ $files_key ]['size'][] = $file_size;
				$_FILES[ $files_key ]['uploaded'][] = true;
			}
			return true;
		}
		return false;
	}
	
	/**
	 * Validate an uploaded file (or files) based on provided options.
	 *
	 * This method validates the files in the $_FILES array for the given key. It is designed
	 * to work with files prepared via the updated prepare method, which populates $_FILES
	 * with arrays of values (allowing multiple file uploads). Overriding options (passed via
	 * $options) may define custom restrictions. See $default_options for available option types.
	 *
	 * @param array|string $file_key The key in the $_FILES array to validate, if an array is passed it's considered a path to the $_REQUEST if nested
	 * @param array  $options  An array of overriding validation options, as per EM_Uploadar::$default_options
	 *
	 * @throws \EM_Exception
	 * @return bool Validated file (or files) on success, null if no file is provided, throws error if validation fails.
	 */
	public static function validate( $file_key, $options = [], $data = [] ) {
		// prepare the files
		static::prepare( $file_key, $data );
		
		$files_key = $file_key;
		if( is_array($file_key) ) {
			$files_key = implode('-', $file_key);
			$file_key = array_pop($file_key);
		}
		
		$options = static::get_options( $options );
		
		// Check if files have been prepared.
		if ( empty( $_FILES[ $files_key ] ) || empty( $_FILES[ $files_key ]['size'][0] ) ||  current($_FILES[ $files_key ]['size']) <= 0 ) {
			if ( !empty( $options['required'] ) ) {
				throw new EM_Exception( __( 'File upload is required', 'events-manager' ), 'upload_required' );
			}
			static::$validated[$files_key] = true; // nothing 'wrong'
			return null;
		}
		
		// Check the "allow_multiple" option: if defined as false and more than one file is uploaded, return an error.
		if ( empty( $options['allow_multiple'] ) && count( $_FILES[ $files_key ]['size'] ) > 1 ) {
			throw new EM_Exception( __( 'Multiple file uploads are not allowed', 'events-manager' ), 'multiple_files_not_allowed' );
		} elseif ( !empty($options['max_files']) && count( $_FILES[ $files_key ]['size'] ) > $options['max_files'] ) {
			// individual field handlers need to also verify previously uploaded items don't exceed maximum somehow, such as modifying max_files before validating or additional validation
			throw new EM_Exception( sprintf(__( 'Maximum of %d files are allowed.', 'events-manager' ), $options['max_files']), 'multiple_files_not_allowed' );
		}
		
		$validated_files = array();
		
		// Determine permitted extensions from options.
		if ( ! empty( $options['extensions'] ) && is_array( $options['extensions'] ) ) {
			$restricted_extensions = array_flip( $options['extensions'] );
		} else {
			$restricted_extensions = array();
		}
		if ( ! empty( $restricted_extensions ) ) {
			$permitted_extensions = array_intersect_key( static::$supported_file_types, $restricted_extensions );
		} else {
			$permitted_extensions = static::$supported_file_types;
		}
		
		// filter by type as well
		if( !empty( $options['type']) ) {
			foreach ( $permitted_extensions as $extension => $extension_options ) {
				if ( !in_array( $extension_options['type'], $options['type'] ) ) {
					unset($permitted_extensions[$extension]);
				}
			}
		}
		
		// Loop through each file using the keys from the 'name' array.
		foreach ( $_FILES[ $files_key ]['name'] as $index => $file_name ) {
			$file_errors = array();
			// flatten $_FILES to single file one at a time
			$single_file = [];
			foreach ( $_FILES[ $files_key ] as $k => $file_array ) {
				$single_file[ $k ] = $file_array[$index];
			}
			
			// Skip files with size 0.
			if ( $single_file['size'] <= 0 ) {
				if ( ! empty( $options['required'] ) ) {
					$file_errors[] = __( 'File upload is required.', 'events-manager' );
				}
				// Skip this file.
				continue;
			}
			
			// proceed here if the uploaded key wasn't added during the static::prepare() function, because that'd mean it was previously uploaded by the API and that checks validate() already
			if ( empty($single_file['uploaded']) ) {
				
				// Ensure the file was properly uploaded via HTTP POST.
				if ( !is_uploaded_file( $single_file['tmp_name'] ) ) {
					$file_errors[] = __( 'Error uploading file, please try again!', 'events-manager' );
					// Skip this file.
					continue;
				}
				
				// Validate file size files.
				if ( !empty( $options['max_file_size'] ) && $single_file['size'] > $options['max_file_size'] ) {
					$file_errors[] = __( 'The file is too big! Maximum allowed size: ', 'events-manager' ) . size_format( $options['max_file_size'] );
					continue;
				}
				
				// Extract the file extension.
				preg_match( '/\.([a-zA-Z0-9]+)$/', $single_file['name'], $extension_match );
				$extension_str = ! empty( $extension_match[1] ) ? strtolower( $extension_match[1] ) : '';
				
				if ( $extension_str && array_key_exists( $extension_str, $permitted_extensions ) ) {
					$extension = $permitted_extensions[ $extension_str ];
					
					// Validate MIME type.
					if ( !in_array( $single_file['type'], $extension['mime'] ) ) {
						$file_errors[] = __( 'Unrecognized file format, could not match file MIME type according to file extension.', 'events-manager' );
					}
					
					if ( $extension['type'] === 'image' ) {
						
						// Validate EXIF type for images (if applicable).
						$exif_valid = true;
						if ( $extension['exif_type'] !== null ) {
							$exif_valid = exif_imagetype( $single_file['tmp_name'] ) === $extension['exif_type'];
						}
						if ( ! $exif_valid ) {
							$file_errors[] = __( 'Unrecognized image format, corrupted or non-present image EXIF header data.', 'events-manager' );
						} else {
							$image_info = getimagesize( $single_file['tmp_name'] );
							if ( false === $image_info ) {
								$file_errors[] = __( 'Could not read image size information.', 'events-manager' );
							} else {
								list( $width, $height ) = $image_info;
								$max_width  = $options['image_max_width'];
								$max_height = $options['image_max_height'];
								$min_width  = $options['image_min_width'];
								$min_height = $options['image_min_height'];
								
								if ( ($max_width && $width > $max_width ) || ($max_height && $height > $max_height ) ) {
									$w = $max_width ?: '*';
									$h = $max_height ?: '*';
									$file_errors[] = __( 'The image is too big! Maximum allowed dimensions: ', 'events-manager' ) . "$w x $h";
								}
								if ( ($min_width && $width < $min_width ) || ( $min_height && $height < $min_height ) ) {
									$w = $min_width ?: '*';
									$h = $min_height ?: '*';
									$file_errors[] = __( 'The image is too small! Minimum allowed dimensions: ', 'events-manager' ) . "$w x $h";
								}
							}
						}
					} else {
						// The browser-supplied type above is only a hint; libmagic decides what the bytes are, and anything a browser would execute is refused whatever the extension says.
						$sniffed_mime = static::sniff_mime_type( $single_file['tmp_name'] );
						if ( $sniffed_mime && static::is_active_content_mime( $sniffed_mime ) ) {
							$file_errors[] = __( 'The file content does not match its file extension.', 'events-manager' );
						}
						// Additional security validations for non-image file types.
						switch ( $extension_str ) {
							case 'pdf':
								$handle = fopen( $single_file['tmp_name'], 'rb' );
								if ( $handle ) {
									$header = fread( $handle, 4 ); // Technically you could read more to get version, e.g., 8 bytes.
									fclose( $handle );
									if ( strpos( $header, '%PDF' ) !== 0 ) {
										$file_errors[] = __( 'The file does not appear to be a valid PDF.', 'events-manager' );
									}
								} else {
									$file_errors[] = __( 'Could not open the PDF file for inspection.', 'events-manager' );
								}
								break;
							case 'doc':
							case 'xls':
							case 'ppt':
								$handle = fopen( $single_file['tmp_name'], 'rb' );
								if ( $handle ) {
									$header = fread( $handle, 8 );
									fclose( $handle );
									$expected = "\xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1";
									if ( $header !== $expected ) {
										$file_errors[] = __( 'The file does not appear to be a valid Microsoft Office document.', 'events-manager' );
									}
								} else {
									$file_errors[] = __( 'Could not open the file for inspection.', 'events-manager' );
								}
								break;
							case 'csv':
								$first_line = fgets( fopen( $single_file['tmp_name'], 'r' ) );
								if ( !str_contains( $first_line, ',' ) && !str_contains( $first_line, ';' ) ) {
									$file_errors[] = __( 'CSV file does not appear to contain valid data.', 'events-manager' );
								}
								break;
						}
						// further validation if necessary, and ideally validate any custom-added extensions!
						$file_errors = array_merge( $file_errors, (array) apply_filters('em_uploads_uploader_validate_extension_' . $extension_str, [], $single_file, ['file_key' => $file_key, 'files_key' => $files_key, 'options' => $options] ) );
					}
				} else {
					$allowed_exts = implode( ', ', array_keys( $permitted_extensions ) );
					$file_errors[] = sprintf( __( 'Uploaded file type not allowed. Permitted file types are: %s', 'events-manager' ), $allowed_exts );
				}
			}
			$validated_files[] = $single_file;
		}
		
		// If any errors were accumulated, or no files were validated throw exception.
		if ( ! empty( $file_errors ) ) {
			throw new EM_Exception( $file_errors, 'em_uploads_uploader_validate' );
		} elseif ( empty( $validated_files ) ) {
			throw new EM_Exception( __( 'No valid files were uploaded', 'events-manager' ), 'em_uploads_uploader_no_valid_files' );
		}
		
		// got here so it's OK
		static::$validated[$files_key] = true;
		return true;
	}
	
	/**
	 * Uploads one or more files at once from $_FILES[$file_key], assumes any validation (such as limiting upload items, sizes, formats etc.) or prepartion (for uploads done via the API) has already been done.
	 *
	 * No files are deleted here, only uploaded, any file deletions (if necessary) should be done before or after this uplaod.
	 *
	 * Upon success, an array of uploaded files is returned. If any files have an error whilst uploading, all successfully uploaded files are reverted back to the temporary file and an exception is thrown.
	 *
	 * @param array|string $file_key
	 * @param string $destination
	 * @param string $file_name    Filename to be used instead of uploaded filename. Multiple files will have a number added automatically if not unique, but if you provided {uuid} in the string a unique ID will be added in place of this, for example 'file-{uuid}' could become 'file-1j231231123123.ext'
	 *
	 * @throws EM_Exception
	 * @return array|null       Array of uploaded items including file, url and mime keys, null if no file was uploaded.
	 */
	public static function upload( $file_key, $destination = false, $file_name = false ) {
		// handle contained file key paths
		$files_key = $file_key;
		if( is_array($file_key) ) {
			$files_key = implode('-', $file_key);
			$file_key = array_pop($file_key);
		}
		// Check if this was validated
		if ( empty(static::$validated[$files_key]) ) {
			throw new EM_Exception( $file_key . ' not validated, cannot upload.', 'em_uploads_uploader_not_validated' );
		}
		// Re-check if files have been prepared.
		if ( empty( $_FILES[ $files_key ] ) || empty( $_FILES[ $files_key ]['size'][0] ) ||  current($_FILES[ $files_key ]['size']) <= 0 ) {
			return null;
		}
		// separate $_FILES key into multiple arrays for this upload because wp_handle_upload expects only one file
		// also, if $file_name is defined, we will rename filenames so they match the pattern provided
		$files = [];
		// currently testing uploading new file (fail), cannot add new file with form not unlocking submit button, same with f
		foreach( array_keys($_FILES[$files_key]['name']) as $i ) {
			$file = [];
			foreach ( $_FILES[$files_key] as $key => $values ) {
				$file[$key] = $values[$i];
			}
			// if a unique file name is provided, sort it out here
			if ( $file_name ) {
				// add the original file extension to end of file
				$file['filename'] = $file['name'];
				$file_extension_array = explode( '.', $file['filename'] );
				$file_extension = end( $file_extension_array );
				$file['uuid'] = str_replace('-','', wp_generate_uuid4());
				$new_file_name = str_replace('{uuid}', $file['uuid'], $file_name); // replace {uuid} with a dashless UUIDv4
				$file['name'] = $new_file_name . '.' . $file_extension;
			}
			$files[$file['tmp_name']] = $file;
		}
		require_once(ABSPATH . "wp-admin" . '/includes/file.php');
		
		// add short-circuit for custom uploads folder
		if ( !empty($destination) ) {
			static::$temp_uploads_dir = $destination;
			add_filter('upload_dir', [static::class, 'upload_dir'], 100 );
		}
		
		// upload files
		$uploaded_files = $uploads = [];
		foreach ( $files as $fn => $file ) {
			$result = wp_handle_upload( $file, ['test_form' => false, 'action' => 'em_handle_upload'] );
			/* Attach file to item */
			if ( !empty($result['error']) || is_wp_error( $result ) ){ /* @var array|\WP_Error $result */
				// error, undo previous uploads and exit loop
				$error = !empty($result['error']) ? $result['error'] : $result->get_error_message();
				// go through previous uploads
				foreach ( $uploaded_files as $upload_file_name => $upload ) {
					// as _wp_handle_upload does, inverted
					// phpcs:ignore WordPress.PHP.NoSilencedErrors.Discouraged
					@copy( $upload['file'], $upload_file_name );
					unlink( $upload['file'] );
				}
				throw new EM_Exception( $error, 'em_uploads_uploader_upload_failed' );
			} else {
				// uploaded, add uuid and move on
				$uploaded_files[$fn] = $result;
				$result['name'] = $file_name ? $file['filename'] : $file['name']; // original filename if $filename supplied
				$uploads[ $file['uuid'] ] = $result;
			}
		}
		
		// remove short-circuit for custom uploads folder
		if ( !empty($destination) ) {
			static::$temp_uploads_dir = null;
			remove_filter('upload_dir', [static::class, 'upload_dir'], 100 );
		}
		
		return $uploads;
	}
	
	public static function upload_dir( $upload_dir = false, $temp_uploads_dir = false ) {
		// remove year/month from subdirectory, add EM subdir
		if ( !$upload_dir ) {
			$upload_dir = _wp_upload_dir();
		}
		$subdir = $temp_uploads_dir ?: static::$temp_uploads_dir;
		if ( preg_match('/^\//', $subdir) ) {
			// absolute path
			$upload_dir['subdir'] = '';
			$upload_dir['url'] = $upload_dir['baseurl'] = '';
			$upload_dir['path'] = $upload_dir['basedir'] . $subdir;
		} else {
			// relative to uploads folder
			$upload_dir['subdir'] = preg_replace('/\/[0-9]{2,4}\/[0-9]{2,4}/', '', $upload_dir['subdir']) . '/' . $subdir;
			$upload_dir['url'] = $upload_dir['baseurl'] . $upload_dir['subdir'];
			$upload_dir['path'] = $upload_dir['basedir'] . $upload_dir['subdir'];
		}
		return $upload_dir;
	}
	
	/**
	 * Handle image upload for custom post types using WordPress media handling functions.
	 * It uses internal methods for file preparation and validation. On a successful upload, the image is attached
	 * as the featured image (post thumbnail) of the specified custom post.
	 *
	 * Note: If a deletion request is detected (via a request parameter named "{$file_key}_delete" or "{$file_key}--delete" ),
	 *  image deletion is handled by calling static::post_image_delete().
	 *
	 * @param string $file_key The key in the $_FILES array for the image upload.
	 * @param int    $post_id  The ID of the custom post to attach the image to.
	 *
	 * @throws EM_Exception IF there's a failure during upload.
	 * @return int|null     Attachment ID on success, null if nothing was uploaded.
	 */
	public static function post_image_upload( $file_key, $post_id ) {
		// If deletion is requested, handle it via the post_image_delete method.
		if ( ! empty( $_REQUEST[ $file_key . '_delete' ] ) ) {
			static::post_image_delete( $post_id );
		}
		// Check if files have been prepared.
		if ( empty( $_FILES[ $file_key ] ) || empty( $_FILES[ $file_key ]['size'][0] ) ||  current($_FILES[ $file_key ]['size']) <= 0 ) {
			// if nothing was uploaded, check to delete image post-upload, in case em-uploader.js removed the file
			if ( !empty($_REQUEST[ $file_key . '--deleted' ][$file_key]) ) {
				static::post_image_delete( $post_id );
			}
			return null;
		}
		
		// a little trick... we flatten the $_FILES key for this image, because media_handle_upload expects only one file
		$file = [];
		foreach( $_FILES[$file_key] as $key => $value ) {
			$file[$key] = is_array( $value ) ? current($value) : $value;
		}
		$_FILES[$file_key] = $file;
		
		// Include WordPress media handling files.
		require_once( ABSPATH . 'wp-admin/includes/file.php' );
		require_once( ABSPATH . 'wp-admin/includes/image.php' );
		require_once( ABSPATH . 'wp-admin/includes/media.php' );
		
		// Process the upload.
		$attachment_id = media_handle_upload( $file_key, $post_id, [], ['test_form' => false, 'action' => 'em_handle_upload'] );
		if ( is_wp_error( $attachment_id ) ) {
			$error_string = __( 'There was an error uploading the image.', 'events-manager' );
			$error_string .= ' <em>('. implode(' ', $attachment_id->get_error_messages()) .')</em>';
			throw new EM_Exception( $error_string, 'upload_error' );
		}
		// Update the custom post meta to attach the new image as the featured image.
		static::post_image_delete( $post_id );
		update_post_meta( $post_id, '_thumbnail_id', $attachment_id );
		
		return apply_filters( 'em_uploads_uploader_handle_post_image_upload', true, $post_id );
	}
	
	public static function post_image_delete( $post_id, $force_delete = true ) {
		global $wpdb;
		//check that this image isn't being used by another CPT
		$post_thumbnail_id = get_post_thumbnail_id( $post_id );
		$sql = $wpdb->prepare('SELECT count(*) FROM '.$wpdb->postmeta." WHERE meta_key='_thumbnail_id' AND meta_value=%d", array($post_thumbnail_id));
		if( $wpdb->get_var($sql) <= 1 ){
			//not used by any other CPT, so just delete the image entirely (would usually only be used via front-end which has no media manager)
			$result = wp_delete_attachment($post_thumbnail_id, $force_delete );
		}else{
			//just delete image association
			$result = delete_post_meta($post_id, '_thumbnail_id');
		}
		return $result;
	}
	
	/**
	 * @param \EM_Object $EM_Object
	 * @param string $path
	 * @param string $name
	 *
	 * @return void
	 */
	public static function post_image_uploader( $EM_Object, $path, $name ) {
		$path = esc_attr($path);
		$name = esc_attr($name);
		$accepted = implode(', ', Uploader::get_accepted_mime_types(['type' => 'image']) );
		?>
		<input id='<?php echo $path ?>' name='<?php echo $name ?>' class='<?php echo $path ?> em-uploader' type='file' size='40' data-api-path="<?php echo $path ?>" data-api-nonce="<?php echo wp_create_nonce('em_uploads_api/'.$path); ?>" accept="<?php echo esc_attr($accepted); ?>">
		<script type="application/json" class="em-uploader-files">
			<?php
				// you can also do this for em-uploader-options and supply overriding options for filepond
				// prepare data for uploaded event image(s)
				$image_data = [];
				$image_url = $EM_Object->get_image_url();
				if ( !empty($_REQUEST[$name]) ) {
					foreach( $_REQUEST[$name] as $file_id ) {
						$image_data[] = [
							'id' => $file_id,
							'name' => !empty($_REQUEST[$name . '--names'][$file_id]) ? $_REQUEST[$name . '--names'][$file_id] : false,
							'nonce' => wp_create_nonce( 'em_uploads_api_file/'. $path .'/' . $EM_Object->post_id), // nonce for deleting the image
						];
					}
				} elseif ( $image_url ) {
					$parsedUrl = parse_url($image_url);
					$pathInfo = pathinfo( $parsedUrl['path'] );
					$image_data[] = [
						'id' => $name, // add a unique ID so we can identify the file should we need to delete it, in this case one image per event so event_id is enough
						'url' => $image_url, // url to get image for preview
						'name' => $pathInfo['basename'], // file name for display purposes
						'nonce' => wp_create_nonce( 'em_uploads_api_file/'. $path .'/' . $EM_Object->post_id), // nonce for deleting the image
					];
				}
				echo json_encode( $image_data );
			?>
		</script>
		<ul class="em-input-upload-files em-input-upload-fallback">
			<?php
			if ( !empty($pathInfo) ) {
				?>
				<li data-file_id="<?php echo esc_attr($name); ?>">
					<?php if ( $image_url != '') : ?>
						<img src='<?php echo esc_url($EM_Object->get_image_url('medium')); ?>' alt='<?php echo esc_attr($EM_Object->name); ?>'>
					<?php endif; ?>
					<button type="button" class="em-icon em-icon-undo em-tooltip" aria-label="<?php esc_html_e('Undo','em-pro'); ?>"></button>
					<a href="<?php echo esc_url($image_url); ?>" target="_blank"><?php echo esc_html( $pathInfo['basename'] ); ?></a>
					<button type="button" class="em-icon em-icon-trash em-tooltip" aria-label="<?php esc_html_e('Delete','events-manager'); ?>"></button>
				</li>
				<?php
			}
			?>
		</ul>
		<ul class="em-input-upload-files-tbd hidden">
			<li><?php esc_html_e('Image will be deleted when saving your changes if unused by others.', 'em-pro'); ?></li>
		</ul>
		<?php
			if ( !empty($_REQUEST[$name.'--deleted']) ){
				foreach( $_REQUEST[$name.'--deleted'] as $file_id  => $value ) {
					?>
					<input type="hidden" name="<?php echo $name . '--deleted['. esc_attr($file_id) .']'; ?>" value="<?php echo esc_attr($value); ?>">
					<?php
				}
			}
			if ( !empty($_REQUEST[$name.'--names']) ){
				foreach( $_REQUEST[$name.'--names'] as $file_id => $file_name ) {
					?>
					<input type="hidden" name="<?php echo $name . '--names['. esc_attr($file_id) .']'; ?>" value="<?php echo esc_attr($file_name); ?>">
					<?php
				}
			}
		?>
		<script type="application/json" class="em-uploader-options">
			<?php
			$json_options = array(
				'maxFileSize' => em_get_option('dbem_image_max_size'),
			);
			echo json_encode($json_options);
			?>
		</script>
		<?php
	}
}
add_filter('events_manager_loaded', ['EM\Uploads\Uploader', 'init'], 1);