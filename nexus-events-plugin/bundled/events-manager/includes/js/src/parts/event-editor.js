/**
 * Resolve the element that scopes a recurrence editor's event-level "When" fields. In the classic editor the recurrences metabox lives inside the post <form>, so closest('form') finds it. In the Gutenberg canvas block the same metabox HTML is injected into a .em-event-when-block <div> with no surrounding <form>, so closest('form') returns null and any closest('form').querySelector(...) call throws a TypeError. Fall back to the canvas block container, then document, so these lookups resolve in both contexts. Declared at the file's top level (the recurrence handlers below live outside the first IIFE) so every call site can see it.
 */
function emRecurrenceFormRoot( el ) {
	return el.closest('form') || el.closest('.em-event-when-block') || document;
}

document.addEventListener('em_event_editor_ready', function() {

	// load event recurrence data
	document.querySelectorAll('.em-recurrence-sets').forEach( function( recurrenceSets ) {
		recurrenceSets.querySelector('.em-recurrence-set[data-type="include"]:first-child').dataset.primary = "1"; // set primary recurrence flag for JS (CSS uses selector instead)
		document.dispatchEvent( new CustomEvent('em_event_editor_recurrences', { detail: { recurrenceSets : recurrenceSets } } ) );
	});

	// Event Status Warning
	document.querySelectorAll('select[name="event_active_status"]').forEach(select => {
		select.addEventListener('change', function (event) {
			if ( select.value === '0' && !confirm( EM.event_cancellations.warning.replace(/\\n/g, '\n') ) ) { 
				event.preventDefault();
			}
		});
	});

	// disable recurrence meta box selection since we must always show it
	document.getElementById('em-event-recurring-hide')?.setAttribute('disabled', '');

	// Handle the recurring/repeating event selection (extracted to setupEventTypeToggles
	// so it can run per-container; see the em_setup_ui_elements listener below).
	setupEventTypeToggles( document );

	document.dispatchEvent( new CustomEvent('em_event_editor_loaded') );
});

// Re-run the event-type setup whenever EM (re)initialises UI inside a container. EM binds
// .event_type once on em_event_editor_ready against document, which only reaches the hidden
// classic metabox — the Gutenberg canvas block's checkbox lives in the editor-canvas iframe.
// The block calls em_setup_ui_elements( container ) after injecting its metabox HTML, so this
// wires the canvas copy too.
document.addEventListener('em_setup_ui_elements', function( e ) {
	if ( e.detail && e.detail.container ) {
		setupEventTypeToggles( e.detail.container );
	}
});

/**
 * Wire the recurring/repeating event-type control(s) within a root element. Idempotent via
 * data-em-type-bound. handleRecurring toggles em-is-recurring / em-type-* on the resolved
 * form root so EM's existing visibility CSS does the showing/hiding — no per-context CSS.
 */
