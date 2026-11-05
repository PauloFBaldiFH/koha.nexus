<?php
namespace EM\Consent;
use EM_Event, EM_Location, EM_Booking;

class Consent {
	public static $options = array(
		'remember' => 'dbem_data_consent_remember',
		'label' => 'dbem_data_consent_text',
		'param' => 'data_consent',
		'meta_key' => 'em_consent',
	);
	public static $prefix = 'consent';
	
	public static $required = true;
	
	public static function init() {
		// Consent validation is only ever meant to fire for public-facing
		// submission contexts (frontend HTML POST, frontend AJAX). It must NOT
		// fire during admin saves, REST API requests, wp-cron or WP-CLI, none
		// of which carry a public submitter's consent checkbox. is_admin()
		// returns false for all of those, so is_excluded_request() covers
		// what is_admin() alone misses.
		$is_frontend       = !is_admin() && !static::is_excluded_request();
		$is_relevant_ajax  = defined('DOING_AJAX') && DOING_AJAX && !empty($_REQUEST['action']) && $_REQUEST['action'] != 'booking_add_one';
		if( $is_frontend || $is_relevant_ajax ){
			add_action('init', [ static::class, 'hooks' ]);
		}
		// build options array dynamically based on a prefix, unless already specified
		static::$options['remember'] = static::$options['remember'] ?? 'dbem_data_' . static::$prefix . '_remember';
		static::$options['label'] = static::$options['label'] ?? 'dbem_data_' . static::$prefix . '_text';
		static::$options['param'] = static::$options['param'] ?? 'data_' . static::$prefix ;
		static::$options['meta_key'] = static::$options['meta_key'] ?? 'em_' . static::$prefix ;
	}
	
	public static function hooks(){
		//BOOKINGS
		if( em_get_option('dbem_data_'. static::$prefix .'_bookings') == 1 || ( em_get_option('dbem_data_' . static::$prefix . '_bookings') == 2 && !is_user_logged_in() ) ){
			add_action('em_booking_form_footer', [ static::class, 'checkbox' ], 9, 0); //supply 0 args since arg is $EM_Event and callback will think it's an event submission form
			add_action('em_booking_form_after_user_details', [ static::class, 'checkbox' ], 9, 0); //supply 0 args since arg is $EM_Event and callback will think it's an event submission form
			add_filter('em_booking_get_post', [ static::class, 'em_booking_get_post' ], 10, 2);
			add_filter('em_booking_validate', [ static::class, 'em_booking_validate' ], 10, 2);
			add_filter('em_booking_save', [ static::class, 'em_booking_save' ], 10, 2);
		}
		//EVENTS
		if( em_get_option('dbem_data_' . static::$prefix . '_events') == 1 || ( em_get_option('dbem_data_' . static::$prefix . '_events') == 2 && !is_user_logged_in() ) ){
			add_action('em_front_event_form_footer', [ static::class, 'event_checkbox' ], 9, 1);
			add_action('em_event_get_post_meta', [ static::class, 'cpt_get_post' ], 10, 2);
			add_action('em_event_validate', [ static::class, 'cpt_validate' ], 10, 2);
			add_action('em_event_save', [ static::class, 'cpt_save' ], 10, 2);
		}
		//LOCATIONS
		if( em_get_option('dbem_data_' . static::$prefix . '_locations') == 1 || ( em_get_option('dbem_data_' . static::$prefix . '_events') == 2 && !is_user_logged_in() ) ){
			add_action('em_front_location_form_footer', [ static::class, 'location_checkbox' ], 9, 1);
			add_action('em_location_get_post_meta', [ static::class, 'cpt_get_post' ], 10, 2);
			add_action('em_location_validate', [ static::class, 'cpt_validate' ], 10, 2);
			add_action('em_location_save', [ static::class, 'cpt_save' ], 10, 2);
		}
	}
	
	/**
	 * Checks a booking or person
	 * @param $item
	 * @param $type
	 *
	 * @return bool
	 */
	public static function has_consented( $item, $type = false ) {
		if( $item instanceof \EM_Booking ) {
			$EM_Booking = $item;
			$EM_Person = $EM_Booking->get_person();
		} elseif ( $item instanceof \EM_Person ) {
			$EM_Person = $item;
		}
		$consented = $EM_Person->{ static::$options['meta_key'] } ?? null;
		if ( $consented === null ) {
			if( $EM_Person->{ static::$options['meta_key'] . '_revoked' } ) {
				// if not revoked we can only assume they consented by default (in the event user had not previously consented)
				$consented = false;
			} elseif( em_get_option('dbem_data_' . static::$prefix . '_default') ) {
				$consented = true;
			}
		}
		return apply_filters( 'em_consent_has_consented', $consented == true, static::class, ['item' => $item, 'type' => $type, 'EM_Person' => $EM_Person ?? null ] );
	}
	
	public static function get_error_booking() {
		return em_get_option('dbem_data_' . static::$prefix . '_bookings_error');
	}
	
