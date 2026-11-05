<?php
/* WARNING!!! (2013-07-10) We intend to add a few more fields into this search form over the coming weeks/months.
 * Overriding shouldn't hinder functionality at all but these new search options won't appear on your form!
 */
/*
 * By modifying this in your theme folder within plugins/events-manager/templates/events-search.php, you can change the way the search form will look.
 * To ensure compatability, it is recommended you maintain class, id and form name attributes, unless you now what you're doing.
 * You also have an $args array available to you with search options passed on by your EM settings or shortcode
 */
/* @var $args array */
if( empty($args['id']) ) $args['id'] = rand(100, getrandmax()); // prevent warnings
$id =  esc_attr($args['id']); // id of form for unique selections
$show_advanced = !empty($args['show_advanced']);
//em_template_classes('search', 'modal,search-advanced');
?>
<div class="<?php em_template_classes('search'); ?> <?php echo esc_attr(implode(' ', $args['css_classes'])); ?>" id="em-search-<?php echo $id; ?>" data-view="<?php echo esc_attr($args['view']); ?>">
	<form action="<?php echo !empty($args['search_url']) ? esc_url($args['search_url']) : EM_URI; ?>" method="post" class="em-search-form" id="em-search-form-<?php echo $id; ?>">
		<input type="hidden" name="action" value="<?php echo esc_attr($args['search_action']); ?>">
		<input type="hidden" name="view_id" value="<?php echo esc_attr($args['id']); ?>">
		<?php if( $args['show_main'] ): //show the 'main' search form ?>
			<?php em_locate_template('templates/search/form-main.php', true, array('args' => $args)); ?>
		<?php else: ?>
			<input type="hidden" name="view" value="<?php echo !empty($args['view']) ? esc_attr($args['view']) : esc_attr(em_get_option('dbem_search_form_view')); ?>">
		<?php endif; ?>
		<?php if( $show_advanced ): ?>
			<?php if( $args['advanced_mode'] == 'inline' ): //show inline if requested ?>
				<?php em_locate_template( 'templates/search/form-advanced-inline.php', true, array('args' => $args) ); ?>
			<?php else: // Search Form Pop-Up Shown as separate form ?>
				<?php em_locate_template( 'templates/search/form-advanced-modal.php', true, array('args' => $args) ); ?>
			<?php endif; ?>
		<?php endif; ?>
		<?php do_action('em_search_form_footer', $args); ?>
	</form>
</div>

<?php if( empty($args['has_view']) ): // if called by another shortcode e.g. events_list, then that shortcode should generate the search form and wrap itself in the below ?>
	<div class='<?php em_template_classes('view-container'); ?> <?php echo esc_attr(implode(' ', $args['css_classes'])); ?>' id="em-view-<?php echo $id; ?>" data-view="<?php echo esc_attr($args['view']); ?>"></div>
<?php endif; ?>