function setupEventTypeToggles( root ) {
	( root || document ).querySelectorAll( '.event_type' ).forEach( eventType => {
		if ( eventType.dataset.emTypeBound ) {
			return;
		}
		eventType.dataset.emTypeBound = '1';
		const form = emRecurrenceFormRoot( eventType );
		eventType.addEventListener( 'change', function () {
			// When set to recurring or repeating, sync the main event data to primary recurrence set
			if ( handleRecurring() ) {
				let eventDateTimes = form.querySelector('.event-form-when');
				let eventDatePicker = eventDateTimes.querySelector('.em-datepicker.em-event-dates');
				let selectedDates;
				if ( eventDatePicker.classList.contains('em-datepicker-until') ) {
					selectedDates = [
						eventDatePicker.querySelector('.em-date-input-start.flatpickr-input')._flatpickr.selectedDates[0],
						eventDatePicker.querySelector('.em-date-input-end.flatpickr-input')._flatpickr.selectedDates[0]
					];
				} else {
					selectedDates = eventDatePicker.querySelector('.em-date-input.flatpickr-input')._flatpickr.selectedDates;
				}
				let eventTimeRange = eventDateTimes.querySelector('.em-time-range');
				// we need to get jQuery elements to handle the timepicker
				let eventStartTime = eventTimeRange.querySelector('.em-time-input.em-time-start');
				let eventEndTime = eventTimeRange.querySelector('.em-time-input.em-time-end');
				let eventAllDay = eventTimeRange.querySelector('input.em-time-all-day');
				let timezone = eventDateTimes.querySelector('select.event_timezone')?.value;
				let eventStatus = eventDateTimes.querySelector('select.event_active_status')?.value;
				let setDateTimes = false;

				// here, we're copying over all the regular event date/time/timezone data into the primary recurrence so there's some UI continuity in case user started adding dates before selecting recurring type
				let recurrenceSet = form.querySelector('.em-recurrence-set[data-primary="1"]');
				if ( recurrenceSet ) {
					// copy over the times first - if not the datepicker triggers a change loop and sets the 12am times back onto the event
					let timeRange = recurrenceSet.querySelector( '.em-recurrence-advanced .em-time-range' );
					if ( timeRange ) {
						let recurrenceStartTime = timeRange.querySelector( '.em-time-input.em-time-start' );
						let recurrenceEndTime = timeRange.querySelector( '.em-time-input.em-time-end' );
						let recurrenceAllDay = timeRange.querySelector( '.em-time-all-day' );
						if ( recurrenceStartTime ) {
							recurrenceStartTime.value = eventStartTime?.value;
						}
						if ( recurrenceEndTime ) {
							recurrenceEndTime.value = eventEndTime?.value;
						}
						if ( recurrenceAllDay ) {
							recurrenceAllDay.checked = eventAllDay?.checked;
						}
					}
					// get equivalent datepicker, timepicker and timezone
					if ( recurrenceSet.querySelector('select.recurrence_freq')?.value === 'on' ) {
						// we set the selected dates to those we selected in the datepicker, for now
						let recurrenceDatePicker = recurrenceSet.querySelector('.em-on-selector .em-date-input.flatpickr-input')?._flatpickr
						if ( !recurrenceDatePicker?.selectedDates ) {
							recurrenceDatePicker?.setDate( selectedDates, true );
							setDateTimes = true; // setting date triggers the setDateTimes event already
						}
					} else {
						// get the regular date range
						recurrenceSet.querySelectorAll('.em-recurrence-advanced .em-datepicker .em-date-input.flatpickr-input').forEach( input => {
							// add if we don't have dates set already
							if ( !input._flatpickr?.selectedDates.length ) {
								if (input.closest('.em-datepicker-until')) {
									input._flatpickr.setDate( input.classList.contains('em-date-input-start') ? selectedDates[0] : selectedDates[1], true );
									setDateTimes = true; // setting date triggers the setDateTimes event already
								} else if (input.closest('.em-datepicker-range')) {
									input._flatpickr.setDate( selectedDates, true );
									setDateTimes = true; // setting date triggers the setDateTimes event already
								}
							}
						});
					}
					// copy over the timezone
					[ 'select.recurrence_timezone', 'select.recurrence_status' ].forEach( selector => {
						let select = recurrenceSet.querySelector( selector );
						let value = selector === 'select.recurrence_timezone' ? timezone : eventStatus;
						if ( value && select ) {
							if ( select.selectize ) {
								select.selectize.setValue( value, true );
							} else {
								select.value = value;
							}
						}
					});
					// trigger a recurrence summary refresh
					if ( !setDateTimes ) {
						recurrenceSet.closest( '.em-recurrence-sets' ).dispatchEvent( new CustomEvent( 'setDateTimes' ) );
					}
				}
			}
		});
		/**
		 * Handles toggling of recurring event settings for a form element.
		 * Determines if the event is recurring based on the specified event type and updates the form element's classes accordingly.
		 */
		let handleRecurring = function() {
			// check now if it's recurring as well
			let isRecurring = false;
			if ( form ) {
				// it's recurring/repeating if the checkbox is checked, we add is-recurring regardless
				isRecurring = eventType.type === 'checkbox' ? eventType.checked : eventType.value !== 'single';
				form.classList.toggle( 'em-is-recurring', isRecurring );
				if ( eventType.type === 'checkbox' ) {
					// checkboxes are now only for recurring
					form.classList.toggle( 'em-type-recurring', eventType.checked );
				}
				// remove the em-type- classes and add the current selected type, defaulting to single
				form.classList.remove( ...[ ...form.classList ].filter( className => className.startsWith( 'em-type-' ) ) );
				form.classList.add( 'em-type-' + eventType.value );
			}
			return isRecurring;
		}
		handleRecurring();
	});
}