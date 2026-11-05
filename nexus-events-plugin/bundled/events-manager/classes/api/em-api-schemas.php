<?php
namespace EM\API;

/**
 * Input schemas for REST + Ability args, kept in lockstep with the OpenAPI YAML.
 *
 * Field-naming policy: top-level keys mirror the live admin/public form $_POST contract so a single shape works across `EM_*::get_post()`, MCP abilities, and REST. Extras pass through verbatim via `Utils::with_request_data()`; documented properties below are the canonical core set.
 */
class Schemas {

	/** Shared description for additionalProperties on input schemas — points API consumers at EM core. */
	const ADDITIONAL_PROPERTIES_DESCRIPTION = 'Any extra field name accepted by the matching EM core `get_post()` / `get_post_meta()` method (or by callbacks hooking into them — Pro add-ons, custom plugins, theme code). Documented properties on the parent schema are the canonical set; everything else passes through to `$_REQUEST` unchanged.';

	public static function collection_input() {
		return array(
			'type' => 'object',
			'properties' => array(
				'page'     => array( 'type' => 'integer', 'minimum' => 1,  'description' => 'Page number (1-based).' ),
				'per_page' => array( 'type' => 'integer', 'minimum' => 1, 'maximum' => 100, 'description' => 'Items per page. Server clamps to a max of 100 to prevent abuse.' ),
				'search'   => array( 'type' => 'string',  'description' => 'Free-text search across the resource\'s indexed fields.' ),
				'context'  => array( 'type' => 'string',  'enum' => array( 'view', 'edit', 'embed' ), 'description' => 'Response shape. `view` is the public projection; `edit` includes admin-only fields; `embed` is the minimal shape used when the resource is nested inside another response.' ),
			),
		);
	}

	public static function media_upload_input() {
		// Polymorphic input. Provide ONE of: id (existing attachment), source_url (sideload), content_base64 (inline), or a multipart `file` field on the HTTP request.
		return array(
			'type' => 'object',
			'properties' => array(
				'id'             => array( 'type' => 'integer', 'description' => 'Existing media library attachment ID. Returns its current metadata without re-uploading.' ),
				'source_url'     => array( 'type' => 'string', 'format' => 'uri', 'description' => 'Public HTTPS URL of an image to sideload into the media library. Use this for "find a relevant image from Unsplash and attach it." Internally calls `media_sideload_image()`.' ),
				'content_base64' => array( 'type' => 'string', 'description' => 'Base64-encoded file bytes for inline upload. Pair with `filename` (required) and `mime_type` (recommended).' ),
				'filename'       => array( 'type' => 'string', 'description' => 'Filename for the inline upload. Required when `content_base64` is provided.' ),
				'mime_type'      => array( 'type' => 'string', 'description' => 'MIME type for the inline upload. Optional but recommended; WordPress will sniff from the filename otherwise.' ),
				'title'          => array( 'type' => 'string', 'description' => 'Display title for the attachment. Defaults to the filename.' ),
				'alt_text'       => array( 'type' => 'string', 'description' => 'Alt text stored on `_wp_attachment_image_alt`. Important for accessibility.' ),
				'caption'        => array( 'type' => 'string', 'description' => 'Attachment caption (`post_excerpt`).' ),
				'description'    => array( 'type' => 'string', 'description' => 'Long-form attachment description (`post_content`).' ),
				'post_id'        => array( 'type' => 'integer', 'description' => 'Media-library organisation only: sets the attachment\'s `post_parent` so it shows under that post in the library. This does NOT make it the post\'s featured image — for that use `featured_image_for_event` / `featured_image_for_location` below, or pass the returned attachment id to `featured_image` on update-event / update-location.' ),
				'featured_image_for_event'    => array( 'type' => 'integer', 'description' => 'Convenience: after uploading, set this attachment as the featured image (thumbnail) of the given Events Manager event ID, in one call. Requires permission to edit that event. The response includes a `featured_image_set` confirmation, or a `warnings` entry if it could not be applied.' ),
				'featured_image_for_location' => array( 'type' => 'integer', 'description' => 'Convenience: after uploading, set this attachment as the featured image (thumbnail) of the given Events Manager location ID, in one call. Requires permission to edit that location.' ),
			),
		);
	}

