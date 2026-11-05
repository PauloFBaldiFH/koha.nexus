<div class="em-item em-taxonomy em-category" style="--default-border:#_CATEGORYCOLOR;">
	<div class="em-item-image {no_image}has-placeholder{/no_image}">
		{has_image}
		#_CATEGORYIMAGE{medium}
		{/has_image}
		{no_image}
		<div class="em-item-image-placeholder"></div>
		{/no_image}
	</div>
	<div class="em-item-info">
		<h3 class="em-item-title">#_CATEGORYLINK</h3>
		<div class="em-event-meta em-item-meta">
			{has_events}
			<div class="em-item-meta-line em-taxonomy-events em-category-events">
				<span class="em-icon-calendar em-icon"></span>
				<div>
					<p><?php esc_html_e('Next Event', 'events-manager'); ?></p>
					<p>#_CATEGORYNEXTEVENT</p>
					<p><a href="#_CATEGORYURL"><?php esc_html_e('See All', 'events-manager'); ?></a></p>
				</div>
			</div>
			{/has_events}
			{no_events}
			<div class="em-item-meta-line em-taxonomy-no-events em-category-no-events">
				<span class="em-icon-calendar em-icon"></span>
				<div><?php esc_html_e('No upcoming events', 'events-manager'); ?></div>
			</div>
			{/no_events}
		</div>
		<div class="em-item-desc">
			#_CATEGORYEXCERPT{25}
		</div>
		<div class="em-item-actions input">
			<a class="em-item-read-more button" href="#_CATEGORYURL"><?php esc_html_e('More Info', 'events-manager'); ?></a>
		</div>
	</div>
</div>