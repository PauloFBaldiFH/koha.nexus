<?php
global $EM_Location, $post;
$required = apply_filters('em_required_html','<i>*</i>');
?>
<div class="<?php em_template_classes('location-editor'); ?> em-location-where <?php if( em_get_option( 'dbem_gmap_is_active' ) ) echo 'has-map'; ?>">
	<?php if ( em_get_option( 'dbem_gmap_is_active' ) ): ?>
		<p class="em-location-data-maps-tip"><?php _e("If you're using the Google Maps, the more detail you provide, the more accurate Google can be at finding your location. If your address isn't being found, please <a href='http://maps.google.com'>try it on maps.google.com</a> by adding all the fields below separated by commas.",'events-manager')?></p>
	<?php endif; ?>
	<div id="em-location-data" class="em-location-data input">
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
	</div>
	<?php if ( em_get_option( 'dbem_gmap_is_active' ) ) em_locate_template('forms/map-container.php',true); ?>
	<div id="location_coordinates" style='display: none;'>
		<input id='location-latitude' name='location_latitude' type='text' value='<?php echo $EM_Location->location_latitude; ?>' size='15' />
		<input id='location-longitude' name='location_longitude' type='text' value='<?php echo $EM_Location->location_longitude; ?>' size='15' />
	</div>
</div>