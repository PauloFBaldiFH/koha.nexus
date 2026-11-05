<?php 
/*
 * This file contains the HTML generated for a single location Google map. You can copy this file to yourthemefolder/plugins/events/templates and modify it in an upgrade-safe manner.
 * 
 * There is one argument passed to you, which is the $args variable. This contains the arguments you could pass into shortcodes, template tags or functions like EM_Events::get().
 * 
 * In this template, we encode the $args array into JSON for javascript to easily parse and request the locations from the server via AJAX.
 */
	/* @var $EM_Location EM_Location */
	if ( em_get_option('dbem_gmap_is_active') && ( is_object($EM_Location) && $EM_Location->location_latitude != 0 && $EM_Location->location_longitude != 0 ) ) {
		//assign random number for element id reference
		$rand = rand();
		//get dimensions with px or % added in
		$width = (isset($args['width'])) ? $args['width']:em_get_option('dbem_map_default_width','400px');
		$height = (isset($args['height'])) ? $args['height']:em_get_option('dbem_map_default_height','300px');
		$width = preg_match('/(px)|%/', $width) ? $width:$width.'px';
		$height = preg_match('/(px)|%/', $height) ? $height:$height.'px';
		//generate map depending on type
		if( em_get_option('dbem_gmap_type') == 'embed' ){
			$map_url = $EM_Location->get_google_maps_embed_url();
			?>
			<div class="em-location-map-container"  style='position:relative; background: #CDCDCD; width: <?php echo esc_attr($width) ?>; height: <?php echo esc_attr($height) ?>;'>
				<iframe class="em-location-map" style="width:100%; height:100%; border:0;" src="<?php echo esc_attr($map_url); ?>" allowfullscreen></iframe>
			</div>
			<?php
		}else{
			?>
			<div class="em em-location-map-container" style="position:relative; <?php if( $width ) echo 'width:'. esc_attr($width).';'; ?> <?php if( $height ) echo 'height: '. esc_attr($height) .';' ?>">
				<div class='em-location-map' id='em-location-map-<?php echo $rand ?>' style="width: 100%; height: 100%;" title="<?php echo esc_attr($EM_Location->location_name); ?>">
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
			</div>
			<div class='em-location-map-info' id='em-location-map-info-<?php echo $rand ?>' style="display:none; visibility:hidden;">
				<div class="em-map-balloon">
					<div class="em-map-balloon-content" ><?php echo $EM_Location->output(em_get_option('dbem_location_baloon_format')); ?></div>
				</div>
			</div>
			<div class='em-location-map-coords' id='em-location-map-coords-<?php echo $rand ?>' style="display:none; visibility:hidden;">
				<span class="lat"><?php echo $EM_Location->location_latitude; ?></span>
				<span class="lng"><?php echo $EM_Location->location_longitude; ?></span>
			</div>
			<?php if( !empty($args['map_style']) ): ?>
				<script type="text/javascript">
					if( typeof EM == 'object'){
						if( typeof EM.google_map_id_styles != 'object' ) EM.google_map_id_styles = [];
						EM.google_map_id_styles['<?php echo $rand; ?>'] = <?php echo $args['map_style']; ?>;
					}
				</script>
			<?php endif;
		}
	}elseif( is_object($EM_Location) && $EM_Location->location_latitude == 0 && $EM_Location->location_longitude == 0 ){
		echo '<i>'. __('Map Unavailable', 'events-manager') .'</i>';
	}