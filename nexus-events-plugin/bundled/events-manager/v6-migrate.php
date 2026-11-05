<?php
class EM_v6_Migration {
	public static function init(){
		$v6 = EM_Options::get('v6', null);
		if( $v6 === null ) return;
		if( (!is_admin() || defined('EM_DOING_AJAX')) && $v6 === 'p' ){
			add_action('events_manager_loaded', 'EM_v6_Migration::preview_formats', 1);
		}
		add_action('admin_init', 'EM_v6_Migration::actions');
		add_action('em_options_page_header', 'EM_v6_Migration::em_options_page_header');
	}
	
	public static function preview_formats(){
		if( !current_user_can('manage_options') ) return;
		add_filter('pre_option_dbem_advanced_formatting', '__return_zero');
		add_filter('pre_option_dbem_css_theme_font_weight', '__return_zero');
		add_filter('pre_option_dbem_css_theme_font_family', '__return_zero');
		add_filter('pre_option_dbem_css_theme_font_size', '__return_zero');
		add_filter('pre_option_dbem_css_theme_line_height', '__return_zero');
	}
	
	public static function actions(){
		global $EM_Notices; /* @var EM_Notices $EM_Notices */
		// deal with v6 migration
		if( !empty($_REQUEST['action']) && $_REQUEST['action'] == 'v6_migrate' && wp_verify_nonce($_REQUEST['nonce'], 'v6-migrate') && current_user_can('manage_options') ){
			$data = get_option('dbem_data');
			switch( $_REQUEST['do'] ){
				case 'preview':
					$data['v6'] = 'p';
					break;
				case 'preview-disable':
					$data['v6'] = false;
					break;
				case 'migrate':
					// migrate all options over
					$data['v6'] = 'undo'; // this is for legacy widgets, v7 will remove it
					// disable preview in case
					remove_filter('em_formats_filter', 'EM_v6_Migration::preview_formats', 1);
					// copy over new formats overriding old ones, but putting them in an 'undo' var
					$undo = array();
					foreach( EM_Formats::get_default_formats( true ) as $format ){
						$format_content = call_user_func('EM_Formats::'.$format, '');
						$undo[$format] = get_option($format);
						update_option($format, $format_content );
					}
					update_option('dbem_v6_undo', $undo, false); // no auto-loading this
					// add overriding styling
					update_option('dbem_advanced_formatting', 0);
					update_option('dbem_css_theme_font_weight', 0);
					update_option('dbem_css_theme_font_family', 0);
					update_option('dbem_css_theme_font_size', 0);
					update_option('dbem_css_theme_line_height', 0);
					// remove notices and add confirmation
					EM_Admin_Notices::remove('v6-update', is_multisite());
					EM_Admin_Notices::remove('v6-update2', is_multisite());
					$EM_Notices->add_confirm(esc_html__('You nave successfully migrated to the default v6 formatting options, enjoy! We have an undo option, just in case...', 'events-manager'), true);
					break;
				case 'dismiss':
					unset($data['v6']);
					EM_Admin_Notices::remove('v6-update', is_multisite());
					EM_Admin_Notices::remove('v6-update2', is_multisite());
					break;
				case 'dismiss-undo':
					delete_option('dbem_v6_undo');
					$data['v6'] = true;
					break;
				case 'undo':
					$data['v6'] = false;
					$undo = get_option('dbem_v6_undo');
					update_option('dbem_advanced_formatting', 2);
					update_option('dbem_css_theme_font_weight', 1);
					update_option('dbem_css_theme_font_family', 1);
					update_option('dbem_css_theme_font_size', 1);
					update_option('dbem_css_theme_line_height', 1);
					if( empty($undo) ){
						$EM_Notices->add_error('Oh dear... looks like the undo data was deleted from your wp_options table. Please see if you have a backup of that table and look for the <strong>dbem_v6_undo</strong> option_name value.', true);
					}else{
						$count = 0;
						foreach( $undo as $option => $value ){
							if( preg_match('/^dbem_/', $option) ) {
								update_option($option, $value);
								$count++;
							}
						}
						$EM_Notices->add_confirm("Migration has been undone, your previous formatting settings ($count values) have been restored. You can migrate again if you need to!", true);
					}
					break;
			}
			update_option('dbem_data', $data);
			$referrer = em_wp_get_referer();
			//add tab hash path to url if supplied
			if( !empty($_REQUEST['tab_path']) ){
				$referrer_array = explode('#', $referrer);
				$referrer = esc_url_raw($referrer_array[0] . '#' . $_REQUEST['tab_path']);
			}
			wp_safe_redirect($referrer);
			die();
		}
	}
	
