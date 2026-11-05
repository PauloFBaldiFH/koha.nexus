<?php
namespace EM\Consent;

class Comms_Admin extends Consent_Admin {
	
	public static $prefix = 'comms_consent';
	
	public static function hooks() {
		// here we override the Consent hooks with admin hooks
		add_action('em_data_privacy_consent_settings_table_footer', [ static::class, 'admin_options'] );
	}
	
	
	public static function get_admin_meta_box_title() {
		return esc_html( 'Consent'); //override this
	}
	
	/**
	 * Meta options box for privacy and data protection rules for GDPR (and other dp laws) compliancy
	 */
	public static function admin_options(){
		?>
		<thead>
		<tr class="em-header">
			<th colspan="2">
				<h4><?php esc_html_e('Communications Consent', 'events-manager'); ?></h4>
				<p>
					<?php esc_html_e('You can also request specific consent from your users to be contacted via supplied communication options (Email, Phone, SMS, WhatsApp, Facebook, Telegram etc.), this can be separate to your privacy policy, given that this relates to consenting to non-essential communication such as marketing or non-email-based reminders.', 'events-manager'); ?>
				</p>
			</th>
		</tr>
		</thead>
		<?php
		em_options_radio_binary( __('Is consent required?', 'events-manager'), 'dbem_data_' . static::$prefix . '_required', '', '' , '#dbem_data_comms_consent_bookings_error_row, #dbem_data_comms_consent_cpt_error_row');
		static::admin_options_settings_table_consent_options();
	}
	
	public static function admin_options_intro() {}
	
	public static function admin_options_settings_table_header () {}
}
Comms_Admin::init();