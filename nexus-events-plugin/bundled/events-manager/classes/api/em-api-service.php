<?php
namespace EM\API;

class Service {

	public static function list_events( $params = array() ) {
		$params = Utils::normalize_input( $params );
		$accepted = array( 'search', 'scope', 'status', 'active_status', 'cancelled', 'active', 'category', 'tag', 'location', 'location_id', 'town', 'state', 'country', 'region', 'near', 'near_unit', 'near_distance', 'event_type', 'event_archetype', 'orderby', 'order', 'blog', 'private', 'private_only', 'timeslots' );
		$args = Utils::collection_args( $params, Utils::pick_search_args( $params, $accepted ) );
		if ( empty( $params['context'] ) || $params['context'] !== 'edit' || !current_user_can( 'edit_others_events' ) ) {
			$args['private'] = current_user_can( 'read_private_events' );
			if ( empty( $params['status'] ) ) {
				$args['status'] = 1;
			}
		}
		$events = \EM_Events::get( $args );
		// Snapshot the matched-row count now, before the loop below: prepare_event() -> EM_Event::to_api() runs a nested EM_Events::get() (recurrence lookup) that overwrites the EM_Events::$num_rows_found global, so reading it after the loop returns the last page-event's nested-query count instead of ours — wrong, and orderby-dependent because it's whichever event sorts last. See linked issue.
		$total = (int) \EM_Events::$num_rows_found;
		$items = array();
		foreach ( $events as $EM_Event ) {
			// The query layer only knows about event_status/event_private, so a password-protected event still matches here and would be serialized with its raw content.
			if ( $EM_Event->password_required() ) continue;
			$items[] = static::prepare_event( $EM_Event, $params['context'] ?? 'view' );
		}
		return array(
			'items' => $items,
			'pagination' => Utils::pagination( $total, $args['page'], $args['limit'] ),
		);
	}

	public static function get_event( $id, $context = 'view' ) {
		$EM_Event = em_get_event( $id );
		if ( !$EM_Event || !$EM_Event->get_id() ) {
			return Utils::error( 'em_api_event_not_found', __( 'Event not found.', 'events-manager' ), 404 );
		}
		if ( !static::can_read_event( $EM_Event, $context ) ) {
			return Utils::error( 'em_api_event_forbidden', __( 'You do not have permission to view this event.', 'events-manager' ), 403 );
		}
		return static::prepare_event( $EM_Event, $context );
	}

	public static function get_event_availability( $id ) {
		$EM_Event = em_get_event( $id );
		if ( !$EM_Event || !$EM_Event->get_id() ) {
			return Utils::error( 'em_api_event_not_found', __( 'Event not found.', 'events-manager' ), 404 );
		}
		if ( !static::can_read_event( $EM_Event ) ) {
			return Utils::error( 'em_api_event_forbidden', __( 'You do not have permission to view this event.', 'events-manager' ), 403 );
		}
		$EM_Bookings = $EM_Event->get_bookings();
		$tickets = array();
		foreach ( $EM_Event->get_tickets() as $EM_Ticket ) {
			$tickets[] = array(
				'id' => absint( $EM_Ticket->ticket_id ),
				'name' => $EM_Ticket->ticket_name,
				'description' => $EM_Ticket->ticket_description,
				'price' => $EM_Ticket->get_price(),
				'spaces' => $EM_Ticket->get_spaces(),
				'available_spaces' => $EM_Ticket->get_available_spaces(),
				'available' => $EM_Ticket->is_available(),
			);
		}
		return apply_filters( 'em_api_event_availability', array(
			'event_id' => $EM_Event->get_event_uid(),
			'bookings_enabled' => !empty( $EM_Event->event_rsvp ),
			'open' => $EM_Bookings->is_open(),
			'spaces' => $EM_Bookings->get_spaces(),
			'available_spaces' => $EM_Bookings->get_available_spaces(),
			'tickets' => $tickets,
		), $EM_Event );
	}

	/**
	 * Describe everything an agent needs to create a booking for one event:
	 * required fields, where they live in the payload, payment options, and a
	 * ready-to-submit example. Pro augments via the em_api_booking_requirements
	 * filter (custom booking/attendee form fields, gateways).
	 */
	public static function get_booking_requirements( $id ) {
		$EM_Event = em_get_event( $id );
		if ( !$EM_Event || !$EM_Event->get_id() ) {
			return Utils::error( 'em_api_event_not_found', __( 'Event not found.', 'events-manager' ), 404 );
		}
		if ( !static::can_read_event( $EM_Event ) ) {
			return Utils::error( 'em_api_event_forbidden', __( 'You do not have permission to view this event.', 'events-manager' ), 403 );
		}
		$EM_Bookings = $EM_Event->get_bookings();
		$tickets = array();
		foreach ( $EM_Event->get_tickets() as $EM_Ticket ) {
			$price = (float) $EM_Ticket->get_price();
			$tickets[] = array(
				'id'               => absint( $EM_Ticket->ticket_id ),
				'name'             => $EM_Ticket->ticket_name,
				'price'            => $price,
				'is_free'          => $price <= 0,
				'available_spaces' => $EM_Ticket->get_available_spaces(),
				'min'              => !empty( $EM_Ticket->ticket_min ) ? absint( $EM_Ticket->ticket_min ) : 1,
				'max'              => !empty( $EM_Ticket->ticket_max ) ? absint( $EM_Ticket->ticket_max ) : null,
			);
		}
		$payload = array(
			'event_id'         => $EM_Event->get_event_uid(),
			'bookings_open'    => !empty( $EM_Event->event_rsvp ) && $EM_Bookings->is_open(),
			'spaces_available' => $EM_Bookings->get_available_spaces(),
			'tickets'          => $tickets,
			// Core defaults; Pro replaces booking_fields with the custom form and adds attendee_fields + payment.
			'booking_fields'   => array(
				static::with_field_validation( array( 'field' => 'user_name',  'label' => __( 'Name', 'events-manager' ),  'type' => 'text',  'required' => true, 'location' => 'booking.user_name' ), $EM_Event ),
				static::with_field_validation( array( 'field' => 'user_email', 'label' => __( 'Email', 'events-manager' ), 'type' => 'email', 'required' => true, 'location' => 'booking.user_email' ), $EM_Event ),
			),
			'attendee_fields'  => array(),
			'payment'          => array( 'required_when' => 'never', 'field' => 'gateway', 'active_gateways' => array() ),
			'notes'            => array(),
		);
		$payload = apply_filters( 'em_api_booking_requirements', $payload, $EM_Event );
		$payload['example_payload'] = static::build_booking_example( $payload );
		// When the form has optional fields beyond the required minimum, also emit a full example so a client can see every field at its correct location (especially the per-attendee nesting). It's a structure reference, not data to submit — values are illustrative.
		$full_example = static::build_booking_example( $payload, true );
		if ( $full_example != $payload['example_payload'] ) {
			$payload['example_payload_full'] = $full_example;
			$payload['notes'][] = __( '`example_payload` is the minimal valid booking (required fields only). `example_payload_full` additionally shows every optional field at its correct location — the values are illustrative placeholders, so replace them with the booker\'s real input and omit any field they did not provide.', 'events-manager' );
		}
		return $payload;
	}

	/**
	 * Attaches a `validation` block to a single requirement-field entry, with format/pattern/example/messages inferred from the field type and event context. Pro overlays its own field-specific overrides (custom regex, custom error messages) by calling this and merging. Returns the field entry (passed through with `validation` added). Safe to call on any shape — fields that have no useful validation just get a minimal `validation: { required_message?, invalid_message? }` block.
	 *
	 * @param array     $field    Requirement-field entry being assembled.
	 * @param \EM_Event $EM_Event Event we're describing requirements for (used for country context on phone fields, etc.).
	 * @return array
	 */
	public static function with_field_validation( $field, $EM_Event = null ) {
		$field['validation'] = static::build_field_validation( $field, $EM_Event );
		return $field;
	}

	/**
	 * Build the validation metadata block for one requirement-field entry. Filterable via `em_api_field_validation` so add-ons or sites can refine the schema per field type without forking the service.
	 *
	 * @return array
	 */
	public static function build_field_validation( $field, $EM_Event = null ) {
		$type = isset( $field['type'] ) ? (string) $field['type'] : 'text';
		$label = isset( $field['label'] ) ? (string) $field['label'] : ( isset( $field['field'] ) ? (string) $field['field'] : '' );
		$validation = array(
			/* translators: %s is the human-readable field label, e.g. "Phone" */
			'required_message' => sprintf( __( '%s is required.', 'events-manager' ), $label ?: __( 'Value', 'events-manager' ) ),
		);
		switch ( $type ) {
			case 'email':
			case 'user_email':
				$validation['format']          = 'email';
				$validation['pattern']         = '^[^\\s@]+@[^\\s@]+\\.[^\\s@]+$';
				$validation['example']         = 'jane@example.com';
				$validation['invalid_message'] = __( 'Please enter a valid email address.', 'events-manager' );
				break;
			case 'tel':
			case 'dbem_phone':
				$country = static::resolve_event_country( $EM_Event );
				$phone_enabled = class_exists( '\\EM\\Phone' ) && \EM\Phone::is_enabled();
				if ( $phone_enabled ) {
					$validation['format']           = 'E.164';
					$validation['pattern']          = '^\\+[1-9]\\d{6,14}$';
					$validation['preferred_format'] = 'E.164';
					$validation['invalid_message']  = __( 'Please provide a valid phone number.', 'events-manager' );
					$validation['human_hint']       = __( 'Use international format starting with `+` and a country code, e.g. `+447400123456`.', 'events-manager' );
					$example = \EM\Phone::example_number( $country );
					if ( $example ) {
						$validation['example'] = $example;
					}
				} else {
					$validation['format']          = 'tel';
					$validation['example']         = $country === 'US' ? '+15551234567' : '+447400123456';
					$validation['invalid_message'] = __( 'Please provide a valid phone number.', 'events-manager' );
				}
				if ( $country ) {
					$validation['country_context'] = $country;
				}
				break;
			case 'url':
				$validation['format']          = 'uri';
				$validation['pattern']         = '^https?://.+';
				$validation['example']         = 'https://example.com';
				$validation['invalid_message'] = __( 'Please enter a valid URL.', 'events-manager' );
				break;
			case 'number':
				$validation['format']          = 'integer';
				$validation['pattern']         = '^-?\\d+$';
				$validation['example']         = '1';
				break;
			case 'date':
				$validation['format']  = 'date';
				$validation['pattern'] = '^\\d{4}-\\d{2}-\\d{2}$';
				$validation['example'] = gmdate( 'Y-m-d' );
				break;
		}
		return apply_filters( 'em_api_field_validation', $validation, $field, $EM_Event );
	}

	/**
	 * Best-effort ISO 3166-1 alpha-2 country code for an event, used as default context when building country-aware field examples (phone numbers, etc.).
	 */
	protected static function resolve_event_country( $EM_Event = null ) {
		if ( $EM_Event && method_exists( $EM_Event, 'get_location' ) ) {
			$EM_Location = $EM_Event->get_location();
			if ( $EM_Location && !empty( $EM_Location->location_country ) ) {
				return strtoupper( (string) $EM_Location->location_country );
			}
		}
		$site_default = em_get_option( 'dbem_location_default_country' );
		if ( $site_default ) {
			return strtoupper( (string) $site_default );
		}
		$phone_default = em_get_option( 'dbem_phone_default_country' );
		return $phone_default ? strtoupper( (string) $phone_default ) : '';
	}