	public static function get_error_cpt() {
		return em_get_option('dbem_data_' . static::$prefix . '_cpt_error');
	}
	
	/**
	 * Wrapper function in case old overriden templates didn't pass the EM_Event object and depended on global value
	 * @param EM_Event $event
	 */
	public static function event_checkbox( $event ){
		if( empty($event) ){ global $EM_Event; }
		else{ $EM_Event = $event ; }
		static::checkbox($EM_Event);
	}
	
	/**
	 * Wrapper function in case old overriden templates didn't pass the EM_Location object and depended on global value
	 * @param EM_Location $location
	 */
	public static function location_checkbox( $location ){
		if( empty($location) ){ global $EM_Location; }
		else{ $EM_Location = $location ; }
		static::checkbox($EM_Location);
	}
	
	public static function get_label() {
		return em_get_option( static::$options['label'] );
	}
	
	/**
	 * Outputs a checkbox that can be used to obtain consent.
	 * @param EM_Event|EM_Location|EM_Booking|bool $EM_Object
	 */
	public static function checkbox( $EM_Object = false ){
		if( !empty($EM_Object) && (!empty($EM_Object->booking_id) || !empty($EM_Object->post_id)) ) return; //already saved so consent was given at one point
		if( !doing_action('em_booking_form_after_user_details') && did_action('em_booking_form_after_user_details') ) return; // backcompat
		$label = static::get_label();
		// check if consent was previously given and check box if true
		if( is_user_logged_in() ){
			$consent_given_already = get_user_meta( get_current_user_id(), static::$options['meta_key'], true );
			if( !empty($consent_given_already) && em_get_option( static::$options['remember'] ) == 1 ) return; //ignore if consent given as per settings
			if( !empty($consent_given_already) && em_get_option( static::$options['remember'] ) == 2 ) $checked = true;
		}
		if( empty($checked) && !empty($_REQUEST[ static::$options['param'] ]) ) $checked = true;
		// output checkbox
		?>
		<p class="input-group input-checkbox em-consent-checkbox input-field-data_<?php echo esc_attr(static::$prefix); ?>">
			<label>
				<input type="checkbox" name="<?php echo esc_attr(static::$options['param']) ?>" value="1" <?php if( !empty($checked) ) echo 'checked="checked"'; ?>>
				<?php echo $label; ?>
			</label>
		</p>
		<?php
	}
	/**
	 * Saves consent to the current date time if consented in booking meta, or to 0 if not set. Validation will let this pass or not.
	 *
	 * @param bool $result
	 * @param EM_Booking $EM_Booking
	 * @return bool
	 */
	public static function em_booking_get_post( $result, $EM_Booking ){
		if( !empty($_REQUEST[ static::$options['param'] ]) ){
			if( empty($EM_Booking->booking_meta['registration'][ static::$options['meta_key'] ]) ) {
				$EM_Booking->booking_meta['registration'][ static::$options['meta_key'] ] = current_time( 'mysql', true );
				$EM_Booking->get_person()->{static::$options['meta_key']} = current_time( 'mysql', true );
			}
		} else {
			// When the checkbox was intentionally hidden because this user's consent is remembered, its absence from the POST is not a revocation — carry the stored consent forward.
			if ( is_user_logged_in() && em_get_option( static::$options['remember'] ) == 1 && get_user_meta( get_current_user_id(), static::$options['meta_key'], true ) ) {
				return $result;
			}
			if ( $EM_Booking->get_user_meta( static::$options['meta_key']) ) {
				$EM_Booking->booking_meta['registration'][ static::$options['meta_key'] . '_revoked' ] = current_time( 'mysql', true );
				$EM_Booking->get_person()->{static::$options['meta_key'] . '_revoked'} = current_time( 'mysql', true );
			}
			$EM_Booking->booking_meta['registration'][ static::$options['meta_key'] ] = 0;
			$EM_Booking->get_person()->{static::$options['meta_key']} = 0;
		}
		return $result;
	}
	
	/**
	 * Validates a bookng to ensure consent is/was given.
	 *
	 * @param bool $result
	 * @param EM_Booking $EM_Booking
	 * @return bool
	 */
	public static function em_booking_validate( $result, $EM_Booking ){
		if( is_user_logged_in() && ($EM_Booking->person_id == get_current_user_id() || $EM_Booking->person_id === null) ){
			//check if consent was previously given and ignore if settings dictate so
			$consent_given_already = get_user_meta( get_current_user_id(), static::$options['meta_key'], true );
			if( $consent_given_already && em_get_option( static::$options['remember'] ) == 1 ) {
				return $result;
			} //ignore if consent given as per settings
		}
		if( empty($EM_Booking->booking_meta['registration'][ static::$options['meta_key'] ]) && static::$required ){
			if( !empty($_REQUEST['action']) && !empty($_REQUEST['booking_id']) && !empty($_REQUEST['_wpnonce']) && $_REQUEST['action'] == 'booking_save'  && wp_verify_nonce($_REQUEST['_wpnonce'], 'booking_save_'.$_REQUEST['booking_id']) ) {
				// we're saving a previously submitted booking here, so we can ignore consent to prevent blocks in editing a booking
				return $result;
			}
			$EM_Booking->add_error( static::get_error_booking() );
			$result = false;
		}
		return $result;
	}
	
