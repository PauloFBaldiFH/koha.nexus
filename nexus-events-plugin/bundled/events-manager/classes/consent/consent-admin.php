<?php
namespace EM\Consent;

class Consent_Admin {
	
	public static $prefix = 'consent';
	
	public static function init() {
		add_action('admin_init', [ static::class, 'hooks'] );
	}
	
	public static function hooks() {
		// here we override the Consent hooks with admin hooks
		add_action('em_settings_general_footer', [ static::class, 'admin_options'] );
	}
	
	public static function get_consent_options() {
		return array(
			0 => __('Do not include', 'events-manager'),
			1 => __('Include all', 'events-manager'),
			2 => __('Include only guest submissions', 'events-manager')
		);
	}
	
	public static function get_admin_meta_box_title() {
		return esc_html( 'Consent'); //override this
	}
	
	/**
	 * Meta options box for privacy and data protection rules for GDPR (and other dp laws) compliancy
	 */
	public static function admin_options(){
		global $save_button;
		?>
		<div  class="postbox " id="em-opt-data-<?php echo esc_attr(static::$prefix); ?>" >
			<div class="handlediv" title="<?php __('Click to toggle', 'events-manager'); ?>"><br /></div><h3><span><?php echo static::get_admin_meta_box_title() ?> </span></h3>
			<div class="inside">
				<?php static::admin_options_intro(); ?>
				<table class='form-table'>
					<?php
						do_action('em_data_' . static::$prefix . '_settings_table_header');
						static::admin_options_settings_table_header();
						static::admin_options_settings_table_consent_options();
						static::admin_options_settings_table_footer();
						do_action('em_data_' . static::$prefix . '_settings_table_footer');
						echo $save_button;
					?>
				</table>
			</div> <!-- . inside -->
		</div> <!-- .postbox -->
		<?php
	}
	
	public static function admin_options_intro() {}
	
	public static function admin_options_settings_table_header () {}
	
	public static function admin_options_settings_table_consent_options(){
		$consent_options = static::get_consent_options();
		$consent_remember = array(
			0 => __('Always show and ask for consent', 'events-manager'),
			1 => __('Remember and hide checkbox', 'events-manager'),
			2 => __('Remember and show checkbox', 'events-manager')
		);
		em_options_input_text( __('Consent Text', 'events-manager'), 'dbem_data_' . static::$prefix . '_text', __('%s will be replaced by a link to your site privacy policy page.', 'events-manager') );
		em_options_input_text( __('Bookings Consent Error', 'events-manager'), 'dbem_data_' . static::$prefix . '_bookings_error', __('If the consent checkbox is not checked during a booking, this error will be returned.', 'events-manager') );
		em_options_input_text( __('Consent Error', 'events-manager'), 'dbem_data_' . static::$prefix . '_cpt_error', __('If the consent checkbox is not checked when submitting information such as events or locations, this error will be returned.', 'events-manager') );
		em_options_select( __('Remembering Consent', 'events-manager'), 'dbem_data_' . static::$prefix . '_remember', $consent_remember, __('You can hide or leave the consent box checked for registered users who have provided consent previously.', 'events-manager') );
		em_options_select( __( 'Event Submission Forms', 'events-manager'), 'dbem_data_' . static::$prefix . '_events', $consent_options );
		em_options_select( __( 'Location Submission Forms', 'events-manager'), 'dbem_data_' . static::$prefix . '_locations', $consent_options );
		em_options_select( __( 'Bookings Forms', 'events-manager'), 'dbem_data_' . static::$prefix . '_bookings', $consent_options );
		em_options_radio_binary( __('Consented By Default', 'events-manager'), 'dbem_data_' . static::$prefix . '_default', __('If a user has not previously given or revoked consent for a specific submitted data type (such as bookings), do we assume user has given consent by default?', 'events-manager') );
	}
	
	public static function admin_options_settings_table_footer(){}
}