	/**
	 * Polymorphic shape used by `featured_image` on events/locations and `image` on terms. Accepts an integer attachment ID, a string URL (sideloaded), or any of the `media_upload_input()` object forms (source_url / content_base64 / id). Pass `null` to clear an existing image.
	 */
	public static function image_assignment_input( $description = '' ) {
		return array(
			'oneOf' => array(
				array( 'type' => 'integer', 'description' => 'Existing media library attachment ID.' ),
				array( 'type' => 'string', 'description' => 'Public URL — sideloaded into the media library if not already there.' ),
				array( 'type' => 'object', 'description' => 'Inline or detailed upload — same shape as `POST /media` input.' ),
				array( 'type' => 'null', 'description' => 'Clear the image.' ),
			),
			'description' => $description ?: 'Polymorphic image input. Pass an attachment ID for an existing media library item, a URL to sideload, an object for inline base64 upload, or `null` to clear.',
		);
	}

	public static function location_geo_input( $accepted = array() ) {
		// Input for the location discovery endpoints (countries / regions / states / towns). $accepted lists which parent filters this dimension supports; the special token 'only_available' enables the countries-specific boolean filter.
		$properties = array(
			'search' => array( 'type' => 'string', 'description' => 'Optional case-insensitive substring filter applied to the returned values (and country names, for the countries endpoint).' ),
		);
		if ( in_array( 'country', $accepted, true ) ) {
			$properties['country'] = array( 'type' => 'string', 'description' => 'ISO-3166 alpha-2 country code (e.g. `US`, `GB`). Narrows results to locations within that country.' );
		}
		if ( in_array( 'region', $accepted, true ) ) {
			$properties['region'] = array( 'type' => 'string', 'description' => 'Region name. Narrows results to locations within that region.' );
		}
		if ( in_array( 'state', $accepted, true ) ) {
			$properties['state'] = array( 'type' => 'string', 'description' => 'State/province name. Narrows results to locations within that state.' );
		}
		if ( in_array( 'only_available', $accepted, true ) ) {
			$properties['only_available'] = array( 'type' => 'boolean', 'description' => 'When true, only return countries that have at least one stored location row. When false or omitted (default), the full ISO-3166 country list is returned — useful for populating a country picker on a fresh install.' );
		}
		return array(
			'type' => 'object',
			'properties' => $properties,
		);
	}

	public static function id_input( $description = '' ) {
		// Used for routes that take a path-level ID. Not part of any request *body* schema.
		return array(
			'type' => 'object',
			'properties' => array(
				'id'      => array( 'type' => 'string', 'description' => $description ?: 'Resource ID (numeric for most resources; recurring events use the UID form `parent:child`).' ),
				'context' => array( 'type' => 'string', 'enum' => array( 'view', 'edit', 'embed' ), 'description' => 'Response shape (see collection_input).' ),
			),
			'required' => array( 'id' ),
		);
	}

