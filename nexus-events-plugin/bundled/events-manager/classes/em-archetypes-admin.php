<?php
namespace EM;

class Archetypes_Admin {

	/**
	 * Array of option names that can be overridden by a specific archetype.
	 * @var array
	 */
	protected static $options = [];

	public static function init() {
		add_action( 'em_options_save', [ static::class, 'em_options_save' ] );
		add_action( 'admin_footer', [ static::class, 'admin_footer' ] );
	}

	public static function em_options_save() {
		try {
			if ( defined('EM_SETTINGS_ARCHETYPES_MERGED') && EM_SETTINGS_ARCHETYPES_MERGED || Archetypes::get_current() === Archetypes::$event['cpt'] ) {
				// save the custom archetypes
				$options = static::get_post();
				if ( !empty( $options ) ) {
					static::save_archetypes( $options, is_network_admin() );
				}
				// If in network admin, skip saving base event/location fields; network controls only manage available archetypes
				if ( !is_network_admin() ) {
					// then save the main event and location archetypes
					static::save_main_archetype();
					if ( Archetypes::$event['cpt'] !== EM_POST_TYPE_EVENT ) {
						// change the redirect to the new CPT
						add_filter( 'em_options_save_redirect', function () {
							return add_query_arg( 'post_type', Archetypes::$event['cpt'], wp_get_referer() );
						} );
					}
					static::save_main_archetype( 'locations' );
				}
				// subsite selection saving for choose mode
				if ( is_multisite() && !is_network_admin() && Archetypes::get_ms_mode() === 'choose' ) {
					$available = array_keys( (array) get_site_option( 'em_ms_event_archetypes', [] ) );
					// Include base event CPT as a valid choice as well
					$available[] = Archetypes::$event['cpt'];
					$available = array_unique( $available );
					$selected = isset( $_POST['em_archetypes_selected'] ) && is_array( $_POST['em_archetypes_selected'] ) ? array_map( 'sanitize_key', $_POST['em_archetypes_selected'] ) : [ EM_POST_TYPE_EVENT ];
					$selected = array_values( array_intersect( $selected, $available ) );
					update_option( 'em_archetypes_selected', $selected );
					$default = isset( $_POST['em_archetype_default'] ) ? sanitize_key( $_POST['em_archetype_default'] ) : '';
					if ( $default && in_array( $default, $selected, true ) ) {
						update_option( 'em_archetype_default', $default );
					} else {
						update_option( 'em_archetype_default', $selected[0] );
					}
				}
			}
			// save options themselves for previously created archetypes, not deleted ones anymore
			if ( !empty($_POST['em_archetype_options']) ) {
				if ( defined('EM_SETTINGS_ARCHETYPES_MERGED') && EM_SETTINGS_ARCHETYPES_MERGED ) {
					// we're saving everything
					$archetypes_options = [];
				} else {
					// just saving current archetype
					$the_archetype = Archetypes::get_current();
					$archetypes_options = get_option( 'em_event_archetypes_options', [] );
					$archetypes_options[ $the_archetype ] = [];
				}
				foreach ( $_POST['em_archetype_options'] as $type => $post_options ) {
					if ( !empty($the_archetype) && $type !== $the_archetype ) continue; // skip in single mode
					if ( in_array( $type, array_keys( Archetypes::$types ) ) ) {
						foreach ( $post_options as $postKey => $postValue ) {
							if ( is_array( $postValue ) ) {
								$filtered = [];
								foreach ( $postValue as $postValue_key => $postValue_val ) {
									if ( $postValue_val !== '' ) {
										$filtered[ $postValue_key ] = wp_unslash( $postValue_val );
									}
								}
								$postValue = $filtered;
							} else {
								if ( $postValue !== '' ) {
									$postValue = wp_unslash( $postValue );
								}
							}
							$archetypes_options[ $type ][ $postKey ] = em_options_save_kses_deep( $postValue );
						}
					}
				}
				update_option( 'em_event_archetypes_options', $archetypes_options );
			}
		} catch ( Exception $ex ) {
			global $EM_Notices;
			$EM_Notices->add_error( $ex->get_messages(), true );
		}
	}

