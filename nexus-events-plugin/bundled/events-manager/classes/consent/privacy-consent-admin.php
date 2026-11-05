<?php
namespace EM\Consent;

class Privacy_Consent_Admin extends Consent_Admin {
	
	public static $prefix = 'privacy_consent';
	
	public static function get_admin_meta_box_title() {
		return esc_html__ ( 'Privacy Policy and Consent', 'events-manager');
	}
	
	public static function admin_options_intro() {
		?>
		<p class="em-boxheader"><?php echo sprintf(__('Depending on the nature of your site, you will be subject to one or more national and international privacy/data protection laws such as the %s. Below are some options that you can use to tailor how Events Manager interacts with WordPress privacy tools.','events-manager'), '<a href=http://ec.europa.eu/justice/smedataprotect/index_en.htm">GDPR</a>'); ?></p>
		<p class="em-boxheader"><?php echo sprintf(__('For more information see our <a href="%s">data privacy documentation</a>.','events-manager'), 'https://wp-events-plugin.com/documentation/data-privacy-gdpr-compliance/'); ?></p>
		<p class="em-boxheader"><?php echo __('All options below relate to data that may have been submitted by or collected from the user requesting their personal data, which would also include events and locations where they are the author.', 'events-manager'); ?></p>
		<?php
	}
	
	public static function admin_options_settings_table_header () {
		$privacy_options = static::get_consent_options();
		?>
		<thead>
		<tr class="em-header">
			<th colspan="2"><h4><?php esc_html_e('Export Personal Data'); ?></h4></th>
		</tr>
		</thead>
		<?php
		em_options_select ( __( 'Events', 'events-manager'), 'dbem_data_privacy_export_events', $privacy_options );
		em_options_select ( __( 'Locations', 'events-manager'), 'dbem_data_privacy_export_locations', $privacy_options, __('Locations submitted by guest users are not included, unless they are linked to events also submitted by them.', 'events-manager') );
		em_options_select ( __( 'Bookings', 'events-manager'), 'dbem_data_privacy_export_bookings', $privacy_options, __('This is specific to bookings made by the user, not bookings that may have been made to events they own.', 'events-manager'), $privacy_options );
		?>
		<thead>
		<tr class="em-header">
			<th colspan="2"><h4><?php esc_html_e('Erase Personal Data'); ?></h4></th>
		</tr>
		</thead>
		<?php
		em_options_select ( __( 'Events', 'events-manager'), 'dbem_data_privacy_erase_events', $privacy_options );
		em_options_select ( __( 'Locations', 'events-manager'), 'dbem_data_privacy_erase_locations', $privacy_options, __('Locations submitted by guest users are not included, unless they are linked to events also submitted by them.', 'events-manager') );
		em_options_select ( __( 'Bookings', 'events-manager'), 'dbem_data_privacy_erase_bookings', $privacy_options, __('This is specific to bookings made by the user, not bookings that may have been made to events they own.', 'events-manager'), $privacy_options );
		?>
		<thead>
		<tr class="em-header">
			<th colspan="2">
				<h4><?php esc_html_e('Consent', 'events-manager'); ?></h4>
				<p><?php esc_html_e('If you collect personal data, you may want to request their consent. The options below will automatically add checkboxes requesting this consent.', 'events-manager'); ?></p>
			</th>
		</tr>
		</thead>
		<?php
	}
}
Privacy_Consent_Admin::init();