	/**
	 * Build a ready-to-submit example booking payload from the requirements.
	 *
	 * With $include_optional = false (default) only required fields are emitted — the minimal valid booking, safe for a client to copy and fill. With $include_optional = true every field is emitted (a full structure reference). Upload fields are always skipped: a file can't be expressed as a JSON scalar, so a placeholder would mislead — they stay visible in booking_fields/attendee_fields with their own metadata.
	 */
	protected static function build_booking_example( $payload, $include_optional = false ) {
		$example = array( 'event_id' => (string) ( $payload['event_id'] ?? '' ) );
		if ( !empty( $payload['payment']['active_gateways'] ) ) {
			$slugs = array_column( $payload['payment']['active_gateways'], 'slug' );
			$example['gateway'] = in_array( 'offline', $slugs, true ) ? 'offline' : reset( $slugs );
		}
		$booking = array();
		foreach ( (array) ( $payload['booking_fields'] ?? array() ) as $field ) {
			if ( ( !$include_optional && empty( $field['required'] ) ) || ( $field['type'] ?? '' ) === 'upload' ) continue;
			$booking[ $field['field'] ] = static::booking_example_value( $field );
		}
		if ( $booking ) {
			$example['booking'] = $booking;
		}
		$ticket = $payload['tickets'][0] ?? null;
		if ( $ticket ) {
			$ticket_entry = array( 'spaces' => 1 );
			$attendee = array();
			foreach ( (array) ( $payload['attendee_fields'] ?? array() ) as $field ) {
				if ( ( !$include_optional && empty( $field['required'] ) ) || ( $field['type'] ?? '' ) === 'upload' ) continue;
				$attendee[ $field['field'] ] = static::booking_example_value( $field );
			}
			if ( $attendee ) {
				$ticket_entry['ticket_bookings'] = array( array( 'attendee' => $attendee ) );
			}
			$example['em_tickets'] = array( (string) $ticket['id'] => $ticket_entry );
		}
		return $example;
	}

	protected static function booking_example_value( $field ) {
		// Prefer a validator-aware example when build_field_validation set one
		// (the only path that gets phone numbers right per country).
		if ( !empty( $field['validation']['example'] ) ) {
			return (string) $field['validation']['example'];
		}
		if ( !empty( $field['options'] ) && is_array( $field['options'] ) ) {
			return reset( $field['options'] );
		}
		$id = (string) ( $field['field'] ?? '' );
		switch ( $field['type'] ?? 'text' ) {
			case 'user_login': return 'janedoe';
			case 'email':      return 'jane@example.com';
			case 'tel':        return '+447400123456';
			case 'number':     return '1';
			case 'date':       return gmdate( 'Y-m-d' );
			case 'checkbox':   return '1';
		}
		if ( strpos( $id, 'email' ) !== false ) return 'jane@example.com';
		if ( strpos( $id, 'phone' ) !== false ) return '+447400123456';
		if ( strpos( $id, 'login' ) !== false ) return 'janedoe';
		if ( strpos( $id, 'first' ) !== false ) return 'Jane';
		if ( strpos( $id, 'last' )  !== false ) return 'Doe';
		return 'Jane Doe';
	}

	public static function create_event( $data ) {
		return static::save_event( $data );
	}

	public static function update_event( $id, $data ) {
		return static::save_event( $data, $id );
	}

	public static function save_event( $data, $id = 0 ) {
		$data = Utils::normalize_input( $data );
		$EM_Event = $id ? em_get_event( $id ) : new \EM_Event();
		if ( $id && ( !$EM_Event || !$EM_Event->get_id() ) ) {
			return Utils::error( 'em_api_event_not_found', __( 'Event not found.', 'events-manager' ), 404 );
		}
		if ( !$EM_Event->can_manage( 'edit_events', 'edit_others_events' ) ) {
			return Utils::object_error( 'em_api_event_forbidden', $EM_Event, __( 'You do not have permission to save this event.', 'events-manager' ), 403 );
		}
		if ( !empty( $data['em_tickets'] ) && !$EM_Event->can_manage( 'manage_bookings', 'manage_others_bookings' ) ) {
			return Utils::object_error( 'em_api_ticket_forbidden', $EM_Event, __( 'You do not have permission to manage tickets for this event.', 'events-manager' ), 403 );
		}
		do_action( 'em_api_event_save_pre', $EM_Event, $data, $id );
		// For partial updates, pre-load current event state so EM_Event::get_post()
		// (which is destructive on missing $_POST keys) doesn't wipe untouched fields.
		$base = $id ? $EM_Event->to_request_data() : array();
		// Translate API-friendly flat times to the nested event_timeranges[0] shape EM expects.
		$data = static::translate_event_input( $data );
		// Translate the recurrence/timeslot shape (recurrences.sets[] + when.timeranges[]) into the internal form-array.
		$data = static::translate_recurrence_input( $data );
		// to_request_data() re-emits the event's time as a timerange with no timerange_id.
		// On update, timeranges::get_post() can't match it to the existing row, so it appends
		// a duplicate and the save fails with "Timeranges cannot overlap". Only re-post the
		// timeranges when the caller is actually changing the time, and carry the existing
		// timerange_id through so EM updates the row in place instead of duplicating it.
		if ( $id ) {
			if ( !array_key_exists( 'event_timeranges', $data ) ) {
				unset( $base['event_timeranges'] );
			} elseif ( isset( $data['event_timeranges'][0] ) && is_array( $data['event_timeranges'][0] ) && empty( $data['event_timeranges'][0]['timerange_id'] ) ) {
				$first = $EM_Event->get_timeranges()->get_first();
				if ( $first && !empty( $first->timerange_id ) ) {
					$data['event_timeranges'][0]['timerange_id'] = $first->timerange_id;
				}
			}
		}
		// Consent must travel in the request data, not be pre-set on the object: EM core's consent handler reads $_REQUEST[data_privacy_consent] during get_post (cpt_get_post on em_event_get_post_meta) and get_post rebuilds event_attributes from the request, wiping anything set beforehand. Defaults to granted so admin event creation doesn't trip the privacy-consent validator that fires when the site requires it. Mirrors what booking_request_data already does for bookings.
		$request_data = static::apply_consent_to_request_data( static::normalize_em_tickets_keys( array_merge( $base, $data ) ), $data, 'event' );
		$valid = Utils::with_request_data( $request_data, function() use ( $EM_Event, $data ) {
			if ( !$EM_Event->get_post( true ) ) {
				return false;
			}
			static::apply_force_status( $EM_Event, $data, 'event' );
			return true;
		} );
		if ( !$valid ) {
			return Utils::object_error( 'em_api_event_invalid', $EM_Event, __( 'Event data is invalid.', 'events-manager' ), 400 );
		}
		if ( !$EM_Event->save() ) {
			return Utils::object_error( 'em_api_event_save_failed', $EM_Event, __( 'Event could not be saved.', 'events-manager' ), 500 );
		}
		static::save_event_terms( $EM_Event, $data );
		// The event is saved and valid at this point. A featured-image failure (e.g. the source URL blocks hotlinking, or the file isn't a valid image) is non-fatal — don't 400 the whole create and strand a created-but-imageless event. Keep the event, surface a warning naming the problem so the caller can retry just the image.
		$featured_result = static::apply_featured_image( $EM_Event->post_id ?? 0, $data );
		$warnings = is_wp_error( $featured_result ) ? array( static::featured_image_warning( $featured_result ) ) : array();
		do_action( 'em_api_event_save', $EM_Event, $data, $id );
		return static::with_warnings( static::prepare_event( $EM_Event, 'edit' ), $warnings );
	}

	public static function delete_event( $id, $force = false ) {
		$EM_Event = em_get_event( $id );
		if ( !$EM_Event || !$EM_Event->get_id() ) {
			return Utils::error( 'em_api_event_not_found', __( 'Event not found.', 'events-manager' ), 404 );
		}
		if ( !$EM_Event->can_manage( 'delete_events', 'delete_others_events' ) ) {
			return Utils::object_error( 'em_api_event_forbidden', $EM_Event, __( 'You do not have permission to delete this event.', 'events-manager' ), 403 );
		}
		$previous = static::prepare_event( $EM_Event, 'edit' );
		if ( !$EM_Event->delete( Utils::is_truthy( $force ) ) ) {
			// Orphan fallback: EM_Event::delete() returns false and strands the em_events row when the WP post is already gone and EM's own orphaned_event detection didn't engage (e.g. a stale post_id or an object-cache race).
			// That row would otherwise return a blank 500 on every retry and never clear, so detect the missing post and remove the row directly via delete_meta(), leaving the normal delete path untouched.
			if ( $EM_Event->event_id && ( empty( $EM_Event->post_id ) || !get_post( $EM_Event->post_id ) ) && $EM_Event->delete_meta() ) {
				wp_cache_delete( $EM_Event->event_id, 'em_events' );
				return array( 'deleted' => true, 'orphaned' => true, 'previous' => $previous );
			}
			return Utils::object_error( 'em_api_event_delete_failed', $EM_Event, __( 'Event could not be deleted.', 'events-manager' ), 500 );
		}
		return array( 'deleted' => true, 'previous' => $previous );
	}

	public static function list_event_tickets( $id, $params = array() ) {
		$EM_Event = em_get_event( $id );
		if ( !$EM_Event || !$EM_Event->get_id() ) {
			return Utils::error( 'em_api_event_not_found', __( 'Event not found.', 'events-manager' ), 404 );
		}
		$params = Utils::normalize_input( $params );
		if ( !static::can_read_event( $EM_Event, $params['context'] ?? 'view' ) ) {
			return Utils::error( 'em_api_event_forbidden', __( 'You do not have permission to view this event.', 'events-manager' ), 403 );
		}
		$items = array();
		$can_manage = $EM_Event->can_manage( 'manage_bookings', 'manage_others_bookings' );
		foreach ( $EM_Event->get_tickets( true ) as $EM_Ticket ) {
			// Readers get what the booking form would show them; hidden and unavailable tickets are a manager's view.
			if ( !$can_manage && !$EM_Ticket->is_displayable() ) continue;
			$items[] = static::prepare_ticket( $EM_Ticket, $params['context'] ?? 'view' );
		}
		return array(
			'items' => $items,
			'pagination' => Utils::pagination( count( $items ), 1, max( 1, count( $items ) ) ),
		);
	}

	public static function get_ticket( $id, $context = 'view' ) {
		$EM_Ticket = static::get_ticket_object( $id );
		if ( is_wp_error( $EM_Ticket ) ) return $EM_Ticket;
		if ( !static::can_read_event( $EM_Ticket->get_event(), $context ) ) {
			return Utils::error( 'em_api_ticket_forbidden', __( 'You do not have permission to view this ticket.', 'events-manager' ), 403 );
		}
		if ( !$EM_Ticket->can_manage() && !$EM_Ticket->is_displayable() ) {
			return Utils::error( 'em_api_ticket_not_found', __( 'Ticket not found.', 'events-manager' ), 404 );
		}
		return static::prepare_ticket( $EM_Ticket, $context );
	}

	public static function create_event_ticket( $event_id, $data ) {
		$EM_Event = em_get_event( $event_id );
		if ( !$EM_Event || !$EM_Event->get_id() ) {
			return Utils::error( 'em_api_event_not_found', __( 'Event not found.', 'events-manager' ), 404 );
		}
		if ( !$EM_Event->can_manage( 'manage_bookings', 'manage_others_bookings' ) ) {
			return Utils::object_error( 'em_api_ticket_forbidden', $EM_Event, __( 'You do not have permission to manage tickets for this event.', 'events-manager' ), 403 );
		}
		$data = Utils::normalize_input( $data );
		unset( $data['id'], $data['ticket_id'] );
		$data['event_id'] = $EM_Event->get_event_id();
		$EM_Ticket = new \EM_Ticket();
		$EM_Ticket->event = $EM_Event;
		$EM_Ticket->get_post( $data );
		if ( !$EM_Event->event_rsvp ) {
			$EM_Event->event_rsvp = 1;
			$EM_Event->save();
		}
		if ( !$EM_Ticket->save() ) {
			return Utils::object_error( 'em_api_ticket_save_failed', $EM_Ticket, __( 'Ticket could not be saved.', 'events-manager' ), 400 );
		}
		return static::prepare_ticket( $EM_Ticket, 'edit' );
	}

	public static function update_ticket( $id, $data ) {
		$EM_Ticket = static::get_ticket_object( $id );
		if ( is_wp_error( $EM_Ticket ) ) return $EM_Ticket;
		if ( !$EM_Ticket->can_manage() ) {
			return Utils::object_error( 'em_api_ticket_forbidden', $EM_Ticket, __( 'You do not have permission to update this ticket.', 'events-manager' ), 403 );
		}
		$data = Utils::normalize_input( $data );
		// An update keeps the identifiers of the record we actually authorised. EM_Ticket::get_post() reads ticket_id and event_id straight off this array, so a body carrying someone else's ticket_id re-points the UPDATE at their row, and save()'s own can_manage() re-resolves through the body's event_id, which an event the caller owns satisfies. The creation handler above strips these for the same reason.
		unset( $data['id'] );
		$data['ticket_id'] = $EM_Ticket->ticket_id;
		$data['event_id'] = $EM_Ticket->event_id;
		$EM_Ticket->get_post( $data );
		if ( !$EM_Ticket->save() ) {
			return Utils::object_error( 'em_api_ticket_save_failed', $EM_Ticket, __( 'Ticket could not be saved.', 'events-manager' ), 400 );
		}
		return static::prepare_ticket( $EM_Ticket, 'edit' );
	}

