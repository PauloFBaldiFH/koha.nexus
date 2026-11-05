<?php
// The following are included in the scope of this event date range picker
/* @var int $id */
/* @var string|int $i */
/* @var string $type */
/* @var EM\Recurrences\Recurrence_Set $Recurrence_Set */
?>
<div class="advanced-summary">
    <span class="dates">
        <span class="start-date <?php if ( $Recurrence_Set->recurrence_date_start ) echo 'is-set'; ?>"><?php echo $Recurrence_Set->start->format(em_get_datepicker_format()); ?></span> -
        <span class="end-date <?php if ( $Recurrence_Set->recurrence_date_end ) echo 'is-set'; ?>"><?php echo $Recurrence_Set->end->format(em_get_datepicker_format()); ?></span>
    </span>

	<?php
		$times = !$Recurrence_Set->all_day ? $Recurrence_Set->start->format(em_get_hour_format()) . ' - ' . $Recurrence_Set->end->format(em_get_hour_format()) : '';
		$isset = !empty($Recurrence_Set->recurrence_all_day) || $Recurrence_Set->recurrence_start_time || $Recurrence_Set->recurrence_end_time;
	?>

	@ <span class="times <?php if ( $isset ) echo 'is-set'; ?>"><?php echo $times; ?></span>
	<span class="all-day <?php if ( $isset ) echo 'is-set'; ?>"><?php echo esc_html__('All day', 'events-manager'); ?></span>

	(<span class="timezone <?php if ( $Recurrence_Set->recurrence_timezone ) echo 'is-set'; ?>"><?php echo $Recurrence_Set->start->getTimezone()->getCity(); ?></span>)

	<span class="duration-days">|
        <span class="duration <?php if ( $Recurrence_Set->recurrence_duration ) echo 'is-set'; ?>"><?php echo $Recurrence_Set->duration; ?></span>
        <span class="recurrence-days-desc em-singular hidden"><?php echo esc_html__('day', 'events-manager'); ?></span>
        <span class="recurrence-days-desc em-plural"><?php echo esc_html__('days', 'events-manager'); ?></span>
    </span>
</div>