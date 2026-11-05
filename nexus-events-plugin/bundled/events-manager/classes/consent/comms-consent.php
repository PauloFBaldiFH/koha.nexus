<?php
namespace EM\Consent;

use EM_DateTime;
use EM_Person;

class Comms extends Consent {
	
	public static $options = array(
		'remember' => 'dbem_data_comms_consent_remember',
		'label' => 'dbem_data_comms_consent_text',
		'param' => 'data_comms_consent',
		'meta_key' => 'em_comms_consent',
	);
	
	public static $prefix = 'comms_consent';
	public static $required = false;
	
	public static function init() {
		static::$required = em_get_option('dbem_data_' . static::$prefix . '_required') == true;
		parent::init();
		if( is_admin() ) {
			include('comms-consent-admin.php');
		}
		// add hooks here because they need to run always
		// add consent hook for bookings table
		add_filter('em_bookings_table_cols_template', array( static::class, 'em_bookings_table_cols_template' ),10,2 );
		add_filter('em_bookings_table_rows_col_comms_consent', array( static::class, 'em_bookings_table_rows_col_comms_consent'), 10, 3);
		add_filter('em_bookings_table_get_sortable_columns', array( static::class, 'em_bookings_table_get_sortable_columns'), 10, 2);
		add_filter('em_bookings_sql_fields_orderby_user_meta', array( static::class, 'em_bookings_sql_fields_orderby_user_meta'), 10, 2);
		
		// add consent confirmation to profile and booking info areas
		add_action('em_person_get_summary', [ static::class, 'em_person_get_summary' ] ); // add to summary for exporting etc.
		// add field to wp dashboard profile in contact information section
		add_action( 'show_user_profile', [ static::class, 'show_profile_fields' ], 10 );
		add_action( 'edit_user_profile', [ static::class, 'show_profile_fields' ], 10 );
		add_action( 'em_user_profile_fields', [ static::class, 'show_profile_field' ], 10 );
		add_action( 'personal_options_update', [ static::class, 'save_profile_fields' ] );
		add_action( 'edit_user_profile_update', [ static::class, 'save_profile_fields' ] );
		// no user booking mode and displaying consent option
		add_action( 'em_person_display_summary_bottom', [ static::class, 'em_person_display_summary_bottom' ] ); //$this
		add_action( 'em_booking_get_person_editor_bottom', [ static::class, 'em_booking_get_person_editor_bottom' ] ); //$this
		if( !empty($_REQUEST['action']) && $_REQUEST['action'] == 'booking_modify_person'){ //only hook in if we're editing a no-user booking
			add_filter('em_booking_get_person_post', [ static::class, 'em_booking_get_post' ], 100, 2);
			add_filter('em_nouser_booking_details_modified', [ static::class, 'em_nouser_booking_details_modified' ], 100, 2);
		}
	}
	
	/* -------------------------------- USER PROFILE AREAS -------------------------------- */
	
	
	public static function em_person_display_summary_bottom( $EM_Person ) {
		// output a td with consent
		$consented = static::has_consented( $EM_Person );
		$already_revoked = $EM_Person->{ static::$options['meta_key'] . '_revoked' };
		$consent_text = $consented ? __('Yes', 'events-manager') : __('No', 'events-manager');
		?>
		<tr>
			<th><?php esc_html_e('Communications Consent','events-manager'); ?> : </th>
			<td>
				<?php
					echo $consent_text;
					if( !$consented && $already_revoked ) {
						$EM_DateTime = EM_DateTime::create($already_revoked, 'UTC')->setTimezone();
						echo '<p style="color:#600000"><em>' . sprintf( esc_html__('Consent %s on %s', 'events-manager'), strtolower(esc_html__('Revoked', 'event-manager')), $EM_DateTime->formatDefault() ) . '</em></p>';
					}
				?>
			</td>
		</tr>
		<?php
	}
	
