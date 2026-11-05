<div class="em-location-map-container">
	<div id='em-map-404' class="em-location-map-404">
		<p><?php esc_html_e('Location not found', 'events-manager'); ?></p>
		<p><?php esc_html_e('Update your address information above to generate a preciese map location.', 'events-manager'); ?></p>
	</div>
	<div class="em-loading-maps" style="display:none; ">
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
	<div id='em-map' class="em-location-map-content" style='display: none;'></div>
</div>