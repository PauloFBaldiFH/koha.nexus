<?php $args = !empty($args) ? $args:array(); /* @var $args array */ ?>
<!-- START Geo Units Search -->
<div class="em-search-geo-units em-search-field" <?php if( empty($args['geo']) || empty($args['near']) ): ?>style="display:none;"<?php endif; /* show location fields if no geo search is made */ ?>>
	<label for="em-search-geo-unit-<?php echo absint($args['id']); ?>">
		<?php echo esc_html($args['geo_units_label']); ?>
	</label>
	<select name="near_distance" class="em-search-geo-distance">
	    <?php foreach( $args['geo_distance_values'] as $unit ) : ?>
		<option value="<?php echo esc_attr($unit); ?>" <?php if($args['near_distance'] == $unit) echo 'selected="selected"' ?>><?php echo esc_html($unit); ?></option>
		<?php endforeach; ?>
	</select><label class="screen-reader-text" for="em-search-geo-unit-<?php echo absint($args['id']); ?>"><?php echo esc_html(__('distance units','events-manager')); ?></label><select name="near_unit" class="em-search-geo-unit" id="em-search-geo-unit-<?php echo absint($args['id']); ?>">
		<option value="mi"><?php esc_html_e('Miles', 'events-manager'); ?></option>
		<option value="km" <?php if($args['near_unit'] == 'km') echo 'selected="selected"' ?>><?php esc_html_e('Kilometers', 'events-manager'); ?></option>
	</select>
</div>
<!-- END Geo Units Search -->