	/**
	 * Updates or adds the consent date of user account meta if booking was submitted by a user and consent was given for first time.
	 * @param bool $result
	 * @param EM_Booking $EM_Booking
	 * @return bool
	 */
	public static function em_booking_save( $result, $EM_Booking ){
		if( $result ){
			if( $EM_Booking->person_id != 0  ){
				$consent_given_already = get_user_meta( $EM_Booking->person_id, static::$options['meta_key'], true );
				$consent_given = !empty($EM_Booking->booking_meta['registration'][ static::$options['meta_key'] ]);
				if ( $consent_given ) {
					if( !$consent_given_already ) {
						update_user_meta( $EM_Booking->person_id, static::$options['meta_key'], current_time( 'mysql', true ) );
					}
				} elseif( $consent_given_already && !static::$required ) {
					// consent possibly revoked, so we remove consent
					delete_user_meta( $EM_Booking->person_id, static::$options['meta_key'] );
					update_user_meta( $EM_Booking->person_id, static::$options['meta_key'] . '_revoked', current_time( 'mysql', true ) );
				}
			}
		}
		return $result;
	}
	
	/**
	 * Whether this request should never register or run the consent hooks: REST, wp-cron and WP-CLI requests never carry a public submitter's consent checkbox.
	 *
	 * WordPress defines REST_REQUEST in rest_api_loaded(), hooked to parse_request, which runs long after this class is included and after the init action that registers the hooks below. The check in init() therefore cannot see REST_REQUEST yet and registers the consent hooks for every REST request, including the block editor's save. Re-checking here still works because every callback below runs during the save itself, by which point the constant is set. DOING_CRON and WP_CLI are both set before init fires, so those two are actually excluded at the init() call too.
	 * @return bool
	 */
	protected static function is_excluded_request() {
		return ( defined('REST_REQUEST') && REST_REQUEST ) || wp_doing_cron() || ( defined('WP_CLI') && WP_CLI );
	}

	public static function cpt_get_post($result, $EM_Object ){
		if( static::is_excluded_request() ) return $result;
		if( !empty($_REQUEST[ static::$options['param'] ]) ){
			if( get_class($EM_Object) == 'EM_Event' ){
				$EM_Object->event_attributes['_' . static::$options['meta_key']] = 1;
				$EM_Object->get_location()->location_attributes[ '_' . static::$options['meta_key'] ] = 1;
			}else{
				$EM_Object->location_attributes[ '_' . static::$options['meta_key'] ] = 1;
			}
		}
		return $result;
	}
	
	/**
	 * Validate the consent provided to events and locations.
	 * @param bool $result
	 * @param EM_Event|EM_Location $EM_Object
	 * @return bool
	 */
	public static function cpt_validate( $result, $EM_Object ){
		if( static::is_excluded_request() ) return $result;
		if( !empty($EM_Object->post_id) ) return $result;
		if( is_user_logged_in() ){
			//check if consent was previously given and ignore if settings dictate so
			$consent_given_already = get_user_meta( get_current_user_id(), static::$options['meta_key'], true );
			if( !empty($consent_given_already) && em_get_option( static::$options['remember'] ) == 1 ) return $result; //ignore if consent given as per settings
		}
		$attributes = get_class($EM_Object) == 'EM_Event' ? 'event_attributes':'location_attributes';
		if( empty($EM_Object->{$attributes}[ '_' . static::$options['meta_key'] ]) && static::$required ){
			$EM_Object->add_error( static::get_error_cpt() );
			$result = false;
		}
		return $result;
	}
	
	/**
	 * When an event or location is saved and consent is given or supplied again, update user account with latest consent date IF the object isn't associated with an anonymous user.
	 * @param bool $result
	 * @param EM_Event|EM_Location $EM_Object
	 * @return bool
	 */
	public static function cpt_save( $result, $EM_Object ){
		if( static::is_excluded_request() ) return $result;
		$attributes = get_class($EM_Object) == 'EM_Event' ? 'event_attributes':'location_attributes';
		if( $result && !empty($EM_Object->{$attributes}['_' . static::$prefix])){
			if( !em_get_option('dbem_events_anonymous_submissions') || $EM_Object->post_author != em_get_option('dbem_events_anonymous_user') ){
				update_user_meta( $EM_Object->post_author, static::$options['meta_key'], current_time( 'mysql', true ) );
			}
		} elseif ( $result && !static::$required ) {
			// if not required and we're here, then we can consider the user has revoked consent
			delete_user_meta( $EM_Object->post_author, static::$options['meta_key'] );
		}
		return $result;
	}
}
if( is_admin() ) {
	include_once('consent-admin.php');
}