	public static function em_options_page_header(){
		// Deal with v6 transition
		$v6 = EM_Options::get('v6', null);
		if( $v6 !== null && $v6 !== true ){
			$url = add_query_arg(array('action'=>'v6_migrate', 'nonce' => wp_create_nonce('v6-migrate')));
			if( $v6 !== 'undo' ) : ?>
				<div class="notice notice-info">
					<?php if( $v6 === 'p' ): ?>
					<p style="font-weight:bold;">
						<?php esc_html_e('Preview mode is enabled. Only site admins will see the difference, our new default formats will be used instead of your current formats. You can continue to edit/save this settings page without overwriting saved settings.', 'events-manager'); ?>
					</p>
					<?php endif; ?>
					<p><?php esc_html_e('Welcome to Events Manager v6! This latest update includes some major UI improvements, which requires you to update your formats.', 'events-manager'); ?></p>
					<p><?php esc_html_e("To help with the transition, we're providing you with a Preview mode you can activate below, which will temporarily use our new formatting options only for you to see (other site visitors will see your site as usual). If you're happy with the changes, you can switch over completely, or revert individual formats within these settings pages.",'events-manager'); ?></p>
					<p><?php echo sprintf(esc_html__("More information about migrating to v6 can be found %s.",'events-manager'), '<a href="https://wp-events-plugin.com/documentation/v6-migration/" target="_blank">'.esc_html__('here', 'events-manager').'</a>'); ?></p>
					<p>
						<?php if( $v6 === 'p' ): ?>
						<a href="<?php echo esc_url(add_query_arg('do', 'preview-disable', $url)); ?>" class="button-primary button em-tooltip" aria-label="<?php esc_html_e('Revert to viewing your previously saved fromats.', 'events-manager'); ?>"><?php echo sprintf(esc_html__('%s Preview Mode', 'events-manager'), esc_html__('Disable', 'events-manager')); ?></a>
						<?php else: ?>
						<a href="<?php echo esc_url(add_query_arg('do', 'preview', $url)); ?>" class="button-primary button em-tooltip" aria-label="<?php esc_html_e('Only site admins see these changes.', 'events-manager'); ?>"><?php echo sprintf(esc_html__('%s Preview Mode', 'events-manager'), esc_html__('Enable', 'events-manager')); ?></a>
						<?php endif; ?>
						<a href="<?php echo esc_url(add_query_arg('do', 'migrate', $url)); ?>" class="button-secondary button em-tooltip" aria-label="<?php esc_html_e('Copy over our new v6 formats to make the best of our new UI design!', 'events-manager'); ?>"><?php esc_html_e('Migrate Formats', 'events-manager'); ?></a>
						<a href="<?php echo esc_url(add_query_arg('do', 'dismiss', $url)); ?>" class="button-secondary button em-tooltip" aria-label="<?php esc_html_e('Keep your current settings, or individuall revert to default formats.', 'events-manager'); ?>"><?php esc_html_e('Dismiss', 'events-manager'); ?></a>
					</p>
				</div>
			<?php else: ?>
				<div class="notice notice-info">
					<p><?php esc_html_e('You have successfully migrated to Events Manager v6 formatting! We hope you enjoy the changes. In case you had some special formatting you realize you needed, there\'s the undo option below, it will reset all your migrated formats to how they were previoiusly. You can migrate again or individuall migrate each option within the settings page.', 'events-manager'); ?></p>
					<p><?php esc_html_e('If you hare happy with the migration, you can dismiss this message and your old formatting options (i.e. this undo option) will be deleted.', 'events-manager'); ?></p>
					<p>
						<a href="<?php echo esc_url(add_query_arg('do', 'undo', $url)); ?>" class="button-primary button em-tooltip" aria-label="<?php esc_html_e('Revert to viewing your previously saved fromats.', 'events-manager'); ?>"><?php echo esc_html__('Undo Migration', 'events-manager'); ?></a>
						<a href="<?php echo esc_url(add_query_arg('do', 'dismiss-undo', $url)); ?>" class="button-secondary button "><?php esc_html_e('Dismiss', 'events-manager'); ?></a>
					</p>
				</div>
			<?php endif;
		}
	}
}
EM_v6_Migration::init();