	public static function event_input( $require_id = false ) {
		$schema = array(
			'type'     => 'object',
			'required' => array( 'event_name', 'event_start_date' ),
			'properties' => array(
				'event_name'           => array( 'type' => 'string',  'description' => 'Event display title. Required.' ),
				'content'              => array( 'type' => 'string',  'description' => 'Long-form event description. Accepts HTML, sanitized by `wp_kses` against the post-content allowlist.' ),
				'event_type'           => array( 'type' => 'string',  'enum' => array( 'single', 'recurring', 'repeating' ), 'description' => 'Event timing model. `single` is one occurrence; `recurring` is a parent that generates child occurrences; `repeating` is a parent CPT for separately-tracked instances. Defaults to `single`.' ),
				'event_archetype'      => array( 'type' => 'string',  'description' => 'Custom event-archetype CPT slug (configured under Events > Settings > Archetypes). Defaults to the base event type.' ),
				'post_status'          => array( 'type' => 'string',  'enum' => array( 'publish', 'pending', 'draft', 'private' ), 'description' => 'WP post status. Setting `publish` requires the `publish_events` capability; without it, EM will save as `pending` regardless.' ),
				'featured_image'       => static::image_assignment_input( 'WordPress featured image for the event. Accepts an attachment ID, a public URL (sideloaded), an object with `source_url` / `content_base64` / `file`, or `null` to clear. Sets `_thumbnail_id` on the underlying CPT.' ),
				'featured_image_alt'   => array( 'type' => 'string', 'description' => 'Alt text applied to the featured image attachment (`_wp_attachment_image_alt`). Only takes effect when `featured_image` is also provided.' ),

				'event_start_date'     => array( 'type' => 'string', 'format' => 'date', 'description' => 'Event start date in ISO format (`YYYY-MM-DD`). Required.' ),
				'event_end_date'       => array( 'type' => 'string', 'format' => 'date', 'description' => 'Event end date. Defaults to `event_start_date` if omitted.' ),
				'event_start_time'     => array( 'type' => 'string', 'description' => 'Event start time. Accepted forms: `HH:MM`, `HH:MM:SS`, or 12-hour `h:MM AM/PM`. Translated to `event_timeranges[0].start` server-side.' ),
				'event_end_time'       => array( 'type' => 'string', 'description' => 'Event end time (same formats as `event_start_time`).' ),
				'event_rsvp_date'      => array( 'type' => 'string', 'format' => 'date', 'description' => 'Booking cut-off date (no bookings accepted after this date).' ),
				'event_rsvp_time'      => array( 'type' => 'string', 'description' => 'Booking cut-off time of day, partnering with `event_rsvp_date`.' ),
				'event_timezone'       => array( 'type' => 'string', 'description' => 'IANA timezone (e.g. `Europe/London`). Defaults to the site timezone if omitted.' ),
				'event_all_day'        => array( 'type' => 'boolean', 'description' => 'When true, EM clears `start`/`end` times and treats the event as all-day. Translated to `event_timeranges[0].all_day` server-side.' ),
				'event_timeranges'     => array(
					'type'        => 'array',
					'description' => 'Canonical EM time-range structure (mirrors the live event form). Index 0 holds the primary range; additional indices are timeslot generators when `timeslots: true` is set. Sending `event_start_time` / `event_end_time` / `event_all_day` at the top level is translated into this shape — pick whichever style suits the consumer.',
					'items'       => array( 'type' => 'object' ),
				),

				'event_rsvp'           => array( 'type' => 'integer', 'description' => 'Bookings master switch: `1` to enable, `0` to disable. Must be `1` for `em_tickets` to take effect (mirrors the admin-form bookings checkbox).' ),
				'event_rsvp_spaces'    => array( 'type' => 'integer', 'description' => 'Per-booking maximum spaces. `0` = no per-booking cap.' ),
				'event_spaces'         => array( 'type' => 'integer', 'minimum' => 0, 'description' => 'Total event capacity across all tickets. `0` = no event-wide cap.' ),
				'event_active_status'  => array( 'type' => 'integer', 'description' => 'Active-status code (1 = active, 0 = cancelled/inactive; see `EM_Event::get_active_statuses()` for the full enum).' ),
				'event_private'        => array( 'type' => 'integer', 'description' => 'Privacy flag: `1` = private (visible only to users with `read_private_events`), `0` = public.' ),

				'location_id'          => array( 'type' => 'integer', 'description' => 'Existing location ID to bind. Leave empty (and supply `location_name` plus address fields) to create a new location inline.' ),
				'location_name'        => array( 'type' => 'string',  'description' => 'Inline location create — used only when `location_id` is empty.' ),
				'location_address'     => array( 'type' => 'string',  'description' => 'Inline location create: street address.' ),
				'location_town'        => array( 'type' => 'string',  'description' => 'Inline location create: town / city.' ),
				'location_state'       => array( 'type' => 'string',  'description' => 'Inline location create: state / county.' ),
				'location_postcode'    => array( 'type' => 'string',  'description' => 'Inline location create: postal / zip code.' ),
				'location_region'      => array( 'type' => 'string',  'description' => 'Inline location create: region (free-form, used for filtering).' ),
				'location_country'     => array( 'type' => 'string',  'description' => 'Inline location create: ISO 3166-1 alpha-2 country code (e.g. `GB`, `US`).' ),
				'location_latitude'    => array( 'type' => 'number',  'description' => 'Inline location create: WGS-84 latitude.' ),
				'location_longitude'   => array( 'type' => 'number',  'description' => 'Inline location create: WGS-84 longitude.' ),
				'location_type'        => array( 'type' => 'string',  'description' => 'Location type. Default `location` (physical, uses `location_id` or inline fields). ::pro:: values include `url` and `online`.' ),
				'location_url'         => array( 'type' => 'string',  'description' => '::pro:: URL for url-type locations.' ),
				'event_location_url'      => array( 'type' => 'string', 'description' => '::pro:: Legacy event URL field (predates `location_url`).' ),
				'event_location_url_text' => array( 'type' => 'string', 'description' => '::pro:: Display text for `event_location_url`.' ),

				'event_categories' => array( 'type' => 'array', 'items' => array( 'type' => 'integer' ), 'description' => 'Category term IDs. Canonical name matches the live event form $_POST contract.' ),
				'event_tags'       => array( 'type' => 'array', 'items' => array( 'type' => 'integer' ), 'description' => 'Tag term IDs.' ),
				'categories'       => array( 'type' => 'array', 'items' => array( 'type' => 'integer' ), 'description' => 'Deprecated alias for `event_categories`. Kept for back-compat; prefer the canonical name.' ),
				'tags'             => array( 'type' => 'array', 'items' => array( 'type' => 'integer' ), 'description' => 'Deprecated alias for `event_tags`.' ),

				'em_tickets' => array(
					'type'        => 'object',
					'description' => 'Tickets bound to this event. Object keyed by ticket ID (existing) or 1-based sequential index (new). Key `0` is reserved by `EM_Tickets::get_post()` (admin-form template row); the API auto-shifts 0-indexed payloads. Requires `event_rsvp:1` on the event to take effect.',
					'additionalProperties' => static::ticket_input(),
				),
				'em_attributes' => array(
					'type'        => 'object',
					'description' => 'Custom event attributes, keyed by attribute label as configured under Events > Settings > Attributes. Values are typically strings; select-multiple attributes accept an array of strings.',
					'additionalProperties' => true,
				),
				'em_coupons' => array(
					'type'        => 'array',
					'description' => '::pro:: Coupon IDs to bind to this event (event-wide discounts).',
					'items'       => array( 'type' => 'integer' ),
				),

				// ::pro:: overlay fields — pass through verbatim; only active when Pro is installed.
				'waitlist'                 => array( 'type' => 'integer', 'description' => '::pro:: (waitlists) `1` enables the waitlist on this event, `0` disables.' ),
				'waitlist_booking_limit'   => array( 'type' => 'integer', 'description' => '::pro:: (waitlists) Maximum spaces a single waitlist booking may request.' ),
				'waitlist_expiry'          => array( 'type' => 'string',  'description' => '::pro:: (waitlists) Minutes before an offered waitlist slot lapses if not confirmed.' ),
				'waitlist_limit'           => array( 'type' => 'integer', 'description' => '::pro:: (waitlists) Maximum total waitlist size.' ),
				'rsvp_policy'              => array( 'type' => 'string',  'description' => '::pro:: (rsvp-policy) Deadline / cancel policy slug.' ),
				'rsvp_policy_type'         => array( 'type' => 'string',  'description' => '::pro:: (rsvp-policy) Policy enforcement type.' ),
				'bookings_can_cancel'      => array( 'type' => 'string',  'description' => '::pro:: Whether attendees may self-cancel their bookings.' ),
				'bookings_can_cancel_time' => array( 'type' => 'string',  'description' => '::pro:: Cancel cut-off as an ISO 8601 duration before event start (e.g. `P1D` = 1 day before).' ),
				'minimum_capacity_spaces'  => array( 'type' => 'integer', 'description' => '::pro:: Minimum bookings required by the `minimum_capacity_time` deadline; if not met, EM can cancel automatically.' ),
				'minimum_capacity_time'    => array( 'type' => 'string',  'description' => '::pro:: ISO 8601 duration before event start by which `minimum_capacity_spaces` must be met.' ),
				'dependent_event'          => array( 'type' => 'string',  'description' => '::pro:: Prerequisite event UID or ID — bookers must have a booking on that event first.' ),
				'custom_attendee_form'     => array( 'type' => 'integer', 'description' => '::pro:: (bookings-form) Form ID overriding the default attendee form for this event.' ),
				'custom_booking_form'      => array( 'type' => 'integer', 'description' => '::pro:: (bookings-form) Form ID overriding the default booking form.' ),
				'recurrence_rsvp_days'     => array( 'type' => 'integer', 'description' => '::pro:: Per-recurrence RSVP cut-off offset (days). Used with `recurrence_rsvp_days_when`.' ),
				'recurrence_rsvp_days_when'=> array( 'type' => 'string',  'description' => '::pro:: `before` or `after`, qualifies `recurrence_rsvp_days`.' ),

				'data_privacy_consent' => array( 'type' => 'boolean', 'description' => 'Consent flag for privacy-policy acknowledgement. Required when the site\'s privacy add-on is configured to require it.' ),
				'data_comms_consent'   => array( 'type' => 'boolean', 'description' => 'Consent flag for marketing/comms opt-in.' ),
			),
			'additionalProperties' => array(
				'description' => self::ADDITIONAL_PROPERTIES_DESCRIPTION,
			),
		);
		if ( $require_id ) {
			$schema['required'][] = 'id';
			$schema['properties']['id'] = array( 'type' => 'string', 'description' => 'Resource ID. Only used by routes where the ID is not in the path.' );
		}
		return apply_filters( 'em_api_event_input_schema', $schema, $require_id );
	}

