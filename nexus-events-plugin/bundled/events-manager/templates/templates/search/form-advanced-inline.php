<?php
/*
 * By copying and modifying this in your theme (parent or child) folder within plugins/events-manager/templates/search/advanced.php, or alternatively (recommended) in plugin-templates/events-manager/templates/search/advanced.php, you can change the way the search form will look.
 * To ensure compatability, it is strongly recommended you maintain class, id and form name attributes, unless you know what you're doing.
 * You also have an $args array available to you with search options passed on by your EM settings or shortcode
 */
/* @var array $args */
$id = esc_attr($args['id']);
?>
<div class="<?php em_template_classes('search-advanced', 'search-advanced-inline'); ?> <?php echo esc_attr(implode(' ', $args['css_classes_advanced'])); ?>" id="em-search-advanced-<?php echo $id; ?>" data-parent="em-search-form-<?php echo $id; ?>" data-view="<?php echo esc_attr($args['view']); ?>" <?php if( !empty($args['advanced_hidden']) ) echo 'style="display:none"'; ?>>
	<?php
	em_locate_template( 'templates/search/form-advanced.php', true, array('args' => $args) );
	do_action('em_template_events_search_form_footer'); // DEPRECATED - use other hooks hook in here to add extra fields, text etc.
	?>
	<?php do_action('em_search_form_advanced_footer_before', $args); // do not remove ?>
	<footer class="em-submit-section em-search-submit input">
		<?php do_action('em_search_form_advanced_footer_top', $args); // do not remove ?>
		<?php if( !$args['show_main'] ): ?>
			<?php em_locate_template('templates/search/form-views.php', true, array('args' => $args)); ?>
		<?php endif; ?>
		<div>
			<button type="reset" class="button-secondary"><?php esc_html_e('Clear All', 'events-manager'); ?></button>
		</div>
		<div>
			<button type="submit" class="em-search-submit button-primary"><?php echo esc_html($args['search_button']); ?></button>
		</div>
		<?php do_action('em_search_form_advanced_footer_bottom', $args); // do not remove ?>
	</footer>
	<?php do_action('em_search_form_advanced_footer_after', $args); // do not remove ?>
</div>