<?php
global $EM_Event;
$required = apply_filters('em_required_html','<i>*</i>');

//determine location types (if neexed)
$location_types = array();
if( !em_get_option('dbem_require_location') ){
	$location_types[0] = array(
		'selected' =>  $EM_Event->location_id === '0' || $EM_Event->location_id === 0,
		'description' => esc_html__('No Location','events-manager'),
	);
}
if( EM_Locations::is_enabled() ){
	$location_types['location'] = array(
		'selected' =>  !empty($EM_Event->location_id),
		'display-class' => 'em-location-type-place',
		'description' => esc_html__('Physical Location','events-manager'),
	);
}
foreach( EM_Event_Locations\Event_Locations::get_types() as $event_location_type => $EM_Event_Location_Class ){ /* @var EM_Event_Locations\Event_Location $EM_Event_Location_Class */
	if( $EM_Event_Location_Class::is_enabled() ){
		$location_types[$EM_Event_Location_Class::$type] = array(
			'display-class' => 'em-event-location-type-'. $EM_Event_Location_Class::$type,
			'selected' => $EM_Event_Location_Class::$type == $EM_Event->event_location_type,
			'description' => $EM_Event_Location_Class::get_label(),
		);
	}
}
?>
<div class="input em-input-field em-input-field-select em-location-types <?php if( count($location_types) == 1 ) echo 'em-location-types-single'; ?>">
	<label><?php esc_html_e ( 'Location Type', 'events-manager')?></label>
	<select name="location_type" class="em-location-types-select" data-active="<?php echo esc_attr($EM_Event->event_location_type); ?>">
		<?php foreach( $location_types as $location_type => $location_type_option ): ?>
		<option value="<?php echo esc_attr($location_type); ?>" <?php if( !empty($location_type_option['selected']) ) echo 'selected="selected"'; ?> data-display-class="<?php if( !empty($location_type_option['display-class']) ) echo esc_attr($location_type_option['display-class']); ?>">
			<?php echo esc_html($location_type_option['description']); ?>
		</option>
		<?php endforeach; ?>
	</select>
	<?php if( $EM_Event->has_event_location() ): ?>
		<div class="em-location-type-delete-active-alert em-notice-warning">
			<div class="warning-bold">
				<p><em><?php esc_html_e('You are switching location type, if you update this event your event previous location data will be deleted.', 'events-manager'); ?></em></p>
			</div>
			<?php $EM_Event->get_event_location()->admin_delete_warning(); ?>
		</div>
	<?php endif; ?>