	public static function ticket_input( $require_id = false, $require_event_id = false ) {
		$schema = array(
			'type'     => 'object',
			'required' => array( 'ticket_name' ),
			'properties' => array(
				'ticket_id'           => array( 'type' => 'integer', 'description' => 'Existing ticket ID (omit for new tickets). When sent inside `em_tickets[<key>]`, identifies the row to update; new tickets use a positional key and leave this empty.' ),
				'event_id'            => array( 'type' => 'string',  'description' => 'Owning event ID. Auto-populated when the ticket is nested under an event POST/PATCH; required when sending to `/tickets/{id}` directly.' ),
				'ticket_name'         => array( 'type' => 'string',  'description' => 'Ticket display name. Required.' ),
				'ticket_description'  => array( 'type' => 'string',  'description' => 'Long-form ticket description (e.g. what\'s included). Accepts HTML.' ),
				'ticket_status'       => array( 'type' => 'integer', 'description' => '`1` = bookable, `0` = disabled. Defaults to `0` (disabled) if omitted — set explicitly to `1` to make tickets bookable.' ),
				'ticket_price'        => array( 'type' => 'number',  'description' => 'Ticket price in the site currency. `0` = free.' ),
				'ticket_spaces'       => array( 'type' => 'integer', 'minimum' => 0, 'description' => 'Total spaces available at this ticket. `0` = unlimited (subject to `event_spaces`).' ),
				'ticket_min'          => array( 'type' => 'integer', 'minimum' => 0, 'description' => 'Minimum spaces a single booking must request at this ticket.' ),
				'ticket_max'          => array( 'type' => 'integer', 'minimum' => 0, 'description' => 'Maximum spaces a single booking may request at this ticket. `0` = inherit `event_rsvp_spaces`.' ),
				'ticket_required'     => array( 'type' => 'boolean','description' => 'When true, every booking must include at least `ticket_min` spaces at this ticket.' ),
				'ticket_type'         => array( 'type' => 'string', 'enum' => array( 'members', 'guests' ), 'description' => 'Audience restriction: `members` (logged-in users; see `ticket_members_roles`), `guests` (not-logged-in only), or omit for all.' ),
				'ticket_members_roles'=> array( 'type' => 'array', 'items' => array( 'type' => 'string' ), 'description' => 'WP role slugs allowed to book when `ticket_type` is `members`.' ),
				'ticket_start'        => array( 'type' => 'string', 'description' => 'When this ticket becomes available (datetime string, partners with `ticket_start_time`).' ),
				'ticket_end'          => array( 'type' => 'string', 'description' => 'When this ticket stops being available.' ),
				'ticket_start_time'   => array( 'type' => 'string', 'description' => 'Time-of-day partner for `ticket_start` (same formats as `event_start_time`).' ),
				'ticket_end_time'     => array( 'type' => 'string', 'description' => 'Time-of-day partner for `ticket_end`.' ),
				'ticket_order'        => array( 'type' => 'integer', 'description' => 'Display sort index (lowest first).' ),
				'delete'              => array( 'type' => 'string', 'description' => 'WP nonce required by `EM_Tickets::get_post()` to delete this ticket row when sent inside `em_tickets`.' ),
			),
			'additionalProperties' => array(
				'description' => self::ADDITIONAL_PROPERTIES_DESCRIPTION,
			),
		);
		$required = array( 'ticket_name' );
		if ( $require_id )       $required[] = 'ticket_id';
		if ( $require_event_id ) $required[] = 'event_id';
		$schema['required'] = array_values( array_unique( $required ) );
		return $schema;
	}

