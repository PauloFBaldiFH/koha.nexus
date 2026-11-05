<?php
namespace EM;
use EM_ML;

/**
 * @author marcus
 * Contains functions for loading styles on both admin and public sides.
 */
class Scripts_and_Styles {

	public static $locale;
	public static $localize_flatpickr;
	/**
	 * Static property to store additional JS variables to be added in the footer
	 * @var array
	 */
	public static $footer_vars = array();

	public static function init() {
		if ( is_admin() ) {
			//Scripts and Styles
			add_action( 'admin_enqueue_scripts', array ( static::class, 'admin_enqueue' ) );
			add_action( 'admin_print_footer_scripts', array ( static::class, 'localize_script_footer' ), 100 );
		} else {
			add_action( 'wp_enqueue_scripts', array ( static::class, 'public_enqueue' ) );
			add_action( 'em_enqueue_styles', 'EM_Scripts_and_Styles::inline_enqueue' );
			add_action( 'wp_footer', array ( static::class, 'localize_script_footer' ) );
		}
		static::$locale = substr( get_locale(), 0, 2 );
	}

	public static function register(){
		// register scripts - empty for now (removed em-select in favour of direct inclusion in events-manager.js)
		do_action('em_scripts_and_styles_register');
	}

	/**
	 * Enqueuing public scripts and styles
	 */
	public static function public_enqueue() {
		global $wp_query;
		static::register();
		$pages = array( //pages which EM needs CSS or JS
			'events' => em_get_option('dbem_events_page'),
			'edit-events' => em_get_option('dbem_edit_events_page'),
			'edit-locations' => em_get_option('dbem_edit_locations_page'),
			'edit-bookings' => em_get_option('dbem_edit_bookings_page'),
			'my-bookings' => em_get_option('dbem_my_bookings_page')
		);
		$pages = apply_filters('em_scripts_and_styles_public_enqueue_pages', $pages);
		$obj = $wp_query->get_queried_object();
		$obj_id = 0;
		if( is_home() ){
			$obj_id = '-1';
		}elseif( !empty( $obj->ID ) ){
			$obj_id = $obj->ID;
		}

		//Decide whether or not to include certain JS files and dependencies
		$script_deps = array();
		if( em_get_option('dbem_js_limit') ){
			//determine what script dependencies to include, and which to not include
			if( is_page($pages) ){
				$script_deps['jquery'] = 'jquery';
			}
			if( (!empty($pages['events']) && is_page($pages['events']) && ( em_get_option('dbem_events_page_search_form') || (EM_MS_GLOBAL && !get_site_option('dbem_ms_global_events_links', true)) )) || em_get_option('dbem_js_limit_search') === '0' || in_array($obj_id, explode(',', em_get_option('dbem_js_limit_search')))  ){
				//events page only needs datepickers
				$script_deps['jquery-ui-core'] = 'jquery-ui-core';
				$script_deps['jquery-ui-datepicker'] = 'jquery-ui-datepicker';
			}
			if( (!empty($pages['edit-events']) && is_page($pages['edit-events'])) || em_get_option('dbem_js_limit_events_form') === '0' || in_array($obj_id, explode(',', em_get_option('dbem_js_limit_events_form'))) ){
				//submit/edit event pages require
				$script_deps['jquery-ui-core'] = 'jquery-ui-core';
				$script_deps['jquery-ui-datepicker'] = 'jquery-ui-datepicker';
			}
			if( (!empty($pages['edit-bookings']) && is_page($pages['edit-bookings'])) || em_get_option('dbem_js_limit_edit_bookings') === '0' || in_array($obj_id, explode(',', em_get_option('dbem_js_limit_edit_bookings'))) ){
				//edit booking pages require a few more ui scripts
				$script_deps['jquery-ui-core'] = 'jquery-ui-core';
				$script_deps['jquery-ui-widget'] = 'jquery-ui-widget';
				$script_deps['jquery-ui-position'] = 'jquery-ui-position';
				$script_deps['jquery-ui-sortable'] = 'jquery-ui-sortable';
				$script_deps['jquery-ui-dialog'] = 'jquery-ui-dialog';
			}
			if( in_array( $obj->post_type ?? '', Archetypes::get_cpts() ) ){
				$script_deps['jquery'] = 'jquery';
			}
			//check whether to load our general script or not
			if( empty($script_deps) ){
				if( em_get_option('dbem_js_limit_general') === "0" || in_array($obj_id, explode(',', em_get_option('dbem_js_limit_general'))) ){
					$script_deps['jquery'] = 'jquery';
				}
			}
		}else{
			$script_deps = array(
				'jquery'=>'jquery',
				'jquery-ui-core'=>'jquery-ui-core',
				'jquery-ui-widget'=>'jquery-ui-widget',
				'jquery-ui-position'=>'jquery-ui-position',
				'jquery-ui-sortable'=>'jquery-ui-sortable',
				'jquery-ui-datepicker'=>'jquery-ui-datepicker',
				'jquery-ui-dialog'=>'jquery-ui-dialog'
			);
		}
		if( static::$localize_flatpickr ){
			$script_deps['em-flatpickr-localization'] = 'em-flatpickr-localization';
		}
		$script_deps = apply_filters('em_public_script_deps', $script_deps);
		if( !empty($script_deps) ){ //given we depend on jQuery, there must be at least a jQuery dep for our file to be loaded
			static::enqueue_scripts( $script_deps );
		}
		// list tables dependencies
		/*
		$style_deps = array();
		if( (!empty($pages['edit-bookings']) && is_page($pages['edit-bookings'])) || em_get_option('dbem_js_limit_edit_bookings') === '0' || in_array($obj_id, explode(',', em_get_option('dbem_js_limit_edit_bookings'))) ){
			$script_deps[] = 'list-tables';
			$style_deps[] = 'list-tables';
		}
		*/
		//Now decide on showing the CSS file
		if( em_get_option('dbem_css_limit') ){
			$includes = em_get_option('dbem_css_limit_include');
			$excludes = em_get_option('dbem_css_limit_exclude');
			if( (!empty($pages) && is_page($pages)) || (!empty($obj->post_type) && in_array($obj->post_type, Archetypes::get_cpts())) || $includes === "0" || in_array($obj_id, explode(',', $includes)) ){
				$include = true;
			}
			if( $excludes === '0' || (!empty($obj_id) && in_array($obj_id, explode(',', $excludes))) ){
				$exclude = true;
			}
			if( !empty($include) && empty($exclude) ){
				static::enqueue_public_styles();
			}
		}else{
			static::enqueue_public_styles();
		}
	}