	public static function em_nouser_booking_details_modified( $EM_Booking ) {
		// first check if consent has changed in the past minute, if not then we don't bother
		$EM_Person = $EM_Booking->get_person();
		$already_consented = static::has_consented( $EM_Person );
		$already_revoked = $EM_Person->{ static::$options['meta_key'] . '_revoked' };
		if ( $already_consented || $already_revoked ) {
			$one_minute_ago = time() - 60;
			$consented_recently = ( $already_consented && strtotime( $already_consented ) > $one_minute_ago );
			$revoked_recently = ( $already_revoked && strtotime( $already_revoked ) > $one_minute_ago );
			// update what we can here based on email of user if there was a change
			if ( $consented_recently || $revoked_recently ) {
				// if user can modify edit users, modify the user itself too
				if ( current_user_can('edit_users') && em_get_option('dbem_bookings_registration_disable_user_emails') ) { // only needed if guests can use registered emails to book
					// check if there's a user belonging to this email
					$user = get_user_by_email( $EM_Person->user_email );
					if ( $user ) {
						if ( $consented_recently ) {
							update_user_meta( $user->ID, static::$options['meta_key'], current_time( 'mysql', true ) );
						}
						if ( $revoked_recently ) {
							delete_user_meta( $user->ID, static::$options['meta_key'] );
							update_user_meta( $user->ID, static::$options['meta_key'] . '_revoked', current_time( 'mysql', true ) );
						}
					}
				}
				$event_owner_id = !current_user_can('manage_others_bookings') ? get_current_user_id() : false;
				static::update_nouser_bookings_consent( $EM_Person, $event_owner_id );
			}
		}
	}
	
	/**
	 * @param EM_Person $EM_Person
	 * @param bool $consented
	 *
	 * @return int|bool
	 */
	public static function update_user_consent( $EM_Person, $consented = null ) {
		// update consent of user if they are a user
		$consent_action = null;
		$already_consented = $EM_Person->{ self::$options['meta_key'] };
		if ( $consented ) {
			// user has consented
			if ( !$already_consented ) {
				// add consent
				if( $EM_Person->ID ) {
					update_user_meta( $EM_Person->ID, self::$options['meta_key'], current_time( 'mysql', true ) );
				}
				$EM_Person->{self::$options['meta_key']} = current_time( 'mysql', true );
				$consent_action = true;
			}
		} elseif ( $consented === false || $already_consented ) { // if consent not explicitly revoked and no consent previously given, we don't take definitive action
			// only add a revoked record if currently consented or explicitly revoked, otherwise it's neither consented or revoked
			if( $EM_Person->ID ) {
				delete_user_meta( $EM_Person->ID, self::$options['meta_key'] );
				update_user_meta( $EM_Person->ID, self::$options['meta_key'] . '_revoked', current_time( 'mysql', true ) );
			}
			unset( $EM_Person->{self::$options['meta_key']} );
			$EM_Person->{self::$options['meta_key'] . '_revoked'} = current_time( 'mysql', true );
			$consent_action = false;
		}
		if( $consent_action !== null ) {
			// if we consented or revoked, and user may have no-user bookings, we try to update those too, we can update all known records since it's either an admin or the user changing consent
			$result = static::update_nouser_bookings_consent( $EM_Person ) > 0;
		}
		return !empty($result) || ($EM_Person->ID && $consent_action !== null );
	}
	