	public static function delete_ticket( $id, $force = false ) {
		$EM_Ticket = static::get_ticket_object( $id );
		if ( is_wp_error( $EM_Ticket ) ) return $EM_Ticket;
		if ( !$EM_Ticket->can_manage() ) {
			return Utils::object_error( 'em_api_ticket_forbidden', $EM_Ticket, __( 'You do not have permission to delete this ticket.', 'events-manager' ), 403 );
		}
		$previous = static::prepare_ticket( $EM_Ticket, 'edit' );
		if ( $EM_Ticket->get_bookings_count( false, true ) > 0 ) {
			return Utils::error( 'em_api_ticket_has_bookings', __( 'Tickets with bookings cannot be deleted.', 'events-manager' ), 409, array( 'previous' => $previous ) );
		}
		if ( !$EM_Ticket->delete() ) {
			return Utils::object_error( 'em_api_ticket_delete_failed', $EM_Ticket, __( 'Ticket could not be deleted.', 'events-manager' ), 500 );
		}
		return array( 'deleted' => true, 'previous' => $previous );
	}

	public static function list_locations( $params = array() ) {
		$params = Utils::normalize_input( $params );
		$accepted = array( 'search', 'scope', 'status', 'event_status', 'eventful', 'eventless', 'category', 'tag', 'town', 'state', 'country', 'region', 'near', 'near_unit', 'near_distance', 'orderby', 'order', 'blog', 'private', 'private_only' );
		$args = Utils::collection_args( $params, Utils::pick_search_args( $params, $accepted ) );
		if ( empty( $params['context'] ) || $params['context'] !== 'edit' || !current_user_can( 'edit_others_locations' ) ) {
			$args['private'] = current_user_can( 'read_private_locations' );
			if ( empty( $params['status'] ) ) {
				$args['status'] = 1;
			}
		}
		$locations = \EM_Locations::get( $args );
		$items = array();
		foreach ( $locations as $EM_Location ) {
			if ( $EM_Location->password_required() ) continue;
			$items[] = static::prepare_location( $EM_Location, $params['context'] ?? 'view' );
		}
		return array(
			'items' => $items,
			'pagination' => Utils::pagination( \EM_Locations::$num_rows_found, $args['page'], $args['limit'] ),
		);
	}

	/**
	 * Returns the list of countries, paired with their translated display names from em_get_countries(). By default returns the full ISO list so the endpoint can back a country picker on a fresh install with no locations yet.
	 *
	 * @param array $params Optional.
	 *   - `only_available` (bool): when true, narrow the result to country codes that have at least one stored location row. Useful for "what countries do I have events in?" agent queries.
	 *   - `search` (string): case-insensitive substring filter against code or name.
	 * @return array { items: [ { code, name } ] }
	 */
	public static function list_location_countries( $params = array() ) {
		$params = Utils::normalize_input( $params );
		$names = function_exists( 'em_get_countries' ) ? em_get_countries() : array();
		$only_available = !empty( $params['only_available'] ) && Utils::is_truthy( $params['only_available'] );
		if ( $only_available ) {
			global $wpdb;
			$rows = $wpdb->get_col( "SELECT DISTINCT location_country FROM " . EM_LOCATIONS_TABLE . " WHERE location_country IS NOT NULL AND location_country != '' ORDER BY location_country ASC" );
			$items = array();
			foreach ( $rows as $code ) {
				$items[] = array(
					'code' => $code,
					'name' => isset( $names[ $code ] ) ? $names[ $code ] : $code,
				);
			}
		} else {
			$items = array();
			foreach ( $names as $code => $name ) {
				// em_get_countries() prepends a blank with key 0 when its $add_blank arg is set; our call doesn't ask for it, but guard against any future caller that does.
				if ( !$code || !is_string( $code ) ) continue;
				$items[] = array( 'code' => $code, 'name' => $name );
			}
		}
		if ( !empty( $params['search'] ) ) {
			$needle = mb_strtolower( sanitize_text_field( $params['search'] ) );
			$items = array_values( array_filter( $items, function( $item ) use ( $needle ) {
				return strpos( mb_strtolower( $item['code'] ), $needle ) !== false
					|| strpos( mb_strtolower( $item['name'] ), $needle ) !== false;
			} ) );
		}
		// Sort by display name for natural alphabetical reading.
		usort( $items, function( $a, $b ) { return strcasecmp( $a['name'], $b['name'] ); } );
		return array( 'items' => $items );
	}

	/**
	 * Returns the distinct list of regions, optionally narrowed to a country.
	 */
	public static function list_location_regions( $params = array() ) {
		return static::list_location_geo_column( 'location_region', $params, array( 'country' ) );
	}

	/**
	 * Returns the distinct list of states, optionally narrowed to country and/or region.
	 */
	public static function list_location_states( $params = array() ) {
		return static::list_location_geo_column( 'location_state', $params, array( 'country', 'region' ) );
	}

	/**
	 * Returns the distinct list of towns/cities, optionally narrowed to country, region, and/or state.
	 */
	public static function list_location_towns( $params = array() ) {
		return static::list_location_geo_column( 'location_town', $params, array( 'country', 'region', 'state' ) );
	}

	/**
	 * Shared helper for the geo discovery endpoints. Returns DISTINCT non-empty values from a single location column, filtered by any of the supplied parent columns.
	 *
	 * @param string $column         The column to SELECT DISTINCT.
	 * @param array  $params         Request params; `search` narrows results, plus any of $filter_columns.
	 * @param array  $filter_columns Parent columns accepted as filters (e.g. `country`, `region`, `state`).
	 * @return array { items: [ string, ... ] }
	 */
	protected static function list_location_geo_column( $column, $params, $filter_columns ) {
		global $wpdb;
		$params = Utils::normalize_input( $params );
		$conds = array();
		foreach ( $filter_columns as $filter ) {
			if ( !empty( $params[ $filter ] ) ) {
				$conds[] = $wpdb->prepare( "location_{$filter} = %s", sanitize_text_field( $params[ $filter ] ) );
			}
		}
		if ( !empty( $params['search'] ) ) {
			$conds[] = $wpdb->prepare( "{$column} LIKE %s", '%' . $wpdb->esc_like( sanitize_text_field( $params['search'] ) ) . '%' );
		}
		$cond = $conds ? ' AND ' . implode( ' AND ', $conds ) : '';
		$sql = "SELECT DISTINCT {$column} FROM " . EM_LOCATIONS_TABLE . " WHERE {$column} IS NOT NULL AND {$column} != ''" . $cond . " ORDER BY {$column} ASC";
		$items = $wpdb->get_col( $sql );
		return array( 'items' => array_values( $items ) );
	}

	public static function get_location( $id, $context = 'view' ) {
		$EM_Location = em_get_location( absint( $id ) );
		if ( !$EM_Location || !$EM_Location->get_id() ) {
			return Utils::error( 'em_api_location_not_found', __( 'Location not found.', 'events-manager' ), 404 );
		}
		if ( !static::can_read_location( $EM_Location, $context ) ) {
			return Utils::error( 'em_api_location_forbidden', __( 'You do not have permission to view this location.', 'events-manager' ), 403 );
		}
		return static::prepare_location( $EM_Location, $context );
	}

	public static function create_location( $data ) {
		return static::save_location( $data );
	}

	public static function update_location( $id, $data ) {
		return static::save_location( $data, $id );
	}

	public static function save_location( $data, $id = 0 ) {
		$data = Utils::normalize_input( $data );
		$EM_Location = $id ? em_get_location( absint( $id ) ) : new \EM_Location();
		if ( $id && ( !$EM_Location || !$EM_Location->get_id() ) ) {
			return Utils::error( 'em_api_location_not_found', __( 'Location not found.', 'events-manager' ), 404 );
		}
		if ( !$EM_Location->can_manage( 'edit_locations', 'edit_others_locations' ) ) {
			return Utils::object_error( 'em_api_location_forbidden', $EM_Location, __( 'You do not have permission to save this location.', 'events-manager' ), 403 );
		}
		// For partial updates, pre-load current location state — same reasoning as save_event().
		$base = $id ? $EM_Location->to_request_data() : array();
		// Consent flows through the request data (see save_event() for why pre-setting the attribute doesn't survive get_post).
		$request_data = static::apply_consent_to_request_data( array_merge( $base, $data ), $data, 'location' );
		$valid = Utils::with_request_data( $request_data, function() use ( $EM_Location, $data ) {
			if ( !$EM_Location->get_post( true ) ) {
				return false;
			}
			static::apply_force_status( $EM_Location, $data, 'location' );
			return true;
		} );
		if ( !$valid ) {
			return Utils::object_error( 'em_api_location_invalid', $EM_Location, __( 'Location data is invalid.', 'events-manager' ), 400 );
		}
		if ( !$EM_Location->save() ) {
			return Utils::object_error( 'em_api_location_save_failed', $EM_Location, __( 'Location could not be saved.', 'events-manager' ), 500 );
		}
		// Non-fatal featured-image handling — same reasoning as save_event(): keep the saved location, warn rather than 400 on an image sideload failure.
		$featured_result = static::apply_featured_image( $EM_Location->post_id ?? 0, $data );
		$warnings = is_wp_error( $featured_result ) ? array( static::featured_image_warning( $featured_result ) ) : array();
		return static::with_warnings( static::prepare_location( $EM_Location, 'edit' ), $warnings );
	}

	/**
	 * Applies a `featured_image` input value to a CPT post — resolving the polymorphic shape to an attachment ID, calling set_post_thumbnail(), and optionally writing `featured_image_alt` to the attachment's alt-text meta. Returns true on success, WP_Error on failure, or null if `featured_image` was not provided (no-op so partial updates leave the existing thumbnail alone).
	 */
	protected static function apply_featured_image( $post_id, $data ) {
		$post_id = absint( $post_id );
		if ( !$post_id || !array_key_exists( 'featured_image', $data ) ) return null;
		$input = $data['featured_image'];
		if ( $input === null || $input === '' || $input === false ) {
			delete_post_thumbnail( $post_id );
			return true;
		}
		$attachment_id = static::resolve_image_input( $input, $post_id );
		if ( is_wp_error( $attachment_id ) ) return $attachment_id;
		if ( !$attachment_id ) return null;
		set_post_thumbnail( $post_id, $attachment_id );
		if ( !empty( $data['featured_image_alt'] ) ) {
			update_post_meta( $attachment_id, '_wp_attachment_image_alt', sanitize_text_field( $data['featured_image_alt'] ) );
		}
		return true;
	}

	/**
	 * Builds a structured warning entry from a featured-image WP_Error, so the response can tell the caller the image step failed (and why) without failing the whole create/update.
	 */
	protected static function featured_image_warning( $wp_error ) {
		return array(
			'field'   => 'featured_image',
			'code'    => $wp_error->get_error_code() ?: 'em_api_featured_image_failed',
			/* translators: %s: underlying error detail from the image sideload */
			'message' => sprintf( __( 'Saved, but the featured image could not be attached: %s. To fix it: call upload-media (use content_base64 if the source blocks server-side fetches, e.g. Unsplash), then either pass featured_image_for_event/featured_image_for_location on that same upload-media call, or pass the returned attachment id as featured_image to update-event / update-location.', 'events-manager' ), $wp_error->get_error_message() ),
		);
	}

	/**
	 * Attaches a non-empty `warnings` array to a prepared response. No-op (returns the response unchanged) when there are no warnings, so successful responses stay clean.
	 */
	protected static function with_warnings( $response, $warnings ) {
		if ( is_wp_error( $response ) || empty( $warnings ) || !is_array( $response ) ) {
			return $response;
		}
		$response['warnings'] = array_values( $warnings );
		return $response;
	}