	public static function inline_enqueue(){
		// check if we want to override our theme basic styles as per styling options
		if( em_get_option('dbem_css_theme') ){
			$css = array();
			if( em_get_option('dbem_css_theme_font_family') == 1 ) $css[] = '--font-family : inherit;';
			if( em_get_option('dbem_css_theme_font_weight') == 1 ) $css[] = '--font-weight : inherit;';
			if( em_get_option('dbem_css_theme_font_size') == 1 )   $css[] = '--font-size : 1em;';
			if( em_get_option('dbem_css_theme_line_height') == 1 ) $css[] = '--line-height : inherit;';
			if( !empty($css) ){
				wp_add_inline_style( 'events-manager', 'body .em { '. implode(' ', $css) .' }' );
			}
		}
	}

	public static function admin_enqueue( $hook_suffix = false ){
		if( $hook_suffix == 'post.php' || $hook_suffix === true || (!empty($_GET['page']) && substr($_GET['page'],0,14) == 'events-manager') || (!empty($_GET['post_type']) && in_array($_GET['post_type'], Archetypes::get_cpts())) ){
			if( $hook_suffix == 'post.php' && empty($_GET['post_type']) && !empty($_GET['post']) ){
				// don't load if the post being edited isn't an EM one
				$post = get_post($_GET['post']);
				if( !in_array( $post->post_type, Archetypes::get_cpts() ) ) return;
			}
			static::register();
			wp_enqueue_style( 'wp-color-picker' );
			static::enqueue_scripts();
			static::enqueue_admin_styles();
			if( empty($_REQUEST['page']) ) {
				static::enqueue_public_styles();
			}
			do_action('em_enqueue_admin_styles');
			static::enqueue_admin_scripts();
			self::localize_script();
			if( !empty($_REQUEST['page']) && $_REQUEST['page'] === 'events-manager-options' ){
				wp_enqueue_code_editor( array( 'type' => 'text/html' ) );
				$min = static::get_minified_extension_js();
				wp_enqueue_script('events-manager-settings', plugins_url('includes/js/admin-settings'.$min.'.js',EM_FILE), array(), EM_VERSION);
			}
		}
	}