	public static function update_nouser_bookings_consent( $EM_Person, $event_owner_id = false ) {
		global $wpdb;
		$already_consented = $EM_Person->{ static::$options['meta_key'] };
		$already_revoked = $EM_Person->{ static::$options['meta_key'] . '_revoked' };
		// if user can modify others bookings, do it for all bookings, we do it direct to DB to avoid processing
		$sql_select = $wpdb->prepare( 'SELECT booking_id FROM '. EM_BOOKINGS_TABLE . " WHERE person_id = 0 AND booking_id IN ( SELECT booking_id FROM ". EM_BOOKINGS_META_TABLE ." WHERE meta_key='_registration|user_email' AND meta_value=%s )", $EM_Person->user_email );
		if ( $event_owner_id ) {
			// limit bookings to only events belonging to this user
			$sql_select .= $wpdb->prepare( " AND event_id IN ( SELECT event_id FROM ". EM_EVENTS_TABLE . " WHERE event_owner=%d )", $event_owner_id );
		}
		$booking_ids = array_map( 'intval', $wpdb->get_col( $sql_select ) );
		if ( count($booking_ids) > 0 ) {
			$booking_ids_imploded = implode( ',', $booking_ids );
			$meta_key = static::$options['meta_key'];
			// delete then add, we don't know if some were added before or never
			$wpdb->query( $wpdb->prepare( 'DELETE FROM ' . EM_BOOKINGS_META_TABLE . " WHERE meta_key IN (%s, %s) AND booking_id IN ($booking_ids_imploded)", '_registration|' . $meta_key, '_registration|' . $meta_key . '_revoked' ) );
			// insert records
			$inserts = array();
			$values = array();
			foreach ( $booking_ids as $booking_id ) {
				if( $already_consented ) {
					$inserts[] = '(%d, %s, %s)';
					array_push( $values, $booking_id, '_registration|' . $meta_key, $already_consented );
				}
				if ( $already_revoked ) {
					$inserts[] = '(%d, %s, %s)';
					array_push( $values, $booking_id, '_registration|' . $meta_key . '_revoked', $already_revoked );
				}
			}
			if( count($inserts) > 0 ) {
				return $wpdb->query( $wpdb->prepare( 'INSERT INTO ' . EM_BOOKINGS_META_TABLE . ' (booking_id, meta_key, meta_value) VALUES ' . implode( ',', $inserts ), $values ) );
			}
		}
		return 0; // nothing to update
	}
	
	/**
	 * Show consent checkbox in no-user booking mode booking admin editor
	 *
	 * @param \EM_Booking $EM_Booking
	 *
	 * @return void
	 */
	public static function em_booking_get_person_editor_bottom( $EM_Booking ) {
		static::show_profile_field( $EM_Booking->get_person() );
	}
	
	public static function em_person_get_summary( $summary, $EM_Person ) {
		$consents = array(
			'comms_consent_given' => array('name' => __('Communications Consent','events-manager'), 'value' => $EM_Person->{ static::$options['meta_key'] } ),
			'comms_consent_revoked' => array('name' => __('Communications Consent','events-manager') . ' ' . __('Revoked','events-manager') , 'value' => $EM_Person->{ static::$options['meta_key'] . '_revoked' } ),
		);
		return $summary + $consents;
	}
	
	/**
	 * Adds consent checkbox in its own section of further information on profile page.
	 * @param \WP_User $user
	 */
	public static function show_profile_fields ($user) {
		if( did_action('em_user_profile_fields') ) return;
		?>
		<h3><?php echo esc_html( sprintf( __('Events Manager - %s','events-manager'), __('Communications Consent', 'events-manager')) ); ?></h3>
		<table class="form-table em">
			<?php static::show_profile_field( $user ); ?>
		</table>
		<?php
	}
	
	
	/**
	 * Outputs consent checkbox to be added in a table form
	 * @param \WP_User $user
	 */
	public static function show_profile_field( $user ) {
		?>
		<tr>
			<th><label for="em_comms_consent"><?php esc_html_e('Communications Consent', 'events-manager'); ?></label></th>
			<td>
				<?php static::show_user_field( $user ); ?>
			</td>
		</tr>
		<?php
	}
	
	
	/**
	 * Displays consent checkbox field, with context of provided WP_User instance $user.
	 *
	 * @param \WP_User $user The user for whom to display the field.
	 *
	 * @return void
	 */
	public static function show_user_field( $user ) {
		$already_consented = $user->{ static::$options['meta_key'] };
		$already_revoked = $user->{ static::$options['meta_key'] . '_revoked' };
		static::show_checkbox( $already_consented, $already_revoked );
	}
	