</div>
<?php if( EM_Locations::is_enabled() ): ?>
<div id="em-location-data" class="em-location-data em-location-where em-location-type em-location-type-place <?php if( count($location_types) == 1 ) echo 'em-location-type-single ';  em_template_classes('event-editor'); if( em_get_option( 'dbem_gmap_is_active' ) ) echo ' has-map'; ?>">
	<div id="location_coordinates" style='display: none;'>
		<input id='location-latitude' name='location_latitude' type='text' value='<?php echo esc_attr($EM_Event->get_location()->location_latitude); ?>' size='15' >
		<input id='location-longitude' name='location_longitude' type='text' value='<?php echo esc_attr($EM_Event->get_location()->location_longitude); ?>' size='15' >
	</div>
	<div class="em-location-data input">
		<?php if( em_get_option('dbem_use_select_for_locations') || !$EM_Event->can_manage('edit_locations','edit_others_locations') ) : ?>
			<div class="input em-location-data-select">
				<label for="location-select-id"><?php esc_html_e('Location','events-manager') ?> </label>
				<select name="location_id" id='location-select-id' class="em-selectize">
					<?php
					if ( count($location_types) == 1 && !em_get_option('dbem_require_location') ){ // we don't consider optional locations as a type for ddm
						?>
						<option value="0"><?php esc_html_e('No Location','events-manager'); ?></option>
						<?php
					}elseif( empty(em_get_option('dbem_default_location')) ){
						?>
						<option value="0"><?php esc_html_e('Select Location','events-manager'); ?></option>
						<?php
					}
					$ddm_args = array('private'=>$EM_Event->can_manage('read_private_locations'));
					$ddm_args['owner'] = (is_user_logged_in() && !current_user_can('read_others_locations')) ? get_current_user_id() : false;
					$locations = EM_Locations::get($ddm_args);
					$selected_location = !empty($EM_Event->location_id) || !empty($EM_Event->event_id) ? $EM_Event->location_id:em_get_option('dbem_default_location');
					foreach($locations as $EM_Location) {
						$selected = ($selected_location == $EM_Location->location_id) ? "selected='selected' " : '';
						if( $selected ) $found_location = true;
				        ?>
				        <option value="<?php echo esc_attr($EM_Location->location_id) ?>" title="<?php echo esc_attr("{$EM_Location->location_latitude},{$EM_Location->location_longitude}"); ?>" <?php echo $selected ?>><?php echo esc_html($EM_Location->location_name); ?></option>
				        <?php
					}
					if( empty($found_location) && !empty($EM_Event->location_id) ){
						$EM_Location = $EM_Event->get_location();
						if( $EM_Location->post_id ){
							?>
					        <option value="<?php echo esc_attr($EM_Location->location_id) ?>" title="<?php echo esc_attr("{$EM_Location->location_latitude},{$EM_Location->location_longitude}"); ?>" selected="selected"><?php echo esc_html($EM_Location->location_name); ?></option>
					        <?php
						}
					}
					?>
				</select>
			</div>
		<?php else : ?>
			<?php
			global $EM_Location;
			if( $EM_Event->location_id !== 0 ){
				$EM_Location = $EM_Event->get_location();
			}elseif(em_get_option('dbem_default_location') > 0){
				$EM_Location = em_get_location(em_get_option('dbem_default_location'));
			}else{
				$EM_Location = new EM_Location();
			}
			?>
			<div class="em-location-data-name">
				<label for="location-name"><?php _e ( 'Location Name', 'events-manager')?> <?php echo $required; ?></label>
				<input id='location-id' name='location_id' type='hidden' value='<?php echo esc_attr($EM_Location->location_id); ?>' size='15' >
				<input id="location-name" type="text" name="location_name" class="em-selectize-autocomplete em-selectize" value="<?php echo esc_attr($EM_Location->location_name); ?>" >
				<em id="em-location-search-tip"><?php esc_html_e( 'Create a location or start typing to search a previously created location.', 'events-manager')?></em>
				<em id="em-location-reset" style="display:none;"><?php esc_html_e('You cannot edit saved locations here.', 'events-manager'); ?> <a href="#"><?php esc_html_e('Reset this form to create a location or search again.', 'events-manager')?></a></em>
		    </div>
			<div class="input em-location-data-address">
				<label for="location-address"><?php _e ( 'Address', 'events-manager')?>&nbsp;<?php echo $required; ?></label>
				<input id="location-address" type="text" name="location_address" value="<?php echo esc_attr($EM_Location->location_address); ; ?>" >
			</div>
			<div class="input em-location-data-town">
				<label for="location-town"><?php _e ( 'City/Town', 'events-manager')?> <?php echo $required; ?></label>
				<input id="location-town" type="text" name="location_town" value="<?php echo esc_attr($EM_Location->location_town); ?>" >
			</div>
			<div class="input em-location-data-state">
				<label for="location-state"><?php _e ( 'State/County', 'events-manager')?></label>
				<input id="location-state" type="text" name="location_state" value="<?php echo esc_attr($EM_Location->location_state); ?>" >
			</div>
			<div class="input em-location-data-postcode">
				<label for="location-postcode"><?php _e ( 'Postcode', 'events-manager')?></label>
				<input id="location-postcode" type="text" name="location_postcode" value="<?php echo esc_attr($EM_Location->location_postcode); ?>" >
			</div>
			<div class="input em-location-data-region">
				<label for="location-region"><?php _e ( 'Region', 'events-manager')?></label>
				<input id="location-region" type="text" name="location_region" value="<?php echo esc_attr($EM_Location->location_region); ?>" >
			</div>
			<div class="input em-location-data-country">
				<label for="location-country"><?php _e ( 'Country', 'events-manager')?> <?php echo $required; ?></label>
				<select id="location-country" name="location_country" class="em-selectize">
					<option value="0" <?php echo ( $EM_Location->location_country == '' && $EM_Location->location_id == '' && em_get_option('dbem_location_default_country') == '' ) ? 'selected="selected"':''; ?>><?php _e('none selected','events-manager'); ?></option>
					<?php foreach(em_get_countries() as $country_key => $country_name): ?>
					<option value="<?php echo esc_attr($country_key); ?>" <?php echo ( $EM_Location->location_country == $country_key || ($EM_Location->location_country == '' && $EM_Location->location_id == '' && em_get_option('dbem_location_default_country')==$country_key) ) ? 'selected="selected"':''; ?>><?php echo esc_html($country_name); ?></option>
					<?php endforeach; ?>
				</select>
			</div>
			<div class="input em-location-data-url">
				<label for="location-url"><?php esc_html_e( 'URL', 'events-manager')?></label>
				<input id="location-url" type="text" name="location_url" value="<?php echo esc_attr($EM_Location->location_url); ?>" >
			</div>
		<?php endif; ?>
	</div>
	<?php if ( em_get_option( 'dbem_gmap_is_active' ) ):?>
		<?php em_locate_template('forms/map-container.php',true); ?>
	<?php endif; ?>
</div>
<?php endif; ?>
<div class="em-event-location-data">
	<?php foreach( EM_Event_Locations\Event_Locations::get_types() as $event_location_type => $EM_Event_Location_Class ): /* @var EM_Event_Locations\Event_Location $EM_Event_Location_Class */ ?>
		<?php if( $EM_Event_Location_Class::is_enabled() ): ?>
			<div class="em-location-type em-event-location-type-<?php echo esc_attr($event_location_type); ?>  <?php if( count($location_types) == 1 ) echo 'em-location-type-single'; ?> input">
			<?php $EM_Event_Location_Class::load_admin_template(); ?>
			</div>
		<?php endif; ?>
	<?php endforeach; ?>
</div>