	public static function enqueue_public_styles( $deps = array(), $min = true ){
		$min = static::get_minified_extension_css( $min );
		wp_enqueue_style('events-manager', plugins_url('includes/css/events-manager' . $min . '.css', EM_FILE), $deps, EM_VERSION); //main css
		do_action('em_enqueue_styles', $deps, $min);
	}

	public static function enqueue_scripts( $deps = null, $min = true ){
		$min = static::get_minified_extension_js( $min );
		if( $deps === null ){
			// default deps if null
			$deps = array('jquery', 'jquery-ui-core','jquery-ui-widget','jquery-ui-position','jquery-ui-sortable','jquery-ui-datepicker','jquery-ui-dialog','wp-color-picker');
		}
		wp_enqueue_script('events-manager', plugins_url('includes/js/events-manager'.$min.'.js',EM_FILE), $deps, EM_VERSION);
		if( static::$locale != 'en' && file_exists(EM_DIR."/includes/external/flatpickr/l10n/".static::$locale.".min.js") ){
			wp_enqueue_script('em-flatpickr-localization', plugins_url("includes/external/flatpickr/l10n/" . static::$locale . $min. ".js", EM_FILE), array('events-manager'), EM_VERSION);
			static::$localize_flatpickr = true;
		}
		self::localize_script();
		do_action('em_enqueue_scripts', $deps, $min);
	}

	public static function enqueue_admin_styles( $deps = array(), $min = true ){
		$min = static::get_minified_extension_css( $min );
		wp_enqueue_style('events-manager-admin', plugins_url('includes/css/events-manager-admin'.$min.'.css',EM_FILE), $deps, EM_VERSION);
		do_action('em_enqueue_admin_styles', $deps, $min);
	}

	/**
	 * Enqueue admin-only scripts for EM editor screens and fire em_enqueue_admin_scripts so add-ons can inject admin JS. The scripts analogue of enqueue_admin_styles()/em_enqueue_admin_styles. Called on the classic admin (admin_enqueue) AND inside the Gutenberg canvas iframe (EM_Blocks::enqueue_block_styles), so add-on editor JS reaches the canvas the same way add-on CSS does.
	 */
	public static function enqueue_admin_scripts( $deps = array(), $min = true ){
		do_action( 'em_enqueue_admin_scripts', $deps, $min );
	}

	/**
	 * Enqueue the event-editor stylesheet that styles the When/Recurrences/Bookings forms. In the classic editor this is loaded on demand by EM's JS asset-loader when it sees the .em-event-editor body class, so it has no dedicated enqueue path. The block editor renders those same forms inside the canvas iframe, which the JS loader can't reach, so the iframe enqueue (EM_Blocks::enqueue_block_styles) calls this directly. Depends on events-manager-admin so the cascade order matches the classic editor.
	 */
	public static function enqueue_event_editor_styles( $deps = array('events-manager-admin'), $min = true ){
		$min = static::get_minified_extension_css( $min );
		wp_enqueue_style('events-manager-event-editor', plugins_url('includes/css/events-manager-event-editor'.$min.'.css',EM_FILE), $deps, EM_VERSION);
	}

	public static function get_minified_extension_css( $minified = true ) {
		if( !em_get_option('dbem_css_minified', false) ) return ''; // force non-minified file for now, because AVAST AVG is giving a false positive and wreaking havoc
		return static::get_minified_extension( $minified );
	}

	public static function get_minified_extension_js( $minified = true ) {
		if( !em_get_option('dbem_js_minified', false) ) return ''; // force non-minified file for now, because AVAST AVG is giving a false positive and wreaking havoc
		return static::get_minified_extension( $minified );
	}

	public static function get_minified_extension( $minified = true ){
		return ( !$minified || defined( 'WP_DEBUG' ) && WP_DEBUG ) || ( defined( 'SCRIPT_DEBUG' ) && SCRIPT_DEBUG ) || ( defined( 'EM_DEBUG' ) && EM_DEBUG ) ? '' : '.min';
	}