	public static function location_input( $require_id = false ) {
		$schema = array(
			'type'     => 'object',
			'required' => array( 'location_name', 'location_address', 'location_town', 'location_country' ),
			'properties' => array(
				'location_name'      => array( 'type' => 'string', 'description' => 'Display name of the venue. Required.' ),
				'content'            => array( 'type' => 'string', 'description' => 'Long-form venue description. Accepts HTML.' ),
				'post_status'        => array( 'type' => 'string', 'enum' => array( 'publish', 'pending', 'draft', 'private' ), 'description' => 'WP post status. `publish` requires the `publish_locations` capability.' ),
				'location_address'   => array( 'type' => 'string', 'description' => 'Street address. Required.' ),
				'location_town'      => array( 'type' => 'string', 'description' => 'Town or city. Required.' ),
				'location_state'     => array( 'type' => 'string', 'description' => 'State, province, or county.' ),
				'location_postcode'  => array( 'type' => 'string', 'description' => 'Postal or ZIP code.' ),
				'location_region'    => array( 'type' => 'string', 'description' => 'Region label (free-form, used for filtering).' ),
				'location_country'   => array( 'type' => 'string', 'description' => 'ISO 3166-1 alpha-2 country code (e.g. `GB`, `US`). Required.' ),
				'location_latitude'  => array( 'type' => 'number', 'description' => 'WGS-84 latitude.' ),
				'location_longitude' => array( 'type' => 'number', 'description' => 'WGS-84 longitude.' ),
				'featured_image'     => static::image_assignment_input( 'WordPress featured image for the location. Accepts an attachment ID, a public URL (sideloaded), an object with `source_url` / `content_base64` / `file`, or `null` to clear. Sets `_thumbnail_id` on the underlying CPT.' ),
				'featured_image_alt' => array( 'type' => 'string', 'description' => 'Alt text applied to the featured image attachment (`_wp_attachment_image_alt`). Only takes effect when `featured_image` is also provided.' ),
				'em_attributes' => array(
					'type'        => 'object',
					'description' => 'Custom location attributes, keyed by attribute label as configured under Events > Settings > Attributes.',
					'additionalProperties' => true,
				),
				'data_privacy_consent' => array( 'type' => 'boolean', 'description' => 'Privacy-policy acknowledgement, required when the privacy add-on is configured to enforce it.' ),
				'data_comms_consent'   => array( 'type' => 'boolean', 'description' => 'Marketing/comms opt-in.' ),
			),
			'additionalProperties' => array(
				'description' => self::ADDITIONAL_PROPERTIES_DESCRIPTION,
			),
		);
		if ( $require_id ) {
			$schema['required'][] = 'id';
			$schema['properties']['id'] = array( 'type' => 'integer', 'description' => 'Resource ID. Only used by routes where the ID is not in the path.' );
		}
		return $schema;
	}

