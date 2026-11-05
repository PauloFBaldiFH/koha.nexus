<?php 
/*
 * This file contains the HTML generated for maps. You can copy this file to yourthemefolder/plugins/events/templates and modify it in an upgrade-safe manner.
 * 
 * There is one argument passed to you, which is the $args variable. This contains the arguments you could pass into shortcodes, template tags or functions like EM_Events::get().
 * 
 * In this template, we encode the $args array into JSON for javascript to easily parse and request the locations from the server via AJAX.
 */
/* @var array $args */
if( empty($args['id']) ) $args['id'] = rand(100, getrandmax()); // prevent warnings
$id = esc_attr($args['id']); // once
if (em_get_option('dbem_gmap_is_active') == '1') {
	?>
	<div class="em em-location-map-container"  style='position:relative; <?php if( $args['width'] ) echo 'width:'. esc_attr($args['width']).';'; ?> <?php if( $args['height'] ) echo 'height: '. esc_attr($args['height']) .';' ?>'>
		<div class='em-locations-map' id='em-locations-map-<?php echo $id; ?>' style="width:100%; height:100%">
			<div class="em-loading-maps">
				<span><?php _e('Loading Map....', 'events-manager'); ?></span>
				<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" style="margin: auto; background: none; display: block; shape-rendering: auto;" width="200px" height="200px" viewBox="0 0 100 100" preserveAspectRatio="xMidYMid">
					<rect x="19.5" y="26" width="11" height="48" fill="#85a2b6">
						<animate attributeName="y" repeatCount="indefinite" dur="1s" calcMode="spline" keyTimes="0;0.5;1" values="2;26;26" keySplines="0 0.5 0.5 1;0 0.5 0.5 1" begin="-0.2s"></animate>
						<animate attributeName="height" repeatCount="indefinite" dur="1s" calcMode="spline" keyTimes="0;0.5;1" values="96;48;48" keySplines="0 0.5 0.5 1;0 0.5 0.5 1" begin="-0.2s"></animate>
					</rect>
					<rect x="44.5" y="26" width="11" height="48" fill="#bbcedd">
						<animate attributeName="y" repeatCount="indefinite" dur="1s" calcMode="spline" keyTimes="0;0.5;1" values="8;26;26" keySplines="0 0.5 0.5 1;0 0.5 0.5 1" begin="-0.1s"></animate>
						<animate attributeName="height" repeatCount="indefinite" dur="1s" calcMode="spline" keyTimes="0;0.5;1" values="84;48;48" keySplines="0 0.5 0.5 1;0 0.5 0.5 1" begin="-0.1s"></animate>
					</rect>
					<rect x="69.5" y="26" width="11" height="48" fill="#dce4eb">
						<animate attributeName="y" repeatCount="indefinite" dur="1s" calcMode="spline" keyTimes="0;0.5;1" values="8;26;26" keySplines="0 0.5 0.5 1;0 0.5 0.5 1"></animate>
						<animate attributeName="height" repeatCount="indefinite" dur="1s" calcMode="spline" keyTimes="0;0.5;1" values="84;48;48" keySplines="0 0.5 0.5 1;0 0.5 0.5 1"></animate>
					</rect>
				</svg>
			</div>
		</div>
		<script type="application/json" class='em-locations-map-coords' id='em-locations-map-coords-<?php echo $id; ?>' style="display:none; visibility:hidden;"><?php echo EM_Object::json_encode($args, true); ?></script>
		<?php if( !empty($args['map_style']) ): ?>
		<script type="text/javascript">
			if( typeof EM == 'object'){
				if( typeof EM.google_map_id_styles != 'object' ) EM.google_map_id_styles = [];
				EM.google_map_id_styles['<?php echo $id; ?>'] = <?php echo $args['map_style']; ?>;
			}
		</script>
		<?php endif; ?>
	</div>
	<?php
}
?>