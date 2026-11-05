<?php
use EM\Archetypes, EM\Archetypes_Admin;
/*

Project: Events Manager – Archetypes UI

This UI manages a new "Archetypes" feature for dynamically creating custom post types (CPTs) for event categorization.

Data Model (per archetype):
  - label (Plural name, e.g. "Workshops")
  - label_single (Singular name, e.g. "Workshop")
  - slug (Permalink, e.g. "workshop")
  - cpt (CPT name, singular)
  - cpts (CPT name, plural)
  - taxonomies[tags] (bool)
  - taxonomies[categories] (bool)
  - repeating enabled (bool - if get_option('dbem_repeating_enabled') is true)

Behavior:
  - Fist section is a fixed form with main archetype, which can have custom name, CPT, slug and taxonomy selection (if other archetypes exist)
  - Custmom archetypes are additionally shown or can be added via the editor UI
  - Custom archetypes are stored in hidden input `event_archetypes` as JSON array
  - Pseudo-form: no input `name` attributes; JS handles validation and serialization
  - Archetypes shown in text view with "Edit" button → reveals form with Save/Cancel
  - Custom archetypes taken from EM\Archetypes::$types

Special Rules:
  - Already created archetypes
    - `cpt` and `cpts` are readonly by default, editable only after confirmation (with `data-nonce`)
    - Can be deleted with confirmation (uses `data-nonce`)
  - Newly created archetypes without saving
    - do not need confirmation to delete
    - if cancelled before 'saving' (not to be confused with submitting the settings page form itself) are removed

Additional Notes:
  - Uses <template> to define new archetype block for JS
  - Pressing Enter on inputs does NOT submit the form

 */