	/**
	 * Returns the featured-image attachment shape for a CPT post, or null when no thumbnail is set. Used by prepare_event / prepare_location to overlay `featured_image` on top of EM's existing `to_api()` output.
	 */
	protected static function get_featured_image_for_post( $post_id ) {
		$post_id = absint( $post_id );
		if ( !$post_id ) return null;
		$thumbnail_id = get_post_thumbnail_id( $post_id );
		return $thumbnail_id ? static::prepare_attachment( $thumbnail_id ) : null;
	}

	public static function delete_location( $id, $force = false ) {
		$EM_Location = em_get_location( absint( $id ) );
		if ( !$EM_Location || !$EM_Location->get_id() ) {
			return Utils::error( 'em_api_location_not_found', __( 'Location not found.', 'events-manager' ), 404 );
		}
		if ( !$EM_Location->can_manage( 'delete_locations', 'delete_others_locations' ) ) {
			return Utils::object_error( 'em_api_location_forbidden', $EM_Location, __( 'You do not have permission to delete this location.', 'events-manager' ), 403 );
		}
		$previous = static::prepare_location( $EM_Location, 'edit' );
		if ( !$EM_Location->delete( Utils::is_truthy( $force ) ) ) {
			return Utils::object_error( 'em_api_location_delete_failed', $EM_Location, __( 'Location could not be deleted.', 'events-manager' ), 500 );
		}
		return array( 'deleted' => true, 'previous' => $previous );
	}

	public static function list_bookings( $params = array() ) {
		$params = Utils::normalize_input( $params );
		if ( !is_user_logged_in() ) {
			return Utils::error( 'em_api_booking_forbidden', __( 'You must be logged in to view bookings.', 'events-manager' ), 401 );
		}
		$accepted = array( 'search', 'scope', 'event', 'event_id', 'status', 'rsvp_status', 'person', 'ticket_id', 'booking_id', 'country', 'region', 'state', 'town', 'near', 'near_unit', 'near_distance', 'orderby', 'order', 'blog', 'timeslot_id' );
		$args = Utils::collection_args( $params, Utils::pick_search_args( $params, $accepted ) );
		if ( !current_user_can( 'manage_others_bookings' ) && !current_user_can( 'manage_bookings' ) ) {
			$args['person'] = get_current_user_id();
			$args['owner'] = get_current_user_id();
		} else {
			// Owner is passed explicitly because it overrides get_default_search(); the count below runs on these args too, so anyone who can't manage others' bookings must stay scoped to their own events or the total leaks matches across the site.
			$args['owner'] = current_user_can( 'manage_others_bookings' ) ? false : get_current_user_id();
		}
		if ( !empty( $params['event_id'] ) && empty( $args['event'] ) ) {
			$args['event'] = $params['event_id'];
		}
		$bookings = \EM_Bookings::get( $args );
		$items = array();
		foreach ( $bookings as $EM_Booking ) {
			if ( static::can_read_booking( $EM_Booking ) ) {
				$items[] = static::prepare_booking( $EM_Booking, $params['context'] ?? 'view' );
			}
		}
		$total = method_exists( '\EM_Bookings', 'count' ) ? \EM_Bookings::count( $args ) : count( $items );
		return array(
			'items' => $items,
			'pagination' => Utils::pagination( $total, $args['page'], $args['limit'] ),
		);
	}

	public static function get_booking( $id, $context = 'view' ) {
		$EM_Booking = em_get_booking( sanitize_text_field( $id ) );
		if ( !$EM_Booking || !$EM_Booking->booking_id ) {
			return Utils::error( 'em_api_booking_not_found', __( 'Booking not found.', 'events-manager' ), 404 );
		}
		if ( !static::can_read_booking( $EM_Booking ) ) {
			return Utils::error( 'em_api_booking_forbidden', __( 'You do not have permission to view this booking.', 'events-manager' ), 403 );
		}
		return static::prepare_booking( $EM_Booking, $context );
	}

	public static function create_booking( $data ) {
		return static::save_booking( $data );
	}

	public static function update_booking( $id, $data ) {
		return static::save_booking( $data, $id );
	}

	public static function save_booking( $data, $id = 0 ) {
		$data = Utils::normalize_input( $data );
		$EM_Booking = $id ? em_get_booking( sanitize_text_field( $id ) ) : new \EM_Booking();
		if ( !$id ) {
			$filtered_booking = apply_filters( 'em_api_create_booking_object', $EM_Booking, $data, $id );
			if ( $filtered_booking instanceof \EM_Booking ) {
				$EM_Booking = $filtered_booking;
			}
		}
		if ( $id && ( !$EM_Booking || !$EM_Booking->booking_id ) ) {
			return Utils::error( 'em_api_booking_not_found', __( 'Booking not found.', 'events-manager' ), 404 );
		}
		if ( $id && !$EM_Booking->can_manage( 'manage_bookings', 'manage_others_bookings' ) ) {
			return Utils::object_error( 'em_api_booking_forbidden', $EM_Booking, __( 'You do not have permission to save this booking.', 'events-manager' ), 403 );
		}
		if ( !$id && !static::can_create_booking() ) {
			return Utils::error( 'em_api_booking_forbidden', __( 'You do not have permission to create bookings through the API.', 'events-manager' ), 403 );
		}
		// Let an add-on (Events Manager Pro) reshape the request data — e.g. map a structured booker `person` object onto the booking-form field names. Core books under the authenticated account, so it leaves the request data as-is.
		$request_data = apply_filters( 'em_api_booking_request_data', static::booking_request_data( $data, $EM_Booking ), $data, $EM_Booking, $id );
		$override_availability = !empty( $data['override_availability'] ) && current_user_can( 'manage_bookings' );
		// "Booking on behalf of someone else" — attributing a booking to a guest or another user instead of the authenticated account — is a Pro capability (it depends on Pro's manual-booking / custom-form machinery). Core never does it: it always books as the authenticated account. Pro opts a create in by returning true here, and core then flips EM_Bookings::$force_registration for the save cycle so the booking form reads the supplied booker details rather than the current user. The API add() path never calls em_booking_add_registration(), so this can't create a WordPress account on its own — it only steers the form's person resolution.
		$force_registration = (bool) apply_filters( 'em_api_booking_force_registration', false, $EM_Booking, $data, $id );
		// Run the whole get_post → validate → save cycle with the form-post environment in place. EM core and the Pro booking form re-read $_REQUEST during validate() and add()/save() (gateways, custom form fields, uploads), so the request data has to stay in $_REQUEST for the entire cycle, not just get_post().
		$persist = function() use ( $EM_Booking, $data, $id, $override_availability ) {
			if ( !$EM_Booking->get_post( $override_availability ) || !$EM_Booking->validate( $override_availability ) ) {
				return static::booking_invalid_error( $EM_Booking );
			}
			// Extension point: an add-on (Pro) can assign an explicit booker here — a guest person or a different WP user — returning a WP_Error to abort (e.g. an invalid guest email). Core does nothing, leaving the booking attributed to the authenticated account.
			$person_result = apply_filters( 'em_api_assign_booking_person', null, $EM_Booking, $data, $id );
			if ( is_wp_error( $person_result ) ) {
				return $person_result;
			}
			if ( !$id ) {
				$saved = $EM_Booking->get_event()->get_bookings()->add( $EM_Booking );
			} else {
				$saved = $EM_Booking->save( !isset( $data['send_email'] ) || Utils::is_truthy( $data['send_email'] ) );
			}
			if ( !$saved ) {
				return Utils::object_error( 'em_api_booking_save_failed', $EM_Booking, __( 'Booking could not be saved.', 'events-manager' ), 500 );
			}
			return true;
		};
		$result = Utils::with_request_data( $request_data, function() use ( $persist, $force_registration ) {
			if ( !$force_registration ) {
				return $persist();
			}
			$previous_force_registration = \EM_Bookings::$force_registration;
			\EM_Bookings::$force_registration = true;
			try {
				return $persist();
			} finally {
				\EM_Bookings::$force_registration = $previous_force_registration;
			}
		} );
		if ( is_wp_error( $result ) ) {
			return $result;
		}
		static::enforce_explicit_booking_status( $EM_Booking, $data );
		return static::prepare_booking( $EM_Booking, 'edit' );
	}

	/**
	 * Honour an explicitly-requested `booking_status` after the booking is created/saved.
	 *
	 * On create, EM_Bookings::add() runs the gateway's post-create hook, which for the offline gateway forces the booking to status 5 (awaiting payment) — clobbering any booking_status the caller set through the $_POST contract. That's correct for a real customer checkout, but an admin seeding bookings (or confirming one) wants the status they asked for. So when the caller can manage bookings AND passed an explicit numeric booking_status that differs from where the gateway left it, re-apply it via set_status() (which runs after the gateway and is the canonical status-change path). No-op for non-managers (the field was already stripped in booking_request_data) and when no explicit status was given.
	 */
	protected static function enforce_explicit_booking_status( $EM_Booking, $data ) {
		if ( !isset( $data['booking_status'] ) || !is_numeric( $data['booking_status'] ) || !$EM_Booking->can_manage() ) {
			return;
		}
		$requested = absint( $data['booking_status'] );
		if ( !array_key_exists( $requested, $EM_Booking->status_array ) || (int) $EM_Booking->booking_status === $requested ) {
			return;
		}
		$send_email = isset( $data['send_email'] ) ? Utils::is_truthy( $data['send_email'] ) : false; // Seeding/admin status corrections default to silent — don't fire a status-change email unless the caller asks.
		$EM_Booking->set_status( $requested, $send_email );
	}

	/**
	 * Validation error for create/update booking. Surfaces the real field errors
	 * (now non-empty thanks to object_error) and appends a pointer to
	 * get-booking-requirements so an agent can fetch the exact fields, their
	 * payload locations, and a ready-to-submit example for this event.
	 */
	protected static function booking_invalid_error( $EM_Booking ) {
		$error   = Utils::object_error( 'em_api_booking_invalid', $EM_Booking, __( 'Booking data is invalid.', 'events-manager' ), 400 );
		$message = trim( $error->get_error_message() );
		$hint    = __( "Call get-booking-requirements with this event's ID for the exact required fields, their payload locations (attendee fields go under em_tickets[<ticket_id>].ticket_bookings[].attendee), and a ready-to-submit example.", 'events-manager' );
		if ( strpos( $message, 'get-booking-requirements' ) === false ) {
			$message = $message === '' ? $hint : $message . ' ' . $hint;
		}
		$data = (array) $error->get_error_data();
		$data['booking_requirements_ability'] = 'events-manager/get-booking-requirements';
		return new \WP_Error( 'em_api_booking_invalid', $message, $data );
	}

	public static function set_booking_status( $id, $status, $send_email = true, $ignore_spaces = false ) {
		$EM_Booking = em_get_booking( sanitize_text_field( $id ) );
		if ( !$EM_Booking || !$EM_Booking->booking_id ) {
			return Utils::error( 'em_api_booking_not_found', __( 'Booking not found.', 'events-manager' ), 404 );
		}
		if ( !is_numeric( $status ) || !array_key_exists( absint( $status ), $EM_Booking->status_array ) ) {
			return Utils::error( 'em_api_booking_status_invalid', __( 'Booking status is invalid.', 'events-manager' ), 400 );
		}
		if ( !$EM_Booking->can_manage( 'manage_bookings', 'manage_others_bookings' ) ) {
			return Utils::object_error( 'em_api_booking_forbidden', $EM_Booking, __( 'You do not have permission to change this booking status.', 'events-manager' ), 403 );
		}
		if ( !$EM_Booking->set_status( absint( $status ), Utils::is_truthy( $send_email ), Utils::is_truthy( $ignore_spaces ) ) ) {
			return Utils::object_error( 'em_api_booking_status_failed', $EM_Booking, __( 'Booking status could not be changed.', 'events-manager' ), 500 );
		}
		return static::prepare_booking( $EM_Booking, 'edit' );
	}

