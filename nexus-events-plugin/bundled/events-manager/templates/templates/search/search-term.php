<?php
/* This general search will find matches within event_name, event_notes, and the location_name, address, town, state and country. */
/* @var array $args */
$classes = array();
if( em_get_option('dbem_search_form_text_hide_m') ) $classes[] = 'hide-medium';
if( em_get_option('dbem_search_form_text_hide_s') ) $classes[] = 'hide-small';
?>
<!-- START General Search -->
<div class="em-search-text em-search-field input <?php echo implode(' ', $classes); ?>">
	<label for="em-search-text-<?php echo absint($args['id']); ?>" class="screen-reader-text">
		<?php echo esc_html($args['search_term_label']); ?>
	</label>
	<input type="text" name="em_search" class="em-search-text" id="em-search-text-<?php echo absint($args['id']); ?>"  placeholder="<?php echo esc_attr($args['search_term_label']); ?>" value="<?php echo esc_attr($args['search']); ?>">
</div>
<!-- END General Search -->