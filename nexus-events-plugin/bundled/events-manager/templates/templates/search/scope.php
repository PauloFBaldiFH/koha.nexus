<?php
/* @var $args array */
$classes = array();
if( em_get_option('dbem_search_form_dates_hide_m') ) $classes[] = 'hide-medium';
if( em_get_option('dbem_search_form_dates_hide_s') ) $classes[] = 'hide-small';
?>
<!-- START Date Search -->
<div class="em-search-scope em-search-field em-datepicker em-datepicker-range input <?php echo implode(' ', $classes); ?>" data-separator="<?php echo esc_attr($args['scope_seperator']); ?>"  data-format="<?php echo esc_attr($args['scope_format']); ?>">
	<label for="em-search-scope-<?php echo absint($args['id']) ?>" class="screen-reader-text"><?php echo esc_html($args['scope_label']); ?></label>
	<input id="em-search-scope-<?php echo absint($args['id']) ?>" type="hidden" class="em-date-input em-search-scope" aria-hidden="true" placeholder="<?php echo esc_html($args['scope_label']); ?>">
	<div class="em-datepicker-data">
		<input type="date" name="scope[0]" value="<?php echo esc_attr($args['scope'][0]); ?>" aria-label="<?php echo esc_html($args['scope_label']); ?>">
		<span class="separator"><?php echo esc_html($args['scope_seperator']); ?></span>
		<input type="date" name="scope[1]" value="<?php echo esc_attr($args['scope'][1]); ?>" aria-label="<?php echo esc_html($args['scope_seperator']); ?>">
	</div>
</div>
<?php /* Example alternatives
<div class="em-search-scope em-search-field em-datepicker em-datepicker-until" data-separator="<?php echo esc_attr($args['scope_seperator']); ?>">
	<label for="em-search-scope-start-<?php echo absint($args['id']) ?>" class="screen-reader-text"><?php echo esc_html($args['scope_label']); ?></label>
	<input type="hidden" class="em-date-input em-date-input-start" id="em-search-scope-start-<?php echo absint($args['id']) ?>" aria-hidden="true">
    <input id="em-search-scope-<?php echo absint($args['id']) ?>" type="hidden" class="em-date-input em-search-scope" aria-hidden="true" placeholder="<?php echo esc_html($args['scope_label']); ?>">
    <label for="em-search-scope-end-<?php echo absint($args['id']) ?>"><?php echo esc_html($args['scope_seperator']); ?></label>
	<input type="hidden" class="em-date-input em-date-input-end" id="em-search-scope-end-<?php echo absint($args['id']) ?>" aria-hidden="true" placeholder="<?php echo esc_html($args['scope_seperator']); ?>">
	<div class="em-datepicker-data">
		<input type="date" name="scope[0]" value="<?php echo esc_attr($args['scope'][0]); ?>" aria-label="<?php echo esc_html($args['scope_label']); ?>">
		<span class="separator"><?php echo esc_html($args['scope_seperator']); ?></span>
		<input type="date" name="scope[1]" value="<?php echo esc_attr($args['scope'][1]); ?>" aria-label="<?php echo esc_html($args['scope_seperator']); ?>">
	</div>
</div>
<div class="em-search-scope em-search-field em-datepicker" data-separator="<?php echo esc_attr($args['scope_seperator']); ?>">
	<label>Date</label>
	<input type="hidden" class="em-date-input em-date-input-start" aria-hidden="true">
	<div class="em-datepicker-data">
		<input type="date" name="scope[0]" value="2022-05-10">
	</div>
</div>
*/ ?>
<!-- END Date Search -->