	public static function delete_booking( $id ) {
		$EM_Booking = em_get_booking( sanitize_text_field( $id ) );
		if ( !$EM_Booking || !$EM_Booking->booking_id ) {
			return Utils::error( 'em_api_booking_not_found', __( 'Booking not found.', 'events-manager' ), 404 );
		}
		if ( !$EM_Booking->can_manage( 'manage_bookings', 'manage_others_bookings' ) ) {
			return Utils::object_error( 'em_api_booking_forbidden', $EM_Booking, __( 'You do not have permission to delete this booking.', 'events-manager' ), 403 );
		}
		$previous = static::prepare_booking( $EM_Booking, 'edit' );
		if ( !$EM_Booking->delete() ) {
			return Utils::object_error( 'em_api_booking_delete_failed', $EM_Booking, __( 'Booking could not be deleted.', 'events-manager' ), 500 );
		}
		return array( 'deleted' => true, 'previous' => $previous );
	}

	public static function list_terms( $taxonomy, $params = array() ) {
		if ( !taxonomy_exists( $taxonomy ) ) {
			return Utils::error( 'em_api_taxonomy_not_found', __( 'Taxonomy not found.', 'events-manager' ), 404 );
		}
		$params = Utils::normalize_input( $params );
		$page = !empty( $params['page'] ) ? absint( $params['page'] ) : 1;
		$per_page = !empty( $params['per_page'] ) ? min( 100, max( 1, absint( $params['per_page'] ) ) ) : 20;
		$args = array(
			'taxonomy' => $taxonomy,
			'hide_empty' => isset( $params['hide_empty'] ) ? Utils::is_truthy( $params['hide_empty'] ) : false,
			'number' => $per_page,
			'offset' => ( $page - 1 ) * $per_page,
		);
		if ( !empty( $params['search'] ) ) {
			$args['search'] = sanitize_text_field( $params['search'] );
		}
		$terms = get_terms( $args );
		if ( is_wp_error( $terms ) ) return $terms;
		$count_args = $args;
		unset( $count_args['number'], $count_args['offset'] );
		$total = wp_count_terms( $count_args );
		if ( is_wp_error( $total ) ) $total = count( $terms );
		$items = array();
		foreach ( $terms as $term ) {
			$items[] = static::prepare_term( $term, $taxonomy );
		}
		return array(
			'items' => $items,
			'pagination' => Utils::pagination( $total, $page, $per_page ),
		);
	}

	public static function get_term( $taxonomy, $id ) {
		$term = get_term( absint( $id ), $taxonomy );
		if ( !$term || is_wp_error( $term ) ) {
			return Utils::error( 'em_api_term_not_found', __( 'Term not found.', 'events-manager' ), 404 );
		}
		return static::prepare_term( $term, $taxonomy );
	}

	public static function save_term( $taxonomy, $data, $id = 0 ) {
		if ( !static::can_manage_terms() ) {
			return Utils::error( 'em_api_term_forbidden', __( 'You do not have permission to manage event terms.', 'events-manager' ), 403 );
		}
		$data = Utils::normalize_input( $data );
		$args = array();
		if ( isset( $data['slug'] ) ) $args['slug'] = sanitize_title( $data['slug'] );
		if ( isset( $data['description'] ) ) $args['description'] = wp_kses_post( $data['description'] );
		if ( isset( $data['parent'] ) ) $args['parent'] = absint( $data['parent'] );
		$name = !empty( $data['name'] ) ? sanitize_text_field( $data['name'] ) : '';
		if ( $id ) {
			$result = wp_update_term( absint( $id ), $taxonomy, array_merge( array_filter( array( 'name' => $name ) ), $args ) );
		} else {
			if ( !$name ) {
				return Utils::error( 'em_api_term_invalid', __( 'Term name is required.', 'events-manager' ), 400 );
			}
			$result = wp_insert_term( $name, $taxonomy, $args );
		}
		if ( is_wp_error( $result ) ) return $result;
		$term_id = absint( $result['term_id'] );
		$image_result = static::apply_term_color_and_image( $taxonomy, $term_id, $data );
		if ( is_wp_error( $image_result ) ) return $image_result;
		return static::get_term( $taxonomy, $term_id );
	}

	/**
	 * Writes `color` and `image` overlays for a term into EM_META_TABLE under the keys the EM taxonomy admin already uses (`{option_name}-bgcolor` / `{option_name}-image` / `{option_name}-image-id`). Resolves the polymorphic `image` input via resolve_image_input() so URL/base64/multipart all work. No-op for keys that aren't in $data, so partial updates leave existing color/image untouched.
	 */
	protected static function apply_term_color_and_image( $taxonomy, $term_id, $data ) {
		$option_name = static::taxonomy_option_name( $taxonomy );
		if ( !$option_name || !$term_id ) return null;
		global $wpdb;
		if ( array_key_exists( 'color', $data ) ) {
			if ( $data['color'] === null || $data['color'] === '' ) {
				$wpdb->delete( EM_META_TABLE, array( 'object_id' => $term_id, 'meta_key' => $option_name . '-bgcolor' ) );
				wp_cache_delete( $term_id, 'em_' . $option_name . '_colors' );
			} else {
				$color = sanitize_hex_color( $data['color'] );
				if ( !$color ) {
					return Utils::error( 'em_api_term_color_invalid', __( '`color` must be a valid hex colour (e.g. `#80b538`).', 'events-manager' ), 400 );
				}
				static::upsert_em_meta( $term_id, $option_name . '-bgcolor', $color );
				wp_cache_set( $term_id, $color, 'em_' . $option_name . '_colors' );
			}
		}
		if ( array_key_exists( 'image', $data ) ) {
			if ( $data['image'] === null || $data['image'] === '' || $data['image'] === false ) {
				$wpdb->delete( EM_META_TABLE, array( 'object_id' => $term_id, 'meta_key' => $option_name . '-image' ) );
				$wpdb->delete( EM_META_TABLE, array( 'object_id' => $term_id, 'meta_key' => $option_name . '-image-id' ) );
			} else {
				$attachment_id = static::resolve_image_input( $data['image'] );
				if ( is_wp_error( $attachment_id ) ) return $attachment_id;
				if ( $attachment_id ) {
					$url = wp_get_attachment_url( $attachment_id );
					if ( $url ) static::upsert_em_meta( $term_id, $option_name . '-image', $url );
					static::upsert_em_meta( $term_id, $option_name . '-image-id', (string) $attachment_id );
				}
			}
		}
		return true;
	}

	/**
	 * INSERT-or-UPDATE for EM_META_TABLE rows keyed by (object_id, meta_key). Mirrors what em-taxonomy-admin.php does inline, just factored out.
	 */
	protected static function upsert_em_meta( $object_id, $meta_key, $meta_value ) {
		global $wpdb;
		$exists = $wpdb->get_var( $wpdb->prepare( 'SELECT COUNT(*) FROM ' . EM_META_TABLE . ' WHERE object_id = %d AND meta_key = %s', $object_id, $meta_key ) );
		if ( $exists ) {
			$wpdb->update( EM_META_TABLE, array( 'meta_value' => $meta_value ), array( 'object_id' => $object_id, 'meta_key' => $meta_key ) );
		} else {
			$wpdb->insert( EM_META_TABLE, array( 'object_id' => $object_id, 'meta_key' => $meta_key, 'meta_value' => $meta_value ) );
		}
	}

	/**
	 * Maps a WP taxonomy slug to the EM taxonomy `option_name` used as the prefix for term meta keys (`category-bgcolor`, `tag-image`, etc.).
	 */
	protected static function taxonomy_option_name( $taxonomy ) {
		if ( defined( 'EM_TAXONOMY_CATEGORY' ) && $taxonomy === EM_TAXONOMY_CATEGORY ) return 'category';
		if ( defined( 'EM_TAXONOMY_TAG' ) && $taxonomy === EM_TAXONOMY_TAG ) return 'tag';
		return null;
	}

	public static function delete_term( $taxonomy, $id ) {
		if ( !current_user_can( 'delete_event_categories' ) ) {
			return Utils::error( 'em_api_term_forbidden', __( 'You do not have permission to delete event terms.', 'events-manager' ), 403 );
		}
		$previous = static::get_term( $taxonomy, $id );
		if ( is_wp_error( $previous ) ) return $previous;
		$result = wp_delete_term( absint( $id ), $taxonomy );
		if ( is_wp_error( $result ) ) return $result;
		if ( !$result ) {
			return Utils::error( 'em_api_term_delete_failed', __( 'Term could not be deleted.', 'events-manager' ), 500 );
		}
		return array( 'deleted' => true, 'previous' => $previous );
	}

	public static function can_create_booking() {
		$allow_anonymous = em_get_option( 'dbem_bookings_anonymous' ) && apply_filters( 'em_api_allow_anonymous_booking_create', false );
		$allowed = is_user_logged_in() || $allow_anonymous;
		return apply_filters( 'em_api_can_create_booking', $allowed );
	}

	public static function can_manage_terms() {
		return current_user_can( 'edit_event_categories' );
	}

	protected static function can_read_event( $EM_Event, $context = 'view' ) {
		if ( $context === 'edit' ) {
			return $EM_Event->can_manage( 'edit_events', 'edit_others_events' );
		}
		// A password-protected post stays published, so the checks below would otherwise wave it through and to_api() would hand back the raw post_content the password exists to withhold.
		if ( $EM_Event->password_required() ) {
			return false;
		}
		if ( $EM_Event->is_published() && empty( $EM_Event->event_private ) ) {
			return true;
		}
		if ( $EM_Event->event_private && current_user_can( 'read_private_events' ) ) {
			return true;
		}
		return $EM_Event->can_manage( 'edit_events', 'edit_others_events' );
	}

	protected static function can_read_location( $EM_Location, $context = 'view' ) {
		if ( $context === 'edit' ) {
			return $EM_Location->can_manage( 'edit_locations', 'edit_others_locations' );
		}
		if ( $EM_Location->password_required() ) {
			return false;
		}
		if ( $EM_Location->is_published() && empty( $EM_Location->location_private ) ) {
			return true;
		}
		if ( $EM_Location->location_private && current_user_can( 'read_private_locations' ) ) {
			return true;
		}
		return $EM_Location->can_manage( 'edit_locations', 'edit_others_locations' );
	}

	protected static function can_read_booking( $EM_Booking ) {
		if ( !$EM_Booking || !$EM_Booking->booking_id ) return false;
		if ( $EM_Booking->can_manage( 'manage_bookings', 'manage_others_bookings' ) ) return true;
		return is_user_logged_in() && absint( $EM_Booking->person_id ) === get_current_user_id();
	}

	protected static function prepare_event( $EM_Event, $context = 'view' ) {
		$can_manage = $context === 'edit' && $EM_Event->can_manage( 'edit_events', 'edit_others_events' );
		$api = $EM_Event->to_api();
		$api = Utils::strip_private_owner_data( $api, $can_manage && $context === 'edit' );
		if ( $context !== 'edit' ) {
			unset( $api['blog_id'] );
		} else {
			$api['permissions'] = array(
				'edit' => $can_manage,
				'delete' => $EM_Event->can_manage( 'delete_events', 'delete_others_events' ),
			);
		}
		$api['featured_image'] = static::get_featured_image_for_post( $EM_Event->post_id ?? 0 );
		return apply_filters( 'em_api_prepare_event', $api, $EM_Event, $context );
	}

	protected static function prepare_location( $EM_Location, $context = 'view' ) {
		$can_manage = $context === 'edit' && $EM_Location->can_manage( 'edit_locations', 'edit_others_locations' );
		$api = $EM_Location->to_api();
		if ( !$can_manage || $context !== 'edit' ) {
			unset( $api['blog_id'] );
		} else {
			$api['permissions'] = array(
				'edit' => $can_manage,
				'delete' => $EM_Location->can_manage( 'delete_locations', 'delete_others_locations' ),
			);
		}
		$api['featured_image'] = static::get_featured_image_for_post( $EM_Location->post_id ?? 0 );
		return apply_filters( 'em_api_prepare_location', $api, $EM_Location, $context );
	}

	protected static function prepare_booking( $EM_Booking, $context = 'view' ) {
		$args = array( 'event' => $context !== 'embed' );
		$api = $EM_Booking->to_api( $args );
		if ( $context !== 'edit' && !current_user_can( 'manage_bookings' ) && !current_user_can( 'manage_others_bookings' ) ) {
			unset( $api['meta'] );
		}
		if ( $context === 'edit' ) {
			$api['permissions'] = array(
				'edit' => $EM_Booking->can_manage( 'manage_bookings', 'manage_others_bookings' ),
				'delete' => $EM_Booking->can_manage( 'manage_bookings', 'manage_others_bookings' ),
			);
		}
		return apply_filters( 'em_api_prepare_booking', $api, $EM_Booking, $context );
	}

