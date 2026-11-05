<?php $args = !empty($args) ? $args:array(); /* @var $args array */ ?>
<!-- START Region Search -->
<div class="em-search-region em-search-field">
	<label class="screen-reader-text" for="em-search-region-<?php echo absint($args['id']); ?>">
		<?php echo esc_html($args['region_label']); ?>
	</label>
	<select name="region" class="em-search-region em-selectize" id="em-search-region-<?php echo absint($args['id']); ?>">
		<option value=''><?php echo esc_html(em_get_option('dbem_search_form_regions_label')); ?></option>
		<?php
		global $wpdb;
		$em_states = $cond = array();
		if( !empty($args['country']) ) $cond[] = $wpdb->prepare("AND location_country=%s", $args['country']);
		if( !empty($cond) || empty($args['search_countries']) ){ //get specific country regions or all regions if no country fields exists
			$em_states = $wpdb->get_results("SELECT DISTINCT location_region FROM ".EM_LOCATIONS_TABLE." WHERE location_region IS NOT NULL AND location_region != '' AND location_status=1 ".implode(' ', $cond)." ORDER BY location_region", ARRAY_N);
		}
		foreach($em_states as $region){
			?>
			 <option<?php echo (!empty($args['region']) && $args['region'] == $region[0]) ? ' selected="selected"':''; ?>><?php echo esc_html($region[0]); ?></option>
			<?php
		}
		?>
	</select>
</div>	
<!-- END Region Search -->