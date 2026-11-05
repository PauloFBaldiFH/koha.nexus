<?php
/* @var array $args */
$id =  esc_attr( $args['id'] );
?>
<?php if( !empty($args['views']) && count($args['views']) > 1 ): //show the advanced search toggle if advanced fields are collapsed ?>
	<div class="em-search-views" aria-label="<?php esc_attr_e('View Types', 'events-manager'); ?>">
		<?php $search_views = em_get_search_views(); ?>
		<div class="em-search-views-trigger" data-template="em-search-views-options-<?php echo $id; ?>">
			<button type="button" class="em-search-view-option em-clickable em-search-view-type-<?php echo esc_attr($args['view']); ?>" data-view="<?php echo esc_attr($args['view']); ?>"><?php echo esc_html($search_views[$args['view']]['name']); ?></button>
		</div>
		<div class="em-search-views-options input" id="em-search-views-options-<?php echo $id; ?>">
			<fieldset class="em-search-views-options-list" id="em-search-views-options-select-<?php echo $id; ?>">
				<legend class="screen-reader-text"><?php esc_html_e('Search Results View Type','events-manager'); ?></legend>
				<?php foreach( $args['views'] as $view ): $view_name = $search_views[$view]['name']; ?>
					<label class="em-search-view-option em-search-view-type-<?php echo esc_attr($view); ?> <?php if( $view === $args['view'] ) echo 'checked'; ?>"  data-view="<?php echo esc_attr($view); ?>">
						<input type="radio" name="view" class="em-search-view-option em-search-view-type-<?php echo esc_attr($view); ?>" value="<?php echo esc_attr($view); ?>"  <?php if( $view === $args['view'] ) echo 'checked'; ?>>
						<?php echo esc_html($view_name); ?>
					</label>
				<?php endforeach; ?>
			</fieldset>
		</div>
	</div>
<?php else: ?>
	<input name="view" type="hidden" value="<?php echo esc_attr($args['view']); ?>">
<?php endif; ?>