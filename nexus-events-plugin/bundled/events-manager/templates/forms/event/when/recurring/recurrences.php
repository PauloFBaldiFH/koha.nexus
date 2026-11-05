<?php
// The following are included in the scope of this event date range picker
/* @var int $id */
/* @var EM_Event $EM_Event */
global $EM_Event;
$days_names = em_get_days_names();
$hours_format = em_get_hour_format();
$classes = array();
$id = rand();
$EM_Event->get_recurrence_sets()->add_empty_set(); // prepare for at least one recurrence to exist for creating an event
$types = [
	'include' => '',
	'exclude' => __("Events won't recurr on the following dates:", 'events-manager'),
];
?>
<div class="em-recurrence-sets" <?php if ( $EM_Event->event_id ) echo 'data-event_id="'.$EM_Event->event_id.'"'; ?>>
	<?php foreach( $types as $type => $description ): $i = 1; ?>
		<?php $type_count = count( $EM_Event->get_recurrence_sets()->{$type} ); ?>
		<div class="em-recurrence-type em-recurrence-type-<?php echo $type; ?> <?php if ( $type_count === 0 ) echo 'em-recurrence-type-new'; ?>" data-type="<?php echo $type; ?>" data-count="<?php echo $type_count; ?>" data-index="<?php echo $i; ?>">
			<p><strong><?php echo esc_html($description); ?></strong></p>
			<div class="em-recurrence-type-sets">
				<?php foreach( $EM_Event->get_recurrence_sets()->{$type} as $Recurrence_Set ) : ?>
					<div class="em-recurrence-set <?php if ( !$Recurrence_Set->recurrence_set_id ) echo 'new-recurrence-set'; ?>" data-type="<?php echo esc_attr($type); ?>" id="recurrence-set-<?php echo $type .'-'. $i .'-'. $id; ?>">
						<?php
							include( em_locate_template('forms/event/when/recurring/recurrences/set.php') );
							$i++;
						?>
					</div>
				<?php endforeach; ?>
			</div>
			<?php if ( $type === 'include' ): ?>
				<button type="button" class="em-add-recurrence-set" data-nostyle data-type="<?php echo $type; ?>">+ <?php esc_html_e('Event Dates', 'events-manager') ?></button>
			<?php elseif ( $type === 'exclude' ) : ?>
				<?php include( em_locate_template( 'forms/event/when/recurring/recurrences/reschedule-modal-exclude.php' ) ); ?>
			<?php endif; ?>
			<button type="button" class="em-add-recurrence-set" data-nostyle data-type="exclude">+ <?php esc_html_e('Unavailable Dates', 'events-manager') ?></button>
		</div>
	<?php endforeach; ?>
	<template class="em-recurrence-set-template">
		<?php
			$i = 'N%';
			$type = 'T%';
			$Recurrence_Set = new EM\Recurrences\Recurrence_Set();
			$is_recurrence_template = true;
			include( em_locate_template('forms/event/when/recurring/recurrences/set.php') );
		?>
	</template>
</div>