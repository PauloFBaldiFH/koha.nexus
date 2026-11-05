<?php
$label = !empty($args['advanced_hidden']) ? $args['search_text_show'] : $args['search_text_hide'];
$id = esc_attr($args['id']);
?>
<div class="em-search-advanced-trigger">
	<button type="button" class="em-search-advanced-trigger em-clickable em-tooltip" id="em-search-advanced-trigger-<?php echo $id; ?>" data-search-advanced-id="em-search-advanced-<?php echo $id; ?>"
	        aria-label="<?php echo esc_attr($label); ?>"
	        data-label-show="<?php echo esc_attr($args['search_text_show']); ?>"
	        data-label-hide="<?php echo esc_attr($args['search_text_hide']); ?>">
	</button>
</div>