	/**
	 * Displays a checkbox field for user consent to be contacted via communication messages.
	 *
	 * @param bool $already_consented Optional. Whether the user has already consented to receive communications. Default false.
	 * @param bool $already_revoked Optional. Whether the user has already revoked consent to receive communications. Default false.
	 *
	 * @return void
	 *
	 */
	public static function show_checkbox( $already_consented = false, $already_revoked = false ) {
		?>
		<input type="checkbox" name="<?php echo static::$options['param']; ?>" <?php checked( $already_consented == true ); ?>>
		<?php
		if( $already_consented ) {
			echo '<p><em>';
			$EM_DateTime = EM_DateTime::create($already_consented, 'UTC')->setTimezone();
			echo sprintf( esc_html__('Consent %s on %s', 'events-manager'), strtolower(esc_html__('Received', 'event-manager')), $EM_DateTime->formatDefault() );
			if( $already_revoked ) {
				$EM_DateTime = EM_DateTime::create($already_revoked, 'UTC')->setTimezone();
				echo '<br>' . sprintf( esc_html__('Consent previously %s on %s', 'events-manager'), strtolower(esc_html__('Revoked', 'event-manager')), $EM_DateTime->formatDefault() );
			}
			echo '<em></p>';
		} elseif ( $already_revoked ) {
			$EM_DateTime = EM_DateTime::create($already_revoked, 'UTC')->setTimezone();
			echo '<p style="color:#600000"><em>' . sprintf( esc_html__('Consent %s on %s', 'events-manager'), strtolower(esc_html__('Revoked', 'event-manager')), $EM_DateTime->formatDefault() ) . '</em></p>';
		}
	}
	
	/**
	 * Detect if checkbox cheked or not and either add consent record or delete and add revoked record.
	 * @param int $user_id
	 * @return void
	 */
	public static function save_profile_fields( $user_id ) {
		$EM_Person = new EM_Person($user_id);
		$consented = !empty($_REQUEST[ static::$options['param'] ]) ? true : null;
		static::update_user_consent( $EM_Person, $consented );
	}
	
	/* -------------------------------- BOOKING TABLES -------------------------------- */
	
	/**
	 * Add consent booking admin column
	 * @param array $template
	 * @param \EM_Bookings_Table $EM_Bookings_Table
	 *
	 * @return array
	 */
	public static function em_bookings_table_cols_template($template, $EM_Bookings_Table){
		$template[ static::$prefix ] = esc_html__('Communications Consent', 'events-manager'); // remove all HTML so we don't have CSS grid display issues with sortables
		return $template;
	}
	
	public static function em_bookings_table_rows_col_comms_consent( $val, $EM_Object, $EM_Bookings_Table ){
		extract( $EM_Bookings_Table->get_item_objects($EM_Object) ); /* @var \EM_Booking $EM_Booking */
		//if in MB mode, change $EM_Booking with the main booking to grab coupon info, given that we don't support per-event coupons in MB mode atm
		$consent = $EM_Booking->get_user_meta( static::$options['meta_key'] );
		$consent_text = $consent ? __('Yes', 'events-manager') : __('No', 'events-manager');
		return $consent_text;
	}
	
	public static function em_bookings_table_get_sortable_columns( $sortable_columns, $EM_Bookings_Table ) {
		$sortable_columns[ static::$prefix ] = [ static::$prefix, false ];
		return $sortable_columns;
	}
	
	public static function em_bookings_sql_fields_orderby_user_meta( $orderby ) {
		$orderby[ static::$prefix ] = static::$options['meta_key'];
		return $orderby;
	}
}
Comms::init();