	public static function get_post() {
		// deal with the achetype editor
		if ( !empty($_POST['event_archetypes']) ) {
			// In multisite, allow super admins (network admin) or subsites if policy allows custom archetypes
			$allow_save = true;
			if ( is_multisite() ) {
				$allow_save = is_super_admin() || static::can_subsite_create();
			}
			if ( $allow_save ) {
				$data = json_decode( wp_unslash( $_POST['event_archetypes'] ), true );
				if ( !empty( $data ) ) {
					$archetype_data = [];
					if ( !empty( $data['custom'] ) ) {
						$archetype_data['custom'] = $data['custom'];
					}
					if ( !empty( $data['delete'] ) ) {
						$archetype_data['delete'] = $data['delete'];
					}
					return $archetype_data;
				}
			}
		}
		return [];
	}

	/**
	 * @param string $base
	 *
	 * @return void
	 * @throws Exception
	 */
	public static function save_main_archetype ( $base = 'events' ) {
		// validate CPT to make sure it matches, assuming it's new
		$can_rename_cpts = static::can_rename_cpts();
		foreach ( [ "em_cp_{$base}_cpt", "em_cp_{$base}_cpts" ] as $wp_option_key ) {
			if ( $can_rename_cpts && !empty( $_POST[ $wp_option_key ] ) && em_get_option( $wp_option_key ) !== $_POST[ $wp_option_key ] ) {
				if ( $_POST[ $wp_option_key . '_nonce' ] && wp_verify_nonce( $_POST[ $wp_option_key . '_nonce' ], "edit_{$wp_option_key}" ) ) {
					$new_cpt = sanitize_key( iconv( 'UTF-8', 'ASCII//TRANSLIT', $_POST[ $wp_option_key ] ) );
					if ( $wp_option_key === "em_cp_{$base}_cpt" ) {
						Archetypes_Admin::change_cpt( em_get_option( $wp_option_key ), $new_cpt, $base );
					}
					update_option( $wp_option_key, $new_cpt );
				}
			}
		}
		$can_rename_slugs = static::can_rename_slugs();
		if ( $can_rename_slugs && !empty($_POST["dbem_cp_{$base}_slug"]) ) {
			Archetypes::$event['slug'] = em_options_save_kses_deep( $_POST["dbem_cp_{$base}_slug"] );
			update_option( "dbem_cp_{$base}_slug", Archetypes::$event['slug'] );
		}
		$can_rename_labels = static::can_rename_labels();
		if ( $can_rename_labels && $_POST["dbem_cp_{$base}_label"] ) {
			Archetypes::$event['label'] = em_options_save_kses_deep( $_POST["dbem_cp_{$base}_label"] );
			update_option( "dbem_cp_{$base}_label", Archetypes::$event['label'] );
		}
		if ( $can_rename_labels && $_POST["dbem_cp_{$base}_label_single"] ) {
			Archetypes::$event['label_single'] = em_options_save_kses_deep( $_POST["dbem_cp_{$base}_label_single"] );
			update_option( "dbem_cp_{$base}_label_single", Archetypes::$event['label_single'] );
		}
		if ( !empty($_POST["dbem_cp_{$base}_menu_icon"]) ) {
			Archetypes::$event['menu_icon'] = em_options_save_kses_deep( $_POST["dbem_cp_{$base}_menu_icon"] );
			update_option( "dbem_cp_{$base}_menu_icon", Archetypes::$event['menu_icon'] );
		}
	}

	/**
	 * @param array $data
	 *
	 * @return void
	 */
	public static function save_archetypes( $data, $is_network = false ) {
		// save the custom archetypes
		if ( !empty($data['custom']) ) {
			foreach ( $data['custom'] as $type => $archetype_data ) {
				try {
					static::save_archetype( $type, $archetype_data );
				} catch ( Exception $ex ) {
					global $EM_Notices;
					$EM_Notices->add_error( $ex->get_messages(), true );
				}
			}
		}
		// save the archetypes to the database
		if ( $is_network ) {
			update_site_option( 'em_ms_event_archetypes', Archetypes::$types );
		} else {
			update_option( 'em_event_archetypes', Archetypes::$types );
		}
		// now delete requested CPTs
		if ( !empty($data['delete']) ) {
			foreach ( $data['delete'] as $type => $nonce ) {
				if ( !empty(Archetypes::$types[$type]) ) {
					if ( wp_verify_nonce( $nonce, 'delete_archetype_' . $type ) ) {
						// delete the archetype
						\EM_Events::delete( ['event_archetype' => $type, 'scope' => 'all', 'status' => 'everything'] );
						unset( Archetypes::$types[$type] );
						// save the archetypes to the database again, each time since big data potentially deleted each time and timeouts possible
						if ( $is_network ) {
							update_site_option( 'em_ms_event_archetypes', Archetypes::$types );
						} else {
							update_option( 'em_event_archetypes', Archetypes::$types );
						}
					}
				}
			}
		}
	}