	public static function booking_input( $require_id = false ) {
		$schema = array(
			'type'     => 'object',
			'required' => array( 'event_id', 'em_tickets' ),
			'properties' => array(
				'event_id'   => array( 'type' => 'string',  'description' => 'Event the booking is being made against. Required.' ),
				'em_tickets' => array(
					'type'        => 'object',
					'description' => 'Tickets being booked. Object keyed by ticket ID (the real `ticket_id`, not a positional index). Value: `{ spaces: integer, ticket_bookings?: array }`. `ticket_bookings[i].attendee` carries per-attendee form-field values when the Pro `bookings-form` add-on is active. Required.',
					'additionalProperties' => true,
				),
				'user_name'   => array( 'type' => 'string', 'description' => 'Booker\'s display name. ::pro:: With Events Manager Pro, an authenticated manager supplying `user_name` + `user_email` books on behalf of that guest (the booking is attributed to them, not to your account). Without Pro the booking is always attributed to the authenticated account and this field is ignored for attribution.' ),
				'user_email'  => array( 'type' => 'string', 'format' => 'email', 'description' => 'Booker\'s email address, paired with `user_name`. ::pro:: Used by Pro to book on behalf of a guest (stored as a guest, no WP user account created, unless you pass `person_id`). Ignored for attribution without Pro.' ),
				'dbem_phone'  => array( 'type' => 'string', 'description' => 'Booker\'s phone number. Legacy field name — the `dbem_` prefix matches EM core\'s $_POST contract.' ),
				'person'      => array(
					'type'        => 'object',
					'description' => '::pro:: Structured booker identity, an alternative to the flat `user_name`/`user_email`/`dbem_phone` fields. `{ name|first_name|last_name, email, phone }`. When an Events Manager Pro manager supplies this, the booking is attributed to this guest rather than to the calling account (no WP user is created). Requires Pro; without it, booking-on-behalf is not available and this is ignored.',
					'properties'  => array(
						'name'       => array( 'type' => 'string', 'description' => 'Full display name. Or send `first_name`/`last_name` and a name is composed from them.' ),
						'first_name' => array( 'type' => 'string' ),
						'last_name'  => array( 'type' => 'string' ),
						'email'      => array( 'type' => 'string', 'format' => 'email' ),
						'phone'      => array( 'type' => 'string' ),
					),
				),
				'dbem_country'=> array( 'type' => 'string', 'description' => 'Booker\'s country (ISO 3166-1 alpha-2). Optional, used by some Pro forms.' ),

				'booking_comment'      => array( 'type' => 'string',  'description' => 'Free-text note attached to the booking.' ),
				'gateway'              => array( 'type' => 'string',  'description' => 'Payment gateway slug (e.g. `offline`, `stripe_checkout`, `paypal_advanced`). See the gateway introspection endpoint for the active list.' ),
				'coupon_code'          => array( 'type' => 'string',  'description' => 'Promotional discount code to apply to this booking. ::pro::' ),
				'waitlist'             => array( 'type' => 'boolean', 'description' => '::pro:: Set to `true` to opt this booking into the waitlist when the event is full.' ),
				'waitlist_spaces'      => array( 'type' => 'integer', 'minimum' => 1, 'description' => '::pro:: Spaces requested when joining the waitlist.' ),
				'waitlist_booking_uuid'=> array( 'type' => 'string',  'description' => '::pro:: UUID of an existing waitlist booking being promoted to a real booking.' ),

				'donation_amount'        => array( 'type' => 'string',  'description' => '::pro:: (donations) Optional donation added on top of the ticket cost.' ),
				'extra_charge'           => array( 'type' => 'string',  'description' => '::pro:: (extra-charges) Selected extra-charge option.' ),
				'terms_agreement'        => array( 'type' => 'boolean', 'description' => 'Terms-and-conditions acknowledgement, required by the public booking form when configured.' ),
				'recurrence_timezone'    => array( 'type' => 'string',  'description' => 'Timezone to interpret the booking against for a specific occurrence of a recurring event.' ),

				'booking'        => array( 'type' => 'object', 'description' => '::pro:: (bookings-form) Booking-form field values. Flattened into `$_REQUEST` server-side before `EM_Booking::get_post()` so the form add-on reads them under their configured field slugs.' ),
				'booking_fields' => array( 'type' => 'object', 'description' => '::pro:: (bookings-form) Alias of `booking`. Kept for back-compat with older clients.' ),
				'registration'   => array( 'type' => 'object', 'description' => 'Booking-form fields that map to the WordPress user registration (name / email / etc.). Flattened into `$_REQUEST`.' ),
				'send_email'     => array( 'type' => 'boolean', 'description' => 'When true (default), EM sends the configured booking-confirmation email after save.' ),

				// Admin-only — stripped server-side for callers without `manage_bookings`.
				'person_id'              => array( 'type' => 'integer', 'description' => '::pro:: Admin-only (Events Manager Pro). Assigns the booking to an existing user ID instead of the authenticated caller. Ignored without Pro.' ),
				'booking_status'         => array( 'type' => 'integer', 'description' => 'Admin-only (requires booking-management capability). Sets the booking status (0 pending, 1 approved, 2 rejected, 3 cancelled, 5 awaiting online payment — see `set_booking_status`). On create, a payment gateway may assign its own initial status (e.g. the offline gateway sets 5); this field is re-applied afterwards so the booking ends up in the status you asked for. Status-change emails are NOT sent for this unless you also pass `send_email: true`.' ),
				'booking_tax_rate'       => array( 'type' => 'number',  'description' => 'Admin-only. Override the booking\'s tax rate (decimal, e.g. `0.20` = 20%).' ),
				'manual_booking'         => array( 'type' => 'string',  'description' => 'Admin-only. Nonce that triggers the admin manual-booking flow (bypasses some public-form validations).' ),
				'manual_booking_confirm' => array( 'type' => 'boolean', 'description' => 'Admin-only. Confirms the booking immediately after creation.' ),
				'manual_booking_override'=> array( 'type' => 'boolean', 'description' => 'Admin-only. Bypasses availability / capacity / member-only restrictions.' ),
				'payment_amount'         => array( 'type' => 'string',  'description' => 'Admin-only. Record an upfront payment amount against the booking.' ),
				'payment_full'           => array( 'type' => 'boolean', 'description' => 'Admin-only. Mark the booking as fully paid (skips outstanding-balance accounting).' ),

				'data_privacy_consent' => array( 'type' => 'boolean', 'description' => 'Privacy-policy acknowledgement, required when the privacy add-on is configured to enforce it.' ),
				'data_comms_consent'   => array( 'type' => 'boolean', 'description' => 'Marketing/comms opt-in.' ),
			),
			'additionalProperties' => array(
				'description' => self::ADDITIONAL_PROPERTIES_DESCRIPTION,
			),
		);
		if ( $require_id ) {
			$schema['required'][] = 'id';
			$schema['properties']['id'] = array( 'type' => 'integer', 'description' => 'Resource ID. Only used by routes where the ID is not in the path.' );
		}
		return $schema;
	}

