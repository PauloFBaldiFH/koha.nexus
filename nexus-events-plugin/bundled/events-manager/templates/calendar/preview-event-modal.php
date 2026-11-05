<?php
/* @var EM_Event    $EM_Event   The current EM_Event object being displayed.                 */
/* @var array       $args       The $args passed onto the calendar template via EM_Calendar  */
/* @var array       $calendar   The $calendar array of data passed on by EM_Calendar         */
?>
<div class="<?php em_template_classes('calendar-preview', 'modal'); ?> em-cal-event-content" data-event-id="<?php echo esc_attr($EM_Event->event_id); ?>" data-parent="em-cal-events-content-<?php echo esc_attr($args['id']); ?>">
	<div class="em-modal-popup">
		<header>
			<a class="em-close-modal"></a><!-- close modal -->
			<div class="em-modal-title">
				<?php echo $EM_Event->output('#_EVENTLINK'); ?>
			</div>
		</header>
		<div class="em-modal-content">
			<?php echo $EM_Event->output( $EM_Event->get_option('dbem_calendar_preview_modal_event_format')); ?>
		</div><!-- content -->
	
	</div><!-- modal -->
</div>