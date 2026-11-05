<?php
/* @var EM_Event    $EM_Event   The current EM_Event object being displayed.                 */
/* @var array       $args       The $args passed onto the calendar template via EM_Calendar  */
/* @var array       $calendar   The $calendar array of data passed on by EM_Calendar         */
?>
<section class="em-cal-head em-cal-week-days em-cal-days size-large">
	<?php
	$i = 0;
	foreach( $calendar['row_headers_large'] as $header ){
		?>
		<div class="em-cal-day em-cal-col-<?php echo $i; ?>"><?php echo $header; ?></div>
		<?php
		$i++;
	}
	?>
</section>
<section class="em-cal-head em-cal-week-days em-cal-days size-small size-medium">
	<?php
	$i = 0;
	foreach( $calendar['row_headers_small'] as $header ){
		?>
		<div class="em-cal-day em-cal-col-<?php echo $i; ?>"><?php echo $header; ?></div>
		<?php
		$i++;
	}
	?>
</section>