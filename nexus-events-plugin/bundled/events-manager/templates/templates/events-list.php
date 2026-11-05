<?php
/*
 * Default Events List Template
 * This page displays a list of events, called during the em_content() if this is an events list page.
 * You can override the default display settings pages by copying this file to yourthemefolder/plugins/events-manager/templates/ and modifying it however you need.
 * You can display events however you wish, there are a few variables made available to you:
 */
/* @var array $args - the args passed onto EM_Events::output() */
$args = apply_filters('em_content_events_args', $args);
if( empty($args['id']) ) $args['id'] = rand(100, getrandmax()); // prevent warnings
$id = esc_attr($args['id']);
?>
<div class="<?php em_template_classes('view-container'); ?>" id="em-view-<?php echo $id; ?>" data-view="list">
	<div class="<?php em_template_classes('events-list'); ?>" id="em-events-list-<?php echo $id; ?>" data-view-id="<?php echo $id; ?>">
	<?php
	echo EM_Events::output( $args );
	?>
	</div>
</div>