	/**
	 * Returns an optional suffix to use in CSS/JS enqueueing, which is .min if in production mode
	 *
	 * @return string
	 */
	public static function min_suffix(){
		return !((defined('WP_DEBUG') && WP_DEBUG) || (defined('EM_DEBUG') && EM_DEBUG)) ? '.min':'';
	}

	/**
	 * Localize the script vars that require PHP intervention, removing the need for inline JS.
	 */
	public static function localize_script( $script = 'events-manager' ){
		global $em_localized_js;
		$locale_code = substr ( get_locale(), 0, 2 );
		//Localize
		$em_localized_js = array(
			'ajaxurl' => admin_url('admin-ajax.php'),
			'locationajaxurl' => admin_url('admin-ajax.php?action=locations_search'),
			'firstDay' => em_get_option('start_of_week'),
			'locale' => $locale_code,
			'dateFormat' => 'yy-mm-dd', //em_get_option('dbem_date_format_js', 'yy-mm-dd'), // DEPRECATED (legacy jQuery UI datepicker) - prevents blank datepickers if no option set
			'ui_css' => plugins_url('includes/css/jquery-ui/build.min.css', EM_FILE),
			'show24hours' => em_get_option('dbem_time_24h'),
			'is_ssl' => is_ssl(),
			'autocomplete_limit' => apply_filters('em_locations_autocomplete_limit', 10),
			'calendar' => array(
				'breakpoints' => array( 'small' => 560, 'medium' => 908, 'large' => false, ), // reorder this array for efficiency if you override it, so smallest is first, largest or false is last
				'month_format' => em_get_option('dbem_full_calendar_month_format', 'F Y'),
			),
			'phone' => false,
			'datepicker' => array(
				'format' => em_get_option('dbem_datepicker_format', 'Y-m-d'),
			),
			'search' => array(
				'breakpoints' => array( 'small' => 650, 'medium' => 850, 'full' => false, ) // reorder this array for efficiency if you override it, so smallest is first, largest or false is last
			),
			'url' => plugins_url('', EM_FILE),
			// add assets that load JS or CSS based on classes present in a document load
			// if no absolute url provided, it's assumed to be inside events-manager/includes/external
			'assets' => [],
			'cached' => defined('WP_CACHE') && WP_CACHE || defined('EM_CACHE') && EM_CACHE,
		);
		// get externals, the externals will be loaded during page init via JS to keep things light
		$js = static::get_minified_extension_js().'.js'.'?v='.EM_VERSION;
		$css = static::get_minified_extension_css().'.css'.'?v='.EM_VERSION;
		$js_url = EM_DIR_URI . 'includes/js/';
		$css_url = EM_DIR_URI . 'includes/css/';

		// JS Lazy Loading - Load JS on demand if a certain element is found via querySelector
		// TODOC - Dev docs for how to add JS to EM with lazy loadign
		/* // timepicker v2 - WIP
		$em_localized_js['assets']['.em-time-range'] = [
			'js' => [
				'timepicker-js' => ['url' => 'timepicker-js/timepicker'.$js, 'event' => 'em_timepicker_ready'],
			],
			'css' => [
				'timepicker-js' => 'timepicker-js/timepicker'.$css,
			],
		];
		*/
		// uploads
		if( em_get_option('dbem_uploads_ui') ) {
			$em_localized_js['assets']['input.em-uploader'] = [
				// each type has key for id of script/link (prefixed automatically by -css/js) and either url or for JS possible array of url and event fired onload for script, third value can also be a locale
				'js' => [
					'em-uploader' => ['url' => $js_url.'em-uploader'.$js, 'event' => 'em_uploader_ready', 'requires' => 'filepond'],
					'filepond-validate-size' => 'filepond/plugins/filepond-plugin-file-validate-size'.$js,
					'filepond-validate-type' => 'filepond/plugins/filepond-plugin-file-validate-type'.$js,
					//'filepond-image-preview' => 'filepond/plugins/filepond-plugin-image-preview'.$js, // replaced by our overlay function
					'filepond-image-validate-size' => 'filepond/plugins/filepond-plugin-image-validate-size'.$js,
					'filepond-exif-orientation' => 'filepond/plugins/filepond-plugin-image-exif-orientation'.$js,
					'filepond-get-file' => 'filepond/plugins/filepond-plugin-get-file'.$js,
					'filepond-plugin-image-overlay' => 'filepond/plugins/filepond-plugin-image-overlay'.$js,
					'filepond-plugin-image-thumbnail' => 'filepond/plugins/filepond-plugin-image-thumbnail'.$js,
					'filepond-plugin-pdf-preview-overlay' => 'filepond/plugins/filepond-plugin-pdf-preview-overlay'.$js,
					'filepond-plugin-file-icon' => 'filepond/plugins/filepond-plugin-file-icon'.$js,
					'filepond' => [ 'url' => 'filepond/filepond'.$js, 'locale' => preg_match('/^en/i', EM_ML::$wplang) ? '' : strtolower(str_replace('_', '-', EM_ML::$wplang)) ],
					//'cropperjs' => 'cropper/cropper'.$js
				],
				'css' => [
					'em-filepond' => 'filepond/em-filepond'.$css,
					'filepond-preview' => 'filepond/plugins/filepond-plugin-image-preview'.$css,
					'filepond-plugin-image-overlay' => 'filepond/plugins/filepond-plugin-image-overlay'.$css,
					'filepond-get-file' => 'filepond/plugins/filepond-plugin-get-file'.$css,
					//'cropperjs' => 'cropper/cropper'.$css,
				],
			];
			// localize variables
			$em_localized_js['uploads'] = [
				'endpoint' => rest_url('events-manager/v1/uploads'),
				'nonce' => wp_create_nonce('em_image_upload'),
				'delete_confirm' => esc_html__('Are you sure you want to delete this file? It will be deleted upon submission.', 'events-manager'),
				'images' => [
					'max_file_size'    => Uploads\Uploader::$default_options['max_file_size'],
					'image_max_width'  => Uploads\Uploader::$default_options['image_max_width'],
					'image_max_height' => Uploads\Uploader::$default_options['image_max_height'],
					'image_min_width'  => Uploads\Uploader::$default_options['image_min_width'],
					'image_min_height' => Uploads\Uploader::$default_options['image_min_height'],
				],
				'files' => [
					'max_file_size'    => Uploads\Uploader::$default_options['max_file_size'],
					'types' => Uploads\Uploader::get_accepted_mime_types(),
				]
			];
			$em_localized_js['api_nonce'] = wp_create_nonce('wp_rest');
		} else {
			$em_localized_js['assets']['input.em-uploader'] = [
				// each type has key for id of script/link (prefixed automatically by -css/js) and either url or for JS possible array of url and event fired onload for script, third value can also be a locale
				'js' => [ 'em-uploader' => ['url' => $js_url.'em-uploader'.$js, 'event' => 'em_uploader_ready'] ],
			];
		}
		// timerange editor for admin area
		$em_localized_js['assets']['.em-event-editor'] = [
			'js' => [
				'event-editor' => ['url' => $js_url.'events-manager-event-editor'.$js, 'event' => 'em_event_editor_ready']
			],
			'css' => [
				'event-editor' => $css_url.'events-manager-event-editor'.$css
			],
		];
		// timezone support via Luxon.js
		$em_localized_js['assets']['.em-recurrence-sets, .em-timezone'] = [
			'js' => [
				'luxon' => ['url' => 'luxon/luxon'.$js, 'event' => 'em_luxon_ready' ],
			],
		];
		// booking form loader
		$em_localized_js['assets']['.em-booking-form, #em-booking-form, .em-booking-recurring, .em-event-booking-form'] = apply_filters('em_booking_form_assets', [
			'js' => [
				'em-bookings' => ['url' => $js_url.'bookingsform'.$js, 'event' => 'em_booking_form_js_loaded' ],
			],
		], $js_url, $js);
		// let other plugins add EM JS/CSS assets
		$em_localized_js['assets'] = apply_filters( 'em_enqueue_assets', $em_localized_js['assets'] );
		// add phone number validation and localization
		if( Phone::is_enabled() ) {
			$em_localized_js['phone'] = array(
				'error' => __('Please enter a valid phone number.', 'events-manager'),
				'detectJS' => em_get_option('dbem_phone_detect') == true,
				//'initialCountry' => 'US',
				'options' => array(
					'initialCountry' => em_get_option('dbem_phone_default_country', 'US'),
					'separateDialCode' => em_get_option('dbem_phone_show_selected_code') == true,
					'showFlags' => em_get_option('dbem_phone_show_flags') == true,
					'onlyCountries' => em_get_option('dbem_phone_countries_include') ?: array(),
					'excludeCountries' => em_get_option('dbem_phone_countries_exclude') ?: array(),
					//'preferredCountries' => em_get_option('dbem_phone_countries_preferred'), // not working in 23.x due to search
					//'nationalMode' => em_get_option('dbem_phone_national_format') == true,
				),
			);
		}
		// localize flatpickr
		if( static::$localize_flatpickr ){
			$em_localized_js['datepicker']['locale'] = static::$locale;
		}
		//maps api key
		if( em_get_option('dbem_gmap_is_active') ){
			if( em_get_option('dbem_google_maps_browser_key') ){
				$em_localized_js['google_maps_api'] = em_get_option('dbem_google_maps_browser_key');
			}
			if( em_get_option('dbem_google_maps_styles') ){
				$em_localized_js['google_maps_styles'] = json_decode(em_get_option('dbem_google_maps_styles'));
			}
		}
		//debug mode
		if( defined('WP_DEBUG') && WP_DEBUG ) $em_localized_js['ui_css'] = plugins_url('includes/css/jquery-ui/build.css', EM_FILE);
		//booking-specific stuff
		if( em_get_option('dbem_rsvp_enabled') ){
			$offset = defined('EM_BOOKING_MSG_JS_OFFSET') ? EM_BOOKING_MSG_JS_OFFSET : 30;
			$em_localized_js = array_merge($em_localized_js, array(
				'bookingInProgress' => __('Please wait while the booking is being submitted.','events-manager'),
				'tickets_save' => __('Save Ticket','events-manager'),
				'bookingajaxurl' => admin_url('admin-ajax.php'),
				'bookings_export_save' => __('Export Bookings','events-manager'),
				'bookings_settings_save' => __('Save Settings','events-manager'),
				'booking_delete' => __("Are you sure you want to delete?",'events-manager'),
				'booking_offset' => $offset,
				'bookings' => array(
					'submit_button' => array(
						'text' => array(
							'default' => em_get_option('dbem_bookings_submit_button'),
							'free' => em_get_option('dbem_bookings_submit_button'),
							'payment' => em_get_option('dbem_bookings_submit_button_paid'),
							'processing' => em_get_option('dbem_bookings_submit_button_processing'),
						),
					),
					'update_listener' => implode( ',', apply_filters('em_booking_form_js_fields_change_match', array() )), // if anything here matches a field in the booking form, em_booking_form_updated JS Event will be triggered
				),
				//booking button
				'bb_full' =>  em_get_option('dbem_booking_button_msg_full'),
				'bb_book' => em_get_option('dbem_booking_button_msg_book'),
				'bb_booking' => em_get_option('dbem_booking_button_msg_booking'),
				'bb_booked' => em_get_option('dbem_booking_button_msg_booked'),
				'bb_error' => em_get_option('dbem_booking_button_msg_error'),
				'bb_cancel' => em_get_option('dbem_booking_button_msg_cancel'),
				'bb_canceling' => em_get_option('dbem_booking_button_msg_canceling'),
				'bb_cancelled' => em_get_option('dbem_booking_button_msg_cancelled'),
				'bb_cancel_error' => em_get_option('dbem_booking_button_msg_cancel_error'),
			));
			// Cancellation warning
			if( em_get_option('dbem_event_status_enabled') ){
				$cancellation_text = __('If you choose to cancel your event, after you save this event, no further bookings will be possible for this event.', 'events-manager');
				$additionals_text = '';
				if( em_get_option('dbem_event_cancelled_bookings') ){
					$additionals_text .= '\n- ' . __('Bookings will be automatically cancelled.', 'events-manager');
					if( em_get_option('dbem_event_cancelled_bookings_email') ){
						$additionals_text .= '\n- ' . __('Booking cancellation emails will be sent.', 'events-manager');
					}else{
						$additionals_text .= ' ' . __('Booking cancellation emails are not sent.', 'events-manager');
					}
				}
				if( em_get_option('dbem_event_cancelled_email') ){
					$additionals_text .= '\n- ' . __('All confirmed and pending bookings will be emailed a general event cancellation notification.', 'events-manager');
				}
				if( !empty($additionals_text) ){
					$cancellation_text .= '\n\n' . __('Also, the following will occur:', 'events-manager');
					$cancellation_text .= '\n' . $additionals_text;
				}
				$em_localized_js['event_cancellations'] = array(
					'warning' => $cancellation_text,
				);
			}
		}
		$em_localized_js['txt_search'] = em_get_option('dbem_search_form_text_label',__('Search','events-manager'));
		$em_localized_js['txt_searching'] = __('Searching...','events-manager');
		$em_localized_js['txt_loading'] = __('Loading...','events-manager');

		//logged in messages that visitors shouldn't need to see
		if( is_user_logged_in() || is_page(em_get_option('dbem_edit_events_page')) ){
			if( em_get_option('dbem_recurrence_enabled') || em_get_option('dbem_repeating_enabled') ){
				if( !empty($_REQUEST['action']) && ($_REQUEST['action'] == 'edit' || $_REQUEST['action'] == 'event_save') && !empty($_REQUEST['event_id']) ){
					$em_localized_js['event_recurrence_bookings'] = __('Are you sure you want to continue?', 'events-manager') .PHP_EOL;
					$em_localized_js['event_recurrence_bookings'] .= __('Modifications to event tickets will cause all bookings to individual recurrences of this event to be deleted.', 'events-manager');
				}
				$em_localized_js['event_detach_warning'] = __('Are you sure you want to detach this event? By doing so, this event will be independent of the recurring set of events.', 'events-manager');
				$delete_text = ( !EMPTY_TRASH_DAYS ) ? __('This cannot be undone.','events-manager'):__('All events will be moved to trash.','events-manager');
				$em_localized_js['delete_recurrence_warning'] = __('Are you sure you want to delete all recurrences of this event?', 'events-manager').' '.$delete_text;
			}
			if( em_get_option('dbem_rsvp_enabled') ){
				$em_localized_js['disable_bookings_warning'] = __('Are you sure you want to disable bookings? If you do this and save, you will lose all previous bookings. If you wish to prevent further bookings, reduce the number of spaces available to the amount of bookings you currently have', 'events-manager');
				$em_localized_js['booking_warning_cancel'] = em_get_option('dbem_booking_warning_cancel');
			}
		}
		//load admin/public only vars
		if( is_admin() ){
			$em_localized_js['event_post_types'] = Archetypes::get_cpts(['location']); // all but location
			$em_localized_js['event_post_type'] = EM_POST_TYPE_EVENT;
			$em_localized_js['location_post_type'] = EM_POST_TYPE_LOCATION;
			if( !empty($_GET['page']) && $_GET['page'] == 'events-manager-options' ){
				$em_localized_js['close_text'] = __('Collapse All','events-manager');
				$em_localized_js['open_text'] = __('Expand All','events-manager');
			}
			$em_localized_js['option_reset'] = __('Option value has been reverted. Please save your settings for it to take effect.', 'events-manager');
			$em_localized_js['admin'] = array(
				'settings' => array(
					'option_override_tooltip' => __("You can override this specific set of formats rather than using the plugin defaults.")
				),
			);
		}
		$em_localized_js = apply_filters('em_wp_localize_script', $em_localized_js);
		wp_localize_script($script,'EM', $em_localized_js);
	}

	/**
	 * Add variables to the EM JavaScript object in the footer
	 * Can be called anywhere before wp_footer to add variables to the EM object
	 *
	 * @param string $key   The key to add to the EM object
	 * @param mixed  $value The value to assign to the key
	 */
	public static function add_js_var($key, $value) {
		self::$footer_vars[$key] = $value;
	}

	/**
	 * Adds additional values to the EM JavaScript object before the closing </body> tag
	 * This method can be used to inject dynamic values into the EM JavaScript object that
	 * may change during page load or need to be added after initial script localization
	 */
	public static function localize_script_footer() {
		if ( !wp_script_is('events-manager', 'done') ) return;
		$footer_data = apply_filters('em_wp_localize_script_footer', self::$footer_vars);
		?>
		<script type="text/javascript">
			(function() {
				let targetObjectName = 'EM';
				if ( typeof window[targetObjectName] === 'object' && window[targetObjectName] !== null ) {
					Object.assign( window[targetObjectName], <?php echo wp_json_encode( $footer_data ); ?>);
				} else {
					console.warn( 'Could not merge extra data: window.' + targetObjectName + ' not found or not an object.' );
				}
			})();
		</script>
		<?php
	}
}
Scripts_and_Styles::init();