$admin_icon_desc = sprintf( __( 'Icon to appear in dashboard admin menu for this Archetype. Accepts URLs to PNG/SVG images, %s or leave blank for default.', 'events-manager' ), '<a href="https://developer.wordpress.org/resource/dashicons/" target="_blank">'. __('dashicon classes', 'events-manager') . '</a>' );
?>
<div class="postbox" id="em-opt-archetypes">
	<div class="handlediv" title="<?php __('Click to toggle', 'events-manager'); ?>"><br /></div><h3><span class="dashicons dashicons-networking" style="color:#777; margin-right:5px;"></span> <?php _e('Events Types (Archetypes)', 'events-manager'); ?></h3>
	<div class="inside">
		<div class="em-boxheader">
			<p><?php esc_html_e('You can create more than one "type" of event, which can have its own admin section, URL structure, calendar and formatting. For example, you may have events, appointments, and workshops all running under the Events Manager engine!', 'events-manager'); ?></p>
		</div>
		<?php if ( is_multisite() && is_network_admin() ) : ?>
		<table class="form-table">
			<tr class="em-header">
				<td colspan="2">
					<h4><?php _e('Multisite Settings', 'events-manager'); ?></h4>
					<p><?php esc_html_e('Control how subsites use Archetypes. Define network-wide types here and decide whether subsites can create, choose, or must use your list. You can also allow/deny renaming specific base settings.', 'events-manager'); ?></p>
				</td>
			</tr>
			<?php em_options_radio_binary ( __( 'Enable custom event archetypes?', 'events-manager'), 'dbem_ms_archetypes_enabled', __('Users will be able to create additional custom event post types on their own sub-sites.','events-manager'), '', '#event-archetypes-container' ); ?>
			<tbody class="em-archetypes-settings">
				<?php em_options_select( __('Subsite Archetype Mode', 'events-manager'), 'dbem_ms_archetypes_mode', [ 'custom' => __('Allow subsites to create their own', 'events-manager'), 'choose' => __('Subsites choose from network list', 'events-manager'), 'network' => __('Force network-defined list (no subsite choice)', 'events-manager') ] ); ?>
				<?php em_options_radio_binary( sprintf( __( 'Rename %s?', 'events-manager' ), __( 'Labels', 'events-manager' ) ), 'dbem_archetypes_rename_labels', sprintf( __( 'Site admins will be allowed to rename the base event and location %s on their individual sites.', 'events-manager' ), __( 'labels', 'events-manager' ) ) ); ?>
				<?php em_options_radio_binary( sprintf( __( 'Rename %s?', 'events-manager' ), __( 'Slugs', 'events-manager' ) ), 'dbem_archetypes_rename_slugs', sprintf( __( 'Site admins will be allowed to rename the base event and location %s on their individual sites.', 'events-manager' ), __( 'slugs', 'events-manager' ) ) ); ?>
			</tbody>
			<tbody class="em-archetypes-settings em-ms-local-options">
				<?php em_options_radio_binary( sprintf( __( 'Rename %s?', 'events-manager' ), __( 'CPTs', 'events-manager' ) ), 'dbem_archetypes_rename_cpts', sprintf( __( 'Site admins will be allowed to rename the base event and location %s on their individual sites.', 'events-manager' ), __( 'CPTs', 'events-manager' ) ) ); ?>
			</tbody>
		</table>
		<?php endif; ?>
		<table class="form-table em-archetypes-settings" id="event-archetypes-container">

			<?php if ( Archetypes_Admin::can_rename_cpts() || Archetypes_Admin::can_rename_labels() || Archetypes_Admin::can_rename_slugs() ) : ?>
			<tbody class="base-event-form" data-group="archetypes-base-event">
				<tr class="em-header">
					<td colspan="2">
						<?php
						// Get the main event archetype
						$main_event = Archetypes::$event;
						// Create a hidden input to store the JSON data
						?>
						<input type="hidden" name="event_archetypes" id="event-archetypes-input" value="">
						<!-- Base Event Form (Hard-coded) -->
						<h4><?php _e('Base Event Settings', 'events-manager'); ?></h4>
						<p><?php esc_html_e('Configure the base settings for your events. These settings affect how events are stored and accessed in the database.', 'events-manager'); ?></p>
					</td>
				</tr>
				<?php
				// Get label values from main event archetype
				$label_value = Archetypes::$event['label'] ?? __('Events', 'events-manager');
				$label_single_value = Archetypes::$event['label_single'] ?? __('Event', 'events-manager');
				$taxonomies = get_option('dbem_cp_event_taxonomies');

				// Label fields (only shown when more than one archetype exists)
				if ( Archetypes_Admin::can_rename_labels() ) {
					em_options_input_text( sprintf( __( 'Label', 'events-manager' ) . ' (%s)', __( 'Plural', 'events-manager' ) ), 'dbem_cp_events_label', esc_html( sprintf(__('This will be used in admin menus and other areas identifying the type of %s you are working with.', 'events-manager'), __('event', 'events-manager')) ), __('Events', 'events-manager'));
					em_options_input_text( sprintf( __( 'Label', 'events-manager' ) . ' (%s)', __( 'Single', 'events-manager' ) ), 'dbem_cp_events_label_single', esc_html( sprintf(__('Similar to label but used in instances when referring to one single %s type.', 'events-manager'), __('event', 'events-manager')) ), __('Event', 'events-manager') );
				}
				// Regular input for events slug
				if ( Archetypes_Admin::can_rename_slugs() ) {
					em_options_input_text( __('Permalink Slug', 'events-manager'), 'dbem_cp_events_slug',
							sprintf(__('e.g. %s - you can use / Separators too', 'events-manager'), '<strong>'.home_url().'/<code>'.esc_html( get_option('dbem_cp_events_slug', EM_POST_TYPE_EVENT_SLUG)).'</code>/2012-olympics/</strong>'),
							EM_POST_TYPE_EVENT_SLUG
					);
				}
				?>

				<!-- CPT name (Single) with special handling -->
				<?php if ( Archetypes_Admin::can_rename_cpts() ): ?>
				<tr valign="top" id="em_cp_events_cpt_row">
					<th><?php _e( 'CPT', 'events-manager' ); ?> (<?php _e( 'Single', 'events-manager' ); ?>)</th>
					<td>
						<input type="text" id="em_cp_events_cpt" value="<?php echo esc_attr( get_option('em_cp_events_cpt', 'event') ); ?>" disabled data-name="em_cp_events_cpt" size="45">
						<input type="hidden" id="em_cp_events_cpt_nonce" data-name="em_cp_events_cpt_nonce" value="<?php echo wp_create_nonce('edit_em_cp_events_cpt'); ?>">
						<span class="dashicons dashicons-edit edit-base-cpt" title="<?php esc_attr_e('Edit', 'events-manager'); ?>"></span>
						<br>
						<em><?php echo esc_html( sprintf(__('The unique name (singular) used to identify %s in the database. Use lowercase alphanumeric characters, dashes and underscores only.', 'events-manager'), __('events', 'events-manager')) ); ?></em>
					</td>
				</tr>
				<?php endif; ?>

				<!-- CPT name (Plural) with special handling -->
				<?php if ( Archetypes_Admin::can_rename_cpts() ): ?>
				<tr valign="top" id="em_cp_events_cpts_row">
					<th><?php _e( 'CPT', 'events-manager' ); ?> (<?php _e( 'Plural', 'events-manager' ); ?>)</th>
					<td>
						<input type="text" id="em_cp_events_cpts" value="<?php echo esc_attr( get_option('em_cp_events_cpts', 'events') ); ?>" disabled data-name="em_cp_events_cpts" size="45">
						<input type="hidden" id="em_cp_events_cpts_nonce" data-name="em_cp_events_cpts_nonce" value="<?php echo wp_create_nonce('edit_em_cp_events_cpts'); ?>">
						<span class="dashicons dashicons-edit edit-base-cpt" title="<?php esc_attr_e('Edit', 'events-manager'); ?>"></span>
						<br>
						<em><?php esc_html_e('Plural version of the Custom Post Type (CPT) name, used internally.', 'events-manager'); ?></em>
					</td>
				</tr>
				<?php endif; ?>

				<?php em_options_input_text( __( 'Admin Icon', 'events-manager' ), 'dbem_cp_events_menu_icon', $admin_icon_desc ); ?>
			</tbody>
			<?php endif; ?>
						
			<?php if ( is_multisite() && !is_network_admin() && Archetypes::get_ms_mode() === 'choose' ) : ?>
			<tbody class="archetypes-select-ui em-subsection">
				<tr class="em-header">
					<td colspan="2">
						<h4><?php _e('Available Archetypes', 'events-manager'); ?></h4>
						<p><?php esc_html_e('Select which archetypes this site will use and choose a default type.', 'events-manager'); ?></p>
					</td>
				</tr>
				<tr>
					<td colspan="2">
						<?php 
							$available = (array) get_site_option('em_ms_event_archetypes', []);
							$selected = (array) get_option('em_archetypes_selected', []);
							$default = get_option('em_archetype_default', '');
							$list = array_merge( [ Archetypes::$event['cpt'] => [ 'label' => Archetypes::$event['label'] ?: __('Events', 'events-manager') ] ], $available );
						?>
						<table id="em-archetypes-select">
							<thead>
								<tr>
									<th><?php esc_html_e('Archetype', 'events-manager'); ?></th>
									<th><?php esc_html_e('Default', 'events-manager'); ?></th>
								</tr>
							</thead>
							<tbody>
							<?php foreach ( Archetypes::get_cpts([], ['event', 'types']) as $cpt ) :
								$checked = in_array( $cpt, $selected, true );
								$label = Archetypes::get( $cpt )['label'];
							?>
							<tr>
								<td>
									<input type="checkbox" name="em_archetypes_selected[]" value="<?php echo esc_attr($cpt); ?>" <?php checked( $checked ); ?>>
									<?php echo esc_html($label); ?> <code><?php echo esc_html($cpt); ?></code></td>
								<td><input type="radio" name="em_archetype_default" value="<?php echo esc_attr($cpt); ?>" <?php checked( $default === $cpt ); ?> ></td>
							</tr>
							<?php endforeach; ?>
							</tbody>
						</table>
					</td>
				</tr>
			</tbody>
			<?php elseif ( !is_multisite() || is_network_admin() || Archetypes::get_ms_mode() === 'custom' ) : ?>
			<tbody class="archetypes-ui-container em-subsection">
				<tr class="em-header">
					<td colspan="2">
						<h4><?php _e('Archetypes UI Builder', 'events-manager'); ?></h4>
						<p><?php esc_html_e('Use the UI builder below to create and manage additional event types (archetypes).', 'events-manager'); ?></p>
					</td>
				</tr>
				<tr class="archetypes-list-row">
					<td colspan="2">
						<div id="archetypes-list">
							<?php
								$custom_types = Archetypes::$types;
								$custom_types[] = 'template';

								// Create JS variables for use in the editor
								global $wp_post_types;
 							$js_vars = [
			                            'i18n' => [
											'warning_cpt_change' => esc_js(__('Warning: Changing the CPT name can have wider implications and may affect any other plugins that specifically work with this custom post type name. Are you sure you want to continue?', 'events-manager')),
											'confirm_delete' => esc_js(__('Are you sure you want to delete this archetype? This action cannot be undone.', 'events-manager')),
			                                'error_slug_format' => esc_js(__('Permalink slug must contain only lowercase letters, numbers, hyphens and forward slashes.', 'events-manager')),
											'error_cpt_format' => esc_js(__('CPT name must contain only lowercase letters, numbers, and underscores.', 'events-manager')),
											'error_cpts_format' => esc_js(__('CPT name (plural) must contain only lowercase letters, numbers, and underscores.', 'events-manager')),
											'error_required_fields' => esc_js(__('Please fill in all required fields correctly.', 'events-manager')),
											'error_cpt_exists' => esc_js(__('This CPT name is already used by an existing WordPress post type. Please choose another name.', 'events-manager')),
							                'error_icon_format' => esc_js(__('Please provide a dashicons class, url to a png/svg file, or leave blank for default menu icon.', 'events-manager')),
											'yes' => __('Yes', 'events-manager'),
											'no' => __('No', 'events-manager'),
										],
										'post_types' => array_keys($wp_post_types),
										'repeating_enabled' => get_option('dbem_repeating_enabled'),
										'permissions' => [
											'rename_labels' => Archetypes_Admin::can_rename_labels(),
											'rename_slugs' => Archetypes_Admin::can_rename_slugs(),
											'rename_cpts'  => Archetypes_Admin::can_rename_cpts(),
										],
										'ms_mode' => is_multisite() ? get_site_option('dbem_ms_archetypes_mode', 'custom') : 'custom'
									];

								// Add JS variables to be accessed via EM.archetypesEditor
								EM_Scripts_and_Styles::add_js_var('archetypesEditor', $js_vars);
							?>

							<!-- Custom archetypes -->
							<?php foreach ($custom_types as $key => $type): ?>
								<?php
									$is_template = ($type === 'template');
									$display_style = $is_template ? 'style="display:none;"' : '';
									$edit_style = $is_template ? '' : 'style="display:none;"';

									// Set default values for template
									if ( $is_template ) {
										$archetype = [
											'label' => '',
											'label_single' => '',
											'slug' => '',
											'cpt' => '',
											'cpts' => '',
											'taxonomies' => ['event-tags', 'event-categories'],
											'menu_icon' => '',
										];
									} else {
										$archetype = $type;
									}

									// CPT fields (readonly for existing archetypes)
									$readonly = $is_template ? '' : ' disabled';
									$edit_icon = $is_template ? '' : ' <span class="dashicons dashicons-edit edit-cpt" title="' . esc_attr__('Edit', 'events-manager') . '"></span>';

									// Add nonce for main event CPT fields
									$cpt_nonce = $archetype['cpt'] ? ' data-nonce="' . wp_create_nonce('edit_cpt_' . $archetype['cpt']) . '"' : '';
									$cpts_nonce = $archetype['cpt'] ? ' data-nonce="' . wp_create_nonce('edit_cpts_' . $archetype['cpt']) . '"' : '';
								?>
	                            <?php if ( $is_template ) : ?><template id="archetype-template"><?php endif; ?>
	                            <div class="archetype-item" data-key="<?php echo esc_attr( $is_template ? 'new' : $key ); ?>" data-cpt="<?php echo esc_attr($archetype['cpt']); ?>" data-delete-nonce="<?php echo wp_create_nonce('delete_archetype_' . $archetype['cpt']); ?>">
	                                <h4>
	                                    <?php echo esc_html($archetype['label']); ?>
	                                    <?php if ($is_template): ?>
	                                        <?php _e('New Archetype', 'events-manager'); ?> <span><?php _e('(New)', 'events-manager'); ?></span>
	                                    <?php endif; ?>
	                                </h4>

									<table class="form-table">
		                                <tbody class="archetype-display" <?php echo $display_style; ?>>
		                                    <tr>
			                                    <th class="archetype-label-title"><?php _e( 'Name', 'events-manager' ); ?>
				                                    <em>(<?php _e( 'Plural', 'events-manager' ); ?>)</em>:
			                                    </th>
			                                    <td class="archetype-display-label"><?php echo esc_html($archetype['label']); ?></td>
		                                    </tr>
		                                    <tr>
			                                    <th class="archetype-label-single-title"><?php _e( 'Name', 'events-manager' ); ?>
				                                    <em>(<?php _e( 'Single', 'events-manager' ); ?>)</em>:
			                                    </th>
			                                    <td class="archetype-display-label-single"><?php echo esc_html($archetype['label_single']); ?></td>
		                                    </tr>
		                                    <tr>
		                                        <th class="archetype-slug-title"><?php _e('Permalink Slug', 'events-manager'); ?>:</th>
		                                        <td class="archetype-display-slug"><?php echo esc_html($archetype['slug']); ?></td>
		                                    </tr>
		                                    <tr>
			                                    <th class="archetype-cpt-title"><?php _e( 'CPT', 'events-manager' ); ?> (<?php _e( 'Single', 'events-manager' ); ?>)</th>
			                                    <td class="archetype-display-cpt"><?php echo esc_html($archetype['cpt']); ?></td>
		                                    </tr>
		                                    <tr>
			                                    <th class="archetype-cpts-title" scope="row"><?php _e( 'CPT', 'events-manager' ); ?> (<?php _e( 'Plural', 'events-manager' ); ?>)</th>
			                                    <td class="archetype-display-cpts"><?php echo esc_html($archetype['cpts']); ?></td>
		                                    </tr>
		                                    <tr>
			                                    <th class="archetype-icon-title" scope="row"><?php _e( 'Admin Icon', 'events-manager' ); ?></th>
			                                    <td class="archetype-display-icon" placeholder="<?php echo esc_html__('Default', 'events-manager'); ?>"><?php echo esc_html( $archetype['menu_icon'] ?? esc_html__('Default', 'events-manager') ); ?></td>
		                                    </tr>
											<tr class="archetype-buttons">
												<th colspan="2">
													<button type="button" class="button edit-archetype"><?php _e('Edit', 'events-manager'); ?></button>
													<button type="button" class="button delete-archetype"><?php _e('Delete', 'events-manager'); ?></button>
												</th>
											</tr>
										</tbody>

										<tbody class="archetype-edit" <?php echo $edit_style; ?>>
			                                <tr>
				                                <th><?php _e( 'Label', 'events-manager' ); ?> <em>(<?php _e( 'Plural', 'events-manager' ); ?>)</em></th>
				                                <td>
			                                        <input type="text" class="archetype-label archetype-display-label" data-name="label" value="<?php echo esc_attr($archetype['label']); ?>" placeholder="<?php _e( 'Events', 'events-manager' ); ?>">
			                                        <p><em><?php echo esc_html( sprintf(__('This will be used in admin menus and other areas identifying the type of %s you are working with.', 'events-manager'), __('event', 'events-manager')) ); ?></em></p>
			                                    </td>
			                                </tr>
			                                <tr>
				                                <th><?php _e( 'Label', 'events-manager' ); ?>  <em>(<?php _e( 'Single', 'events-manager' ); ?>)</em></th>
				                                <td>
			                                        <input type="text" class="archetype-label-single archetype-display-label-single" data-name="label_single" value="<?php echo esc_attr($archetype['label_single']); ?>" placeholder="<?php _e( 'Events', 'events-manager' ); ?>">
			                                        <p><em><?php echo esc_html( sprintf(__('Similar to label but used in instances when referring to one single %s type.', 'events-manager'), __('event', 'events-manager')) ); ?></em></p>
			                                    </td>
			                                </tr>
			                                <tr>
			                                    <th><?php _e('Permalink Slug', 'events-manager'); ?>:</th>
			                                    <td>
			                                        <input type="text" class="archetype-slug archetype-display-slug" data-name="slug" value="<?php echo esc_attr($archetype['slug']); ?>" placeholder="events/slug">
			                                        <p><em><?php echo sprintf(__('e.g. %s - you can use / Separators too', 'events-manager'), '<strong>'.home_url().'/<code>'.esc_html( $archetype['slug'] ?: 'events/slug' ).'</code>/2012-olympics/</strong>'); ?></em></p>
			                                    </td>
			                                </tr>
			                                <tr>
											    <th><?php _e('CPT (Single)', 'events-manager'); ?></th>
			                                    <td>
			                                        <input type="text" class="archetype-cpt archetype-display-cpt" data-name="cpt" value="<?php echo esc_attr($archetype['cpt']); ?>"<?php echo $readonly . $cpt_nonce; ?> placeholder="event"><?php echo $edit_icon; ?>
			                                        <p>
			                                            <em>

														    <em><?php echo esc_html( sprintf(__('The unique name (singular) used to identify %s in the database. Use lowercase alphanumeric characters, dashes and underscores only.', 'events-manager'), __('events', 'events-manager')) ); ?></em>
			                                            </em>
			                                        </p>
			                                    </td>
			                                </tr>
			                                <tr>
											    <th><?php _e('CPT (Plural)', 'events-manager'); ?></th>
			                                    <td>
			                                        <input type="text" class="archetype-cpts archetype-display-cpts" data-name="cpts" value="<?php echo esc_attr($archetype['cpts']); ?>"<?php echo $readonly . $cpts_nonce; ?> placeholder="events"><?php echo $edit_icon; ?>
			                                        <p><em><?php esc_html_e('Plural version of the Type Key, used internally. For example, workshop would be workshops.', 'events-manager'); ?></em></p>
			                                    </td>
			                                </tr>
			                                <tr>
				                                <th><?php _e('Admin Icon', 'events-manager'); ?>:</th>
				                                <td>
					                                <input type="text" class="archetype-icon archetype-display-icon" data-name="menu_icon" value="<?php echo esc_attr($archetype['menu_icon'] ?? ''); ?>" placeholder="dashicons-em-calendar">
					                                <p><em><?php echo $admin_icon_desc; ?></em></p>
				                                </td>
			                                </tr>
											<tr class="archetype-actions">
												<td colspan="2">
													<button type="button" class="button button-primary save-archetype"><?php _e('Save', 'events-manager'); ?></button>
													<button type="button" class="button cancel-edit"><?php _e('Cancel', 'events-manager'); ?></button>
												</td>
											</tr>
										</tbody>
									</table>
								</div>
								<?php if ( $is_template ) : ?></template><?php endif; ?>
							<?php endforeach; ?>
						</div>
					</td>
				</tr>

				<tr class="add-new-archetype">
					<td colspan="2">
						<button type="button" class="button" id="add-new-archetype"><?php _e('Add New Archetype', 'events-manager'); ?></button>
					</td>
				</tr>
			</tbody>
			<?php endif; ?>

			<!-- Base Location Settings (mirrors Base Event Settings but for Locations; no taxonomy/repeating checkboxes) -->
			<?php if ( Archetypes_Admin::can_rename_cpts() || Archetypes_Admin::can_rename_labels() || Archetypes_Admin::can_rename_slugs() ) : ?>
			<tbody class="base-location-form">
				<tr class="em-header">
					<td colspan="2">
						<h4><?php _e('Base Location Settings', 'events-manager'); ?></h4>
						<p><?php esc_html_e('Configure the base settings for your locations. These settings affect how locations are stored and accessed in the database.', 'events-manager'); ?></p>
					</td>
				</tr>
				<?php
				// Label fields (only shown when labels can be renamed)
				if ( Archetypes_Admin::can_rename_labels() ) {
					em_options_input_text( sprintf( __( 'Label', 'events-manager' ) . ' (%s)', __( 'Plural', 'events-manager' ) ), 'dbem_cp_locations_label', esc_html( sprintf(__('This will be used in admin menus and other areas identifying the type of %s you are working with.', 'events-manager'), __('location', 'events-manager')) ), __('Locations', 'events-manager') );
					em_options_input_text( sprintf( __( 'Label', 'events-manager' ) . ' (%s)', __( 'Single', 'events-manager' ) ), 'dbem_cp_locations_label_single', esc_html( sprintf(__('Similar to label but used in instances when referring to one single %s type.', 'events-manager'), __('location', 'events-manager')) ), __('Location', 'events-manager') );
				}
				// Regular input for locations slug
				if ( Archetypes_Admin::can_rename_slugs() ) {
					em_options_input_text( __('Permalink Slug', 'events-manager'), 'dbem_cp_locations_slug',
						sprintf(__('e.g. %s - you can use / Separators too', 'events-manager'), '<strong>'.home_url().'/<code>'.esc_html( get_option('dbem_cp_locations_slug', 'locations')).'</code>/my-venue/</strong>'),
						'locations'
					);
				}
				?>

				<!-- CPT name (Single) with special handling for Locations -->
				<?php if ( Archetypes_Admin::can_rename_cpts() ): ?>
				<tr valign="top" id="em_cp_locations_cpt_row">
					<th scope="row"><?php _e( 'CPT', 'events-manager' ); ?>
						<em>(<?php _e( 'Single', 'events-manager' ); ?>)</em></th>
					<td>
						<input type="text" id="em_cp_locations_cpt" value="<?php echo esc_attr( get_option('em_cp_locations_cpt', 'location') ); ?>"
							disabled data-name="em_cp_locations_cpt" size="45">
						<input type="hidden" id="em_cp_locations_cpt_nonce" data-name="em_cp_locations_cpt_nonce" value="<?php echo wp_create_nonce('edit_em_cp_locations_cpt'); ?>">
						<span class="dashicons dashicons-edit edit-base-cpt" title="<?php esc_attr_e('Edit', 'events-manager'); ?>"></span>
						<br>
						<em><?php echo esc_html( sprintf(__('The unique name (singular) used to identify %s in the database. Use lowercase alphanumeric characters, dashes and underscores only.', 'events-manager'), __('locations', 'events-manager')) ); ?></em>
					</td>
				</tr>
				<?php endif; ?>

				<!-- CPT name (Plural) with special handling for Locations -->
				<?php if ( Archetypes_Admin::can_rename_cpts() ): ?>
				<tr valign="top" id="em_cp_locations_cpts_row">
					<th scope="row"><?php _e('CPT (Plural)', 'events-manager'); ?></th>
					<td>
						<input type="text" id="em_cp_locations_cpts" value="<?php echo esc_attr( get_option('em_cp_locations_cpts', 'locations') ); ?>" disabled data-name="em_cp_locations_cpts" size="45">
						<input type="hidden" id="em_cp_locations_cpts_nonce" data-name="em_cp_locations_cpts_nonce" value="<?php echo wp_create_nonce('edit_em_cp_locations_cpts'); ?>">
						<span class="dashicons dashicons-edit edit-base-cpt" title="<?php esc_attr_e('Edit', 'events-manager'); ?>"></span>
						<br>
						<em><?php esc_html_e('Plural version of the Custom Post Type name, used internally.', 'events-manager'); ?></em>
					</td>
				</tr>
				<?php endif; ?>

			</tbody>
			<?php endif; ?>

			<?php global $save_button; echo $save_button; ?>
		</table>
	</div>
</div>