	protected static function prepare_ticket( $EM_Ticket, $context = 'view' ) {
		$api = array(
			'id' => absint( $EM_Ticket->ticket_id ),
			'event_id' => absint( $EM_Ticket->event_id ),
			'name' => $EM_Ticket->name,
			'description' => $EM_Ticket->description,
			'status' => (bool) $EM_Ticket->status,
			'price' => (float) $EM_Ticket->get_price(),
			'spaces' => $EM_Ticket->get_spaces(),
			'available_spaces' => $EM_Ticket->get_available_spaces(),
			'booked_spaces' => $EM_Ticket->get_booked_spaces(),
			'reserved_spaces' => $EM_Ticket->get_reserved_spaces(),
			'pending_spaces' => $EM_Ticket->get_pending_spaces(),
			'min' => $EM_Ticket->min === null ? null : absint( $EM_Ticket->min ),
			'max' => $EM_Ticket->max === null ? null : absint( $EM_Ticket->max ),
			'required' => (bool) $EM_Ticket->required,
			'members' => (bool) $EM_Ticket->members,
			'members_roles' => array_values( (array) $EM_Ticket->members_roles ),
			'guests' => (bool) $EM_Ticket->guests,
			'start' => static::prepare_ticket_datetime( $EM_Ticket->ticket_start ),
			'end' => static::prepare_ticket_datetime( $EM_Ticket->ticket_end ),
			'order' => $EM_Ticket->ticket_order === null ? null : absint( $EM_Ticket->ticket_order ),
			'bookings_count' => $EM_Ticket->ticket_id ? absint( $EM_Ticket->get_bookings_count() ) : 0,
		);
		if ( !$EM_Ticket->can_manage() ) {
			// Booking counters and the member role list are management data; the booking form shows a reader none of it.
			unset( $api['members_roles'], $api['reserved_spaces'], $api['pending_spaces'], $api['bookings_count'] );
		}
		if ( $context === 'edit' ) {
			$api['meta'] = is_array( $EM_Ticket->ticket_meta ) ? $EM_Ticket->ticket_meta : array();
			$api['permissions'] = array(
				'edit' => $EM_Ticket->can_manage(),
				'delete' => $EM_Ticket->can_manage() && $EM_Ticket->get_bookings_count() === 0,
			);
		}
		return apply_filters( 'em_api_prepare_ticket', $api, $EM_Ticket, $context );
	}

	protected static function prepare_term( $term, $taxonomy ) {
		$class = $taxonomy === EM_TAXONOMY_TAG ? 'EM_Tag' : 'EM_Category';
		$EM_Term = class_exists( $class ) ? new $class( $term ) : false;
		$api = array(
			'id' => absint( $term->term_id ),
			'name' => $term->name,
			'slug' => $term->slug,
			'taxonomy' => $taxonomy,
			'description' => $term->description,
			'parent' => absint( $term->parent ),
			'count' => absint( $term->count ),
		);
		if ( $EM_Term ) {
			$api['color'] = $EM_Term->get_color();
			$api['image_url'] = $EM_Term->get_image_url();
			$api['url'] = $EM_Term->get_url();
			// Look up the attachment ID directly so consumers don't have to map URL → ID.
			$option_name = static::taxonomy_option_name( $taxonomy );
			$attachment_id = null;
			if ( $option_name ) {
				global $wpdb;
				$attachment_id = $wpdb->get_var( $wpdb->prepare( 'SELECT meta_value FROM ' . EM_META_TABLE . ' WHERE object_id = %d AND meta_key = %s LIMIT 1', $term->term_id, $option_name . '-image-id' ) );
				$attachment_id = $attachment_id ? absint( $attachment_id ) : null;
			}
			$api['image'] = $attachment_id ? static::prepare_attachment( $attachment_id ) : null;
		}
		return apply_filters( 'em_api_prepare_term', $api, $term, $taxonomy );
	}

	protected static function get_ticket_object( $id ) {
		$EM_Ticket = \EM_Ticket::get( absint( $id ) );
		if ( !$EM_Ticket || empty( $EM_Ticket->ticket_id ) ) {
			return Utils::error( 'em_api_ticket_not_found', __( 'Ticket not found.', 'events-manager' ), 404 );
		}
		return $EM_Ticket;
	}

	/**
	 * Translate API-friendly flat time fields to the event_timeranges[0] shape EM core expects.
	 *
	 * EM core's EM_Event::get_post_meta() routes start/end times through the timeranges
	 * subsystem, not the flat event_start_time / event_end_time keys. Accept both shapes from
	 * API consumers; rewrite to the canonical nested form before with_request_data().
	 *
	 * Precedence: an explicit event_timeranges in $data wins. Flat fields fill in what's
	 * missing so a partial PATCH (e.g. just event_start_time) doesn't drop the other endpoint.
	 */
	protected static function translate_event_input( $data ) {
		$all_day    = $data['event_all_day'] ?? null;
		$start_time = $data['event_start_time'] ?? null;
		$end_time   = $data['event_end_time'] ?? null;
		if ( $all_day !== null || $start_time !== null || $end_time !== null ) {
			$tr = ( isset( $data['event_timeranges'][0] ) && is_array( $data['event_timeranges'][0] ) )
				? $data['event_timeranges'][0]
				: array();
			if ( Utils::is_truthy( $all_day ) ) {
				$tr['all_day'] = '1';
				unset( $tr['start'], $tr['end'] );
			} else {
				unset( $tr['all_day'] );
				if ( $start_time !== null ) $tr['start'] = $start_time;
				if ( $end_time !== null )   $tr['end']   = $end_time;
			}
			$data['event_timeranges'] = array( 0 => $tr ) + ( $data['event_timeranges'] ?? array() );
		}
		unset( $data['event_start_time'], $data['event_end_time'], $data['event_all_day'] );
		return $data;
	}

	/**
	 * Apply post_status from API payload to an EM CPT object, respecting publish capability.
	 * Used after EM_Event::get_post() / EM_Location::get_post() since force_status isn't
	 * part of the native $_POST contract.
	 */
	protected static function apply_force_status( $EM_Object, $data, $type ) {
		if ( empty( $data['post_status'] ) ) return;
		$status = Utils::sanitize_post_status( $data['post_status'] );
		if ( !$status ) return;
		$cap = $type === 'location' ? 'publish_locations' : 'publish_events';
		if ( current_user_can( $cap ) || $status !== 'publish' ) {
			$EM_Object->force_status = $status;
		}
	}

	/**
	 * Translate the API recurrence/timeslot shape (the inverse of EM_Event::to_api) into the internal $_REQUEST form-array that EM_Event::get_post() / Recurrence_Sets::get_post() / Timeranges::get_post() consume. Keeps EM's existing to_api field names (`freq`, `interval`, `byday` CSV, `byweekno`, `days`, `type`, `set_id`) and maps them to the internal `recurrence_*` names here.
	 *
	 * Safety is an app-level concern, not an API one (see docs/proposals/recurrence-rest-api.md): the app shows the "this will cancel occurrences" confirmation, so the API just applies the change. We honour that by (a) being non-destructive by omission — callers omit what they don't change — (b) treating removal as explicit only (`delete:true`), (c) defaulting any destructive reschedule to `cancel`, and (d) minting the nonces EM core still checks server-side for the authenticated, edit_events-capable user, so the app never has to handle them.
	 */
	protected static function translate_recurrence_input( $data ) {
		// when.timeranges[] -> event_timeranges[] (single-event / occurrence timeslot model). Explicit timeslots win over the flat times translate_event_input() already expanded into index 0.
		if ( isset( $data['when']['timeranges'] ) && is_array( $data['when']['timeranges'] ) ) {
			$data['event_timeranges'] = static::map_timeranges_input( $data['when']['timeranges'] );
			unset( $data['when']['timeranges'] );
		}
		if ( !isset( $data['recurrences']['sets'] ) || !is_array( $data['recurrences']['sets'] ) ) {
			return $data;
		}
		$uid = get_current_user_id();
		$out = array();
		$i = 0;
		$has_new_exclude = false;
		foreach ( $data['recurrences']['sets'] as $set ) {
			if ( !is_array( $set ) ) continue;
			$type   = ( !empty( $set['type'] ) && $set['type'] === 'exclude' ) ? 'exclude' : 'include';
			$set_id = !empty( $set['set_id'] ) ? absint( $set['set_id'] ) : 0;
			$action = ( isset( $set['action'] ) && $set['action'] === 'delete' ) ? 'delete' : 'cancel';
			$row = array( 'recurrence_type' => $type );
			if ( $set_id ) $row['recurrence_set_id'] = $set_id;
			// Explicit delete: mint the delete nonce core expects (no client nonce).
			if ( !empty( $set['delete'] ) && $set_id ) {
				$row['delete'] = wp_create_nonce( 'delete_recurrence_' . $set_id . '_' . $uid );
				$row['reschedule'] = array( 'action' => $action );
				$out[ $type ][ $i++ ] = $row;
				continue;
			}
			if ( isset( $set['freq'] ) )     $row['recurrence_freq']     = $set['freq'];
			if ( isset( $set['interval'] ) ) $row['recurrence_interval'] = $set['interval'];
			$freq = $set['freq'] ?? '';
			if ( $freq === 'weekly' && isset( $set['byday'] ) ) {
				// byday CSV (to_api shape) -> recurrence_bydays[] (weekly write shape)
				$row['recurrence_bydays'] = array_values( array_filter( array_map( 'trim', explode( ',', (string) $set['byday'] ) ), function ( $v ) { return $v !== ''; } ) );
			} elseif ( $freq === 'monthly' ) {
				if ( isset( $set['byday'] ) )    $row['recurrence_byday']    = $set['byday'];
				if ( isset( $set['byweekno'] ) ) $row['recurrence_byweekno'] = $set['byweekno'];
			}
			if ( $freq === 'on' && isset( $set['dates'] ) ) {
				$row['recurrence_dates'] = is_array( $set['dates'] ) ? implode( ',', $set['dates'] ) : (string) $set['dates'];
			}
			if ( isset( $set['days'] ) )       $row['recurrence_duration']   = $set['days'];
			if ( isset( $set['start_date'] ) ) $row['recurrence_start_date'] = $set['start_date'];
			if ( isset( $set['end_date'] ) )   $row['recurrence_end_date']   = $set['end_date'];
			// Timezone applies to every set including excludes — it interprets the set's dates, so an exclude's skipped days depend on it.
			if ( isset( $set['timezone'] ) ) $row['recurrence_timezone'] = $set['timezone'];
			// Status is include-only (an exclude has no active status).
			if ( $type !== 'exclude' && isset( $set['status'] ) ) {
				$row['recurrence_status'] = $set['status'];
			}
			// Times round-trip for BOTH includes and excludes. For an include they are the per-occurrence timeslots; for an exclude a timed window skips just that part of the matched dates rather than the whole day (EM stores recurrence_start/end_time and its collision check is time-aware — only the admin form's editor is disabled for excludes, not the data path).
			if ( isset( $set['timeranges'] ) && is_array( $set['timeranges'] ) && $set['timeranges'] ) {
				$row['timeranges']    = static::map_timeranges_input( $set['timeranges'] );
				$row['override_time'] = 1; // apply these times to this set (the primary applies its own regardless)
			}
			// Existing set: mint the reschedule nonces core checks so any pattern/date/time change is applied without the app handling nonces.
			if ( $set_id ) {
				$row['reschedule'] = array(
					'pattern' => wp_create_nonce( 'reschedule-pattern-' . $set_id ),
					'dates'   => wp_create_nonce( 'reschedule-dates-' . $set_id ),
					'times'   => wp_create_nonce( 'reschedule-times-' . $set_id ),
					'action'  => $action,
				);
			} elseif ( $type === 'exclude' ) {
				$has_new_exclude = true;
			}
			$out[ $type ][ $i++ ] = $row;
		}
		// A new exclude on a live event needs the event-wide exclude nonce; mint it server-side.
		if ( $has_new_exclude ) {
			$out['exclude_reschedule'] = array( 'nonce' => wp_create_nonce( 'reschedule_exclude_' . $uid ), 'action' => 'cancel' );
		}
		$data['recurrences'] = $out;
		return $data;
	}

