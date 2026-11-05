<?php
/*
 * By copying and modifying this in your theme (parent or child) folder within plugins/events-manager/templates/search/advanced.php, or alternatively (recommended) in plugin-templates/events-manager/templates/search/advanced.php, you can change the way the search form will look.
 * To ensure compatability, it is strongly recommended you maintain class, id and form name attributes, unless you know what you're doing.
 * You also have an $args array available to you with search options passed on by your EM settings or shortcode
 */
/* @var array $args */
?>
<section class="em-search-main em-search-advanced-main-sections">
	<?php
	// main three searches on top
	if( !empty($args['search_term_advanced']) ) em_locate_template('templates/search/search.php',true,array('args'=>$args));
	if( !empty($args['search_scope_advanced']) ) em_locate_template('templates/search/scope.php',true,array('args'=>$args));
	if( !empty($args['search_geo_advanced']) ) em_locate_template('templates/search/geo.php',true,array('args'=>$args));
	?>
</section>
<section class="em-search-advanced-sections input  em-search-advanced-style-<?php echo esc_attr($args['search_advanced_style']); ?>">
	<?php do_action('em_search_form_advanced_sections_header', $args); ?>
    <?php if ( !empty($args['search_countries']) || !empty($args['search_regions']) || !empty($args['search_states']) || !empty($args['search_towns']) || !empty($args['search_geo_units']) || !empty($args['search_eventful']) ) : ?>
	<section class="em-search-section-location em-search-advanced-section">
		<header>Location Options</header>
		<div class="em-search-section-content">
			<?php
			em_locate_template('templates/search/location.php', true, array('args'=>$args));
			if( !empty($args['search_geo_units']) ) em_locate_template('templates/search/geo-units.php',true, array('args'=>$args));
			if( !empty($args['search_eventful']) ) em_locate_template('templates/search/eventful-locations.php',true,array('args'=>$args));
			?>
		</div>
	</section>
    <?php endif; ?>
	<?php if( em_get_option('dbem_categories_enabled') && !empty($args['search_categories']) ): ?>
		<section class="em-search-section-categories em-search-advanced-section">
			<?php if( !empty($args['category_label']) ) : ?><header><?php echo esc_html($args['category_label']); ?></header><?php endif; ?>
			<div class="em-search-section-content">
				<?php em_locate_template('templates/search/categories.php',true,array('args'=>$args)); ?>
			</div>
		</section>
	<?php endif; ?>
	<?php if( em_get_option('dbem_tags_enabled') && !empty($args['search_tags']) ): ?>
		<section  class="em-search-section-tags em-search-advanced-section ">
			<?php if( !empty($args['tag_label']) ) : ?><header><?php echo esc_html($args['tag_label']); ?></header><?php endif; ?>
			<div class="em-search-section-content">
				<?php em_locate_template('templates/search/tags.php',true,array('args'=>$args)); ?>
			</div>
		</section>
	<?php endif; ?>
    <?php do_action('em_search_form_advanced_sections_footer', $args); ?>
</section>