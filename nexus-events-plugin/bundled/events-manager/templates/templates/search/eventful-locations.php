<?php
/* This general search will find matches within event_name, event_notes, and the location_name, address, town, state and country. */
/* @var array $args */
?>
<!-- START General Search -->
<div class="em-search-eventful em-search-field input">
	<label for="em-search-eventful-<?php echo absint($args['id']); ?>" class="inline-left em-tooltip" aria-label="<?php echo esc_js($args['search_eventful_locations_tooltip']); ?>">
		<?php echo esc_html($args['search_eventful_locations_label']); ?>
	</label>
	<input type="checkbox" name="eventful" class="em-search-eventful" id="em-search-eventful-<?php echo absint($args['id']); ?>" value="1" <?php selected( !empty($args['eventful']) ); ?>>
</div>
<!-- END General Search -->