	/** Map the API timerange/timeslot sub-shape to EM's internal timeranges form-array (start/end/all_day/timeslots + duration/buffer/frequency generator, with timerange_id for in-place edits). */
	protected static function map_timeranges_input( $timeranges ) {
		$out = array();
		$i = 0;
		foreach ( (array) $timeranges as $tr ) {
			if ( !is_array( $tr ) ) continue;
			$row = array();
			if ( !empty( $tr['id'] ) )       $row['timerange_id'] = absint( $tr['id'] );
			if ( isset( $tr['start'] ) )      $row['start']    = $tr['start'];
			if ( isset( $tr['end'] ) )        $row['end']      = $tr['end'];
			if ( !empty( $tr['all_day'] ) )   $row['all_day']  = 1;
			if ( !empty( $tr['timeslots'] ) ) $row['timeslots'] = 1;
			foreach ( array( 'duration', 'buffer', 'frequency' ) as $g ) {
				if ( isset( $tr[ $g ] ) ) $row[ $g ] = $tr[ $g ]; // {qty,unit}, form-native
			}
			$out[ $i++ ] = $row;
		}
		return $out;
	}

	/**
	 * EM_Tickets::get_post() skips $_POST['em_tickets'][0] because the EM admin form
	 * reserves row 0 for the JS template. API consumers shouldn't need to know that —
	 * if the payload uses 0-indexed sequential keys, shift everything up by 1.
	 */
	protected static function normalize_em_tickets_keys( $data ) {
		if ( !isset( $data['em_tickets'] ) || !is_array( $data['em_tickets'] ) ) {
			return $data;
		}
		$tickets = $data['em_tickets'];
		if ( array_key_exists( 0, $tickets ) || array_key_exists( '0', $tickets ) ) {
			$shifted = array();
			$i = 1;
			foreach ( $tickets as $row ) {
				$shifted[ $i++ ] = $row;
			}
			$data['em_tickets'] = $shifted;
		}
		return $data;
	}

	protected static function prepare_ticket_datetime( $value ) {
		if ( empty( $value ) || $value === '0000-00-00 00:00:00' ) {
			return null;
		}
		$timestamp = strtotime( $value );
		return $timestamp ? gmdate( 'c', $timestamp ) : $value;
	}

	protected static function save_event_terms( $EM_Event, $data ) {
		if ( empty( $EM_Event->post_id ) ) return;
		// Prefer event_categories / event_tags to match the live event form ($_POST contract).
		// Accept categories / tags as deprecated aliases.
		$categories = $data['event_categories'] ?? $data['categories'] ?? null;
		$tags       = $data['event_tags']       ?? $data['tags']       ?? null;
		if ( $categories !== null && taxonomy_exists( EM_TAXONOMY_CATEGORY ) && current_user_can( 'edit_events' ) ) {
			wp_set_object_terms( $EM_Event->post_id, array_map( 'absint', (array) $categories ), EM_TAXONOMY_CATEGORY );
		}
		if ( $tags !== null && taxonomy_exists( EM_TAXONOMY_TAG ) && current_user_can( 'edit_events' ) ) {
			wp_set_object_terms( $EM_Event->post_id, array_map( 'absint', (array) $tags ), EM_TAXONOMY_TAG );
		}
	}

	/**
	 * Prepare the $_REQUEST/$_POST data for EM_Booking::get_post().
	 *
	 * Field shape matches the live booking form ($_POST contract): flat user_name,
	 * user_email, dbem_phone, dbem_country at top level — no `person` wrapper. EM core
	 * and Pro add-ons read what they need from $_REQUEST directly (coupon_code, waitlist,
	 * donation_amount, etc.) so the payload passes through verbatim. We only gate
	 * admin-only fields (booking_tax_rate, person_id, booking_status, manual_booking*,
	 * payment_*) when the caller is not a booking manager.
	 */
	protected static function booking_request_data( $data, $EM_Booking ) {
		$request = $data;
		$request['event_id'] = $data['event_id'] ?? $data['event'] ?? $EM_Booking->event_id ?? null;
		// Flatten booking-form sub-objects so EM_Form / Pro forms read them from $_REQUEST.
		foreach ( array( 'booking', 'booking_fields', 'fields', 'registration' ) as $key ) {
			if ( !empty( $data[ $key ] ) && is_array( $data[ $key ] ) ) {
				$request = array_merge( $request, $data[ $key ] );
			}
		}
		// Liberal input: agents sometimes prefix booking-form fields. EM core reads them by
		// bare fieldid, so strip a `booking_form_field_` prefix before they reach $_REQUEST.
		foreach ( $request as $key => $value ) {
			if ( strpos( (string) $key, 'booking_form_field_' ) === 0 ) {
				$bare = substr( $key, 19 );
				if ( $bare !== '' && !array_key_exists( $bare, $request ) ) {
					$request[ $bare ] = $value;
				}
				unset( $request[ $key ] );
			}
		}
		// Gate admin-only fields when the caller is not a booking manager.
		if ( !$EM_Booking->can_manage() ) {
			foreach ( array( 'booking_tax_rate', 'person_id', 'booking_status',
				'manual_booking', 'manual_booking_confirm', 'manual_booking_override',
				'payment_amount', 'payment_full' ) as $admin_field ) {
				unset( $request[ $admin_field ] );
			}
		}
		return static::apply_consent_to_request_data( $request, $data, 'booking' );
	}

	protected static function apply_consent_to_request_data( $request, $data, $context ) {
		foreach ( static::get_consent_classes() as $class ) {
			$options = $class::$options;
			if ( empty( $options['param'] ) ) {
				continue;
			}
			if ( array_key_exists( $options['param'], $data ) ) {
				$request[ $options['param'] ] = Utils::is_truthy( $data[ $options['param'] ] ) ? 1 : 0;
			} elseif ( apply_filters( 'em_api_consent_default', true, $context, $class, $data ) ) {
				$request[ $options['param'] ] = 1;
			}
		}
		return $request;
	}

	/**
	 * Uploads an image (or other media) to the WordPress media library and returns the attachment shape used everywhere else in this API. Accepts three input forms (the resolver below treats them as equivalent):
	 *
	 *   - `{ source_url: "https://..." }`                 → `media_sideload_image()`
	 *   - `{ filename, mime_type, content_base64 }`       → `wp_handle_sideload()` of decoded bytes
	 *   - `{ _files_file: $_FILES['file'] }`              → `wp_handle_upload()` (multipart)
	 *
	 * Optional inputs: `title`, `alt_text`, `caption`, `description`, `post_id` (attach to a post).
	 *
	 * @return array|\WP_Error Attachment info { id, url, mime_type, title, alt_text, width, height } or error.
	 */
	public static function upload_media( $data ) {
		$data = Utils::normalize_input( $data );
		if ( !current_user_can( 'upload_files' ) ) {
			return Utils::error( 'em_api_media_forbidden', __( 'You do not have permission to upload media.', 'events-manager' ), 403 );
		}
		// `post_id` lands on the attachment as post_parent, here and inside the sideload/upload helpers resolve_attachment_id() calls, so the caller has to be able to edit whatever they are attaching to.
		if ( !empty( $data['post_id'] ) && !current_user_can( 'edit_post', absint( $data['post_id'] ) ) ) {
			return Utils::error( 'em_api_media_parent_forbidden', __( 'You do not have permission to attach media to that post.', 'events-manager' ), 403 );
		}
		$supplied_attachment = !empty( $data['id'] ) || !empty( $data['attachment_id'] );
		$attachment_id = static::resolve_attachment_id( $data );
		if ( is_wp_error( $attachment_id ) ) return $attachment_id;
		// `upload_files` authorises adding a file, not editing one somebody else added. An attachment we created below is owned by the caller and needs no further check, but one they passed in by ID does.
		if ( $supplied_attachment && !current_user_can( 'edit_post', $attachment_id ) ) {
			return Utils::error( 'em_api_media_edit_forbidden', __( 'You do not have permission to edit this attachment.', 'events-manager' ), 403 );
		}
		// Optional post-upload metadata.
		$post_update = array( 'ID' => $attachment_id );
		if ( !empty( $data['title'] ) ) $post_update['post_title'] = sanitize_text_field( $data['title'] );
		if ( isset( $data['caption'] ) ) $post_update['post_excerpt'] = wp_kses_post( $data['caption'] );
		if ( isset( $data['description'] ) ) $post_update['post_content'] = wp_kses_post( $data['description'] );
		if ( !empty( $data['post_id'] ) ) $post_update['post_parent'] = absint( $data['post_id'] );
		if ( count( $post_update ) > 1 ) wp_update_post( $post_update );
		if ( isset( $data['alt_text'] ) ) update_post_meta( $attachment_id, '_wp_attachment_image_alt', sanitize_text_field( $data['alt_text'] ) );
		$response = static::prepare_attachment( $attachment_id );
		// Optional one-call convenience: set this attachment as an event/location featured image (thumbnail), so the agent doesn't have to follow up with update-event/update-location just to wire the image. `post_id` above only sets post_parent (library organisation), never _thumbnail_id — this is the param that actually makes it the featured image.
		list( $featured_set, $featured_warning ) = static::maybe_set_uploaded_featured_image( $attachment_id, $data );
		if ( $featured_set ) {
			$response['featured_image_set'] = $featured_set;
		}
		return static::with_warnings( $response, $featured_warning ? array( $featured_warning ) : array() );
	}

	/**
	 * Handle the `featured_image_for_event` / `featured_image_for_location` convenience params on upload-media: set the freshly-uploaded attachment as that resource's featured image, capability-checked. Returns [ $confirmation|null, $warning|null ] — a confirmation array on success, or a warning (resource not found / no permission) so the caller learns the image uploaded fine but wasn't wired as featured, without failing the whole upload.
	 */
	protected static function maybe_set_uploaded_featured_image( $attachment_id, $data ) {
		$event_id    = !empty( $data['featured_image_for_event'] ) ? $data['featured_image_for_event'] : 0;
		$location_id = !empty( $data['featured_image_for_location'] ) ? $data['featured_image_for_location'] : 0;
		if ( !$event_id && !$location_id ) {
			return array( null, null );
		}
		if ( $event_id ) {
			$EM_Event = em_get_event( $event_id );
			if ( !$EM_Event || !$EM_Event->get_id() ) {
				return array( null, static::featured_target_warning( 'featured_image_for_event', __( 'Event not found, so the uploaded image was not set as its featured image.', 'events-manager' ) ) );
			}
			if ( !$EM_Event->can_manage( 'edit_events', 'edit_others_events' ) ) {
				return array( null, static::featured_target_warning( 'featured_image_for_event', __( 'You do not have permission to edit that event, so the uploaded image was not set as its featured image.', 'events-manager' ) ) );
			}
			set_post_thumbnail( $EM_Event->post_id, $attachment_id );
			return array( array( 'event_id' => absint( $EM_Event->event_id ), 'post_id' => absint( $EM_Event->post_id ), 'attachment_id' => absint( $attachment_id ) ), null );
		}
		$EM_Location = em_get_location( $location_id );
		if ( !$EM_Location || !$EM_Location->get_id() ) {
			return array( null, static::featured_target_warning( 'featured_image_for_location', __( 'Location not found, so the uploaded image was not set as its featured image.', 'events-manager' ) ) );
		}
		if ( !$EM_Location->can_manage( 'edit_locations', 'edit_others_locations' ) ) {
			return array( null, static::featured_target_warning( 'featured_image_for_location', __( 'You do not have permission to edit that location, so the uploaded image was not set as its featured image.', 'events-manager' ) ) );
		}
		set_post_thumbnail( $EM_Location->post_id, $attachment_id );
		return array( array( 'location_id' => absint( $EM_Location->location_id ), 'post_id' => absint( $EM_Location->post_id ), 'attachment_id' => absint( $attachment_id ) ), null );
	}

