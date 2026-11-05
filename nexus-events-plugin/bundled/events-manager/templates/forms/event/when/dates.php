<?php
// The following are included in the scope of this event date range picker
/* @var int $id */
/* @var bool $with_recurring Set if a recurring event or front-end to show both options. */
/* @var EM_Event $EM_Event */
?>
<div class="em-datepicker em-datepicker-range em-event-dates">

	<label for="em-date-start-end-<?php echo $id ?>" class="em-event-text"><?php _e ( 'Event Dates ', 'events-manager'); ?></label>
	<input id="em-date-start-end-<?php echo $id ?>" type="hidden" class="em-date-input em-date-start-end" aria-hidden="true" placeholder="<?php _e ( 'Select date range', 'events-manager'); ?>">
	
	<div class="em-datepicker-data">
		<input type="date" name="event_start_date" value="<?php if( $EM_Event->event_start_date ) echo $EM_Event->start()->getDate(); ?>" aria-label="<?php _e ( 'From ', 'events-manager'); ?>">
		<span class="separator"><?php _e('to','events-manager'); ?></span>
		<input type="date" name="event_end_date" value="<?php if( $EM_Event->event_end_date ) echo $EM_Event->end()->getDate(); ?>" aria-label="<?php _e('to','events-manager'); ?>">
	</div>
</div>
