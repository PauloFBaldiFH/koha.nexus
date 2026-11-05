<?php
/* @var array $args */
$classes = array();
if( em_get_option('dbem_search_form_geo_hide_m') ) $classes[] = 'hide-medium';
if( em_get_option('dbem_search_form_geo_hide_s') ) $classes[] = 'hide-small';
?>
<!-- START GeoLocation Search -->
<div class="em-search-geo em-search-field input <?php echo implode(' ', $classes); ?>">
	<label for="em-search-geo-<?php echo absint($args['id']) ?>" class="screen-reader-text">
		<?php echo esc_html($args['geo_label']); ?>
	</label>
	<input type="text" name="geo" class="em-search-geo" id="em-search-geo-<?php echo absint($args['id']) ?>" value="<?php echo esc_attr($args['geo']); ?>" placeholder="<?php echo esc_html($args['geo_label']); ?>">
	<input type="hidden" name="near" class="em-search-geo-coords" value="<?php echo esc_attr($args['near']); ?>" >
	<div id="em-search-geo-attr" ></div>
	<script type="text/javascript">
		EM.geo_placeholder = '<?php echo esc_attr($args['geo_label']); ?>';
		EM.geo_alert_guess = '<?php esc_attr_e('We are going to use %s for searching.','events-manager'); ?> \n\n <?php esc_attr_e('If this is incorrect, click cancel and try a more specific address.','events-manager') ?>';
		<?php
		//include separately, which allows you to just modify the html or completely override the JS
		$template = em_locate_template('templates/search/geo.js');
		include_once($template); //include only once
		?>
	</script>
</div>
<!-- END GeoLocation Search -->