	protected static function featured_target_warning( $field, $message ) {
		return array(
			'field'   => $field,
			'code'    => 'em_api_featured_target_unavailable',
			/* translators: %s: detail of why the image could not be set as featured */
			'message' => sprintf( __( 'The image uploaded successfully but was not set as a featured image: %s The attachment ID is in this response — pass it to update-event/update-location `featured_image` once the target is editable.', 'events-manager' ), $message ),
		);
	}

	/**
	 * Load the WordPress media-handling includes (media_sideload_image, media_handle_sideload, media_handle_upload, wp_generate_attachment_metadata, …). These are wp-admin-only files not loaded during a front-end REST request, so any media path must pull them in first. Idempotent — require_once is cheap on repeat.
	 */
	protected static function load_media_functions() {
		require_once ABSPATH . 'wp-admin/includes/file.php';
		require_once ABSPATH . 'wp-admin/includes/media.php';
		require_once ABSPATH . 'wp-admin/includes/image.php';
	}

	/**
	 * Resolves any of the supported media-input shapes to a real attachment ID, sideloading the bytes into the WP media library where needed.
	 *
	 * @return int|\WP_Error
	 */
	protected static function resolve_attachment_id( $data ) {
		// Ensure the WP media-handling functions are loaded. These live in wp-admin/includes and aren't present on a front-end REST request, so any path that sideloads/handles an upload (upload-media, but also featured_image / term image on event/location/term saves) must pull them in. Previously this require sat only inside upload_media(), so calling resolve_image_input() from save_event() fataled with "undefined function media_sideload_image()".
		static::load_media_functions();
		// Existing ID — caller's done the work.
		if ( !empty( $data['id'] ) || !empty( $data['attachment_id'] ) ) {
			$id = absint( $data['id'] ?? $data['attachment_id'] );
			if ( !$id || get_post_type( $id ) !== 'attachment' ) {
				return Utils::error( 'em_api_media_invalid_id', __( 'Attachment ID not found.', 'events-manager' ), 404 );
			}
			return $id;
		}
		// Multipart upload from /media POST.
		if ( !empty( $data['_files_file'] ) ) {
			$file = $data['_files_file'];
			if ( !is_array( $file ) || empty( $file['tmp_name'] ) || !is_uploaded_file( $file['tmp_name'] ) ) {
				return Utils::error( 'em_api_media_invalid_upload', __( 'Invalid file upload.', 'events-manager' ), 400 );
			}
			$overrides = array( 'test_form' => false );
			// media_handle_upload expects $_FILES key — stage the file as $_FILES['em_api_media'].
			$_FILES['em_api_media'] = $file;
			$attachment_id = media_handle_upload( 'em_api_media', !empty( $data['post_id'] ) ? absint( $data['post_id'] ) : 0, array(), $overrides );
			unset( $_FILES['em_api_media'] );
			if ( is_wp_error( $attachment_id ) ) return $attachment_id;
			return $attachment_id;
		}
		// URL sideload.
		if ( !empty( $data['source_url'] ) ) {
			$source_url = esc_url_raw( $data['source_url'] );
			// wp_http_validate_url still permits private/reserved hosts (incl. the 169.254 cloud-metadata range), so also require every resolved address to be publicly routable before fetching.
			if ( !$source_url || !wp_http_validate_url( $source_url ) || !static::is_public_url( $source_url ) ) {
				return Utils::error( 'em_api_media_invalid_url', __( 'Invalid source URL.', 'events-manager' ), 400 );
			}
			$post_id = !empty( $data['post_id'] ) ? absint( $data['post_id'] ) : 0;
			$desc = !empty( $data['title'] ) ? sanitize_text_field( $data['title'] ) : null;
			// The host is resolved again when the download connects and on every redirect, so a DNS answer that changes after the check above (rebinding) or a redirect to a private address would slip past it. Re-check each hop and pin cURL to the address just validated.
			$pin = array( static::class, 'pin_public_request' );
			$redirect_guard = array( static::class, 'guard_redirect' );
			add_action( 'http_api_curl', $pin, 10, 1 );
			add_action( 'requests-requests.before_redirect', $redirect_guard, 10, 1 );
			try {
				$attachment_id = media_sideload_image( $source_url, $post_id, $desc, 'id' );
			} finally {
				remove_action( 'http_api_curl', $pin, 10 );
				remove_action( 'requests-requests.before_redirect', $redirect_guard, 10 );
			}
			if ( is_wp_error( $attachment_id ) ) return $attachment_id;
			return absint( $attachment_id );
		}
		// Base64 inline upload.
		if ( !empty( $data['content_base64'] ) ) {
			$filename = !empty( $data['filename'] ) ? sanitize_file_name( $data['filename'] ) : 'upload-' . wp_unique_id( 'em-' ) . '.bin';
			$bytes = base64_decode( $data['content_base64'], true );
			if ( $bytes === false || $bytes === '' ) {
				return Utils::error( 'em_api_media_invalid_base64', __( 'content_base64 is not valid base64 data.', 'events-manager' ), 400 );
			}
			$tmp_file = wp_tempnam( $filename );
			if ( !$tmp_file || file_put_contents( $tmp_file, $bytes ) === false ) {
				return Utils::error( 'em_api_media_tempfile_failed', __( 'Failed to write upload to temporary file.', 'events-manager' ), 500 );
			}
			$file_array = array(
				'name'     => $filename,
				'tmp_name' => $tmp_file,
				'error'    => 0,
				'size'     => filesize( $tmp_file ),
			);
			if ( !empty( $data['mime_type'] ) ) $file_array['type'] = sanitize_text_field( $data['mime_type'] );
			$post_id = !empty( $data['post_id'] ) ? absint( $data['post_id'] ) : 0;
			$desc = !empty( $data['title'] ) ? sanitize_text_field( $data['title'] ) : null;
			$attachment_id = media_handle_sideload( $file_array, $post_id, $desc );
			if ( file_exists( $tmp_file ) ) @unlink( $tmp_file );
			if ( is_wp_error( $attachment_id ) ) return $attachment_id;
			return absint( $attachment_id );
		}
		return Utils::error( 'em_api_media_missing_source', __( 'Provide one of `id`, `source_url`, `content_base64`, or a multipart `file` upload.', 'events-manager' ), 400 );
	}

	/**
	 * Confirms every address the host resolves to is publicly routable, guarding source_url sideloads against SSRF to loopback, private, reserved or link-local ranges (notably the 169.254.0.0/16 cloud-metadata range that wp_http_validate_url permits).
	 */
	protected static function is_public_url( $url ) {
		return (bool) static::public_ips( $url );
	}

	/**
	 * Resolves the URL's host and returns its addresses only when every one is publicly routable, otherwise false.
	 */
	protected static function public_ips( $url ) {
		$scheme = strtolower( (string) wp_parse_url( $url, PHP_URL_SCHEME ) );
		if ( !in_array( $scheme, array( 'http', 'https' ), true ) ) {
			return false;
		}
		$host = wp_parse_url( $url, PHP_URL_HOST );
		if ( empty( $host ) || strtolower( $host ) === 'localhost' ) {
			return false;
		}
		$host = trim( $host, '[]' );
		if ( filter_var( $host, FILTER_VALIDATE_IP ) ) {
			$ips = array( $host );
		} else {
			// gethostbynamel() is IPv4-only, so an AAAA-only name pointing at a private address would otherwise pass.
			$ips = (array) gethostbynamel( $host );
			foreach ( (array) @dns_get_record( $host, DNS_AAAA ) as $record ) {
				if ( !empty( $record['ipv6'] ) ) $ips[] = $record['ipv6'];
			}
		}
		$ips = array_filter( $ips );
		if ( empty( $ips ) ) {
			return false;
		}
		foreach ( $ips as $ip ) {
			if ( ! filter_var( $ip, FILTER_VALIDATE_IP, FILTER_FLAG_NO_PRIV_RANGE | FILTER_FLAG_NO_RES_RANGE ) ) {
				return false;
			}
		}
		return array_values( $ips );
	}

	/**
	 * http_api_curl callback for source_url sideloads: re-validates the URL this cURL handle is about to fetch (each redirect hop gets its own handle) and pins the connection to the address just checked.
	 */
	public static function pin_public_request( $handle ) {
		$url = curl_getinfo( $handle, CURLINFO_EFFECTIVE_URL );
		$ips = static::public_ips( $url );
		if ( !$ips ) {
			static::refuse_request();
		}
		$host = trim( wp_parse_url( $url, PHP_URL_HOST ), '[]' );
		if ( !filter_var( $host, FILTER_VALIDATE_IP ) ) {
			$port = wp_parse_url( $url, PHP_URL_PORT ) ?: ( strtolower( wp_parse_url( $url, PHP_URL_SCHEME ) ) === 'https' ? 443 : 80 );
			$ip = $ips[0];
			curl_setopt( $handle, CURLOPT_RESOLVE, array( $host . ':' . $port . ':' . ( strpos( $ip, ':' ) !== false ? '[' . $ip . ']' : $ip ) ) );
		}
	}

	/**
	 * Redirect check for source_url sideloads, covering non-cURL transports too, since WordPress' own redirect validation resolves IPv4 only and older versions still allow the 169.254 cloud-metadata range.
	 */
	public static function guard_redirect( $location ) {
		if ( !static::is_public_url( $location ) ) {
			static::refuse_request();
		}
	}

	/**
	 * Aborts the in-flight request; WP_Http turns a Requests exception into a WP_Error for the caller.
	 */
	protected static function refuse_request() {
		$class = class_exists( '\WpOrg\Requests\Exception' ) ? '\WpOrg\Requests\Exception' : '\Requests_Exception';
		throw new $class( __( 'Invalid source URL.', 'events-manager' ), 'em_api_media_invalid_url' );
	}

	/**
	 * Returns the canonical API shape for an attachment, used by upload_media and by the polymorphic featured-image / term-image resolvers on the read side.
	 */
	public static function prepare_attachment( $attachment_id ) {
		$attachment_id = absint( $attachment_id );
		if ( !$attachment_id || get_post_type( $attachment_id ) !== 'attachment' ) return null;
		$meta = wp_get_attachment_metadata( $attachment_id );
		$url = wp_get_attachment_url( $attachment_id );
		$alt = get_post_meta( $attachment_id, '_wp_attachment_image_alt', true );
		$post = get_post( $attachment_id );
		$api = array(
			'id'        => $attachment_id,
			'url'       => $url ?: null,
			'mime_type' => $post ? $post->post_mime_type : null,
			'title'     => $post ? $post->post_title : null,
			'alt_text'  => $alt ?: null,
			'width'     => isset( $meta['width'] ) ? absint( $meta['width'] ) : null,
			'height'    => isset( $meta['height'] ) ? absint( $meta['height'] ) : null,
		);
		return apply_filters( 'em_api_prepare_attachment', $api, $attachment_id );
	}

	/**
	 * Polymorphic featured-image / term-image resolver. Accepts the same shapes as upload_media plus a bare integer (attachment ID) or string (URL — sideloaded). Returns an attachment ID, null to clear, or a WP_Error. Used by event/location featured_image and term image inputs to keep one mental model for "give me an image" across every resource.
	 */
	public static function resolve_image_input( $input, $post_id = 0 ) {
		if ( $input === null || $input === '' || $input === false ) return null; // explicit clear
		if ( is_numeric( $input ) ) {
			return static::resolve_attachment_id( array( 'id' => $input ) );
		}
		if ( is_string( $input ) ) {
			return static::resolve_attachment_id( array( 'source_url' => $input, 'post_id' => $post_id ) );
		}
		if ( is_array( $input ) ) {
			if ( $post_id && empty( $input['post_id'] ) ) $input['post_id'] = $post_id;
			return static::resolve_attachment_id( $input );
		}
		return Utils::error( 'em_api_image_invalid', __( 'Image input must be an attachment ID, URL, or object with source_url / content_base64 / file.', 'events-manager' ), 400 );
	}

	protected static function get_consent_classes() {
		$classes = array_filter( array(
			class_exists( '\EM\Consent\Consent' ) ? '\EM\Consent\Consent' : null,
			class_exists( '\EM\Consent\Privacy' ) ? '\EM\Consent\Privacy' : null,
			class_exists( '\EM\Consent\Comms' ) ? '\EM\Consent\Comms' : null,
		) );
		return apply_filters( 'em_api_consent_classes', $classes );
	}
}
