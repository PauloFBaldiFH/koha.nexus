<?php
/* @var EM_Event    $EM_Event       The current EM_Event object being displayed.                 */
/* @var int         $id             A unique ID use to display this calendar instance            */
/* @var EM_DAteTime $EM_DateTime    The current date/time in an EM_DateTime object               */
/* @var array       $args           The $args passed onto the calendar template via EM_Calendar  */
/* @var array       $calendar       The $calendar array of data passed on by EM_Calendar         */
?>
<section class="em-cal-nav em-cal-nav-<?php echo esc_attr($args['calendar_header']); ?>">
	<?php if( $args['has_advanced_trigger'] ): ?>
		<button class="em-search-advanced-trigger em-clickable" data-search-advanced-id="em-search-advanced-<?php echo esc_attr($id); ?>"  data-parent-trigger="em-search-advanced-trigger-<?php echo esc_attr($id); ?>"></button>
	<?php endif; ?>
	<?php ob_start(); ?>
	<div class="month input">
		<?php if( !empty($args['calendar_nav']) && !empty($args['calendar_month_nav']) ): ?>
			<form action="" method="get">
				<input type="month" class="em-month-picker" value="<?php echo esc_attr($EM_DateTime->i18n('Y-m')) ?>" data-month-value="<?php echo esc_attr($EM_DateTime->i18n( em_get_option('dbem_full_calendar_month_format') )) ?>">
				<span class="toggle"></span>
			</form>
		<?php else: ?>
			<?php echo esc_html($EM_DateTime->i18n(em_get_option('dbem_full_calendar_month_format'))); ?>
		<?php endif; ?>
	</div>
	<?php
		$header = ob_get_clean();
		if ( $args['calendar_header'] !== 'centered' ) {
			echo $header;
		}
	?>
	<?php if( !empty($args['calendar_nav']) ) : ?>
	<div class="month-nav input">
		<a class="em-calnav em-calnav-prev" href="<?php echo esc_url($calendar['links']['previous_url']); ?>" data-disabled="<?php echo empty($calendar['links']['previous_url']) ? 1 : 0; ?>" <?php if( !empty($args['calendar_nav_nofollow'] ) ) echo 'rel="nofollow"' ?>>
			<svg viewBox="0 0 15 15" xmlns="http://www.w3.org/2000/svg"><path d="M10 14L3 7.5L10 1" stroke="#555" stroke-linecap="square"></path></svg>
		</a>
		<?php if( $args['calendar_header'] === 'centered' ) : ?>
			<?php echo $header; ?>
		<?php else: ?>
			<a href="<?php echo esc_url($calendar['links']['today_url']); ?>" class="em-calnav-today button button-secondary size-large size-medium <?php if( date('Y-m') === $EM_DateTime->format('Y-m') ) echo 'is-today'; ?>" <?php if( !empty($args['calendar_nav_nofollow'] ) ) echo 'rel="nofollow"' ?>>
				<?php esc_html_e('Today', 'events-manager'); ?>
			</a>
		<?php endif; ?>
		<a class="em-calnav em-calnav-next" href="<?php echo esc_url($calendar['links']['next_url']); ?>" data-disabled="<?php echo empty($calendar['links']['next_url']) ? 1 : 0; ?>" <?php if( !empty($args['calendar_nav_nofollow'] ) ) echo 'rel="nofollow"' ?>>
			<svg viewBox="0 0 15 15" xmlns="http://www.w3.org/2000/svg"><path d="M5 14L12 7.5L5 1" stroke="#555" stroke-linecap="square"></path></svg>
		</a>
	</div>
	<?php endif; ?>
</section>