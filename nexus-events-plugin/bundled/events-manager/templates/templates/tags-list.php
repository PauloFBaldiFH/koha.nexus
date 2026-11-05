<?php
/*
 * Default Tags List Template
 * This page displays a list of locations, called during the em_content() if this is an tags list page.
 * You can override the default display settings pages by copying this file to yourthemefolder/plugins/events-manager/templates/ and modifying it however you need.
 * You can display locations (or whatever) however you wish, there are a few variables made available to you:
 *
 * $args - the args passed onto EM_Tags::output()
 *
 */
$args = apply_filters('em_content_tags_args', $args);
if( empty($args['id']) ) $args['id'] = rand(100, getrandmax()); // prevent warnings
$id = esc_attr($args['id']);
?>
<div class="<?php em_template_classes('view-container'); ?>" id="em-view-<?php echo $id; ?>" data-view="list">
	<div class="<?php em_template_classes('tags-list'); ?>" id="em-tags-list-<?php echo $id; ?>" data-view-id="<?php echo $id; ?>">
		<?php
		echo EM_Tags::output( $args );
		?>
	</div>
</div>