	/**
	 * @param $type
	 * @param $data
	 *
	 * @return void
	 * @throws Exception
	 */
	public static function save_archetype( $type, $data ) {
		$archetype = Archetypes::$types[ $type ] ?? [];
		$new = empty($archetype);
		if ( $data['cpt'] ) {
			if ( $new || ( $data['cpt'] !== $archetype['cpt'] && ['cpt_nonce'] && wp_verify_nonce( $data['cpt_nonce'], 'edit_cpt_' . $type ) ) ) {
				$cpt = sanitize_key( iconv( 'UTF-8', 'ASCII//TRANSLIT', $data['cpt'] ) );
				if ( $archetype ) {
					// check that we don't have a conflict, if so then we bail
					static::change_cpt( $type, $cpt );
					// unset the old archetype data so we don't save two of the same archetype
					unset( Archetypes::$types[ $type ] );
				}
				$archetype['cpt'] = $cpt;
			}
		}
		if ( $data['cpts'] ) {
			if ( $new || ( $data['cpt'] !== $archetype['cpt'] && $data['cpts_nonce'] && wp_verify_nonce( $data['cpts_nonce'], 'edit_cpts_' . $type ) ) ) {
				$archetype['cpts'] = sanitize_key( iconv( 'UTF-8', 'ASCII//TRANSLIT', $data['cpts'] ) );
			}
		}
		if ( $data['slug'] ) {
			$archetype['slug'] = em_options_save_kses_deep( $data['slug'] );
		}
		if ( $data['label'] ) {
			$archetype['label'] = em_options_save_kses_deep( $data['label'] );
		}
		if ( $data['label_single'] ) {
			$archetype['label_single'] = em_options_save_kses_deep( $data['label_single'] );
		}
		if ( $data['menu_icon'] ) {
			$archetype['menu_icon'] = em_options_save_kses_deep( $data['menu_icon'] );
		}

		/* redundant
		if ( !empty($data['features']) ) {
			$archetype['features'] = static::sanitize_features_setting( $data['features'] );
		}
		*/
		// save the archetype to Archetypes::$types
		static::validate_archetype( $archetype );
		Archetypes::$types[ $archetype['cpt'] ] = $archetype;
	}

	public static function validate_archetype( $data ) {
		$required = [ 'cpt', 'cpts', 'slug', 'label', 'label_single' ];
		foreach ( $required as $field ) {
			if ( !isset( $data[ $field ] ) || empty( $data[ $field ] ) ) {
				throw new Exception( sprintf( __( 'Missing required field: %s', 'events-manager' ), $field ) );
			}
		}
	}

	/**
	 *
	 * @param $current
	 * @param $new
	 *
	 * @return void
	 * @throws Exception
	 */
	public static function change_cpt( $current, $new, $base = 'events' ) {
		$post_types = get_post_types();
		if ( !in_array( $new, $post_types ) ) {
			// clean the post type so it's acceptable
			$post_type = substr( sanitize_key($new), 0, 20 );
			if ( $post_type === $new ) {
				// modify all CPTs in DB to reflect this new CPT
				global $wpdb;
				$wpdb->update( $wpdb->posts, [ 'post_type'=>$post_type ], [ 'post_type' => $current ] );
				$wpdb->query( $wpdb->prepare("UPDATE {$wpdb->posts} SET guid = REPLACE(guid, %s, %s) WHERE `guid` LIKE %s", "post_type={$current}&", "post_type={$post_type}&", "%post_type={$current}&%") );
				if ( $base === 'events' ) {
					$wpdb->update( EM_EVENTS_TABLE, [ 'event_archetype'=>$post_type ], [ 'event_archetype' => $current ] );
				}
			} else {
				throw new Exception( sprintf( __( 'Cannot create a Archetype CPT name %s, this must be at most 20 characters long, containing letters, numbers, dashes and underscores only.', 'events-manager' ), "<code>{$new}</code>", "<code>{$_POST['em_cp_events_cpts']}</code>" ), true );
			}
		} else {
			throw new Exception( sprintf( __( 'You cannot change the CPT type of %s to %s. This custom post type already exists.', 'events-manager' ), "<code>{$new}</code>", "<code>{$_POST['em_cp_events_cpts']}</code>" ), true );
		}
	}

