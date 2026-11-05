<?php
/*
This template is the main meat of the calendar, most of the heavy lifting is done here to show dates according to settings.
*/
/* @var array       $args       The $args passed onto the calendar template via EM_Calendar  */
/* @var array       $calendar   The $calendar array of data passed on by EM_Calendar         */
?>
<section class="em-cal-body em-cal-days <?php echo esc_attr(implode(' ', $calendar['css']['dates_classes'])); ?>">
	<?php
	$cal_count = count($calendar['cells']); //to prevent an extra tr
	$col_count = $tot_count = 1; //this counts collumns in the $calendar_array['cells'] array
	$col_max = count($calendar['row_headers']); //each time this collumn number is reached, we create a new collumn, the number of cells should divide evenly by the number of row_headers
	// go through day cells
	$events = $multiday_slots = $multiday_slots_freed = array();
	$event_style = $args['calendar_event_style'] ?? 'pill';
	$is_single_dot = ( $event_style === 'dot' ); // 'dot' = one dot per day, no overflow +
	$is_dots = ( $event_style === 'dot' || $event_style === 'dots' ); // either dot style renders dots instead of pills
	foreach($calendar['cells'] as $date => $cell_data ){
		$class = ( !empty($cell_data['events']) && count($cell_data['events']) > 0 ) ? 'eventful eventful':'eventless';
		if(!empty($cell_data['type'])){
			$class .= "-".$cell_data['type'];
		}
		//In some cases (particularly when long events are set to show here) long events and all day events are not shown in the right order. In these cases,
		//if you want to sort events cronologically on each day, including all day events at top and long events within the right times, add define('EM_CALENDAR_SORTTIME', true); to your wp-config.php file
		//if( defined('EM_CALENDAR_SORTTIME') && EM_CALENDAR_SORTTIME ) ksort($cell_data['events']); //indexes are timestamps
		?>
		<div class="<?php echo esc_attr($class); ?> em-cal-day em-cal-col-<?php echo $col_count; ?>">
			<?php if( !empty($cell_data['events']) && count($cell_data['events']) > 0 ): ?>
				<div class="em-cal-day-date colored" data-date="<?php echo esc_attr($date); ?>" data-timestamp="<?php echo esc_attr($cell_data['date']); ?>" >
					<a href="<?php echo esc_url($cell_data['link']); ?>" title="<?php echo esc_attr($cell_data['link_title']); ?>"><?php echo esc_html(date('j',$cell_data['date'])); ?></a>
					<?php if( !$is_dots && $args['limit'] && $cell_data['events_count'] > $args['limit'] && em_get_option('dbem_display_calendar_events_limit_msg') != '' ): ?>
						<div class="limited-icon size-small size-medium">+</div>
					<?php endif; ?>
					<?php if ( $is_dots ): ?>
						<div class="em-cal-day-dots">
							<?php
							// 'dot' shows a single dot for the day; 'dots' shows one dot per event up to the limit
							$dot_events = $is_single_dot ? array_slice( $cell_data['events'], 0, 1 ) : $cell_data['events'];
							foreach ( $dot_events as $EM_Event ) :
								$EM_Category = $EM_Event->get_categories()->get_first();
								$dot_color = $EM_Category ? $EM_Category->get_color() : em_get_option('dbem_category_default_color');
								$dot_color = apply_filters('em_calendar_dot_color', $dot_color, $EM_Event);
								?>
								<span class="em-cal-dot" style="--dot-color:<?php echo esc_attr($dot_color); ?>;" data-event-id="<?php echo esc_attr($EM_Event->event_id); ?>"></span>
							<?php endforeach; ?>
							<?php if ( !$is_single_dot && $args['limit'] && $cell_data['events_count'] > $args['limit'] ) : ?>
								<span class="em-cal-dot em-cal-dot-more">+</span>
							<?php endif; ?>
						</div>
					<?php endif; ?>
				</div>
				<?php if ( !$is_dots ): ?>
				<?php
				// ouptut event data
				$single_day_events = $allday_events = $colors = array();
				$multiday_slots_content = $multiday_slots;
				foreach($multiday_slots_content as $k => $v ){
					$url = '';
					if( !empty($events[$v]) ) {
						$EM_Event = $events[$v];
						$url = $EM_Event->get_permalink();
					}
					$multiday_slots_content[$k] = '<div class="em-cal-event multiday" data-event-url="'. esc_url($url) .'" data-event-id="'.absint($v).'"></div>';
				} //placeholder
				foreach( $cell_data['events'] as $EM_Event ){ /* @var EM_Event $EM_Event */
					$events[$EM_Event->event_id] = $EM_Event;
					$classes = array();
					$event_allday = $event_multiday = $event_multiday_continuation = false;
					// get primary color of event
					$EM_Category = $EM_Event->get_categories()->get_first();
					if( $EM_Category ) {
						$colors[] = $EM_Category->get_color();
					} else {
						$colors[] = em_get_option('dbem_category_default_color');
					}
					// check multi-day events first
					if( !empty($args['long_events']) && $EM_Event->event_start_date != $EM_Event->event_end_date ){
						$event_multiday = true;
						$event_text = '';
						// multi-day event classes
						if( $EM_Event->event_start_date === $date || $col_count === 1 ){
							$days_left_in_week = $col_max - ($col_count - 1);
							$EM_DateTime = new EM_DateTime($date, $EM_Event->end()->getTimezone());
							$days_left_in_event = $EM_DateTime->diff( $EM_Event->end() )->days + 1;
							//$days_left_in_event = floor(($EM_Event->end()->getTimestamp() - $cell_data['date']) / DAY_IN_SECONDS);
							if( $EM_Event->event_start_date === $date ){
								// first day of event
								$event_text = $EM_Event->output(  $calendar['format'] );
								$classes[] = 'has-start';
								// is end date at and of this week?
								if( $days_left_in_event < $days_left_in_week ){
									$classes[] = 'has-end days-'. $days_left_in_event;
								}else{
									$classes[] = 'days-'. $days_left_in_week;
								}
							}elseif( $col_count === 1 ){
								// event continues onto following week, so decide when it ends or if it rolls over to next week
								$event_multiday_continuation = true;
								$event_text = $EM_Event->output(  $calendar['format'] );
								if( $days_left_in_event < $days_left_in_week ){
									// spans a few more days and ends
									$classes[] = 'has-end';
									$classes[] = 'days-'.$days_left_in_event;
								}else{
									// spans whole week
									$classes[] = 'days-'.$days_left_in_week;
								}
							}
							// generate event multiday content
							ob_start();
							?>
							<div class="em-cal-event multiday <?php echo esc_attr(implode(' ', $classes)); ?>" style="<?php echo esc_attr($EM_Event->get_colors(true)); ?>" data-event-url="<?php echo esc_url($EM_Event->get_permalink()); ?>" data-event-id="<?php echo esc_attr($EM_Event->event_id); ?>">
								<?php if( !empty($event_text) ): ?><div><?php echo $event_text; ?></div><?php endif; ?>
							</div>
							<?php
							$event_content = ob_get_clean();
							// take event content and slot it into cell array, whether into reserved spot or to an unreserved spot
							if( $col_count == 1 ) {
								// fill up the slots which will be empty on first column
								$days_key = $days_left_in_event - 1;
								while( !empty($multiday_slots_content[(string) $days_key]) ){
									$days_key += 0.00001; // PHP truncates float keys to int; the (string) cast above is what makes this nudge land on a new slot
								}
								$multiday_slots_content[(string) $days_key] = $event_content;
								$multiday_slots[(string) $days_key] = $EM_Event->event_id;
							}else{
								// check if reserved
								if( in_array( $EM_Event->event_id, $multiday_slots ) ){
									// already reserved, so add to content slot
									foreach( $multiday_slots as $k => $v ){
										if( $EM_Event->event_id === $v ){
											$multiday_slots_content[$k] = $event_content;
										}
									}
								}else{
									$multiday_slot_found = false;
									foreach( $multiday_slots as $k => $v ){
										if( empty($v) ){
											$multiday_slots_content[$k] = $event_content;
											$multiday_slots[$k] = $EM_Event->event_id;
											$multiday_slot_found = true;
										}
									}
									if( !$multiday_slot_found ){
										$multiday_slots_content[] = $event_content;
										$multiday_slots[] = $EM_Event->event_id;
									}
								}
							}
						}
						if( $EM_Event->event_end_date === $date ){
							$multiday_slots_freed[] = $EM_Event->event_id;
						}
					}elseif ( $EM_Event->event_start_date === $date ){
						// regular single-day event
						ob_start();
						?>
						<div class="em-cal-event" style="<?php echo esc_attr($EM_Event->get_colors(true)); ?>" data-event-url="<?php echo esc_url($EM_Event->get_permalink()); ?>" data-event-id="<?php echo esc_attr($EM_Event->event_id); ?>">
							<div><?php echo $EM_Event->output( $calendar['format'] ); ?></div>
						</div>
						<?php
						$single_day_events[] = ob_get_clean();
					}
				}
				// considerations for start of week
				if( $col_count == 1 ){
					// reorder slot lists built further up, and re-index them so they're numeric from 0
					krsort($multiday_slots);
					krsort($multiday_slots_content);
					$multiday_slots_content = array_values($multiday_slots_content);
					$multiday_slots = array_values($multiday_slots); // this will be re-used for the rest of the week
				}
				// output result
				$cell_events = array_merge($multiday_slots_content, $allday_events, $single_day_events);
				echo implode($cell_events);
				
				// free up slots after content has been output
				foreach( $multiday_slots_freed as $event_id ){
					foreach( $multiday_slots as $k => $v ){
						if( $v == $event_id ){
							$multiday_slots[$k] = '';
						}
					}
				}
				$multiday_slots_freed = array();
				// remove empty slots at end of multiday
				foreach( array_reverse($multiday_slots, true) as $k => $v ){
					if( empty($v) ){
						unset($multiday_slots[$k]);
					}else{
						break;
					}
				}
				if( !empty($colors) ){
					?>
					<span class="date-day-colors" data-colors="<?php echo esc_attr(json_encode($colors)); ?>"></span>
					<?php
				}
				?>
				<?php if( $args['limit'] && $cell_data['events_count'] > $args['limit'] && em_get_option('dbem_display_calendar_events_limit_msg') != '' ): ?>
					<div class="em-cal-day-limit"><a href="<?php echo esc_url($cell_data['link']); ?>" class="button">
							<?php echo str_replace('%COUNT%', $cell_data['events_count'] - $args['limit'], em_get_option('dbem_display_calendar_events_limit_msg')); ?></a>
					</div>
				<?php endif; ?>
				<?php endif; // end dots / pill switch ?>

			<?php else:?>
				<div class="em-cal-day-date">
					<span><?php echo esc_html(date('j',$cell_data['date'])); ?></span>
				</div>
			<?php endif; ?>
		</div>
		<?php
		//create a new row once we reach the end of a table collumn
		$col_count= ($col_count == $col_max ) ? 1 : $col_count+1;
		if ($col_count == 1 && $tot_count < $cal_count) {
			$multiday_slots = array();
		}
		$tot_count ++;
	}
	?>
</section>