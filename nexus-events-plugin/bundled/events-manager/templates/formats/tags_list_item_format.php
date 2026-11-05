<div class="em-item em-taxonomy em-tag" style="--default-border:#_TAGCOLOR;">
	<div class="em-item-image {no_image}has-placeholder{/no_image}">
		{has_image}
		#_TAGIMAGE{medium}
		{/has_image}
		{no_image}
		<div class="em-item-image-placeholder"></div>
		{/no_image}
	</div>
	<div class="em-item-info">
		<h3 class="em-item-title">#_TAGLINK</h3>
		<div class="em-event-meta em-item-meta">
			{has_events}
			<div class="em-item-meta-line em-taxonomy-events em-tag-events">
				<span class="em-icon-calendar em-icon"></span>
				<div>
					<p><?php esc_html_e('Next Event', 'events-manager'); ?></p>
					<p>#_TAGNEXTEVENT</p>
					<p><a href="#_TAGURL"><?php esc_html_e('See All', 'events-manager'); ?></a></p>
				</div>
			</div>
			{/has_events}
			{no_events}
			<div class="em-item-meta-line em-taxonomy-no-events em-tag-no-events">
				<span class="em-icon-calendar em-icon"></span>
				<div><?php esc_html_e('No upcoming events', 'events-manager'); ?></p></div>
			</div>
			{/no_events}
		</div>
		<div class="em-item-desc">
			#_TAGEXCERPT{25}
		</div>
		<div class="em-item-actions input">
			<a class="em-item-read-more button" href="#_TAGURL"><?php esc_html_e('More Info', 'events-manager'); ?></a>
		</div>
	</div>
</div>