	/**
	 * Returns an array of options that can be overridden by specific archetypes.
	 * Aside from this list there are also some base options that can be overridden and are defined in the settings page when creating an actual custom archetype.
	 * Examples of these are bookings, repeated events, taxonomy support.
	 *
	 * @return array
	 */
	public static function get_overrideable_options() {
		if ( empty( static::$options ) ) {
			$options = apply_filters( 'em_archetypes_overrideable_options', [
				// General
				'dbem_events_default_scope' => true,
				'dbem_timezone_enabled' => true,
				'dbem_event_status_enabled' => true,
				'dbem_recurrence_enabled' => true,
				'dbem_repeating_enabled' => true,
				'dbem_rsvp_enabled' => true,
				'dbem_tags_enabled' => true,
				'dbem_categories_enabled' => true,
				'dbem_attributes_enabled' => true,
				'dbem_cp_events_custom_fields' => true,
				'dbem_placeholders_custom' => true,
				// General - Location
				'dbem_locations_enabled' => true,
				'dbem_require_location' => true,
				'dbem_location_types' => true,
				// Event Pages
				'dbem_cp_events_template' => true,
				'dbem_cp_events_body_class' => true,
				'dbem_cp_events_post_class' => true,
				'dbem_cp_events_formats' => true,
				'dbem_cp_events_comments' => true,
				// Other Pages
				'dbem_edit_events_page' => true,
				'dbem_edit_bookings_page' => true,
				// Event Listings
				'dbem_events_page' => true,
				'dbem_events_page_search_form' => true,
				'dbem_display_calendar_in_events_page' => true,
				'dbem_disable_title_rewrites' => true,
				'dbem_title_html' => true,
				'dbem_cp_events_has_archive' => true,
				'dbem_events_archive_scope' => true,
				'dbem_cp_events_archive_formats' => true,
				'dbem_cp_events_excerpt_formats' => true,
				'dbem_events_current_are_past' => true,
				'dbem_events_include_status_cancelled' => true,
				'dbem_cp_events_search_results' => true,
				'dbem_events_page_scope' => true,
				'dbem_events_default_limit' => true,
				// Advanced Formatting
				'dbem_advanced_formatting' => true,
				// Event Formatting
				'dbem_search_form_view' => true,
				'dbem_list_date_title' => true,
				'dbem_event_page_title_format' => true, // Only present if EM_MS_GLOBAL && !get_option('dbem_ms_global_events_links')
				'dbem_event_list_groupby' => true,
				'dbem_event_list_groupby_header_format' => true,
				'dbem_event_list_groupby_format' => true,
				'dbem_no_events_message' => true,
				'dbem_advanced_formatting_modes[events-list]' => true,
				'dbem_event_list_item_format_header' => true,
				'dbem_event_list_item_format' => true,
				'dbem_event_list_item_format_footer' => true,
				'dbem_advanced_formatting_modes[events-grid]' => true,
				'dbem_event_grid_item_format_header' => true,
				'dbem_event_grid_item_format' => true,
				'dbem_event_grid_item_format_footer' => true,
				'dbem_event_grid_item_width' => true,
				'dbem_advanced_formatting_modes[event-single]' => true,
				'dbem_single_event_format' => true,
				'dbem_advanced_formatting_modes[event-excerpt]' => true,
				'dbem_event_excerpt_format' => true,
				'dbem_event_excerpt_alt_format' => true,
				// Search Form Formatting
				'dbem_search_form_main' => true,
			    'dbem_search_form_responsive' => true,
			    'dbem_search_form_sorting' => true,
			    'dbem_search_form_text' => true,
			    'dbem_search_form_text_label' => true,
			    'dbem_search_form_text_hide_s' => true,
			    'dbem_search_form_text_hide_m' => true,
			    'dbem_search_form_geo' => true,
			    'dbem_search_form_geo_label' => true,
			    'dbem_search_form_geo_distance_default' => true,
			    'dbem_search_form_geo_unit_default' => true,
			    'dbem_search_form_geo_hide_s' => true,
			    'dbem_search_form_geo_hide_m' => true,
			    'dbem_search_form_dates' => true,
			    'dbem_search_form_dates_label' => true,
			    'dbem_search_form_dates_separator' => true,
			    'dbem_search_form_dates_format' => true,
			    'dbem_search_form_dates_hide_s' => true,
			    'dbem_search_form_dates_hide_m' => true,
			    'dbem_search_form_advanced' => true,
			    'dbem_search_form_submit' => true,
			    'dbem_search_form_advanced_style' => true,
			    'dbem_search_form_advanced_mode' => true,
			    'dbem_search_form_advanced_hidden' => true,
			    'dbem_search_form_advanced_trigger' => true,
			    'dbem_search_form_advanced_show' => true,
			    'dbem_search_form_advanced_hide' => true,
			    'dbem_search_form_text_advanced' => true,
			    'dbem_search_form_text_label_advanced' => true,
			    'dbem_search_form_dates_advanced' => true,
			    'dbem_search_form_dates_label_advanced' => true,
			    'dbem_search_form_dates_separator_advanced' => true,
			    'dbem_search_form_dates_format_advanced' => true,
			    'dbem_search_form_categories' => true,
			    'dbem_search_form_category_label' => true,
			    'dbem_search_form_categories_placeholder' => true,
			    'dbem_search_form_categories_label' => true,
			    'dbem_search_form_categories_include' => true,
			    'dbem_search_form_categories_exclude' => true,
			    'dbem_search_form_tags' => true,
			    'dbem_search_form_tag_label' => true,
			    'dbem_search_form_tags_placeholder' => true,
			    'dbem_search_form_tags_label' => true,
			    'dbem_search_form_tags_include' => true,
			    'dbem_search_form_tags_exclude' => true,
			    'dbem_search_form_geo_advanced' => true,
			    'dbem_search_form_geo_label_advanced' => true,
			    'dbem_search_form_geo_units' => true,
			    'dbem_search_form_geo_units_label' => true,
			    'dbem_search_form_geo_distance_options' => true,
			    'dbem_search_form_countries' => true,
			    'dbem_search_form_default_country' => true,
			    'dbem_search_form_country_label' => true,
			    'dbem_search_form_countries_label' => true,
			    'dbem_search_form_regions' => true,
			    'dbem_search_form_region_label' => true,
			    'dbem_search_form_regions_label' => true,
			    'dbem_search_form_states' => true,
			    'dbem_search_form_state_label' => true,
			    'dbem_search_form_states_label' => true,
			    'dbem_search_form_towns' => true,
			    'dbem_search_form_town_label' => true,
			    'dbem_search_form_towns_label' => true,
				// Emails
				'dbem_bookings_notify_admin' => true,
				'dbem_bookings_contact_email' => true,
				'dbem_bookings_replyto_owner_admins' => true,
				'dbem_bookings_contact_email_confirmed_subject' => true,
				'dbem_bookings_contact_email_confirmed_body' => true,
				'dbem_bookings_contact_email_pending_subject' => true,
				'dbem_bookings_contact_email_pending_body' => true,
				'dbem_bookings_contact_email_cancelled_subject' => true,
				'dbem_bookings_contact_email_cancelled_body' => true,
				'dbem_bookings_contact_email_rejected_subject' => true,
				'dbem_bookings_contact_email_rejected_body' => true,
				'dbem_bookings_replyto_owner' => true,
				'dbem_bookings_email_confirmed_subject' => true,
				'dbem_bookings_email_confirmed_body' => true,
				'dbem_bookings_email_pending_subject' => true,
				'dbem_bookings_email_pending_body' => true,
				'dbem_bookings_email_cancelled_subject' => true,
				'dbem_bookings_email_cancelled_body' => true,
				'dbem_bookings_email_rejected_subject' => true,
				'dbem_bookings_email_rejected_body' => true,
				'dbem_email_disable_registration' => true,
				'dbem_bookings_email_registration_subject' => true,
				'dbem_bookings_email_registration_body' => true,
				'dbem_event_submitted_email_admin' => true,
				'dbem_event_submitted_email_subject' => true,
				'dbem_event_submitted_email_body' => true,
				'dbem_event_resubmitted_email_subject' => true,
				'dbem_event_resubmitted_email_body' => true,
				'dbem_event_published_email_subject' => true,
				'dbem_event_published_email_body' => true,
				'dbem_event_approved_email_subject' => true,
				'dbem_event_approved_email_body' => true,
				'dbem_event_reapproved_email_subject' => true,
				'dbem_event_reapproved_email_body' => true,
				'dbem_event_cancelled_email_subject' => true,
				'dbem_event_cancelled_email_body' => true

			]);
			// accepts only arrays or true
			foreach ( $options as $option => $value ) {
				if ( is_array( $value ) ||$value === true ) {
					static::$options[$option] = $value;
				}
			}
		}
		return static::$options;
	}

