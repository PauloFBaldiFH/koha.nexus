<?php
	/* @var array $args */
	$id =  esc_attr( $args['id'] );
	if( empty($args['order']) || !in_array($args['order'], array('ASC', 'DESC')) ) {
		$args['order'] = em_get_option('dbem_events_default_order') === 'ASC' ? 'ASC' : 'DESC';
	}
?>
<div class="em-search-sort" aria-label="<?php esc_attr_e('Sorting Order', 'events-manager'); ?>">
	<div class="em-search-sort-trigger" id="em-search-sort-trigger-<?php echo $id; ?>">
		<button type="button" class="em-search-sort-option em-clickable em-search-sort-type-<?php echo esc_attr($args['order']); ?>" data-sort="<?php echo esc_attr($args['order']); ?>"><?php esc_attr_e('Sorting Order', 'events-manager'); ?></button>
		<input name="order" type="hidden" value="<?php echo esc_attr($args['order']); ?>">
	</div>
</div>