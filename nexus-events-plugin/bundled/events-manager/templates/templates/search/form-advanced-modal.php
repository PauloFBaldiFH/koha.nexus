<?php
/*
 * By copying and modifying this in your theme (parent or child) folder within plugins/events-manager/templates/search/advanced.php, or alternatively (recommended) in plugin-templates/events-manager/templates/search/advanced.php, you can change the way the search form will look.
 * To ensure compatability, it is strongly recommended you maintain class, id and form name attributes, unless you know what you're doing.
 * You also have an $args array available to you with search options passed on by your EM settings or shortcode
 */
/* @var array $args */
$id = esc_attr($args['id']);
?>
<div class="em-modal <?php em_template_classes('search', 'search-advanced'); ?> <?php echo esc_attr(implode(' ', $args['css_classes_advanced'])); ?>" id="em-search-advanced-<?php echo $id; ?>" data-parent="em-search-form-<?php echo $id; ?>" data-view="<?php echo esc_attr($args['view']); ?>">
	<div class="em-modal-popup">
		<header>
			<a class="em-close-modal" href="#"></a><!-- close modal -->
			<div class="em-modal-title">
				<?php echo esc_html($args['search_text_show']); ?>
			</div>
		</header>
		<div class="em-modal-content em-search-sections input">
			<?php em_locate_template( 'templates/search/form-advanced.php', true, array('args' => $args) ); ?>
		</div><!-- content -->
		<?php do_action('em_search_form_advanced_footer_before', $args); // do not remove ?>
		<footer class="em-submit-section em-search-submit input">
			<?php do_action('em_search_form_advanced_footer_top', $args); // do not remove ?>
			<div>
				<button type="reset" class="button button-secondary"><?php esc_html_e('Clear All', 'events-manager'); ?></button>
			</div>
			<div>
				<button type="submit" class="em-search-submit button button-primary"><?php echo esc_html($args['search_button']); ?></button>
			</div>
			<?php do_action('em_search_form_advanced_footer_bottom', $args); // do not remove ?>
		</footer>
		<?php do_action('em_search_form_advanced_footer_after', $args); // do not remove ?>
	</div><!-- modal -->
</div>