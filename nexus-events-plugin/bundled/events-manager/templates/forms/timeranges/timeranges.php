<?php
use EM\Timeranges, EM\Timerange;
/* @var string $group_id */
/* @var string $name */
/* @var Timeranges $Timeranges */
// generate timeslot previews if appropriate
$preview_state = ( count($Timeranges->get_timeslots()) > 1 ) ? 'hidden' : '';
$edit_nonce = wp_create_nonce('em_timeranges_edit_' . $Timeranges->group_id);
?>
<div class="em-timeranges-editor input <?php if ( !empty($locked) ) echo 'disabled'; ?>">
	<fieldset class="em-timeranges" data-count="<?php echo esc_attr( $Timeranges->count() ); ?>" data-index="<?php echo esc_attr( $Timeranges->count() ); ?>">
		<legend data-nostyle>
			<?php _e('Times','events-manager'); ?>
			<?php if ( !empty($locked) ): ?>
				<button type="button" class="em-icon em-icon-edit em-tooltip em-timerange-editor-edit" aria-label="<?php esc_attr_e('Edit','events-manager'); ?>" data-nostyle></button>
			<?php endif; ?>
		</legend>
		<?php
		// output current timeranges, or default timeranges if none exist
		$name_template = $name;
		foreach ( $Timeranges->get_timeranges() as $key => $Timerange ) {
			$name = $name_template . '[' . $key . ']';
			include( em_locate_template('forms/timeranges/timerange.php') );
		}
		// output template timerange
		if ( $Timeranges->allow_timeranges ) {
			$name = $name_template . '[X]';
			$Timerange = $Timeranges->get_timerange();
			echo '<template>';
			include( em_locate_template( 'forms/timeranges/timerange.php' ) );
			echo '</template>';
		}
		?>
	</fieldset>
	<div class="em-timeranges-preview <?php echo $preview_state; ?> hidden">
		<a href="#" class="em-timeranges-preview-toggle"><?php esc_html_e('Preview Start Times', 'events-manager'); ?> (<span class="em-timeranges-preview-count">0</span>) <span class="em-icon em-icon-chevron-down"></span> </a>
		<div class="em-timeranges-preview-content <?php echo $preview_state; ?> hidden"></div>
	</div>
	<?php if ( $Timeranges->allow_timeranges ) : ?>
	<div class="em-timeranges-actions">
		<button type="button" class="em-timerange-add button button-secondary"><span class="em-icon em-icon-plus"></span><?php esc_html_e('Add Time Slot', 'events-manager'); ?></button>
	</div>
	<?php endif; ?>
	<?php if ( empty($locked) ): ?>
		<input type="hidden" class="em-timeranges-editor-nonce" name="<?php echo $name_template; ?>[edit_nonce]" value="<?php echo $edit_nonce; ?>" >
	<?php else: ?>
		<input type="hidden" class="em-timeranges-editor-nonce" name="<?php echo $name_template; ?>[edit_nonce]" value="" data-nonce="<?php echo $edit_nonce; ?>" >
		<?php include( em_locate_template( 'forms/timeranges/timeranges-modal.php' ) ); ?>
	<?php endif; ?>
</div>