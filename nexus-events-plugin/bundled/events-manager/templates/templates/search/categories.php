<?php
	/* @var $args array */
	$include = !empty($args['categories_include']) ? $args['categories_include']:array();
	$exclude = !empty($args['categories_exclude']) ? $args['categories_exclude']:array();

?>
<!-- START Category Search -->
<div class="em-search-category em-search-field">
	<label for="em-search-category-<?php echo absint($args['id']) ?>" class="screen-reader-text"><?php echo esc_html($args['category_label']); ?></label>

	<select name="category[]" class="em-search-category em-selectize <?php echo $args['search_multiselect_style']; ?> checkboxes" id="em-search-category-<?php echo absint($args['id']) ?>" multiple
	        data-default="<?php echo esc_attr($args['categories_label']); ?>"
	        data-label="<?php echo esc_attr($args['category_label']); ?>"
            data-clear-text="<?php echo esc_attr($args['categories_clear_text']); ?>"
            data-selected-text="<?php echo esc_attr($args['categories_count_text']); ?>"
	        placeholder="<?php echo esc_attr($args['categories_placeholder']); ?>">
		<?php
		$args_em = apply_filters('em_advanced_search_categories_args', array('orderby'=>'name','hide_empty'=>0, 'include' => $include, 'exclude' => $exclude));
		$categories = EM_Categories::get($args_em);
		$selected = array();
		if( !empty($args['category']) ){
			if( !is_array($args['category']) ){
				$selected = explode(',', $args['category']);
			} else {
				$selected = $args['category'];
			}
		}
		$walker = new EM_Walker_CategoryMultiselect();
		$args_em = apply_filters('em_advanced_search_categories_walker_args', array(
		    'hide_empty' => 0,
		    'orderby' =>'name',
		    'name' => 'category',
		    'hierarchical' => true,
		    'taxonomy' => EM_TAXONOMY_CATEGORY,
		    'selected' => $selected,
		    'show_option_none' => $args['categories_label'],
		    'option_none_value'=> 0,
			'walker'=> $walker,
		));
		echo walk_category_dropdown_tree($categories, 0, $args_em);
		?>
	</select>
</div>
<!-- END Category Search -->