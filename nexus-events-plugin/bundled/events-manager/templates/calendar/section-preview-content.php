<?php
/* @var EM_Event    $EM_Event   The current EM_Event object being displayed.                 */
/* @var array       $events     Array of event
/* @var array       $args       The $args passed onto the calendar template via EM_Calendar  */
/* @var array       $calendar   The $calendar array of data passed on by EM_Calendar         */
?>
<section class="em-cal-events-content" id="em-cal-events-content-<?php echo esc_attr($args['id']); ?>">
	<?php if( $args['calendar_preview_mode'] === 'tooltips' ): ?>
		<?php $tooltip_template_file = em_locate_template('calendar/preview-event-tooltip.php', false); ?>
		<?php foreach( $events as $EM_Event ) : ?>
			<div class="em-cal-event-content em em-event em-item" data-event-id="<?php echo esc_attr($EM_Event->event_id); ?>" data-parent="em-cal-events-content-<?php echo esc_attr($args['id']); ?>">
				<?php include($tooltip_template_file); ?>
			</div>
		<?php endforeach; ?>
	<?php elseif ( $args['calendar_preview_mode'] === 'modal' ): ?>
		<?php $modal_template_file = em_locate_template('calendar/preview-event-modal.php', false); ?>
		<?php foreach( $events as $EM_Event ) : ?>
			<?php include($modal_template_file); ?>
		<?php endforeach; ?>
	<?php endif; ?>
	<?php /* must match the condition adding the responsive-dateclick-modal class in EM_Calendar::output(), which is what binds the JS that opens these */ ?>
	<?php if( $args['calendar_preview_mode_date'] !== 'none' && $args['calendar_preview_mode'] !== 'booking' ): ?>
		<?php $modal_dates_file = em_locate_template('calendar/preview-date-modal.php', false); ?>
		<?php foreach($calendar['cells'] as $date => $cell_data ): $EM_DateTime = new EM_DateTime($date); ?>
			<?php if( !empty($cell_data['events']) && count($cell_data['events']) > 0 ): ?>
				<?php include($modal_dates_file); ?>
			<?php endif; ?>
		<?php endforeach; ?>
	<?php endif; ?>
</section>