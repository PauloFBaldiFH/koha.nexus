<?php
/* @var EM_DateTime  $EM_DateTime    An EM_DateTime object in the timezone of the blog, for current date being displayed.                            */
/* @var array        $cell_data      An EM_DateTime object in the timezone of the blog, for current date being displayed.                            */
/* @var int          $date           UTC Representation of current date being displayed. Time is 00:00:00 UTC, so beware with shifts in timezone!    */
/* @var array        $args           The $args passed onto the calendar template via EM_Calendar                                                     */
/* @var array        $calendar       The $calendar array of data passed on by EM_Calendar                                                            */
?>
<div class="<?php em_template_classes('calendar-preview', 'modal'); ?> em-cal-date-content" data-calendar-date="<?php echo $cell_data['date']; ?>" data-parent="em-cal-events-content-<?php echo esc_attr($args['id']); ?>">
	<div class="em-modal-popup">
		<header>
			<a class="em-close-modal"></a><!-- close modal -->
			<div class="em-modal-title">
				<?php echo sprintf(esc_html__('Events on %s', 'events-manager'), $EM_DateTime->formatDefault(false)); ?>
			</div>
		</header>
		<div class="em-modal-content <?php em_template_classes('calendar-preview', 'events-widget'); /* we're adding some subcomponent class names not generic 'em' and 'pixelbones' classes */ ?>">
			<?php foreach( $cell_data['events'] as $EM_Event ): /* @var EM_Event $EM_Event */ ?>
				<?php echo $EM_Event->output( $EM_Event->get_option('dbem_calendar_preview_modal_date_format') ); ?>
			<?php endforeach; ?>
		</div><!-- content -->
		<?php if( $cell_data['events_count'] > count($cell_data['events']) && em_get_option('dbem_display_calendar_events_limit_msg') != '' ): ?>
		<footer>
			<div class="em-cal-day-limit input"><a href="<?php echo esc_url($cell_data['link']); ?>" class="button">
					<?php echo str_replace('%COUNT%', $cell_data['events_count'] - $args['limit'], em_get_option('dbem_display_calendar_events_limit_msg')); ?></a>
			</div>
		</footer>
		<?php endif; ?>
	</div><!-- modal -->
</div>