	public static function is_overrideable( $option, $type = null ) {
		$has_option = !empty( static::get_overrideable_options()[$option] );
		if ( $has_option && $type ) {
			return static::get_overrideable_options()[$option] === true || in_array( $type, static::get_overrideable_options()[$option] );
		}
		return $has_option;
	}

	public static function can_rename_labels () {
		return !is_multisite() || is_network_admin() || ( !EM_MS_GLOBAL &&  get_site_option( 'dbem_archetypes_rename_labels' ) );
	}

	public static function can_rename_cpts () {
		return !is_multisite() || is_network_admin() || ( !EM_MS_GLOBAL && get_site_option( 'dbem_archetypes_rename_cpts' ) );
	}

	public static function can_rename_slugs () {
		return !is_multisite() || is_network_admin() || ( !EM_MS_GLOBAL && get_site_option( 'dbem_archetypes_rename_slugs' ) );
	}

	public static function can_subsite_create () {
		if ( !is_multisite() || is_network_admin() || is_main_site() ) {
			return true;
		}
		$mode = Archetypes::get_ms_mode();

		return $mode === 'custom';
	}

	/**
	 * Adds some JS to correct submenu items in WP Admin menu not correctly having the parent menu open, rather always opening the first occurrence of that submenu item in another archetype (usually the main EM archetype).
	 * @return void
	 */
	public static function admin_footer(){
		if ( strstr($_REQUEST['page'] ?? '', 'events-manager-') && Archetypes::is_event( $_REQUEST['post_type'] ?? false ) ) {
			// make sure the right menu is open based on the current class name in JS
			?>
			<script type="text/javascript">
				document.addEventListener('DOMContentLoaded', function() {
					let current = document.querySelector('#adminmenu .current');
					let top = current.closest('.menu-top');
					// check if top menu has wp-has-current-submenu class, if not then we need to add it and a subclass, and remove the other menu that may have this
					if ( !top.matches('.wp-has-current-submenu') ) {
						let nav = top.closest('#adminmenu');
						nav.querySelectorAll('.wp-has-current-submenu').forEach( function(el) {
							el.classList.remove('wp-has-current-submenu', 'wp-menu-open');
							el.classList.add('wp-not-current-submenu');
							let topLink = top.querySelector('a.menu-top');
							topLink?.classList.remove('wp-has-current-submenu', 'wp-menu-open');
							topLink?.classList.add('wp-not-current-submenu');
						})
						top.classList.add('wp-has-current-submenu', 'wp-menu-open');
						top.classList.remove('wp-not-current-submenu');
						let topLink = top.querySelector('a.menu-top');
						topLink?.classList.add('wp-has-current-submenu', 'wp-menu-open');
						topLink?.classList.remove('wp-not-current-submenu');
					}
				})
			</script>
			<?php
		}
	}
}
Archetypes_Admin::init();