	public static function booking_status_input() {
		return array(
			'type'     => 'object',
			'required' => array( 'id', 'status' ),
			'properties' => array(
				// Over REST the booking ID comes from the path (/bookings/{id}/status), but MCP abilities have no path component — every parameter must be declared here or the client can't supply it. Without this the MCP tool could set a status but never say which booking, so every call 404'd.
				'id'            => array( 'type' => array( 'integer', 'string' ), 'description' => 'Booking ID (integer) or booking UUID (32-char hex). Required. (Over REST this comes from the URL path instead.)' ),
				'status'        => array( 'type' => 'integer', 'description' => 'New booking status code. See `EM_Booking::$status_array` for the enum (0 pending, 1 approved, 2 rejected, 3 cancelled, etc.). Required.' ),
				'send_email'    => array( 'type' => 'boolean', 'description' => 'When true (default), sends the configured status-change email.' ),
				'ignore_spaces' => array( 'type' => 'boolean', 'description' => 'When true, allow the status change even if the event\'s spaces are already exhausted.' ),
			),
		);
	}

	public static function term_input( $require_id = false ) {
		$schema = array(
			'type'     => 'object',
			'required' => array( 'name' ),
			'properties' => array(
				'name'        => array( 'type' => 'string',  'description' => 'Term display name. Required.' ),
				'slug'        => array( 'type' => 'string',  'description' => 'URL-friendly slug. Auto-generated from `name` if omitted.' ),
				'description' => array( 'type' => 'string',  'description' => 'Long-form term description.' ),
				'parent'      => array( 'type' => 'integer', 'description' => 'Parent term ID for hierarchical taxonomies (categories).' ),
				'color'       => array( 'type' => array( 'string', 'null' ), 'description' => 'Hex colour for term-coloured UI (e.g. `#80b538`). Stored under the EM meta key `{taxonomy}-bgcolor`. Pass `null` to clear.' ),
				'image'       => static::image_assignment_input( 'Term image. Accepts an attachment ID, public URL (sideloaded), media-upload object, or `null` to clear. Stored under `{taxonomy}-image` (URL) and `{taxonomy}-image-id` (attachment ID).' ),
			),
			'additionalProperties' => array(
				'description' => self::ADDITIONAL_PROPERTIES_DESCRIPTION,
			),
		);
		if ( $require_id ) {
			$schema['required'][] = 'id';
			$schema['properties']['id'] = array( 'type' => 'integer', 'description' => 'Term ID. Only used by routes where the ID is not in the path.' );
		}
		return $schema;
	}

	public static function object_output() {
		return array( 'type' => 'object' );
	}

	public static function collection_output() {
		return array(
			'type' => 'object',
			'properties' => array(
				'items'      => array( 'type' => 'array', 'items' => array( 'type' => 'object' ) ),
				'pagination' => array( 'type' => 'object' ),
			),
		);
	}
}
