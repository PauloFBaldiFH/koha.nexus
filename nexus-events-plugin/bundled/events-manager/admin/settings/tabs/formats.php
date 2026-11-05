<?php if( !function_exists('current_user_can') || !current_user_can('manage_options') ) return; ?>
<!-- FORMAT OPTIONS -->
<div class="em-menu-formats em-menu-group"  <?php if( !defined('EM_SETTINGS_TABS') || !EM_SETTINGS_TABS) : ?>style="display:none;"<?php endif; ?>>
	<p>
		<input type="checkbox" id="em-enable-codeEditor" value="1">
		<label for="em-enable-codeEditor" class="em-tooltip" aria-label="<?php esc_attr_e('Enable a code/syntax highlighter when clicking on the larger formatting textbox options below, for easier editing of larger HTML parts.', 'events-manager'); ?>" style="text-decoration: 2px underline dotted #ccc; text-underline-offset: 4px;">
			<?php esc_html_e('Enable Code Editor for Formats', 'events-manager'); ?>
		</label>
	</p>
	<?php
	$current_status = absint(get_option('dbem_advanced_formatting'));
	$archetype_options = em_options_get_archetype_options('dbem_advanced_formatting');
	$disabled_text = __('Disabled', 'events-manager');
	$enabled_text = __('Enabled', 'events-manager');
	$current_text = $current_status ? '<span class="status enabled">('. $enabled_text .')</span>' : '<span class="status disabled">('.$disabled_text.')</span>';
	?>
	<div  class="postbox em-postbox-notice em-postbox-notice-info" id="em-opt-advanced-formatting" data-enabled-text="(<?php echo esc_attr($enabled_text); ?>)" data-disabled-text="(<?php echo esc_attr($disabled_text); ?>)">
		<div class="handlediv" title="<?php __('Click to toggle', 'events-manager'); ?>"><br /></div><h3><span><?php _e ( 'Advanced Mode', 'events-manager'); ?> <?php echo $current_text ?></span></h3>
		<div class="inside">
			<div class="em-default-option em-advanced-formatting">
				<input type="hidden" name="dbem_advanced_formatting" value="<?php echo $current_status; ?>">
				<?php function em_options_advanced_formatting_content( $current_status ) { ?>
				<div>
					<?php
					$advanced_mode = esc_html__('Advanced Mode', 'events-manager');
					$advanced_mode_super = esc_html__('Super Advanced Mode', 'events-manager');
					$disable_text = sprintf(esc_html__('Disable %s', 'events-manager'), $advanced_mode);
					$enable_text = sprintf(esc_html__('Enable %s', 'events-manager'), $advanced_mode);
					?>
					<p>
						<a href="#" class="em-af-toggle button-primary show-0" data-set-status="1"><?php echo $enable_text; ?></a>
						<a href="#" class="em-af-toggle button-secondary show-1 show-2" data-set-status="0"><?php echo $disable_text; ?></a>
					</p>
					<?php
					$disable_text = sprintf(esc_html__('Disable %s', 'events-manager'), $advanced_mode_super);
					$enable_text = sprintf(esc_html__('Enable %s', 'events-manager'), $advanced_mode_super);
					$current_text = $current_status ? $disable_text : $enable_text;
					?>
					<a href="#" class="em-af-toggle button-secondary show-2" data-set-status="1"><?php echo $disable_text; ?></a>
					<a href="#" class="em-af-toggle button-primary show-1 show-0" data-set-status="2"><?php echo $enable_text; ?></a>
				</div>
				<div>
					<?php
					$am = '<code>'. $advanced_mode .'</code>';
					$sam = '<code>'.$advanced_mode_super.'</code>';
					?>
					<p class="em-af-status" data-status="<?php echo $current_status; ?>">
						<span class="em-af-status-0"><?php echo sprintf( esc_html__('You have currently disabled %s', 'events-manager'), $am ); ?></span>
						<span class="em-af-status-1"><?php echo sprintf( esc_html__('You have currently enabled %s', 'events-manager'), $am ); ?></span>
						<span class="em-af-status-2"><?php echo sprintf( esc_html__('You have currently enabled %s', 'events-manager'), $sam ); ?></span>
						<span class="em-af-status-save"><?php esc_html_e('Save your settings for this to take effect!', 'events-manager'); ?></span>
					</p>
					<p>
						<?php echo sprintf(esc_html__("%s allows you to modify some or all of the formats used by Events Manager to generate your content. You can choose to override default formats and customize them to your needs. You do not lose your previously defined custom formats should you enable/disable %s or choose to not override a certain set of formats, they'll appear again once you enable %s again for that content.", 'events-manager'), $am, $am, $am); ?>
					</p>
					<p>
						<?php echo sprintf(esc_html__("%s overrides all formatting choices, which will be be taken from the settings defined on this page. If you want to override only certain formatting, choose the %s instead.", 'events-manager'), $sam, $am); ?>
					</p>
					<p>
						<?php esc_html_e('Clicking these buttons will not have any effect until you save your settings!', 'events-manager'); ?>
					</p>
				</div>
				<?php } em_options_advanced_formatting_content( $current_status ); ?>
			</div>
			<div class="em-archetype-options">
				<?php foreach ( $archetype_options['archetypes'] as $type => $atts ): ?>
					<div class="em-archetype-option em-advanced-formatting" data-archetype="<?php echo $type ?>">
						<input type="hidden" name="<?php echo esc_attr($atts['name']) ?>" type="text" id="em-advanced-formatting_<?php echo $type ?>" value="<?php echo $atts['value'] ?? $current_status ? 1:0; ?>">
						<?php em_options_advanced_formatting_content( $atts['value'] ?? $current_status ? 1:0 ); ?>
					</div>
				<?php endforeach; ?>
			</div>
		</div>
	</div>

	<div  class="postbox " id="em-opt-events-formats" >
	<div class="handlediv" title="<?php __('Click to toggle', 'events-manager'); ?>"><br /></div><h3><span><?php _e ( 'Events', 'events-manager'); ?> </span></h3>
	<div class="inside">
    	<table class="form-table">
		 	<tr class="em-header"><td colspan="2">
		 		<h4><?php echo sprintf(__('%s Page','events-manager'),__('Events','events-manager')); ?></h4>
		 		<p><?php _e('These formats will be used on your events page. This will also be used if you do not provide specified formats in other event lists, like in shortcodes.','events-manager'); ?></p>
		 	</td></tr>
		    <?php
		    $views_map = em_get_search_views();
		    $views = array();
		    foreach( $views_map as $view_key => $view ){
			    $views[$view_key] = $view['name'];
		    }
		    em_options_select ( __( 'Default View', 'events-manager'), 'dbem_search_form_view', $views );
		    ?>
			<?php
			em_options_input_text ( __( 'List events by date title', 'events-manager'), 'dbem_list_date_title', __( 'If viewing a page for events on a specific date, this is the title that would show up. To insert date values, use <a href="http://www.php.net/manual/en/function.date.php">PHP time format characters</a>  with a <code>#</code> symbol before them, i.e. <code>#m</code>, <code>#M</code>, <code>#j</code>, etc.<br/>', 'events-manager') );
			if( EM_MS_GLOBAL && !get_option('dbem_ms_global_events_links') ){
				em_options_input_text ( sprintf(__( 'Single %s title format', 'events-manager'),__('event','events-manager')), 'dbem_event_page_title_format', sprintf(__( 'The format of a single %s page title.', 'events-manager'),__('event','events-manager')).' '.__( 'This is only used when showing events from other blogs.', 'events-manager').$events_placeholder_tip );
			}
			?>
		    <tbody>
			    <tr class="em-subheader">
				    <td colspan="2">
					    <h5><?php esc_html_e( 'Grouped Lists View', 'events-manager'); ?></h5>
					    <p><?php esc_html_e('These options are the defaults applied to lists being showing in Grouped List view mode and can be overriden in individual lists using shortcodes, blocks, widgets etc.', 'events-manager'); ?></p>
				    </td>
			    </tr>
			    <?php
			    $grouby_modes = array('yearly'=>__('Yearly','events-manager'), 'monthly'=>__('Monthly','events-manager'), 'weekly'=>__('Weekly','events-manager'), 'daily'=>__('Daily','events-manager'));
			    em_options_select(__('Grouped list default','events-manager'), 'dbem_event_list_groupby', $grouby_modes, __('If you choose a group by mode, your events page will display events in groups of your chosen time range.','events-manager'));
			    em_options_input_text(__('Grouped list header','events-manager'), 'dbem_event_list_groupby_header_format', __('Choose how to format your group headings.','events-manager').' '. sprintf(__('#s will be replaced by the date format below', 'events-manager'), 'http://codex.wordpress.org/Formatting_Date_and_Time'));
			    em_options_input_text(__('Grouped list format','events-manager'), 'dbem_event_list_groupby_format', __('Choose how to format your group heading dates. Leave blank for default.','events-manager').' '. sprintf(__('Date and Time formats follow the <a href="%s">WordPress time formatting conventions</a>', 'events-manager'), 'http://codex.wordpress.org/Formatting_Date_and_Time'));
			    ?>
		    </tbody>
		    <tbody class="am-af" data-group="format-events-list">
			    <tr class="em-subheader" data-group="format-events-list"><td colspan="2"><h5><?php echo esc_html( sprintf(_x('%1$s %2$s Formats', 'cpt type and view type', 'events-manager'), __('Event', 'events-manager'), __('List', 'events-manager')) ); ?></h5></td></tr>
			    <?php
			    em_options_input_text ( __( 'No events message', 'events-manager'), 'dbem_no_events_message', __( 'The message displayed when no events are available.', 'events-manager') );
				?>
		    </tbody>

		    <!-- ADVANCED Formatting -->
		    <tbody class="am-af" data-group="format-events-list">
		        <?php
		        em_options_radio_binary ( __( 'Override Default Formats?', 'events-manager'), 'dbem_advanced_formatting_modes[events-list]', '', '', '.am-af-events-list' );
		        ?>
		    </tbody>
		    <tbody class="am-af am-af-events-list" data-group="format-events-list">
			    <?php
			    em_options_textarea ( __( 'Default event list format header', 'events-manager'), 'dbem_event_list_item_format_header', __( 'This content will appear just above your code for the default event list format. Default is blank', 'events-manager'), true );
			    em_options_textarea ( __( 'Default event list format', 'events-manager'), 'dbem_event_list_item_format', __( 'The format of any events in a list.', 'events-manager').$events_placeholder_tip, true );
				em_options_textarea ( __( 'Default event list format footer', 'events-manager'), 'dbem_event_list_item_format_footer', __( 'This content will appear just below your code for the default event list format. Default is blank', 'events-manager'), true );
			    ?>
		    </tbody>
		    <!-- /ADVANCED Formatting -->

			<!-- ADVANCED Formatting -->
		    <tbody class="am-af" data-group="format-events-grid">
		        <tr class="em-subheader"><td colspan="2"><h5><?php echo esc_html( sprintf(_x('%1$s %2$s Formats', 'cpt type and view type', 'events-manager'), __('Event', 'events-manager'), __('Grid', 'events-manager')) ); ?></h5></td></tr>
			    <?php
			    em_options_radio_binary ( __( 'Override Default Formats?', 'events-manager'), 'dbem_advanced_formatting_modes[events-grid]', '', '', '.am-af-events-grid' );
			    ?>
		    </tbody>
		    <tbody class="am-af am-af-events-grid" data-group="format-events-grid">
			    <?php
			    em_options_textarea ( sprintf(_x( 'Default %1$s %2$s format header', 'events-manager', 'cpt type and view type'), __('Event', 'events-manager'), __('Grid', 'events-manager')), 'dbem_event_grid_item_format_header', sprintf(__( 'This content will appear just above your code for the %s list format below. Default is blank', 'events-manager'), __('grid','events-manager')), true );
			    em_options_textarea ( sprintf(_x( 'Default %1$s %2$s format', 'events-manager', 'cpt type and view type'), __('Event', 'events-manager'), __('Grid', 'events-manager')), 'dbem_event_grid_item_format', sprintf(__( 'The format of a single %s in a list.', 'events-manager'), __('event','events-manager')).$events_placeholder_tip, true );
			    em_options_textarea ( sprintf(_x( 'Default %1$s %2$s format footer', 'events-manager', 'cpt type and view type'), __('Event', 'events-manager'), __('Grid', 'events-manager')), 'dbem_event_grid_item_format_footer', sprintf(__( 'This content will appear just below your code for the %s list format above. Default is blank', 'events-manager'), __('grid','events-manager')), true );
			    ?>
		    </tbody>
		    <!-- /ADVANCED Formatting -->

		    <?php
		    em_options_input_text( sprintf(_x( 'Default %1$s %2$s width', 'events-manager', 'cpt type and view type'), __('Event', 'events-manager'), __('Grid', 'events-manager')), 'dbem_event_grid_item_width', __( 'The default minimum width, in pixels, that each grid item can shrink to fit on one line.', 'events-manager') );
		    ?>

		    <!-- ADVANCED Formatting -->
		    <tbody class="am-af" data-group="format-event-single">
			    <tr class="em-header">
			        <td colspan="2">
			            <h4><?php echo sprintf(__('Single %s Page','events-manager'),__('Event','events-manager')); ?></h4>
			            <em><?php echo sprintf(__('These formats can be used on %s pages or on other areas of your site displaying an %s.','events-manager'),__('event','events-manager'),__('event','events-manager'));?></em>
			        </td>
			    </tr>
		 	    <?php
		        em_options_radio_binary(__('Override Default Formats?', 'events-manager'), 'dbem_advanced_formatting_modes[event-single]', '', '', '.am-af-event-single');
				?>
		    </tbody>
		    <tbody class="am-af am-af-event-single" data-group="format-event-single">
		    <?php
			em_options_textarea ( sprintf(__('Single %s page format', 'events-manager'),__('event','events-manager')), 'dbem_single_event_format', sprintf(__( 'The format used to display %s content on single pages or elsewhere on your site.', 'events-manager'),__('event','events-manager')).$events_placeholder_tip, true);
			?>
		    </tbody>
		    <!-- /ADVANCED Formatting -->

		    <!-- ADVANCED Formatting -->
		    <tbody class="am-af">
			    <tr class="em-header">
				    <td colspan="2">
					    <h4><?php echo sprintf(__('%s Excerpts','events-manager'),__('Event','events-manager')); ?></h4>
					    <em><?php echo sprintf(__('These formats can be used when WordPress automatically displays %s excerpts on your site and %s is enabled in your %s settings tab.','events-manager'),__('event','events-manager'),'<strong>'.__( 'Override Excerpts with Formats?', 'events-manager').'</strong>','<a href="#formats" class="nav-tab-link" rel="#em-menu-pages">'.__('Pages','events-manager').'  &gt; '.sprintf(__('%s List/Archives','events-manager'),__('Event','events-manager')).'</a>');?></em>
				    </td>
			    </tr>
			    <?php
			    em_options_radio_binary(__('Override Default Formats?', 'events-manager'), 'dbem_advanced_formatting_modes[event-excerpt]', '', '', '.am-af-event-excerpt');
			    ?>
		    </tbody>
		    <tbody class="am-af am-af-event-excerpt">
		    <?php
		    em_options_textarea ( sprintf(__('%s excerpt', 'events-manager'),__('Event','events-manager')), 'dbem_event_excerpt_format', __( 'Used if an excerpt has been defined.', 'events-manager').$events_placeholder_tip, true );
		    em_options_textarea ( sprintf(__('%s excerpt fallback', 'events-manager'),__('Event','events-manager')), 'dbem_event_excerpt_alt_format', __( 'Used if an excerpt has not been defined.', 'events-manager').$events_placeholder_tip, true );
			?>
		    </tbody>
		    <!-- /ADVANCED Formatting -->
		    
			<?php
			echo $save_button;
			?>
		</table>
	</div> <!-- . inside -->
	</div> <!-- .postbox -->

	<div  class="postbox " id="em-opt-search-form" >
	<div class="handlediv" title="<?php __('Click to toggle', 'events-manager'); ?>"><br /></div><h3><span><?php _e ( 'Search Form', 'events-manager'); ?> </span></h3>
	<div class="inside">
		<?php
			// common text
			global $em_localized_js;
			$breakpoints = $em_localized_js['search']['breakpoints'];
			$screen_desc = esc_html__('When the size of the %s is less than %s, this field can be hidden on the main search form to save viewing space. You can still enable this field to show in advanced search settings.', 'events-manager');
			$hide_size_desc_medium = sprintf($screen_desc, __('Search Form','events-manager'), $breakpoints['medium'].'px');
			$hide_size_desc_small = sprintf($screen_desc, __('Search Form','events-manager'), $breakpoints['small'].'px');
		?>
		<table class="form-table em-search-form-main">
		    <tr class="em-header"><td colspan="2"><h4><?php _e('Main Search Fields','events-manager'); ?></h4></td></tr>
			<?php
			em_options_radio_binary ( __( 'Show main search bar?', 'events-manager'), 'dbem_search_form_main', __('Choose whether to display the main search bar. If disabled, advanced search fields will be shown in \'Inline\' mode automatically. You must also choose to enable at least one advanced search field, to avoid having an emtpy search form.','events-manager'), '', '.em-search-form-main-option, .em-search-form-advanced-hidden' );
			$responsive_options = array(
				'one-line' => esc_html__('One Line', 'events-manager'),
				'multi-line' => esc_html__('Multi Line', 'events-manager'),
			);
			$screen_desc = esc_html__('When the size of the %s is less than %s, the search fields and buttons in the main bar can either remain on one line and resize accordingly, or break into multiple lines. If you want to keep all your search terms options, multiple lines will look better as they will look squashed on smaller screens and provide a worse search exprience. You can also hide individual search fields in settings further down to reduce screen clutter as the search from shrinks.', 'events-manager');
			$responsive_desc_medium = sprintf($screen_desc, __('Search Form','events-manager'), $breakpoints['medium'].'px');
			em_options_select( __( 'Responsive Behaviour', 'events-manager'), 'dbem_search_form_responsive', $responsive_options, $responsive_desc_medium );
			?>
			<tbody class="em-subsection em-search-form-main-option">
				<tr class="em-subheader"><td colspan="2"><h4><?php _e('Views','events-manager'); ?></h4></td></tr>
				<tr class="em-subheader">
					<td colspan="2">
						<em><?php echo sprintf(__('These formats can be used when WordPress automatically displays %s excerpts on your site and %s is enabled in your %s settings tab.','events-manager'),__('event','events-manager'),'<strong>'.__( 'Override Excerpts with Formats?', 'events-manager').'</strong>','<a href="#formats" class="nav-tab-link" rel="#em-menu-pages">'.__('Pages','events-manager').'  &gt; '.sprintf(__('%s List/Archives','events-manager'),__('Event','events-manager')).'</a>');?></em>
					</td>
				</tr>
				<tr valign="top" id='dbem_location_types_row'>
					<th scope="row"><?php esc_html_e('View Types', 'events-manager'); ?></th>
					<td>
						<?php
						$archetype_options = em_options_get_archetype_options('dbem_search_form_views');
						$view_types = get_option('dbem_search_form_views', array());
						if( !is_array($view_types) ) $view_types = array();
						?>
						<fieldset class="em-default-option option-checkboxes em-field-checkboxes">
							<legend class="screen-reader-text"><?php esc_html_e('View Types', 'events-manager'); ?></legend>
							<?php foreach ( $views as $view_name => $view_label ): ?>
								<label>
									<input type="checkbox" name="dbem_search_form_views[]" value="<?php  echo esc_attr($view_name); ?>" <?php if( in_array($view_name, $view_types) ) echo 'checked'; ?>>
									<?php echo esc_html($view_label); ?>
								</label>
							<?php endforeach; ?>
						</fieldset>
						<?php if( !empty($archetype_options['archetypes']) ): ?>
						<div class="em-archetype-options">
							<?php foreach ( $archetype_options['archetypes'] as $type => $atts ): ?>
								<div class="em-archetype-option option-checkboxes" data-archetype="<?php echo $type ?>"  <?php if ( empty($atts['value']) ) echo 'data-default'; ?>>
									<?php foreach ( $views as $view_name => $view_label ): ?>
										<label>
											<input type="checkbox" name="<?php echo esc_attr($atts['name']); ?>[]" value="<?php  echo esc_attr($view_name); ?>"
												<?php echo in_array($view_name, $view_types) ? 'data-default' : ''; ?>
												<?php if( in_array($view_name, $atts['value']) ) echo 'checked'; ?>>
											<?php echo esc_html($view_label); ?>
										</label>
									<?php endforeach; ?>
									<br>
									<div class="em-archetype-checkbox-buttons">
										<button type="button" class="button-secondary em-archetype-checkbox-default" <?php if ( empty($atts['value']) ) echo 'disabled'; ?>><?php esc_html_e('Use Defaults', 'events-manager'); ?></button>
										<button type="button" class="button-secondary em-archetype-checkbox-override" <?php if ( empty($atts['value']) ) echo 'disabled'; ?>><?php esc_html_e('Override Defaults', 'events-manager'); ?></button>
									</div>
								</div>
							<?php endforeach; ?>
						</div>
						<?php endif; ?>
						<p><em><?php echo sprintf( esc_html__('Select the view types a user can select to display on the default search form, you can override this selection using the %s argument in shortcodes and PHP functions.', 'events-manager'), '<code>views</code>'); ?></em></p>
					</td>
				</tr>
			</tbody>
			<tbody class="em-subsection em-search-form-main-option">
			<tr class="em-subheader"><td colspan="2"><h5><?php esc_html_e( 'Sorting', 'events-manager'); ?></h5></td></tr>
			<?php
				em_options_radio_binary ( __( 'Show sorting icon?', 'events-manager'), 'dbem_search_form_sorting', __('Show the sorting icon to change the ordering of search results.', 'events-manager') );
			?>
			</tbody>
		    <tbody class="em-subsection em-search-form-main-option">
				<tr class="em-subheader"><td colspan="2"><h5><?php esc_html_e( 'Search', 'events-manager'); ?></h5></td></tr>
				<?php
				em_options_radio_binary ( __( 'Show text search?', 'events-manager'), 'dbem_search_form_text', '', '', '#dbem_search_form_text_label_row, #dbem_search_form_text_hide_m_row, #dbem_search_form_text_hide_s_row' );
				em_options_input_text ( __( 'Label', 'events-manager'), 'dbem_search_form_text_label', __('Appears within the input box.','events-manager') );
				em_options_radio_binary ( sprintf(__( 'Hide on %s screen size?', 'events-manager'), __( 'small', 'events-manager')), 'dbem_search_form_text_hide_s', $hide_size_desc_small );
				em_options_radio_binary ( sprintf(__( 'Hide on %s screen size?', 'events-manager'), __( 'medium', 'events-manager')), 'dbem_search_form_text_hide_m', $hide_size_desc_medium);
				?>
			</tbody>
			<tbody class="em-subsection em-search-form-main-option em-settings-geocoding" id="em-search-form-geo">
				<tr class="em-subheader"><td colspan="2"><h5><?php esc_html_e( 'Geolocation Search', 'events-manager'); ?></h5></td></tr>
				<?php
				em_options_radio_binary ( __( 'Show geolocation search?', 'events-manager'), 'dbem_search_form_geo', '', '', '#dbem_search_form_geo_label_row, #dbem_search_form_geo_distance_default_row, #dbem_search_form_geo_unit_default_row, #dbem_search_form_geo_hide_m_row, #dbem_search_form_geo_hide_s_row' );
				em_options_input_text ( __( 'Label', 'events-manager'), 'dbem_search_form_geo_label', __('Appears within the input box.','events-manager') );
				em_options_input_text ( __( 'Default distance', 'events-manager'), 'dbem_search_form_geo_distance_default', __('Enter a number.','events-manager'), '');
				em_options_select ( __( 'Default distance unit', 'events-manager'), 'dbem_search_form_geo_unit_default', array('km'=>'km','mi'=>'mi'), '');
				em_options_radio_binary ( sprintf(__( 'Hide on %s screen size?', 'events-manager'), __( 'small', 'events-manager')), 'dbem_search_form_geo_hide_s', $hide_size_desc_small );
				em_options_radio_binary ( sprintf(__( 'Hide on %s screen size?', 'events-manager'), __( 'medium', 'events-manager')), 'dbem_search_form_geo_hide_m', $hide_size_desc_medium );
				?>
			</tbody>
			<tbody class="em-subsection em-search-form-main-option em-settings-dates" id="em-search-form-dates">
				<tr class="em-subheader"><td colspan="2"><h5><?php esc_html_e( 'Dates', 'events-manager'); ?></h5></td></tr>
				<?php
				em_options_radio_binary ( __( 'Show date range?', 'events-manager'), 'dbem_search_form_dates', '', '', '#dbem_search_form_dates_label_row, #dbem_search_form_dates_separator_row, #dbem_search_form_dates_format_row, #dbem_search_form_dates_hide_m_row, #dbem_search_form_dates_hide_s_row' );
				em_options_input_text ( __( 'Label', 'events-manager'), 'dbem_search_form_dates_label', __('Appears as the label for this search option.','events-manager') );
				em_options_input_text ( __( 'Date Separator', 'events-manager'), 'dbem_search_form_dates_separator', sprintf(__( 'For when start/end %s are present, this will separate the two (include spaces here if necessary).', 'events-manager'), __('dates','events-manager')) );
				em_options_input_text ( __( 'Date Picker Format', 'events-manager'), 'dbem_search_form_dates_format', __('Customize the format of the selected search dates, we recommend a brief format to keep things short.', 'events-manager'). ' '. sprintf(__( 'This uses a slightly different format to the others on here, for a list of characters to use, visit the <a href="%s">reference page</a>', 'events-manager'),'https://flatpickr.js.org/formatting/#date-formatting-tokens') );
				em_options_radio_binary ( sprintf(__( 'Hide on %s screen size?', 'events-manager'), __( 'small', 'events-manager')), 'dbem_search_form_dates_hide_s', $hide_size_desc_small );
				em_options_radio_binary ( sprintf(__( 'Hide on %s screen size?', 'events-manager'), __( 'medium', 'events-manager')), 'dbem_search_form_dates_hide_m', $hide_size_desc_medium );
				?>
			</tbody>
		</table>
		<table class="form-table">
		    <tr class="em-header"><td colspan="2"><h4><?php _e('Advanced Search Fields','events-manager'); ?></h4></td></tr>
			<?php
			em_options_radio_binary ( __( 'Enable advanced fields?', 'events-manager'), 'dbem_search_form_advanced', __('Enables additional advanced search fields such as dates, country, etc.','events-manager'), '', '.em-search-form-advanced' );
			?>
			<tbody class="em-search-form-advanced">
				<?php
				em_options_input_text ( __( 'Search button text', 'events-manager'), 'dbem_search_form_submit', __("If there's no fields to show in the main search section, this button will be used instead at the bottom of the advanced fields.",'events-manager'));
				em_options_select ( __( 'Advanced search style', 'events-manager'), 'dbem_search_form_advanced_style', array('accordion'=> __('Accordion', 'events-manager'),'headings'=> __('Headings', 'events-manager')), __('The advanced search can be styled in a section-based format, with expandable sections, or directly inline with static headings. If you want headings for some sections and not others, choose Headings and leave specific section heading labels blank in settings further down.','events-manager'), '');

				$triggers = array('inline' => '#dbem_search_form_advanced_hidden_row, #dbem_search_form_advanced_hide_row');
				em_options_select ( __( 'Advanced search mode', 'events-manager'), 'dbem_search_form_advanced_mode', array('inline'=> __('Inline', 'events-manager'),'modal'=> __('Modal', 'events-manager')), __('You can choose to show a popup modal or inline under the main search bar triggered by an icon on the main search bar.','events-manager'), '', $triggers);
				?>
			</tbody>
			<tbody class="em-search-form-advanced em-search-form-advanced-hidden">
				<?php
				em_options_radio_binary ( __( 'Hidden by default?', 'events-manager'), 'dbem_search_form_advanced_hidden', __('If set to yes, advanced search fields will be hidden by default and can be revealed by clicking the "Advanced Search" icon.','events-manager'), '', '#dbem_search_form_advanced_trigger_row', true );
				em_options_radio_binary ( __( 'Show hide/show trigger?', 'events-manager'), 'dbem_search_form_advanced_trigger', __('If set to yes, advanced search fields can toggled by clicking the "Advanced Search" icon.','events-manager'), '', '.em-search-form-advanced-trigger' );
				?>
			</tbody>
            <tbody class="em-search-form-advanced em-search-form-advanced-trigger em-search-form-advanced-hidden">
                <?php
                em_options_input_text ( __( 'Show label', 'events-manager'), 'dbem_search_form_advanced_show', __('The tip text that is shown for the advanced search trigger.','events-manager') );
                em_options_input_text ( __( 'Hide label', 'events-manager'), 'dbem_search_form_advanced_hide', __('The tip text that is shown for the advanced search trigger.','events-manager') );
                ?>
            </tbody>
			<tbody class="em-search-form-advanced em-subsection">
				<tr class="em-subheader"><td colspan="2"><h5><?php esc_html_e( 'Search', 'events-manager'); ?></h5></td></tr>
				<?php
				em_options_radio_binary ( __( 'Show text search?', 'events-manager'), 'dbem_search_form_text_advanced', '', '', '#dbem_search_form_text_label_advanced_row' );
				em_options_input_text ( __( 'Label', 'events-manager'), 'dbem_search_form_text_label_advanced', __('Appears within the input box.','events-manager') );
				?>
			</tbody>
			<tbody class="em-search-form-advanced em-subsection">
				<tr class="em-subheader"><td colspan="2"><h5><?php esc_html_e( 'Dates', 'events-manager'); ?></h5></td></tr>
				<?php
				em_options_radio_binary ( __( 'Show date range?', 'events-manager'), 'dbem_search_form_dates_advanced', '', '', '#dbem_search_form_dates_label_advanced_row, #dbem_search_form_dates_separator_advanced_row, #dbem_search_form_dates_format_advanced_row' );
				em_options_input_text ( __( 'Label', 'events-manager'), 'dbem_search_form_dates_label_advanced', __('Appears as the label for this search option.','events-manager') );
				em_options_input_text ( __( 'Date Separator', 'events-manager'), 'dbem_search_form_dates_separator_advanced', sprintf(__( 'For when start/end %s are present, this will separate the two (include spaces here if necessary).', 'events-manager'), __('dates','events-manager')) );
				em_options_input_text ( __( 'Date Picker Format', 'events-manager'), 'dbem_search_form_dates_format_advanced', __('Customize the format of the selected search dates, we recommend a brief format to keep things short.', 'events-manager'). ' '. sprintf(__( 'This uses a slightly different format to the others on here, for a list of characters to use, visit the <a href="%s">reference page</a>', 'events-manager'),'https://flatpickr.js.org/formatting/#date-formatting-tokens') );
				?>
			</tbody>
			<tbody class="em-search-form-advanced em-subsection">
				<tr class="em-subheader"><td colspan="2"><h5><?php esc_html_e( 'Category', 'events-manager'); ?></h5></td></tr>
				<?php
				em_options_radio_binary ( __( 'Show categories?', 'events-manager'), 'dbem_search_form_categories', '', '', '#dbem_search_form_category_label_row, #dbem_search_form_categories_label_row' );
				em_options_input_text ( __( 'Label', 'events-manager'), 'dbem_search_form_category_label', __('Appears as the label for this search option.','events-manager') );
				em_options_input_text ( __( 'Search Filter Label', 'events-manager'), 'dbem_search_form_categories_placeholder', __('Appears on the text search filter above the categories list.','events-manager') );
				em_options_input_text ( __( 'Categories dropdown label', 'events-manager'), 'dbem_search_form_categories_label', __('Appears as the first default search option.','events-manager') );
				em_options_input_text ( sprintf(__( 'Include %s', 'events-manager'), __('Categories', 'events-manager')), 'dbem_search_form_categories_include', sprintf(__('Include only these %1$s IDs, for multiple values separate by commas such as %2$s.','events-manager'), __('Category', 'events-manager'), '<code>123,124,125</code>') );
				em_options_input_text ( sprintf(__( 'Exclude %s', 'events-manager'), __('Categories', 'events-manager')), 'dbem_search_form_categories_exclude', sprintf(__('Include only these %1$s IDs, for multiple values separate by commas such as %2$s.','events-manager'), __('Category', 'events-manager'), '<code>123,124,125</code>').' '.esc_html__('If inclusion rules are entered above, this setting is ignored.', 'events-manager') );
				?>
			</tbody>
			<tbody class="em-search-form-advanced em-subsection">
				<tr class="em-subheader"><td colspan="2"><h5><?php esc_html_e( 'Tags', 'events-manager'); ?></h5></td></tr>
				<?php
				em_options_radio_binary ( __( 'Show tags?', 'events-manager'), 'dbem_search_form_tags', '', '', '#dbem_search_form_tag_label_row, #dbem_search_form_tags_label_row' );
				em_options_input_text ( __( 'Label', 'events-manager'), 'dbem_search_form_tag_label', __('Appears as the label for this search option.','events-manager') );
				em_options_input_text ( __( 'Search Filter Label', 'events-manager'), 'dbem_search_form_tags_placeholder', __('Appears on the text search filter above the tags list.','events-manager') );
				em_options_input_text ( __( 'Tags dropdown label', 'events-manager'), 'dbem_search_form_tags_label', __('Appears as the first default search option.','events-manager') );
				em_options_input_text ( sprintf(__( 'Include %s', 'events-manager'), __('Tags')), 'dbem_search_form_tags_include', sprintf(__('Include only these %1$s IDs, for multiple values separate by commas such as %2$s.','events-manager'), __('Tag', 'events-manager'), '<code>123,124,125</code>') );
				em_options_input_text ( sprintf(__( 'Exclude %s', 'events-manager'), __('Tags')), 'dbem_search_form_tags_exclude', sprintf(__('Include only these %1$s IDs, for multiple values separate by commas such as %2$s.','events-manager'), __('Tag', 'events-manager'), '<code>123,124,125</code>').' '.esc_html__('If inclusion rules are entered above, this setting is ignored.', 'events-manager') );
				?>
			</tbody>
			<tbody class="em-search-form-advanced em-subsection em-search-form-advanced-geo" id="em-search-form-geo-advanced">
				<tr class="em-subheader"><td colspan="2"><h5><?php esc_html_e( 'Geolocation Search', 'events-manager'); ?></h5></td></tr>
				<?php
				em_options_radio_binary ( __( 'Show geolocation search?', 'events-manager'), 'dbem_search_form_geo_advanced', __('Display a geolocation search textbox which syncs with the main search geolocation box (if enabled).', 'events-manager'), '', '#dbem_search_form_geo_label_advanced_row' );
				em_options_input_text ( __( 'Label', 'events-manager'), 'dbem_search_form_geo_label_advanced', __('Appears within the input box.','events-manager') );
				em_options_radio_binary ( __( 'Show distance options?', 'events-manager'), 'dbem_search_form_geo_units', '', '', '#dbem_search_form_geo_units_label_row, #dbem_search_form_geo_distance_options_row' );
				em_options_input_text ( __( 'Label', 'events-manager'), 'dbem_search_form_geo_units_label', __('Appears as the label for this search option.','events-manager') );
				em_options_input_text ( __( 'Distance Values', 'events-manager'), 'dbem_search_form_geo_distance_options', __('The numerical units shown to those searching by distance. Use comma-separated numbers, such as "25,50,100".','events-manager') );
				?>
			</tbody>
			<tbody class="em-search-form-advanced em-subsection">
				<tr class="em-subheader"><td colspan="2"><h5><?php esc_html_e( 'Country', 'events-manager'); ?></h5></td></tr>
				<?php
				em_options_radio_binary ( __( 'Show countries?', 'events-manager'), 'dbem_search_form_countries', '', '', '#dbem_search_form_default_country_row, #dbem_search_form_country_label_row, #dbem_search_form_countries_label_row' );
				em_options_select ( __( 'Default Country', 'events-manager'), 'dbem_search_form_default_country', em_get_countries(__('no default country', 'events-manager')), __('Search form will be pre-selected with this country.','events-manager') );
				em_options_input_text ( __( 'Label', 'events-manager'), 'dbem_search_form_country_label', __('Appears as the label for this search option.','events-manager') );
				em_options_input_text ( __( 'All countries text', 'events-manager'), 'dbem_search_form_countries_label', __('Appears as the first default search option.','events-manager') );
				?>
			</tbody>
			<tbody class="em-search-form-advanced em-subsection">
				<tr class="em-subheader"><td colspan="2"><h5><?php esc_html_e( 'Region', 'events-manager'); ?></h5></td></tr>
				<?php
				em_options_radio_binary ( __( 'Show regions?', 'events-manager'), 'dbem_search_form_regions', '', '', '#dbem_search_form_region_label_row, #dbem_search_form_regions_label_row' );
				em_options_input_text ( __( 'Label', 'events-manager'), 'dbem_search_form_region_label', __('Appears as the label for this search option.','events-manager') );
				em_options_input_text ( __( 'All regions text', 'events-manager'), 'dbem_search_form_regions_label', __('Appears as the first default search option.','events-manager') );
				?>
			</tbody>
			<tbody class="em-search-form-advanced em-subsection">
				<tr class="em-subheader"><td colspan="2"><h5><?php esc_html_e( 'State/County', 'events-manager'); ?></h5></td></tr>
				<?php
				em_options_radio_binary ( __( 'Show states?', 'events-manager'), 'dbem_search_form_states', '', '', '#dbem_search_form_state_label_row, #dbem_search_form_states_label_row' );
				em_options_input_text ( __( 'Label', 'events-manager'), 'dbem_search_form_state_label', __('Appears as the label for this search option.','events-manager') );
				em_options_input_text ( __( 'All states text', 'events-manager'), 'dbem_search_form_states_label', __('Appears as the first default search option.','events-manager') );
				?>
			</tbody>
			<tbody class="em-search-form-advanced em-subsection">
				<tr class="em-subheader"><td colspan="2"><h5><?php esc_html_e( 'City/Town', 'events-manager'); ?></h5></td></tr>
				<?php
				em_options_radio_binary ( __( 'Show towns/cities?', 'events-manager'), 'dbem_search_form_towns', '', '', '#dbem_search_form_town_label_row, #dbem_search_form_towns_label_row' );
				em_options_input_text ( __( 'Label', 'events-manager'), 'dbem_search_form_town_label', __('Appears as the label for this search option.','events-manager') );
				em_options_input_text ( __( 'All towns/cities text', 'events-manager'), 'dbem_search_form_towns_label', __('Appears as the first default search option.','events-manager') );
				?>
			</tbody>
			<?php echo $save_button; ?>
		</table>
	</div> <!-- . inside -->
	</div> <!-- .postbox -->

	<div  class="postbox " id="em-opt-date-time" >
	<div class="handlediv" title="<?php __('Click to toggle', 'events-manager'); ?>"><br /></div><h3><span><?php _e ( 'Date/Time', 'events-manager'); ?> </span></h3>
	<div class="inside">
		<p class="em-boxheader"><?php
			$date_time_format_tip = sprintf(__('Date and Time formats follow the <a href="%s">WordPress time formatting conventions</a>', 'events-manager'), 'http://codex.wordpress.org/Formatting_Date_and_Time');
			echo $date_time_format_tip; 
		?></p>
		<table class="form-table">
    		<?php
			em_options_input_text ( __( 'Date Format', 'events-manager'), 'dbem_date_format', sprintf(__('For use with the %s placeholder','events-manager'),'<code>#_EVENTDATES</code>') );
			em_options_input_text ( __( 'Date Picker Format', 'events-manager'), 'dbem_datepicker_format', __('Same as <em>Date Format</em>, but this is used for the datepickers used by Events Manager.', 'events-manager'). ' '. sprintf(__( 'This uses a slightly different format to the others on here, for a list of characters to use, visit the <a href="%s">reference page</a>', 'events-manager'),'https://flatpickr.js.org/formatting/#date-formatting-tokens') );
		    em_options_radio_binary ( __( 'Separate Range Inputs?', 'events-manager'), 'dbem_dates_range_double_inputs', __('When submitting events, you can choose to use a single date picker for start/end dates, or separate fields for each date.', 'events-manager') );
			// Legacy jQuery UI DatePicker setting, disabled to not confuse ppl
			//em_options_input_text ( __( 'Date Picker Format (legacy)', 'events-manager'), 'dbem_date_format_js', sprintf(__( 'Same as <em>Date Format</em>, but this is used for the datepickers used by Events Manager. This uses a slightly different format to the others on here, for a list of characters to use, visit the <a href="%s">jQuery formatDate reference</a>', 'events-manager'),'https://api.jqueryui.com/datepicker/#utility-formatDate') );
			em_options_input_text ( __( 'Date Separator', 'events-manager'), 'dbem_dates_separator', sprintf(__( 'For when start/end %s are present, this will separate the two (include spaces here if necessary).', 'events-manager'), __('dates','events-manager')) );
			em_options_input_text ( __( 'Time Format', 'events-manager'), 'dbem_time_format', sprintf(__('For use with the %s placeholder','events-manager'),'<code>#_EVENTTIMES</code>') );
			em_options_input_text ( __( 'Time Separator', 'events-manager'), 'dbem_times_separator', sprintf(__( 'For when start/end %s are present, this will separate the two (include spaces here if necessary).', 'events-manager'), __('times','events-manager')) );
			em_options_input_text ( __( 'All Day Message', 'events-manager'), 'dbem_event_all_day_message', sprintf(__( 'If an event lasts all day, this text will show if using the %s placeholder', 'events-manager'), '<code>#_EVENTTIMES</code>') );
			em_options_radio_binary ( __( 'Use 24h Format?', 'events-manager'), 'dbem_time_24h', __( 'When creating events, would you like your times to be shown in 24 hour format?', 'events-manager') );
			echo $save_button;
			?>
		</table>
	</div> <!-- . inside -->
	</div> <!-- .postbox -->
	      
   	<div  class="postbox " id="em-opt-calendar-formats" >
	<div class="handlediv" title="<?php __('Click to toggle', 'events-manager'); ?>"><br /></div><h3><span><?php _e ( 'Calendar', 'events-manager'); ?></span></h3>
	<div class="inside">
    	<table class="form-table">
    		<?php
		    em_options_select( __( 'Default calendar size', 'events-manager'), 'dbem_calendar_size', array('auto' => esc_html__('Responsive', 'events-manager'), 'large' => esc_html__('Large', 'events-manager'), 'medium' => esc_html__('Medium', 'events-manager'), 'small' => esc_html__('Small', 'events-manager')), sprintf(__( 'Unless speficied with the %s parameter, the calendar will by default remain the chosen size regardless of calendar width. Responsive calendar size will adjust from small to large according to the calendar width on screen.','events-manager'), '<code>calendar_size</code>') );
		    em_options_select( __( 'Default event style', 'events-manager'), 'dbem_calendar_event_style', array('pill' => esc_html__('Pills', 'events-manager'), 'dot' => esc_html__('Single dot', 'events-manager'), 'dots' => esc_html__('Multiple dots', 'events-manager'), 'ring' => esc_html__('Rings', 'events-manager')), sprintf(__( 'How events appear on each calendar day: a labelled pill per event, a single dot, one dot per event (up to the day limit), or a coloured ring around the date. Override per calendar with the %s parameter.', 'events-manager'), '<code>calendar_event_style</code>') );
		    em_options_radio_binary( __( 'Split by timeslots?', 'events-manager'), 'dbem_calendar_timeslots', sprintf(__( 'Unless overriden with the %s parameter in shortcode or PHP arguments, the calendar will by default split events by timeslot if on the same day or show one event for the day which includes the whole range of timeslots.','events-manager'), '<code>timeslots</code>') );
		    em_options_radio_binary ( __( 'Link directly to event on day with single event?', 'events-manager'), 'dbem_calendar_direct_links', __( "If a calendar day has only one event, you can force a direct link to the event (recommended to avoid duplicate content).",'events-manager') );
		    em_options_radio_binary ( __( 'Show list on day with single event?', 'events-manager'), 'dbem_display_calendar_day_single', __( "By default, if a calendar day only has one event, it display a single event when clicking on the link of that calendar date. If you select Yes here, you will get always see a list of events.",'events-manager') );
		    em_options_input_text ( __( 'Month format', 'events-manager'), 'dbem_full_calendar_month_format', __('The format of the month/year header of the calendar.','events-manager').' '.$date_time_format_tip);
		    em_options_input_text ( __( 'Event format', 'events-manager'), 'dbem_calendar_large_pill_format', __( 'The format of each event when displayed in the full calendar.', 'events-manager').$events_placeholder_tip .' <br>'.
			    sprintf(esc_html__('The setting above is new, due to our new calendar display options. Your previous format was %s', 'events-manager'), '<code>'. get_option('dbem_full_calendar_event_format') .'</code>' )
		    );
		    ?>
		    
		    <tr class="em-header"><td colspan="2"><h4><?php _e('Preview Formats','events-manager'); ?></h4></td></tr>
		    <?php
		    em_options_select( __( 'Event Preview Mode', 'events-manager'), 'dbem_calendar_preview_mode', array('tooltips' => esc_html__('Tooltip', 'events-manager'), 'modal' => esc_html__('Modal Popup', 'events-manager'), 'none' => esc_html__('No Preview', 'events-manager')), __( 'Choose how to show a information about an event when clicking or hovering over a single event on the calendar.','events-manager') );
		    em_options_select( __( 'Date Preview Mode', 'events-manager'), 'dbem_calendar_preview_mode_date', array('modal' => esc_html__('Modal Popup', 'events-manager'), 'none' => esc_html__('Direct Link', 'events-manager')), __( 'Choose whether to show a preview of the upcoming events for the date clicked on, or directly link to the calendar day.','events-manager') );
		    ?>

		    <!-- ADVANCED Formatting -->
		    <tbody class="am-af">
		    <?php
		    em_options_radio_binary ( __( 'Override Default Formats?', 'events-manager'), 'dbem_advanced_formatting_modes[calendar-previews]', '', '', '.am-af-calendar-previews' );
		    ?>
		    </tbody>
		    <tbody class="am-af am-af-calendar-previews">
		    <?php
		    em_options_textarea ( __( 'Event modal preview format', 'events-manager'), 'dbem_calendar_preview_modal_event_format', sprintf(esc_html__( 'Used to show a single event when preview mode is set to %s.', 'events-manager'), '<code>'.esc_html__('Modal Popup', 'events-manager').'</code>'), true );
		    em_options_textarea ( __( 'Event tooltip preview format', 'events-manager'), 'dbem_calendar_preview_tooltip_event_format', sprintf(esc_html__( 'Used to show a single event when preview mode is set to %s.', 'events-manager'), '<code>'.esc_html__('Tooltip', 'events-manager').'</code>'), true );
		    em_options_textarea ( __( 'Events date modal preview format', 'events-manager'), 'dbem_calendar_preview_modal_date_format', esc_html__( 'Used to format each event in a list when previewing a single date in a modal popup.', 'events-manager'), true );
    		?>
		    </tbody>
		    <!-- /ADVANCED Formatting -->
		    
    		<tr class="em-header"><td colspan="2"><h4><?php _e('Full-Size Calendar','events-manager'); ?></h4></td></tr>
		    <?php
		    $large_tip = sprintf(esc_html__('This setting will be applied if you choose to specifically show a size %s calendar.', 'events-manager'), esc_html__('large', 'events-manager'));
			$large_tip .= ' ' . esc_html__('This is also the default setting for responsive calendars without a fixed size.', 'events-manager');
		    em_options_radio_binary( __( 'Abbreviated weekdays?', 'events-manager'), 'dbem_full_calendar_abbreviated_weekdays', __( 'Use abbreviations, e.g. Friday = Fri. Useful for certain languages where abbreviations differ from full names.','events-manager') );
		    em_options_input_text ( __( 'Initial lengths', 'events-manager'), 'dbem_full_calendar_initials_length', __( 'Shorten the calendar headings containing the days of the week, use 0 for the full name.', 'events-manager').$events_placeholder_tip);
		    em_options_radio_binary( __( 'Show Long Events?', 'events-manager'), 'dbem_full_calendar_long_events', __( 'Events with multiple dates will appear on each of those dates in the calendar.','events-manager') );
		    ?>
    		<tr class="em-header"><td colspan="2"><h4><?php _e('Small Calendar','events-manager'); ?></h4></td></tr>
			<?php
			$small_tip = sprintf(esc_html__('This setting will be applied if you choose to specifically show a fixed-size %s calendar.', 'events-manager'), esc_html__('small', 'events-manager'));
		    em_options_radio_binary( __( 'Abbreviated weekdays', 'events-manager'), 'dbem_small_calendar_abbreviated_weekdays', __( 'The calendar headings uses abbreviated weekdays','events-manager') );
		    em_options_input_text ( __( 'Initial lengths', 'events-manager'), 'dbem_small_calendar_initials_length', __( 'Shorten the calendar headings containing the days of the week, use 0 for the full name.', 'events-manager').$events_placeholder_tip );
		    em_options_radio_binary( __( 'Show Long Events?', 'events-manager'), 'dbem_small_calendar_long_events', __( 'Events with multiple dates will appear on each of those dates in the calendar.','events-manager'). ' '. $small_tip );
		    ?>		
		    <tr class="em-header"><td colspan="2"><h4><?php echo __('Calendar Day Event List Settings','events-manager'); ?></h4></td></tr>			
			<tr valign="top" id='dbem_display_calendar_orderby_row'>
		   		<th scope="row"><?php _e('Default event list ordering','events-manager'); ?></th>
		   		<td>   
					<select name="dbem_display_calendar_orderby" >
						<?php 
							$orderby_options = apply_filters('dbem_display_calendar_orderby_ddm', array(
								'event_name,event_start_time' => __('Order by event name, then event start time','events-manager'),
								'event_start_time,event_name' => __('Order by event start time, then event name','events-manager')
							)); 
						?>
						<?php foreach($orderby_options as $key => $value) : ?>   
		 				<option value='<?php echo esc_attr($key) ?>' <?php echo ($key == get_option('dbem_display_calendar_orderby')) ? "selected='selected'" : ''; ?>>
		 					<?php echo esc_html($value) ?>
		 				</option>
						<?php endforeach; ?>
					</select> 
					<select name="dbem_display_calendar_order" >
						<?php 
						$ascending = __('Ascending','events-manager');
						$descending = __('Descending','events-manager');
						$order_options = apply_filters('dbem_display_calendar_order_ddm', array(
							'ASC' => __('All Ascending','events-manager'),
							'DESC,ASC' => "$descending, $ascending",
							'DESC,DESC' => "$descending, $descending",
							'DESC' => __('All Descending','events-manager')
						)); 
						?>
						<?php foreach( $order_options as $key => $value) : ?>   
		 				<option value='<?php echo esc_attr($key) ?>' <?php echo ($key == get_option('dbem_display_calendar_order')) ? "selected='selected'" : ''; ?>>
		 					<?php echo esc_html($value) ?>
		 				</option>
						<?php endforeach; ?>
					</select>
					<br/>
					<em><?php _e('When Events Manager displays lists of events the default behavior is ordering by start date in ascending order. To change this, modify the values above.','events-manager'); ?></em>
				</td>
		   	</tr>
		   	<?php
		   		em_options_input_text ( __( 'Calendar events/day limit', 'events-manager'), 'dbem_display_calendar_events_limit', __( 'Limits the number of events on each calendar day. Leave blank for no limit.', 'events-manager') );
		   		em_options_input_text ( __( 'More Events message', 'events-manager'), 'dbem_display_calendar_events_limit_msg', __( 'Text with link to calendar day page with all events for that day if there are more events than the limit above, leave blank for no link as the day number is also a link.', 'events-manager') );
		   	?>
		    <tr class="em-header"><td colspan="2"><h4><?php echo sprintf(__('iCal Feed Settings','events-manager'),__('Event','events-manager')); ?></h4></td></tr>
		    <?php 
			em_options_input_text ( __( 'iCal Title', 'events-manager'), 'dbem_ical_description_format', __( 'The title that will appear in the calendar.', 'events-manager').$events_placeholder_tip );
			em_options_input_text ( __( 'iCal Description', 'events-manager'), 'dbem_ical_real_description_format', __( 'The description of the event that will appear in the calendar.', 'events-manager').$events_placeholder_tip );
			em_options_input_text ( __( 'iCal Location', 'events-manager'), 'dbem_ical_location_format', __( 'The location information that will appear in the calendar.', 'events-manager').$events_placeholder_tip );
			em_options_select( __('iCal Scope','events-manager'), 'dbem_ical_scope', em_get_scopes(), __('Choose to show events within a specific time range.','events-manager'));
			em_options_input_text ( __( 'iCal Limit', 'events-manager'), 'dbem_ical_limit', __( 'Limits the number of future events shown (0 = unlimited).', 'events-manager') );						
		    echo $save_button;        
			?>
		</table>
	</div> <!-- . inside -->
	</div> <!-- .postbox -->
	
	<?php if( get_option('dbem_locations_enabled') ): ?>
	<div  class="postbox " id="em-opt-locations-formats" >
	<div class="handlediv" title="<?php __('Click to toggle', 'events-manager'); ?>"><br /></div><h3><span><?php _e ( 'Locations', 'events-manager'); ?> </span></h3>
	<div class="inside">
    	<table class="form-table">
		    <tr class="em-header"><td colspan="2"><h4><?php echo sprintf(__('%s Page','events-manager'),__('Locations','events-manager')); ?></h4></td></tr>
		    <?php
		    em_options_input_text ( sprintf(__( 'No %s message', 'events-manager'),__('Locations','events-manager')), 'dbem_no_locations_message', sprintf( __( 'The message displayed when no %s are available.', 'events-manager'), __('locations','events-manager')) );
		    ?>
		    
		    <!-- ADVANCED Formatting -->
		    <tbody class="am-af">
		        <tr class="em-subheader"><td colspan="2"><h5><?php echo esc_html( sprintf(_x('%1$s %2$s Formats', 'cpt type and view type', 'events-manager'), __('Location', 'events-manager'), __('List', 'events-manager')) ); ?></h5></td></tr>
			    <?php em_options_radio_binary ( __( 'Override Default Formats?', 'events-manager'), 'dbem_advanced_formatting_modes[locations-list]', '', '', '.am-af-locations-list' ); ?>
		    </tbody>
		    <tbody class="am-af am-af-locations-list">
			<?php
			em_options_textarea ( sprintf(__('%s list header format','events-manager'),__('Locations','events-manager')), 'dbem_location_list_item_format_header', sprintf(__( 'This content will appear just above your code for the %s list format below. Default is blank', 'events-manager'), __('locations','events-manager')), true );
		 	em_options_textarea ( sprintf(__('%s list item format','events-manager'),__('Locations','events-manager')), 'dbem_location_list_item_format', sprintf(__( 'The format of a single %s in a list.', 'events-manager'), __('locations','events-manager')).$locations_placeholder_tip, true );
			em_options_textarea ( sprintf(__('%s list footer format','events-manager'),__('Locations','events-manager')), 'dbem_location_list_item_format_footer', sprintf(__( 'This content will appear just below your code for the %s list format above. Default is blank', 'events-manager'), __('locations','events-manager')), true );
		 	?>
		    </tbody>
		    <!-- /ADVANCED Formatting -->

		    <tr class="em-subheader"><td colspan="2"><h5><?php echo esc_html( sprintf(_x('%1$s %2$s Formats', 'cpt type and view type', 'events-manager'), __('Location', 'events-manager'), __('Grid', 'events-manager')) ); ?></h5></td></tr>
		    <!-- ADVANCED Formatting -->
		    <tbody class="am-af">
		    <?php
		    em_options_radio_binary ( __( 'Override Default Formats?', 'events-manager'), 'dbem_advanced_formatting_modes[locations-grid]', '', '', '.am-af-locations-grid' );
		    ?>
		    </tbody>
		    <tbody class="am-af am-af-locations-grid">
		    <?php
		    em_options_textarea ( sprintf(_x( 'Default %1$s %2$s format header', 'events-manager', 'cpt type and view type'), __('Location', 'events-manager'), __('Grid', 'events-manager')), 'dbem_location_grid_item_format_header', sprintf(__( 'This content will appear just above your code for the %s list format below. Default is blank', 'events-manager'), __('Grid','events-manager')), true );
		    em_options_textarea ( sprintf(_x( 'Default %1$s %2$s format', 'events-manager', 'cpt type and view type'), __('Location', 'events-manager'), __('Grid', 'events-manager')), 'dbem_location_grid_item_format', sprintf(__( 'The format of a single %s in a list.', 'events-manager'), __('event','events-manager')).$locations_placeholder_tip, true );
		    em_options_textarea ( sprintf(_x( 'Default %1$s %2$s format footer', 'events-manager', 'cpt type and view type'), __('Location', 'events-manager'), __('Grid', 'events-manager')), 'dbem_location_grid_item_format_footer', sprintf(__( 'This content will appear just below your code for the %s list format above. Default is blank', 'events-manager'), __('Grid','events-manager')), true );
		    ?>
		    </tbody>
		    <!-- /ADVANCED Formatting -->
		    <?php
		    em_options_input_text( sprintf(_x( 'Default %1$s %2$s width', 'events-manager', 'cpt type and view type'), __('Location', 'events-manager'), __('Grid', 'events-manager')), 'dbem_location_grid_item_width', __( 'The default minimum width, in pixels, that each grid item can shrink to fit on one line.', 'events-manager') );
		    ?>
		    
		    <!-- ADVANCED Formatting -->
		    <tbody class="am-af">
			    <tr class="em-header">
				    <td colspan="2">
					    <h4><?php echo sprintf(__('Single %s Page','events-manager'),__('Location','events-manager')); ?></h4>
					    <em><?php echo sprintf(__('These formats can be used on %s pages or on other areas of your site displaying an %s.','events-manager'),__('location','events-manager'),__('location','events-manager'));?></em>
				    </td>
			    </tr>
			    <?php em_options_radio_binary ( __( 'Override Default Formats?', 'events-manager'), 'dbem_advanced_formatting_modes[location-single]', '', '', '.am-af-location-single' ); ?>
		    </tbody>
		    <tbody class="am-af am-af-location-single">
		    <?php
			if( EM_MS_GLOBAL && get_option('dbem_ms_global_location_links') ){
			  em_options_input_text (sprintf( __( 'Single %s title format', 'events-manager'),__('location','events-manager')), 'dbem_location_page_title_format', sprintf(__( 'The format of a single %s page title.', 'events-manager'),__('location','events-manager')).$locations_placeholder_tip );
			}
			em_options_textarea ( sprintf(__('Single %s page format', 'events-manager'),__('location','events-manager')), 'dbem_single_location_format', sprintf(__( 'The format of a single %s page.', 'events-manager'),__('location','events-manager')).$locations_placeholder_tip, true );
			?>
		    </tbody>
		    <!-- /ADVANCED Formatting -->
		    
		    <!-- ADVANCED Formatting -->
		    <tbody class="am-af">
			    <tr class="em-header">
				    <td colspan="2">
					    <h4><?php echo sprintf(__('%s Excerpts','events-manager'),__('Location','events-manager')); ?></h4>
					    <em><?php echo sprintf(__('These formats can be used when WordPress automatically displays %s excerpts on your site and %s is enabled in your %s settings tab.','events-manager'),__('location','events-manager'),'<strong>'.__( 'Override Excerpts with Formats?', 'events-manager').'</strong>','<a href="#formats" class="nav-tab-link" rel="#em-menu-pages">'.__('Pages','events-manager').'  &gt; '.sprintf(__('%s List/Archives','events-manager'),__('Location','events-manager')).'</a>');?></em>
				    </td>
			    </tr>
			    <?php em_options_radio_binary ( __( 'Override Default Formats?', 'events-manager'), 'dbem_advanced_formatting_modes[location-excerpt]', '', '', '.am-af-location-excerpt' ); ?>
		    </tbody>
		    <tbody class="am-af am-af-location-excerpt">
		    <?php
		 	em_options_textarea ( sprintf(__('%s excerpt', 'events-manager'),__('Location','events-manager')), 'dbem_location_excerpt_format', __( 'Used if an excerpt has been defined.', 'events-manager').$locations_placeholder_tip, true );
		 	em_options_textarea ( sprintf(__('%s excerpt fallback', 'events-manager'),__('Location','events-manager')), 'dbem_location_excerpt_alt_format', __( 'Used if an excerpt has not been defined.', 'events-manager').$locations_placeholder_tip, true );
			?>
		    </tbody>
		    <!-- /ADVANCED Formatting -->
		    
		    <tr class="em-header"><td colspan="2"><h4><?php echo sprintf(__('%s List Formats','events-manager'),__('Event','events-manager')); ?></h4></td></tr>
		    <?php
		    em_options_input_text ( sprintf(__( 'No %s message', 'events-manager'),__('events','events-manager')), 'dbem_location_no_events_message', sprintf(__( 'The message to be displayed in the list generated by %s when no events are available.', 'events-manager'), '<code>#_LOCATIONNEXTEVENTS</code>, <code>#_LOCATIONPASTEVENTS</code>, <code>#_LOCATIONALLEVENTS</code>') );
			?>
		    
		    <!-- ADVANCED Formatting -->
		    <tbody class="am-af">
			    <?php em_options_radio_binary ( __( 'Override Default Formats?', 'events-manager'), 'dbem_advanced_formatting_modes[location-event-lists]', '', '', '.am-af-location-event-lists' ); ?>
		    </tbody>
		    <tbody class="am-af am-af-location-event-lists">
		 	<?php
		 	em_options_input_text ( __( 'Default event list format header', 'events-manager'), 'dbem_location_event_list_item_header_format', __( 'This content will appear just above your code for the default event list format. Default is blank', 'events-manager') , '', true );
		 	em_options_textarea ( sprintf(__( 'Default %s list format', 'events-manager'),__('events','events-manager')), 'dbem_location_event_list_item_format', sprintf(__( 'The format of the events the list inserted in the location page through the %s element.', 'events-manager').$events_placeholder_tip, '<code>#_LOCATIONNEXTEVENTS</code>, <code>#_LOCATIONPASTEVENTS</code>, <code>#_LOCATIONALLEVENTS</code>') , true );
			em_options_input_text ( __( 'Default event list format footer', 'events-manager'), 'dbem_location_event_list_item_footer_format', __( 'This content will appear just below your code for the default event list format. Default is blank', 'events-manager') , '', true );
			?>
		    </tbody>
		    <!-- /ADVANCED Formatting -->
		    
		 	<tr class="em-header"><td colspan="2">
		 		<h4><?php echo sprintf(__('Single %s Format','events-manager'),__('Event','events-manager')); ?></h4>
		 		<p><?php echo sprintf(__('The settings below are used when using the %s placeholder','events-manager'), '<code>#_LOCATIONNEXTEVENT</code>'); ?></p>
		 	</td></tr>
		 	<?php
		 	em_options_input_text ( __( 'Next event format', 'events-manager'), 'dbem_location_event_single_format', sprintf(__( 'The format of the next upcoming event in this %s.', 'events-manager'),__('location','events-manager')).$events_placeholder_tip );
		 	em_options_input_text ( sprintf(__( 'No %s message', 'events-manager'),__('events','events-manager')), 'dbem_location_no_event_message', sprintf(__( 'The message to be displayed in the list generated by %s when no events are available.', 'events-manager'), '<code>#_LOCATIONNEXTEVENT</code>') );
			echo $save_button;
			?>
		</table>
	</div> <!-- . inside -->
	</div> <!-- .postbox -->
	<?php endif; ?>
	
	<?php if( get_option('dbem_categories_enabled') && !(EM_MS_GLOBAL && !is_main_site()) ): ?>
	<div  class="postbox " id="em-opt-categories-formats" >
	<div class="handlediv" title="<?php __('Click to toggle', 'events-manager'); ?>"><br /></div><h3><span><?php _e ( 'Event Categories', 'events-manager'); ?> </span></h3>
	<div class="inside">
    	<table class="form-table">
    		<?php
    		em_options_input_text(sprintf(esc_html__('Default %s color','events-manager'), esc_html__('category','events-manager')), 'dbem_category_default_color', sprintf(esc_html_x('Colors must be in a valid %s format, such as #FF00EE.', 'hex format', 'events-manager'), '<a href="http://en.wikipedia.org/wiki/Web_colors">hex</a>'));
    		?>
		    
		    <tr class="em-header"><td colspan="2"><h4><?php echo sprintf(__('%s Page','events-manager'),__('Categories','events-manager')); ?></h4></td></tr>
		    <?php
		    em_options_input_text ( sprintf(__( 'No %s message', 'events-manager'),__('Categories','events-manager')), 'dbem_no_categories_message', sprintf( __( 'The message displayed when no %s are available.', 'events-manager'), __('categories','events-manager')) );
		    ?>
		    
		    <!-- ADVANCED Formatting -->
		    <tbody class="am-af">
			    <?php em_options_radio_binary ( __( 'Override Default Formats?', 'events-manager'), 'dbem_advanced_formatting_modes[categories-list]', '', '', '.am-af-categories-list' ); ?>
		    </tbody>
		    <tbody class="am-af am-af-categories-list">
			<?php
			em_options_textarea ( sprintf(__('%s list header format','events-manager'),__('Categories','events-manager')), 'dbem_categories_list_item_format_header', sprintf(__( 'This content will appear just above your code for the %s list format below. Default is blank', 'events-manager'), __('categories','events-manager')), true );
		 	em_options_textarea ( sprintf(__('%s list item format','events-manager'),__('Categories','events-manager')), 'dbem_categories_list_item_format', sprintf(__( 'The format of a single %s in a list.', 'events-manager'), __('categories','events-manager')).$categories_placeholder_tip, true );
			em_options_textarea ( sprintf(__('%s list footer format','events-manager'),__('Categories','events-manager')), 'dbem_categories_list_item_format_footer', sprintf(__( 'This content will appear just below your code for the %s list format above. Default is blank', 'events-manager'), __('categories','events-manager')), true );
		 	?>
		    </tbody>
		    <!-- /ADVANCED Formatting -->
		    
		    <tr class="em-header"><td colspan="2"><h4><?php echo sprintf(__('Single %s Page','events-manager'),__('Category','events-manager')); ?></h4></td></tr>
		    <?php
		    em_options_input_text ( sprintf(__( 'Single %s title format', 'events-manager'),__('category','events-manager')), 'dbem_category_page_title_format', __( 'The format of a single category page title.', 'events-manager').$categories_placeholder_tip );
		    ?>

		    <!-- ADVANCED Formatting -->
		    <tbody class="am-af">
			    <?php em_options_radio_binary ( __( 'Override Default Formats?', 'events-manager'), 'dbem_advanced_formatting_modes[category-single]', '', '', '.am-af-category-single' ); ?>
		    </tbody>
		    <tbody class="am-af am-af-category-single">
		 	<?php
			em_options_textarea ( sprintf(__('Single %s page format', 'events-manager'),__('category','events-manager')), 'dbem_category_page_format', sprintf(__( 'The format of a single %s page.', 'events-manager'),__('category','events-manager')).$categories_placeholder_tip, true );
		 	?>
		    </tbody>
		    <!-- /ADVANCED Formatting -->


		    <tr class="em-header"><td colspan="2"><h4><?php echo sprintf(__('%s List Formats','events-manager'),__('Event','events-manager')); ?></h4></td></tr>
		    <?php
		    em_options_input_text ( sprintf(__( 'No %s message', 'events-manager'),__('events','events-manager')), 'dbem_category_no_events_message', sprintf(__( 'The message to be displayed in the list generated by %s when no events are available.', 'events-manager'), '<code>#_CATEGORYPASTEVENTS</code>, <code>#_CATEGORYNEXTEVENTS</code>, <code>#_CATEGORYALLEVENTS</code>') );
			?>
		    
		    <!-- ADVANCED Formatting -->
		    <tbody class="am-af">
			    <?php em_options_radio_binary ( __( 'Override Default Formats?', 'events-manager'), 'dbem_advanced_formatting_modes[category-events-list]', '', '', '.am-af-category-events-list' ); ?>
		    </tbody>
		    <tbody class="am-af am-af-category-events-list">
		 	<?php
		 	em_options_input_text ( __( 'Default event list format header', 'events-manager'), 'dbem_category_event_list_item_header_format', __( 'This content will appear just above your code for the default event list format. Default is blank', 'events-manager'), '', true );
		 	em_options_textarea ( sprintf(__( 'Default %s list format', 'events-manager'),__('events','events-manager')), 'dbem_category_event_list_item_format', sprintf(__( 'The format of the events the list inserted in the category page through the %s element.', 'events-manager').$events_placeholder_tip, '<code>#_CATEGORYPASTEVENTS</code>, <code>#_CATEGORYNEXTEVENTS</code>, <code>#_CATEGORYALLEVENTS</code>'), true );
			em_options_input_text ( __( 'Default event list format footer', 'events-manager'), 'dbem_category_event_list_item_footer_format', __( 'This content will appear just below your code for the default event list format. Default is blank', 'events-manager'), '', true );
			?>
		    </tbody>
		    <!-- /ADVANCED Formatting -->
		    
		 	<tr class="em-header"><td colspan="2">
		 		<h4><?php echo sprintf(__('Single %s Format','events-manager'),__('Event','events-manager')); ?></h4>
		 		<p><?php echo sprintf(__('The settings below are used when using the %s placeholder','events-manager'), '<code>#_CATEGORYNEXTEVENT</code>'); ?></p>
		 	</td></tr>
		 	<?php
		 	em_options_input_text ( __( 'Next event format', 'events-manager'), 'dbem_category_event_single_format', sprintf(__( 'The format of the next upcoming event in this %s.', 'events-manager'),__('category','events-manager')).$events_placeholder_tip );
		 	em_options_input_text ( sprintf(__( 'No %s message', 'events-manager'),__('events','events-manager')), 'dbem_category_no_event_message', sprintf(__( 'The message to be displayed in the list generated by %s when no events are available.', 'events-manager'), '<code>#_CATEGORYNEXTEVENT</code>') );
			echo $save_button;
			?>
		</table>
	</div> <!-- . inside -->
	</div> <!-- .postbox -->
	<?php endif; ?>
	
	<?php if( get_option('dbem_tags_enabled') ): ?>
	<div  class="postbox " id="em-opt-tags-formats" >
	<div class="handlediv" title="<?php __('Click to toggle', 'events-manager'); ?>"><br /></div><h3><span><?php _e ( 'Event Tags', 'events-manager'); ?> </span></h3>
	<div class="inside">
    	<table class="form-table">
    		<?php
    		em_options_input_text(sprintf(esc_html__('Default %s color','events-manager'), esc_html__('tag','events-manager')), 'dbem_tag_default_color', sprintf(esc_html_x('Colors must be in a valid %s format, such as #FF00EE.', 'hex format', 'events-manager'), '<a href="http://en.wikipedia.org/wiki/Web_colors">hex</a>'));
    		?>

		    <tr class="em-header"><td colspan="2"><h4><?php echo sprintf(__('%s Page','events-manager'),__('Tags','events-manager')); ?></h4></td></tr>
		    <?php
		    em_options_input_text ( sprintf(__( 'No %s message', 'events-manager'),__('Tags','events-manager')), 'dbem_no_tags_message', sprintf( __( 'The message displayed when no %s are available.', 'events-manager'), __('tags','events-manager')) );
		    ?>
		    
		    <!-- ADVANCED Formatting -->
		    <tbody class="am-af">
			    <?php em_options_radio_binary ( __( 'Override Default Formats?', 'events-manager'), 'dbem_advanced_formatting_modes[tags-list]', '', '', '.am-af-tags-list' ); ?>
		    </tbody>
		    <tbody class="am-af am-af-tags-list">
			<?php
			em_options_textarea ( sprintf(__('%s list header format','events-manager'),__('Tags','events-manager')), 'dbem_tags_list_item_format_header', sprintf(__( 'This content will appear just above your code for the %s list format below. Default is blank', 'events-manager'), __('tags','events-manager')), true );
		 	em_options_textarea ( sprintf(__('%s list item format','events-manager'),__('Tags','events-manager')), 'dbem_tags_list_item_format', sprintf(__( 'The format of a single %s in a list.', 'events-manager'), __('tags','events-manager')).$categories_placeholder_tip, true);
			em_options_textarea ( sprintf(__('%s list footer format','events-manager'),__('Tags','events-manager')), 'dbem_tags_list_item_format_footer', sprintf(__( 'This content will appear just below your code for the %s list format above. Default is blank', 'events-manager'), __('tags','events-manager')), true );
		 	?>
		    </tbody>
		    <!-- /ADVANCED Formatting -->
		    
		    <tr class="em-header"><td colspan="2"><h4><?php echo sprintf(__('Single %s Page','events-manager'),__('Tag','events-manager')); ?></h4></td></tr>
		    <?php em_options_input_text ( sprintf(__( 'Single %s title format', 'events-manager'),__('tag','events-manager')), 'dbem_tag_page_title_format', __( 'The format of a single tag page title.', 'events-manager').$categories_placeholder_tip ); ?>

		    <!-- ADVANCED Formatting -->
		    <tbody class="am-af">
			    <?php em_options_radio_binary ( __( 'Override Default Formats?', 'events-manager'), 'dbem_advanced_formatting_modes[tag-single]', '', '', '.am-af-tag-single' ); ?>
		    </tbody>
		    <tbody class="am-af am-af-tag-single">
		 	<?php
			em_options_textarea ( sprintf(__('Single %s page format', 'events-manager'),__('tag','events-manager')), 'dbem_tag_page_format', sprintf(__( 'The format of a single %s page.', 'events-manager'),__('tag','events-manager')).$categories_placeholder_tip, true );
		 	?>
		    </tbody>
		    <!-- /ADVANCED Formatting -->

		    <tr class="em-header"><td colspan="2"><h4><?php echo sprintf(__('%s List Formats','events-manager'),__('Event','events-manager')); ?></h4></td></tr>
		    <?php
		    em_options_input_text ( sprintf(__( 'No %s message', 'events-manager'),__('events','events-manager')), 'dbem_tag_no_events_message', __( 'The message to be displayed in the list generated by <code>#_TAGNEXTEVENTS</code>, <code>#_TAGNEXTEVENTS</code> and <code>#_TAGALLEVENTS</code> when no events are available.', 'events-manager') );
			?>
		    
		    <!-- ADVANCED Formatting -->
		    <tbody class="am-af">
			    
			    <?php em_options_radio_binary ( __( 'Override Default Formats?', 'events-manager'), 'dbem_advanced_formatting_modes[tag-events-list]', '', '', '.am-af-tag-events-list' ); ?>
		    </tbody>
		    <tbody class="am-af am-af-tag-events-list">
		 	<?php
			em_options_input_text ( __( 'Default event list format header', 'events-manager'), 'dbem_tag_event_list_item_header_format', __( 'This content will appear just above your code for the default event list format. Default is blank', 'events-manager'), '', true );
		 	em_options_textarea ( sprintf(__( 'Default %s list format', 'events-manager'),__('events','events-manager')), 'dbem_tag_event_list_item_format', __( 'The format of the events the list inserted in the tag page through the <code>#_TAGNEXTEVENTS</code>, <code>#_TAGNEXTEVENTS</code> and <code>#_TAGALLEVENTS</code> element.', 'events-manager').$categories_placeholder_tip, true );
			em_options_input_text ( __( 'Default event list format footer', 'events-manager'), 'dbem_tag_event_list_item_footer_format', __( 'This content will appear just below your code for the default event list format. Default is blank', 'events-manager'), '', true );
			?>
		    </tbody>
		    <!-- /ADVANCED Formatting -->
		    
		 	<tr class="em-header"><td colspan="2">
		 		<h4><?php echo sprintf(__('Single %s Format','events-manager'),__('Event','events-manager')); ?></h4>
		 		<p><?php echo sprintf(__('The settings below are used when using the %s placeholder','events-manager'), '<code>#_TAGNEXTEVENT</code>'); ?></p>
		 	</td></tr>
		 	<?php
		 	em_options_input_text ( __( 'Next event format', 'events-manager'), 'dbem_tag_event_single_format', sprintf(__( 'The format of the next upcoming event in this %s.', 'events-manager'),__('tag','events-manager')).$events_placeholder_tip );
		 	em_options_input_text ( sprintf(__( 'No %s message', 'events-manager'),__('events','events-manager')), 'dbem_tag_no_event_message', sprintf(__( 'The message to be displayed in the list generated by %s when no events are available.', 'events-manager'), '<code>#_CATEGORYNEXTEVENT</code>') );
			echo $save_button;
			?>
		</table>
	</div> <!-- . inside -->
	</div> <!-- .postbox -->
	<?php endif; ?>
	
	<div  class="postbox " id="em-opt-rss-formats" >
	<div class="handlediv" title="<?php __('Click to toggle', 'events-manager'); ?>"><br /></div><h3><span><?php _e ( 'RSS', 'events-manager'); ?> </span></h3>
	<div class="inside">
    	<table class="form-table">
			<?php				
			em_options_input_text ( __( 'RSS main title', 'events-manager'), 'dbem_rss_main_title', __( 'The main title of your RSS events feed.', 'events-manager').$events_placeholder_tip );
			em_options_input_text ( __( 'RSS main description', 'events-manager'), 'dbem_rss_main_description', __( 'The main description of your RSS events feed.', 'events-manager') );
			em_options_input_text ( __( 'RSS title format', 'events-manager'), 'dbem_rss_title_format', __( 'The format of the title of each item in the events RSS feed.', 'events-manager').$events_placeholder_tip );
			em_options_input_text ( __( 'RSS description format', 'events-manager'), 'dbem_rss_description_format', __( 'The format of the description of each item in the events RSS feed.', 'events-manager').$events_placeholder_tip );
			em_options_input_text ( __( 'RSS limit', 'events-manager'), 'dbem_rss_limit', __( 'Limits the number of future events shown (0 = unlimited).', 'events-manager') );
			em_options_select( __('RSS Scope','events-manager'), 'dbem_rss_scope', em_get_scopes(), __('Choose to show events within a specific time range.','events-manager'));
			?>							
			<tr valign="top" id='dbem_rss_orderby_row'>
		   		<th scope="row"><?php _e('Default event list ordering','events-manager'); ?></th>
		   		<td>   
					<select name="dbem_rss_orderby" >
						<?php 
							$orderby_options = apply_filters('em_settings_events_default_orderby_ddm', array(
								'event_start_date,event_start_time,event_name' => __('Order by start date, start time, then event name','events-manager'),
								'event_name,event_start_date,event_start_time' => __('Order by name, start date, then start time','events-manager'),
								'event_name,event_end_date,event_end_time' => __('Order by name, end date, then end time','events-manager'),
								'event_end_date,event_end_time,event_name' => __('Order by end date, end time, then event name','events-manager'),
							)); 
						?>
						<?php foreach($orderby_options as $key => $value) : ?>   
		 				<option value='<?php echo esc_attr($key) ?>' <?php echo ($key == get_option('dbem_rss_orderby')) ? "selected='selected'" : ''; ?>>
		 					<?php echo esc_html($value); ?>
		 				</option>
						<?php endforeach; ?>
					</select> 
					<select name="dbem_rss_order" >
						<?php 
						$ascending = __('Ascending','events-manager');
						$descending = __('Descending','events-manager');
						$order_options = apply_filters('em_settings_events_default_order_ddm', array(
							'ASC' => __('All Ascending','events-manager'),
							'DESC,ASC,ASC' => __("$descending, $ascending, $ascending",'events-manager'),
							'DESC,DESC,ASC' => __("$descending, $descending, $ascending",'events-manager'),
							'DESC' => __('All Descending','events-manager'),
							'ASC,DESC,ASC' => __("$ascending, $descending, $ascending",'events-manager'),
							'ASC,DESC,DESC' => __("$ascending, $descending, $descending",'events-manager'),
							'ASC,ASC,DESC' => __("$ascending, $ascending, $descending",'events-manager'),
							'DESC,ASC,DESC' => __("$descending, $ascending, $descending",'events-manager'),
						)); 
						?>
						<?php foreach( $order_options as $key => $value) : ?>   
		 				<option value='<?php echo esc_attr($key) ?>' <?php echo ($key == get_option('dbem_rss_order')) ? "selected='selected'" : ''; ?>>
		 					<?php echo esc_html($value); ?>
		 				</option>
						<?php endforeach; ?>
					</select>
					<br/>
					<em><?php _e('When Events Manager displays lists of events the default behavior is ordering by start date in ascending order. To change this, modify the values above.','events-manager'); ?></em>
				</td>
		   	</tr>
			<?php
			echo $save_button;
			?>
		</table>
	</div> <!-- . inside -->
	</div> <!-- .postbox -->
	
	<div  class="postbox " id="em-opt-maps-formats" >
	<div class="handlediv" title="<?php __('Click to toggle', 'events-manager'); ?>"><br /></div><h3><span><?php _e ( 'Maps', 'events-manager'); ?> </span></h3>
	<div class="inside">
		<p class="em-boxheader"><?php echo sprintf(__('You can use Google Maps to show where your events are located. For more information on using maps, <a href="%s">see our documentation</a>.','events-manager'),'https://wp-events-plugin.com/documentation/google-maps/'); ?>
		<table class='form-table'>
			<tr valign="top">
				<?php em_options_input_text(__('Default map width','events-manager'), 'dbem_map_default_width', sprintf(__('Can be in form of pixels or a percentage such as %s or %s.', 'events-manager'), '<code>100%</code>', '<code>100px</code>')); ?>
				<?php em_options_input_text(__('Default map height','events-manager'), 'dbem_map_default_height', sprintf(__('Can be in form of pixels or a percentage such as %s or %s.', 'events-manager'), '<code>100%</code>', '<code>100px</code>')); ?>
			</tr>
			
			<!-- ADVANCED Formatting -->
			<tbody class="am-af">
			<?php em_options_radio_binary ( __( 'Override Default Formats?', 'events-manager'), 'dbem_advanced_formatting_modes[maps]', '', '', '.am-af-maps' ); ?>
			</tbody>
			<tbody class="am-af am-af-maps">
				<tr class="em-header"><td colspan="2">
					<h4><?php _e('Global Map Format','events-manager'); ?></h4>
					<p><?php echo sprintf(__('If you use the %s <a href="%s">shortcode</a>, you can display a map of all your locations and events, the settings below will be used.','events-manager'), '<code>[locations_map]</code>','https://wp-events-plugin.com/documentation/shortcodes/'); ?></p>
				</td></tr>
				<?php
				em_options_textarea ( __( 'Location balloon format', 'events-manager'), 'dbem_map_text_format', __( 'The format of the text appearing in the balloon describing the location.', 'events-manager').' '.__( 'Event.', 'events-manager').$locations_placeholder_tip, true );
				?>
				<tr class="em-header"><td colspan="2">
					<h4><?php _e('Single Location/Event Map Format','events-manager'); ?></h4>
					<p><?php echo sprintf(_e('If you use the <code>#_LOCATIONMAP</code> <a href="%s">placeholder</a> when displaying individual event and location information, the settings below will be used.','events-manager'), '<code>[locations_map]</code>','https://wp-events-plugin.com/documentation/placeholders/'); ?></p>
				</td></tr>
				<?php
				em_options_textarea ( __( 'Location balloon format', 'events-manager'), 'dbem_location_baloon_format', __( 'The format of the text appearing in the balloon describing the location.', 'events-manager').$events_placeholder_tip, true );
				?>
			</tbody>
			<!-- /ADVANCED Formatting -->
			
			<?php
			echo $save_button;     
			?> 
		</table>
	</div> <!-- . inside -->
	</div> <!-- .postbox -->
	
	<?php do_action('em_options_page_footer_formats'); ?>
	
</div> <!-- .em-menu-formats -->