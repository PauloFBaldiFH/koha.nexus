<?php
namespace EM\Consent;

class Privacy extends Consent {
	
	public static $options = array(
		'remember' => 'dbem_data_privacy_consent_remember',
		'label' => 'dbem_data_privacy_consent_text',
		'param' => 'data_privacy_consent',
		'meta_key' => 'em_data_privacy_consent',
	);
	
	public static $prefix = 'privacy_consent';
	public static $required = true;
	
	public static function init() {
		parent::init();
		if( is_admin() ) {
			include('privacy-consent-admin.php');
		}
	}
	
	public static function get_error_booking() {
		return esc_html__('You must allow us to collect and store your data in order for us to process your booking.', 'events-manager');
	}
	
	public static function get_error_cpt() {
		return esc_html__('Please check the consent box so we can collect and store your submitted information.', 'events-manager');
	}
	
	public static function get_label() {
		$label = em_get_option( static::$options['label'] );
		// buddyboss fix since bb v1.6.0
		if( has_filter( 'the_privacy_policy_link', 'bp_core_change_privacy_policy_link_on_private_network') ) $bb_fix = remove_filter('the_privacy_policy_link', 'bp_core_change_privacy_policy_link_on_private_network', 999999);
		// replace privacy policy text %s with link to policy page
		if( function_exists('get_the_privacy_policy_link') ) $label = sprintf($label, get_the_privacy_policy_link());
		// buddyboss unfix since bb v1.6.0
		if( !empty($bb_fix) ) add_filter( 'the_privacy_policy_link', 'bp_core_change_privacy_policy_link_on_private_network', 999999, 2 );
		return $label;
	}
}

Privacy::init();