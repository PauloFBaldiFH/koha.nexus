(function() {
	'use strict';

	/**
	 * Timeranges Editor functionality
	 */
	function TimerangesEditor( container ) {
		this.init( container );
	}

	TimerangesEditor.prototype = {
		init: function( container = null ) {
			this.bindEvents( container );
		},

		bindEvents: function( container = null ) {
			let wrapper = container || document;
			let self = this;

			// Initialize preview if there are existing timeranges
			wrapper.querySelectorAll('.em-timeranges-editor').forEach( editor => {
				// Guard against double-binding. These listeners attach to the editor
				// element directly, and in the Gutenberg canvas em_setup_ui_elements can
				// re-run bindEvents over the same editor (e.g. after editing a recurrence
				// date/timeslot), which would stack a duplicate handler and make "Add Time
				// Slot" insert two timeranges per click.
				if ( editor.dataset.emTimerangesBound ) {
					return;
				}
				editor.dataset.emTimerangesBound = '1';

				// Add timerange button
				editor.addEventListener('click', function(e) {
					if (e.target.matches('.em-timerange-add') || e.target.closest('.em-timerange-add')) {
						e.preventDefault();
						let button = e.target.matches('.em-timerange-add') ? e.target : e.target.closest('.em-timerange-add');
						self.addTimerange(button);
						self.updatePreview(e.target);
					}
				});

				// Delete timerange button
				editor.addEventListener('click', function(e) {
					if (e.target.matches('.em-timerange-delete') || e.target.closest('.em-timerange-delete')) {
						e.preventDefault();
						let button = e.target.matches('.em-timerange-delete') ? e.target : e.target.closest('.em-timerange-delete');
						let timeranges = button.closest('.em-timeranges');
						self.deleteTimerange(button);
						self.updatePreview( timeranges );
					}
					// handle the editor
					if ( e.target.matches('.em-timerange-editor-edit') ) {
						self.openUnlockModal( e.target );
					}
				});

				editor.querySelector('.em-timeranges-editor-modal')?.addEventListener('click', function(e) {
					if ( e.target.matches('button.unlock-confirm') ) {
						self.unlockEditor( e.target );
					} else if ( e.target.matches('button.unlock-cancel') ) {
						closeModal( e.currentTarget );
					}
				});

				// Time range validation and overlap detection
				editor.addEventListener('change', function(e) {
					if (e.target.matches('.em-time-start, .em-time-end, .em-time-all-day')) {
						self.validateTimeRanges(e.target);
						// Also update preview when time ranges change
						self.updatePreview(e.target);
					}
				});

				// Advanced options changes
				editor.addEventListener('change', function(e) {
					if (e.target.matches('.em-timerange-duration, .em-timerange-buffer, .em-timerange-frequency, .em-timerange-duration-unit, .em-timerange-buffer-unit, .em-timerange-frequency-unit, .em-timerange-overlap')) {
						self.updatePreview(e.target);
						if (e.target.matches('.em-timerange-duration-unit')) {
							self.syncFrequencyUnit(e.target);
						}
					}
				});

				// Real-time preview updates for time inputs
				editor.addEventListener('input', function(e) {
					if (e.target.matches('.em-time-start, .em-time-end')) {
						self.updatePreview(e.target);
					}
				});

				// Real-time duration changes to update frequency placeholder
				editor.addEventListener('input', function(e) {
					if (e.target.matches('.em-timerange-duration')) {
						self.syncFrequencyWithDuration(e.target);
						self.updatePreview(e.target);
					}
				});

				// Mutual exclusivity between advanced and all-day checkboxes
				editor.addEventListener('change', function(e) {
					if (e.target.matches('.em-timerange-timeslots-trigger input[type="checkbox"]')) {
						self.handleAdvancedToggle(e.target);
					} else if (e.target.matches('.em-timerange-allday input[type="checkbox"]')) {
						self.handleAllDayToggle(e.target);
						self.updatePreview(e.target);
					}
				});

				// Preview toggle
				editor.addEventListener('click', function(e) {
					if (e.target.matches('.em-timeranges-preview-toggle') || e.target.closest('.em-timeranges-preview-toggle')) {
						e.preventDefault();
						let toggle = e.target.matches('.em-timeranges-preview-toggle') ? e.target : e.target.closest('.em-timeranges-preview-toggle');
						self.togglePreview(toggle);
					}
				});

				editor.querySelectorAll('.em-timerange .em-time-start').forEach( input => {
					self.updatePreview( input );
				});
				// disable things if there's a disabled class (for recurring/repeating events)
				if ( editor.classList.contains('disabled') ) {
					let selector = 'input[name], .em-timeranges select, .em-timeranges button:not(.em-timerange-editor-edit), .em-timeranges-actions button';
					editor.querySelectorAll( selector ).forEach( el => { el.disabled = true; });
				}
			});
		},

		openUnlockModal: function( button ) {
			let editor = button.closest('.em-timeranges-editor');
			let modal = button.closest('.em-timeranges-editor').querySelector('.em-timeranges-editor-modal');
			modal.editor = editor;
			openModal( modal );
			modal.addEventListener( 'em_modal_close', function() {
				// re-append modal on close for submission
				editor.append(modal);
			}, { once: true });
		},

		unlockEditor: function( button ) {
			// modal actions confirming reschedule and re-appending modal upon close
			let modal  = button.closest('.em-timeranges-editor-modal');
			modal.editor.classList.remove('disabled')
			// remove all disabled properties
			modal.editor.querySelectorAll('[disabled]').forEach( el => { el.disabled = false; });
			// move the edit action option to the recurrence set to make it visible
			let timeranges = modal.editor.querySelector('.em-timeranges');
			timeranges.insertBefore( modal.querySelector('.timeranges-edit-action'), timeranges.firstElementChild.nextSibling );
			// set the edit nonce so we can update the timeranges on submission
			let nonce = modal.editor.querySelector('.em-timeranges-editor-nonce');
			if ( nonce ) {
				nonce.value = nonce.dataset.nonce;
			} else {
				alert('ERROR: No nonce found for timeranges edit, editing not possible and your changes will not be saved. Contact an administrator about this.');
			}
			closeModal(modal);
		},

		addTimerange: function(button) {
			let container = button.closest('.em-timeranges-editor').querySelector('.em-timeranges');
			let template = container.querySelector('template');
			let currentIndex = parseInt( container.dataset.index || '0', 10 );
			let newIndex = currentIndex + 1;

			if (template) {
				// Get template content
				let templateHtml = template.innerHTML;

				// Replace [X] placeholders with new index
				let newTimerangeHtml = templateHtml.replace(/\[X\]/g, `[${newIndex}]`);

				// Create new timerange element
				let tempDiv = document.createElement('div');
				tempDiv.innerHTML = newTimerangeHtml;
				let newTimerange = tempDiv.firstElementChild;

				// Insert before the add button
				template.before(newTimerange);
				em_setup_ui_elements(newTimerange);

				// Initialize frequency sync for new timerange
				let durationInput = newTimerange.querySelector('.em-timerange-duration');
				if (durationInput) {
					this.syncFrequencyWithDuration(durationInput);
				}

				// unset all day checkboxes
				container.querySelectorAll('.em-timerange-allday input[type="checkbox"]').forEach( checkbox => { if ( checkbox.checked ) { checkbox.click(); } } );

				// Update count
				container.dataset.index = newIndex;
				container.dataset.count = container.querySelectorAll('& > .em-timerange').length;

				// Update preview after adding new timerange
				let startInput = newTimerange.querySelector('.em-time-start');
				if (startInput) {
					this.updatePreview(startInput);
				}

				// Trigger custom event
				let event = new CustomEvent('timerange:added', {
					detail: { timerange: newTimerange, index: newIndex }
				});
				container.dispatchEvent(event);
			}
		},

		deleteTimerange: function(button) {
			let container = button.closest('.em-timeranges-editor').querySelector('.em-timeranges');
			let currentCount = container.querySelectorAll('& > .em-timerange').length;
			let timerange = button.closest('.em-timerange');

			// Only allow deletion if more than one timerange exists
			if ( currentCount > 1 ) {
				// move the delete meta input to the editor for submission
				let nonce = timerange.querySelector('.em-timerange-delete-nonce');
				if ( nonce ) {
					nonce.value = nonce.dataset.nonce;
					container.append(nonce);
				}
				// Remove the timerange
				timerange.remove();
				// Update count
				currentCount--;
				container.dataset.count = container.querySelectorAll('& > .em-timerange').length;
				// Trigger custom event
				let event = new CustomEvent('em_timerange:deleted', {
					detail: { count: currentCount }
				});
				container.dispatchEvent(event);
			}
		},

		handleAdvancedToggle: function(advancedCheckbox) {
			// Find the corresponding all-day checkbox in the same timerange
			let timerange = advancedCheckbox.closest('.em-timerange');
			if (advancedCheckbox.checked) {
				// unset all advanced text inputs
				timerange.querySelectorAll('.em-timerange-timeslots input[type="text"]').forEach( input => { input.value = ''; input.setAttribute('placeholder', '0'); });

				let allDayCheckbox = timerange.querySelector('.em-timerange-allday input[type="checkbox"]');

				if (allDayCheckbox && allDayCheckbox.checked) {
					allDayCheckbox.checked = false;
					// Trigger change event to ensure any other listeners are notified
					allDayCheckbox.dispatchEvent(new Event('change', { bubbles: true }));
				}
			} else {
				// unset all advanced text inputs
				timerange.querySelectorAll('.em-timerange-timeslots input[type="text"]').forEach( input => { input.value = ''; input.setAttribute('placeholder', '0'); });
				this.updatePreview( advancedCheckbox )
			}
		},

		handleAllDayToggle: function(allDayCheckbox) {
			if (allDayCheckbox.checked) {
				// Find the corresponding advanced checkbox in the same timerange
				let timerange = allDayCheckbox.closest('.em-timerange');
				// unset all advanced text inputs
				timerange.querySelectorAll('.em-timerange-timeslots input[type="text"]').forEach( input => { input.value = ''; input.setAttribute('placeholder', '0'); });

				let advancedCheckbox = timerange.querySelector('.em-timerange-timeslots-trigger input[type="checkbox"]');
				if (advancedCheckbox && advancedCheckbox.checked) {
					advancedCheckbox.checked = false;
					// Trigger change event to ensure any other listeners are notified
					advancedCheckbox.dispatchEvent(new Event('change', { bubbles: true }));
				}
			}
		},

		validateTimeRanges: function(changedInput) {
			let container = changedInput.closest('.em-timeranges');
			if (!container) return;

			let allTimeranges = container.querySelectorAll('.em-timerange');
			let hasErrors = false;

			// Clear existing errors, then put back the end-before-start flags this pass does not own.
			allTimeranges.forEach(timerange => {
				timerange.querySelectorAll('.em-time-start, .em-time-end').forEach(input => {
					input.classList.remove('error');
				});
				timerange.querySelectorAll('.em-time-end').forEach(input => {
					em_validate_end_time(input);
				});
			});

			// Get all time ranges
			let timeRanges = [];
			allTimeranges.forEach((timerange, index) => {
				let startInput = timerange.querySelector('.em-time-start');
				let endInput = timerange.querySelector('.em-time-end');

				if (startInput && endInput && startInput.value && endInput.value) {
					timeRanges.push({
						index: index,
						start: this.timeToMinutes(startInput.value),
						end: this.timeToMinutes(endInput.value),
						startInput: startInput,
						endInput: endInput
					});
				}
			});

			// Check for overlaps
			for (let i = 0; i < timeRanges.length; i++) {
				for (let j = i + 1; j < timeRanges.length; j++) {
					let range1 = timeRanges[i];
					let range2 = timeRanges[j];

					// Check if ranges overlap
					if (this.rangesOverlap(range1, range2)) {
						range1.startInput.classList.add('error');
						range1.endInput.classList.add('error');
						range2.startInput.classList.add('error');
						range2.endInput.classList.add('error');
						hasErrors = true;
					}
				}
			}

			return !hasErrors;
		},

		timeToMinutes: function(timeString) {
			if (!timeString) return 0;

			let parts = timeString.toLowerCase().replace(/\s/g, '').match(/^(\d{1,2}):?(\d{2})?\s*(am|pm)?$/);
			if (!parts) return 0;

			let hours = parseInt(parts[1]);
			let minutes = parseInt(parts[2] || 0);
			let ampm = parts[3];

			if (ampm === 'pm' && hours !== 12) hours += 12;
			if (ampm === 'am' && hours === 12) hours = 0;

			return hours * 60 + minutes;
		},

		rangesOverlap: function(range1, range2) {
			// Handle cases where end time is next day (crosses midnight)
			let start1 = range1.start;
			let end1 = range1.end;
			let start2 = range2.start;
			let end2 = range2.end;

			if (end1 < start1) end1 += 24 * 60; // Add 24 hours if crossing midnight
			if (end2 < start2) end2 += 24 * 60; // Add 24 hours if crossing midnight

			return (start1 < end2) && (start2 < end1);
		},

		syncFrequencyWithDuration: function(durationInput) {
			let timerange = durationInput.closest('.em-timerange');
			if ( timerange ) {
				let frequencyInput = timerange.querySelector( '.em-timerange-frequency' );
				// Don't sync if frequency has a value
				if ( frequencyInput ) {
					// Update placeholder with duration value
					frequencyInput.placeholder = durationInput.value || '0';
				}
			}
		},

		syncFrequencyUnit: function(durationUnitSelect) {
			let frequencyUnitSelect = durationUnitSelect.closest('.em-timerange')?.querySelector('.em-timerange-frequency-unit');
			// Don't sync if frequency has a value
			if ( frequencyUnitSelect && !frequencyUnitSelect.previousElementSibling?.value ) {
				// Sync frequency unit with duration unit
				frequencyUnitSelect.value = durationUnitSelect.value;
			}
		},

		updatePreview: function(changedInput) {
			let editor = changedInput.closest('.em-timeranges-editor');
			let previewDiv = editor.querySelector('.em-timeranges-preview');
			let previewContent = previewDiv.querySelector('.em-timeranges-preview-content');

			if ( !previewContent ) return;

			// Get all timeranges and aggregate their times
			let timeranges = editor.querySelector( '.em-timeranges' );
			let allTimeranges = timeranges.querySelectorAll( '.em-timerange' );
			let allGeneratedTimes = [];
			let earliestTime = null;
			let latestTime = null;
			let latestTimeFormatted = null;
			let earliestTimeFormatted = null;
			let allDay = false;

			allTimeranges.forEach( timerange => {
				let startInput = timerange.querySelector( '.em-time-start' );
				let endInput = timerange.querySelector( '.em-time-end' );

				let duration = this.getTimeValue( timerange, 'duration' );
				let buffer = this.getTimeValue( timerange, 'buffer' );
				let frequency = this.getTimeValue( timerange, 'frequency' );

				// Track earliest and latest times
				if ( startInput.value ) {
					let startMinutes = this.timeToMinutes( startInput.value );
					if ( earliestTime === null || startMinutes < earliestTime ) {
						earliestTime = startMinutes;
						earliestTimeFormatted = startInput.value;
						startInput.classList.add('earliest-time');
					} else {
						startInput.classList.remove('earliest-time');
					}
				}
				if ( endInput.value ) {
					let endMinutes = this.timeToMinutes( endInput.value );
					if ( latestTime === null || endMinutes > latestTime ) {
						latestTime = endMinutes;
						latestTimeFormatted = endInput.value;
						endInput.classList.add('latest-time');
					} else {
						endInput.classList.remove('latest-time');
					}
				}
				if ( timerange.querySelector( '.em-timerange-allday input[type="checkbox"]' )?.checked ) {
					allDay = true;
				}

				if ( duration || frequency ) {
					let times = this.generateTimeranges( startInput.value, endInput.value, duration, buffer, frequency );
					allGeneratedTimes.push( ...times );
				} else {
					let startMinutes = this.timeToMinutes( startInput.value );
					allGeneratedTimes.push( startMinutes );
				}
			} );

			// Remove duplicates
			let uniqueTimes = [ ...new Set( allGeneratedTimes ) ];
			// reorder array by value
			uniqueTimes.sort( (a, b) => a - b );
			// get formatted times
			uniqueTimes = uniqueTimes.map( time => this.formatTimeRange( time ) );

			// Add earliest and latest times as data attributes
			timeranges.dataset.start = earliestTimeFormatted;
			timeranges.dataset.end = latestTimeFormatted;
			timeranges.dataset.allday = allDay ? 1:0;

			previewDiv.classList.toggle( 'hidden', uniqueTimes.length === 0 || ( uniqueTimes.length === 1 && allTimeranges.length === 1 ) );
			previewContent.innerHTML = uniqueTimes.join( '' );
			previewDiv.querySelector( '.em-timeranges-preview-count' ).textContent = uniqueTimes.length;
		},

		formatSingleTime: function ( timeString ) {
			if ( !timeString ) return '';
			let minutes = this.timeToMinutes( timeString );
			let hours = Math.floor( minutes / 60 );
			let mins = minutes % 60;

			let ampm = hours >= 12 ? 'PM' : 'AM';
			let displayHours = hours > 12 ? hours - 12 : (hours === 0 ? 12 : hours);

			return `${displayHours}:${mins.toString().padStart(2, '0')} ${ampm}`;
		},

		getTimeValue: function(timerange, type) {
			let qtyInput = timerange.querySelector(`.em-timerange-${type}`);
			let unitSelect = timerange.querySelector(`.em-timerange-${type}-unit`);

			if (!qtyInput || !unitSelect || !qtyInput.value) return 0;

			let qty = parseInt(qtyInput.value);
			let unit = unitSelect.value;

			// Convert to minutes
			switch (unit) {
				case 'H': return qty * 60; // Hours to minutes
				case 'I': return qty;      // Minutes
				case 'S': return Math.round(qty / 60); // Seconds to minutes (rounded)
				default: return qty;
			}
		},

		generateTimeranges: function(startTime, endTime, duration, buffer, frequency) {
			let startMinutes = this.timeToMinutes(startTime);
			let endMinutes = this.timeToMinutes(endTime);
			let slots = [];
			// Handle crossing midnight

			if (endMinutes >= startMinutes) {
				let currentStart = startMinutes;

				if ( currentStart === endMinutes ) {
					slots.push( currentStart );
				} else {
					let interval = frequency > 0 ? frequency : duration + ( buffer || 0 );
					// Generate overlapping slots based on frequency
					for ( let i = 0; currentStart <= endMinutes; i++ ) {
						//let slotEnd = i ? null : currentStart + duration;
						slots.push( currentStart );
						currentStart += interval;
					}
				}
			}

			return slots;
		},

		formatTimeRange: function( startMinutes, endMinutes = null ) {
			let formatTime = (minutes) => {
				// Handle crossing midnight
				minutes = minutes % (24 * 60);
				if (minutes < 0) minutes += 24 * 60;

				let hours = Math.floor(minutes / 60);
				let mins = minutes % 60;

				let ampm = hours >= 12 ? 'PM' : 'AM';
				let displayHours = hours > 12 ? hours - 12 : (hours === 0 ? 12 : hours);

				return `${displayHours}:${mins.toString().padStart(2, '0')} ${ampm}`;
			};

			let result = `<span class="em-timeranges-preview-time">${formatTime(startMinutes)}`;
			if ( endMinutes ) {
				result += ` - ${formatTime(endMinutes)}`;
			}
			result += '</span>'
			return result;
		},

		togglePreview: function(toggle) {
			let previewDiv = toggle.closest('.em-timeranges-preview');
			let previewContent = previewDiv.querySelector('.em-timeranges-preview-content');
			let chevron = toggle.querySelector('.em-icon-chevron-down, .em-icon-chevron-up');

			if (previewContent.classList.contains('hidden')) {
				previewContent.classList.remove('hidden');
				if (chevron) chevron.className = chevron.className.replace('chevron-down', 'chevron-up');

				// Update preview when expanding
				let container = toggle.closest('.em-timeranges-editor');
				if (container) {
					// Use any timerange input to trigger update, since we now aggregate all
					let anyInput = container.querySelector('.em-timerange .em-time-start');
					if (anyInput) {
						this.updatePreview(anyInput);
					}
				}
			} else {
				previewContent.classList.add('hidden');
				if (chevron) chevron.className = chevron.className.replace('chevron-up', 'chevron-down');
			}
		},
	};

	document.addEventListener('em_event_editor_ready', () => {
		window.EM_TimerangesEditor = new TimerangesEditor();
	});
	// add listener for ui setup
	document.addEventListener('em_setup_ui_elements', function (e) {
		if (e.detail.container !== document) {
			window.EM_TimerangesEditor = new TimerangesEditor( e.detail.container );
		}
	});

})();

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

document.addEventListener('em_event_editor_recurrences', function( e ) {
	let recurrenceSets = e.detail.recurrenceSets;

	// shortcuts for functions in recurrences/ui-functions.js
	let updateRecurrenceSummary = ( recurrenceSet ) => recurrenceSet.dispatchEvent( new CustomEvent('updateRecurrenceSummary', { bubbles: true }) );
	let updateSetsCount = () => recurrenceSets.dispatchEvent( new CustomEvent('updateSetsCount') );
	let updateRecurrenceOrder = () => recurrenceSets.dispatchEvent( new CustomEvent('updateRecurrenceOrder') );


	/* ------------------------------------------------------------
	 Add/Remove Recurrnces
	 ------------------------------------------------------------ */

	// ADD NEW RECURRENCE RULE
	let addRecurrence = function ( recurrenceType ) {
		let recurrenceTypeSets = recurrenceSets.querySelector('.em-recurrence-type-' + recurrenceType + ' .em-recurrence-type-sets');

		// Count existing recurrence sets to determine the new index.
		let index = recurrenceTypeSets.querySelectorAll('.em-recurrence-set').length + 1;

		// Copy template HTML
		let template = recurrenceSets.querySelector('.em-recurrence-set-template');
		if ( !template ) return null;
		let recurrenceSet;
		if ( template instanceof HTMLTemplateElement ) {
			// create a blank div which we'll add classes etc. to
			recurrenceSet = document.createElement('div');
		} else {
			// legacy template override which didn't use a template element to enclose the recurrence set type
			recurrenceSet = template.cloneNode(true);
			recurrenceSet.classList.remove('em-recurrence-set-template', 'hidden');
		}
		// Replace all occurrences of "[N%]" with the new index.
		recurrenceSet.innerHTML = template.innerHTML.replace(/T%/g, `${recurrenceType}`).replace(/N%/g, `${index}`);

		// Remove the 'hidden' class and template-specific class; add the active class.
		recurrenceSet.classList.add('em-recurrence-set', 'new-recurrence-set');
		recurrenceSet.querySelector('.em-recurrence-set-type').value = recurrenceType;
		recurrenceSet.dataset.type = recurrenceType;
		recurrenceSet.dataset.index = index;

		// remove include/exclude specific elements depending on type
		if ( recurrenceType === 'exclude' ) {
			recurrenceSet.querySelectorAll('.em-recurrence-advanced .only-include-type').forEach(el => el.remove() );
		}
		if ( recurrenceType === 'include' ) {
			recurrenceSet.querySelectorAll('.em-recurrence-advanced .only-exclude-type').forEach(el => el.remove() );
		}

		// anything more before we append
		let result = { recurrenceSet: recurrenceSet, index: index, success: true };
		recurrenceTypeSets.dispatchEvent( new CustomEvent('beforeAddRecurrence', { detail: result  }) );

		if ( result.success ) {
			// Insert the new recurrence set above the template.
			recurrenceTypeSets.append(recurrenceSet);
			em_setup_ui_elements( recurrenceSet );
			// run all checks
			updateSetsCount();
			emRecurrenceEditor.updateIntervalDescriptor( recurrenceSet );
			emRecurrenceEditor.updateIntervalSelectors( recurrenceSet );
			emRecurrenceEditor.updateDurationDescriptor( recurrenceSet );
			updateRecurrenceSummary( recurrenceSet );
		}

		return recurrenceSet;
	}
	// add include recurrence
	recurrenceSets.querySelectorAll('.em-add-recurrence-set[data-type="include"]').forEach( function( addButton ){
		addButton.addEventListener( 'click', () => addRecurrence('include') );
	});
	// set up listner to add recurrences, exclude and include, the exclude trigger is in reschedule.js
	// CustomEvent.detail defaults to null, so fall back to the dispatching section's own type rather than throwing on a dispatch that omits it.
	recurrenceSets.addEventListener( 'addRecurrence', function ( e ) {
		let recurrenceType = e.detail?.type ?? e.target.closest?.('.em-recurrence-type')?.dataset.type;
		if ( !recurrenceType ) return;
		let recurrenceSet = addRecurrence( recurrenceType );
		if ( e.detail ) e.detail.recurrenceSet = recurrenceSet;
	});

	// REMOVE A RECURRENCE RULE
	recurrenceSets.addEventListener('click', function ( e ) {
		if ( e.target.matches('.em-recurrence-set-action-remove') ) {
			let removeButton = e.target;
			e.preventDefault();

			// Locate the recurrence set container for this remove action.
			let recurrenceSet = removeButton.closest('.em-recurrence-set');

			// Find the hidden delete field (an input whose name contains "[delete]").
			let setId = recurrenceSet.querySelector('input.em-recurrence-set-id');
			let deleteField = recurrenceSet.querySelector('input.em-recurrence-set-delete-field');
			if (setId && deleteField) {
				// Transfer the data-nonce value to the hidden input's value.
				deleteField.value = deleteField.getAttribute('data-nonce');

				// Move the delete field out of the recurrence set into the recurrence container.
				recurrenceSets.appendChild(deleteField);
				recurrenceSets.appendChild(setId);
			}

			// Remove the entire recurrence set from the DOM.
			recurrenceSet.remove();
			// redo all checks
			updateSetsCount();
			updateRecurrenceOrder();
		}
	});
});

document.addEventListener('em_event_editor_recurrences', function( e ) {
	let recurrenceSets = e.detail.recurrenceSets;
	recurrenceSets.querySelectorAll('.em-recurrence-type-sets').forEach( function( recurrenceTypeSets ) {
		let draggedElem = null;
		let placeholder = null;
		let offsetX = 0, offsetY = 0;
		let originalParent = null, originalNextSibling = null;

		recurrenceTypeSets.addEventListener('mousedown', function(e) {
			recurrenceTypeSets.querySelectorAll('.em-recurrence-set:not(:first-child)').forEach( (recurrenceSet) => recurrenceSet.classList.add('reordering') );
			const handle = e.target.closest('.em-recurrence-set-action-order');
			if (!handle) return;
			const set = handle.closest('.em-recurrence-set');
			if (!set) return;
			e.preventDefault();

			// Store original parent and next sibling for later restoration
			originalParent = set.parentNode;
			originalNextSibling = set.nextSibling;

			const rect = set.getBoundingClientRect();
			// Calculate offsets using page coordinates
			offsetX = e.pageX - (rect.left + window.pageXOffset);
			offsetY = e.pageY - (rect.top + window.pageYOffset);

			// wrap set into div for styling preservation via .em
			draggedElem = document.createElement('div');
			draggedElem.classList.add('em', 'em-recurrence-sets');
			draggedElem.append(set);

			// Create a placeholder with the same dimensions
			placeholder = document.createElement('div');
			placeholder.classList.add('drop-placeholder');
			placeholder.style.height = rect.height + 'px';
			placeholder.style.width = rect.width + 'px';
			originalParent.insertBefore(placeholder, originalNextSibling);

			// Move the dragged element to document.body so its absolute positioning is relative to the document
			document.body.appendChild(draggedElem);
			draggedElem.style.position = 'absolute';
			draggedElem.style.width = "100%";
			draggedElem.style.left = (rect.left + window.pageXOffset) + 'px';
			draggedElem.style.top = (rect.top + window.pageYOffset) + 'px';
			draggedElem.style.zIndex = '1000';

			document.addEventListener('mousemove', onMouseMove);
			document.addEventListener('mouseup', onMouseUp);
		});

		function onMouseMove(e) {
			if (!draggedElem) return;
			// Update dragged element's position so the cursor stays at the same offset
			draggedElem.style.left = (e.pageX - offsetX) + 'px';
			draggedElem.style.top = (e.pageY - offsetY) + 'px';

			// Determine where to place the placeholder in the container
			let sets = Array.from(recurrenceTypeSets.querySelectorAll('.em-recurrence-set'));
			let inserted = false;
			for (let set of sets) {
				let rect = set.getBoundingClientRect();
				let setTop = rect.top + window.pageYOffset;
				if (e.pageY < setTop + rect.height / 2) {
					recurrenceTypeSets.insertBefore(placeholder, set);
					inserted = true;
					break;
				}
			}
			if (!inserted) {
				recurrenceTypeSets.appendChild(placeholder);
			}
		}

		function onMouseUp(e) {
			document.removeEventListener('mousemove', onMouseMove);
			document.removeEventListener('mouseup', onMouseUp);

			// Reinsert the dragged element back into its original container before the placeholder
			recurrenceTypeSets.insertBefore(draggedElem.firstElementChild, placeholder);
			draggedElem.remove();
			placeholder.remove();
			placeholder = null;
			draggedElem = null;
			recurrenceTypeSets.querySelectorAll('.em-recurrence-set').forEach( function( recurrenceSet ) {
				if ( recurrenceSet.matches(':first-child') ) {
					recurrenceSet.dataset.primary = '1';
					recurrenceSet.querySelectorAll('.em-time-all-day').forEach( el => { el.indeterminate = false; } );
				} else {
					delete recurrenceSet.dataset.primary;
				}
				recurrenceSet.classList.remove('reordering')
			});
			recurrenceSets.dispatchEvent( new CustomEvent('updateRecurrenceOrder') ); // we could also bubble this on recurrenceTypeSet
		}
	});
});

document.addEventListener('em_event_editor_recurrences', function( e ) {
	let recurrenceSets = e.detail.recurrenceSets;

	// exclude references used throughout here for rescheduling logic
	let recurrenceExcludeSets = recurrenceSets.querySelector('.em-recurrence-type-exclude');
	let recurrenceExcludeModal = recurrenceExcludeSets?.querySelector(':scope > .em-recurrence-set-reshedule-modal');
	let rescheduleExcludeAction = recurrenceExcludeModal?.querySelector('.recurrence-reschedule-action');
	// an out-of-date theme override of recurrences.php would otherwise unbind every exclude control below
	if ( !recurrenceExcludeSets || !recurrenceExcludeModal || !rescheduleExcludeAction ) return;

	/* ------------------------------------------------------------
	 UNDO FUNCTIONALITY
	 ------------------------------------------------------------ */

	// trigger the undo event when clicked, whether in scope of a recurrent set, set type or all sets
	recurrenceSets.querySelectorAll('button.undo').forEach( function( button ) {
		button.addEventListener('click', () => {
			button.closest('.em-recurrence-set, .em-recurrence-type, .em-recurrence-sets')?.dispatchEvent( new CustomEvent( 'undo', { detail: { button: button }, bubbles: true } ) )
		});
	});
	// listen for an undo event to a single set, set types, or all sets and undo the relevant recurrences.
	recurrenceSets.addEventListener('undo', function( e ) {
		e.stopPropagation();
		let recurrences;
		if ( e.target.matches('.em-recurrence-set') ) {
			recurrences = [e.target];
		} else if ( e.target.matches('.em-recurrence-type') ) {
			recurrences = e.target.querySelectorAll('.em-recurrence-set');
		} else {
			recurrences = recurrenceSets.querySelectorAll('.em-recurrence-set');
		}
		recurrences.forEach( function( recurrenceSet ) {
			// set back previous values and re-disable previously disabled elements
			recurrenceSet.querySelectorAll('[data-undo]:not([type="checkbox"]):not(.selectized)').forEach( input => {
				input.value = input.dataset.undo;
				input.readonly = false;
				input.disabled = false;
				if ( input.classList.contains('em-recurrence-frequency') ) {
					input.dispatchEvent( new Event('change', { bubbles: false }) );
				}
			});
			recurrenceSet.querySelectorAll('input[data-undo][type="checkbox"]').forEach( input => { input.checked = input.dataset.undo === '1'; } );
			//recurrenceSet.querySelectorAll('.em-time-input').forEach( input => { jQuery(input).em_timepicker('setTime', new Date('2020-01-01 ' + input.dataset.undo)) } );
			recurrenceSet.querySelectorAll('.em-datepicker').forEach( function( datePicker ) {
				if ( datePicker.closest('.reschedulable') ) {
					datePicker.querySelectorAll('input.em-date-input').forEach( el => { el.disabled = true; el.value = ''; } );
					datePicker.querySelectorAll('.em-date-input.disabled, .em-datepicker-dates').forEach( el => { el.classList.add('disabled') } );
				}
			});
			em_setup_datepicker_dates( recurrenceSet );
			recurrenceSet.querySelectorAll('select.em-selectize.selectized').forEach( el => {
				if ( el.dataset.undo !== undefined ) {
					el.selectize?.setValue( el.dataset.undo.split(',') );
				}
				// disable rescheduling datepickers
				if ( el.closest('.reschedulable') ) {
					el.selectize?.disable();
				}
			});
			// undo the timepicker, by replacing the stored template
			let timeRangeEditor = recurrenceSet.querySelector('.em-recurrence-timeranges');
			if ( timeRangeEditor ) {
				// a newly added set has no stored undo template to restore from
				let timeRangeTarget = timeRangeEditor.querySelector('.recurrence-timeranges-editor');
				let timeRangeUndo = timeRangeEditor.querySelector('.recurrence-timeranges-undo');
				if ( timeRangeTarget && timeRangeUndo ) {
					timeRangeTarget.innerHTML = timeRangeUndo.innerHTML;
				}
			}
			// disable other rechedulable items
			recurrenceSet.querySelectorAll('.reschedulable [name]:not(.selectized), .reschedulable button').forEach( input => { input.disabled = true; } );
			// disable the nonces to reschedule this button type, a newly added set has no stored nonce to disable
			let setNonce = recurrenceSet.querySelector( 'input[type="hidden"][data-nonce]' );
			if ( setNonce ) setNonce.disabled = true;
			// re-enable the reschedule buttons and set flag to false
			recurrenceSet.querySelectorAll('.reschedule-trigger').forEach( button => { button.disabled = false } );
			delete recurrenceSet.dataset.rescheduled;
			// unset modified flag for advanced icon
			recurrenceSet.classList.remove('advanced-modified', 'advanced-modified-dates');
			// update descriptors and selectors
			emRecurrenceEditor.updateIntervalDescriptor( recurrenceSet );
			emRecurrenceEditor.updateIntervalSelectors( recurrenceSet );
			emRecurrenceEditor.updateDurationDescriptor( recurrenceSet );
		});
		// exclude logic
		if ( e.target.matches('.em-recurrence-type-exclude') ) {
			recurrenceExcludeSets.querySelectorAll('.em-recurrence-set.new-recurrence-set').forEach( recurrenceSet => recurrenceSet.querySelector('.em-recurrence-set-action-remove')?.click() );
			recurrenceExcludeModal.querySelector('.em-modal-content')?.append( rescheduleExcludeAction );
			rescheduleExcludeAction.querySelector('[data-nonce]').disabled = true;
		} else if ( e.target.matches('.em-recurrence-set[data-type="exclude"]') ) {
			// check if there are more reschedulable sets, if not then remove the reshedulable notice
			if ( e.target.closest('.em-recurrence-type-exclude').querySelectorAll('.em-recurrence-set[data-rescheduled]').length === 0 ) {
				recurrenceExcludeModal.querySelector('.em-modal-content')?.append( rescheduleExcludeAction );
			}
		}
		recurrenceSets.dispatchEvent( new CustomEvent('updateSetsCount') );
		recurrenceSets.dispatchEvent( new CustomEvent('setAdvancedDefaults', { bubbles: true }) );
	});


	/* ------------------------------------------------------------
	 RESCHEDULING FUNCTIONALITY
	 ------------------------------------------------------------ */

	// RESCHEDULING BUTTONS
	// recurrence rescheduling buttons & modals - we don't need to listen to delegated events since this only applies to previously-created recurrences
	recurrenceSets.querySelectorAll('.em-recurrence-set').forEach( function( recurrenceSet ){
		delete recurrenceSet.dataset.rescheduled;
		let modal = recurrenceSet.dataset.type === 'exclude' ? recurrenceExcludeModal : recurrenceSet.querySelector('.em-recurrence-set-reshedule-modal');

		// trigger reschedule
		recurrenceSet.querySelectorAll('button.reschedule-trigger').forEach( function( button ) {
			button.addEventListener('click', function( e ){
				if ( recurrenceSet.dataset.rescheduled !== undefined ) {
					unlockReschedule( button );
				} else {
					modal.rescheduleButton = button;
					modal.classList.toggle( 'primary-recurrence', recurrenceSet.dataset.primary );
					openModal( modal );
				}
			});
		});

		if ( recurrenceSet.dataset.type === 'include' ) {
			// modal actions confirming reschedule and re-appending modal upon close
			modal.addEventListener( 'em_modal_close', function() {
				// re-append modal on close for submission
				recurrenceSet.append(modal);
				delete modal.rescheduleButton;
			});
			modal.querySelector('button.reschedule-cancel')?.addEventListener( 'click', () => closeModal(modal) );
			modal.querySelector('button.reschedule-confirm')?.addEventListener( 'click', function( e ) {
				unlockReschedule( modal.rescheduleButton );
				// move the reschedule action option to the recurrence set to make it visible
				recurrenceSet.querySelector('.em-recurrence-pattern')?.prepend( modal.querySelector('.recurrence-reschedule-action') );
				// close modal and mark this as rescheduled
				recurrenceSet.dataset.rescheduled = '1';
				closeModal(modal);
			});
			recurrenceSet.addEventListener('undo', function(){
				modal.querySelector('.em-modal-content')?.append( recurrenceSet.querySelector('.recurrence-reschedule-action') );
			});
		}
	});
	// unlock rescheduling inputs and store undoable values
	let unlockReschedule = function ( rescheduleButton ) {
		// remove disabled property from inputs contained in button container
		let reschedulable = rescheduleButton.closest('.reschedulable');
		reschedulable.querySelectorAll('[disabled]').forEach( el => { el.disabled = false } ); // TODO the label of ON datepicker not enabling
		reschedulable.querySelectorAll('.disabled').forEach( el => { el.classList.remove('disabled') } ); // TODO the label of ON datepicker not enabling
		// save the current date/day selection settings so we can re-establish it
		reschedulable.querySelectorAll('.em-datepicker-data input').forEach( input => { input.dataset.undo = input.value; } );
		reschedulable.querySelectorAll('select.em-selectize.selectized').forEach( function( el ) {
			el.selectize?.enable();
			let days = el.selectize?.getValue();
			if ( days ) {
				el.dataset.undo = days.join();
			}
		});
		// enable the nonce to reschedule this button type
		reschedulable.closest('.em-recurrence-set').querySelector( rescheduleButton.dataset.nonce ).disabled = false;
		reschedulable.querySelectorAll('.reschedule-trigger').forEach( button => { button.disabled = true } );
	};


	// EXCLUDE RESCHEDULING
	// add warning for currently created recurrences and adding a new exclusion
	recurrenceSets.querySelectorAll('.em-add-recurrence-set[data-type="exclude"]').forEach( function( addButton ) {
		addButton.addEventListener('click', function (e) {
			if ( recurrenceExcludeSets.querySelectorAll('[data-rescheduled]').length > 0 || !recurrenceSets.dataset.event_id ) {
				let event = new CustomEvent('addRecurrence', { bubbles: true, detail: { type : 'exclude' } });
				recurrenceSets.dispatchEvent( event );
			} else {
				openModal( recurrenceExcludeModal );
			}
		});
	});
	// modal actions - confirming reschedule and re-appending modal upon close
	recurrenceExcludeModal.addEventListener( 'em_modal_close', function() {
		// re-append modal on close for submission
		recurrenceExcludeSets.append(recurrenceExcludeModal);
		delete recurrenceExcludeModal.rescheduleButton;
	});
	recurrenceExcludeModal.querySelector('button.reschedule-cancel')?.addEventListener( 'click', () => closeModal(recurrenceExcludeModal) );
	recurrenceExcludeModal.querySelector('button.reschedule-confirm')?.addEventListener( 'click', function(e ) {
		let recurrenceSet;
		if ( recurrenceExcludeModal.rescheduleButton ) {
			unlockReschedule( recurrenceExcludeModal.rescheduleButton  )
			recurrenceSet = recurrenceExcludeModal.rescheduleButton.closest('.em-recurrence-set');
		} else {
			let detail = { type : 'exclude' };
			let recurrenceTypeSets = recurrenceSets.querySelector('.em-recurrence-type-exclude');
			recurrenceTypeSets?.dispatchEvent( new CustomEvent('addRecurrence', { bubbles: true, detail: detail }) );
			recurrenceSet = detail.recurrenceSet ?? recurrenceTypeSets?.querySelector('.em-recurrence-set:last-child');
		}
		// mark rescheduled, even if it's new because it essentially can reschedule previously created recurrences by negating them
		if ( recurrenceSet ) {
			recurrenceSet.dataset.rescheduled = '1';
		}
		// move the reschedule action option to the recurrence set to make it visible
		recurrenceExcludeSets.firstElementChild.after( rescheduleExcludeAction );
		rescheduleExcludeAction.querySelector('[data-nonce]').disabled = false;
		// close modeal and mark this as rescheduled
		closeModal(recurrenceExcludeModal);
	});

	// move the cancel warning back to reschedule modal if removing an event results in no exclusions
	recurrenceSets.addEventListener('updateSetsCount', function() {
		if ( recurrenceExcludeSets.dataset.count === '0' ) {
			recurrenceExcludeModal.querySelector('.em-modal-content')?.append( rescheduleExcludeAction );
		}
	});
});

// This file deals with dates and times of the main event, determining the overall recurrence duration in dates and times of the recurring event for display purposes.
document.addEventListener('em_event_editor_recurrences', function( e ) {
	let recurrenceSets = e.detail.recurrenceSets;

	document.addEventListener('em_luxon_ready', function(){
		// Sets the overal event dates, times and timezone based on the earliest and latest recurrence date/time, and the primary recurrence timezone.
		// PHP will always handle the real date ranges.
		// This is somewhat redundant and needs a review. The reason is because this doesn't account for timezones, for example we could have an earlier string date/time than another, but the later one is in a TZ that's makes it earlier in UTC time.
		// For this reason, we need a library like Luxon to accurately calculate and use this for displaying estimated start/end date/times.
		// TODO add TimeZone-aware libary to calculate real start/end dates and provide an accurate recurrence summary for all recurrences grouped together.
		
		recurrenceSets.addEventListener('setDateTimes', function() {
			let eventDateTimes = emRecurrenceFormRoot( recurrenceSets ).querySelector('.event-form-when');
			if ( eventDateTimes ) {
				// COLLECT ALL DATES FROM RECURRENCE SETS, update earliest/latest date as we go
				/** @type {luxon.DateTime} */
				let startDateTime;
				/** @type {luxon.DateTime} */
				let endDateTime;
				/** @type {Element} */
				let eventDatePicker = eventDateTimes.querySelector('.em-datepicker.em-event-dates');
				/** @type {Element} */
				let eventTimeRange = eventDateTimes.querySelector('.em-timeranges');
				// we need to get jQuery elements to handle the timepicker
				/** @type {jQuery} */
				let $eventStartTime = jQuery(eventTimeRange.querySelector('.em-time-input.em-time-start'));
				/** @type {jQuery} */
				let $eventEndTime = jQuery(eventTimeRange.querySelector('.em-time-input.em-time-end'));
				let DateTime = luxon.DateTime;
				let timezone = recurrenceSets.querySelector('.em-recurrence-set[data-primary="1"] select.recurrence_timezone')?.value;
				// Replace .5 with :30 in timezone string (for half-hour offsets like UTC+5.5)
				timezone = timezone?.replace(/\.5/g, ':30') || timezone;
				
				// get primary values for other recurrences
				let defaultStartTimeSeconds, defaultEndTimeSeconds;
				let defaultStartDate, defaultEndDate;
				
				// Track if all recurrence sets are marked as all-day
				let allRecurrencesAllDay = true;
				// Track all unique timezones used across recurrence sets
				let uniqueTimezones = new Set();

				// go through each recurring set to get the start time and date
				recurrenceSets.querySelectorAll('.em-recurrence-type-include .em-recurrence-set').forEach( recurrenceSet => {
					let recurrenceTimezone = recurrenceSet.querySelector('.em-recurrence-timezone select')?.value || timezone;
					// Replace .5 with :30 in timezone string (for half-hour offsets like UTC+5.5)
					recurrenceTimezone = recurrenceTimezone?.replace(/\.5/g, ':30') || recurrenceTimezone;
					// Add the timezone to our set of unique timezones
					if (recurrenceTimezone) {
						uniqueTimezones.add(recurrenceTimezone);
					}
					/** @type {luxon.DateTime} */
					let recurrenceStart;
					/** @type {luxon.DateTime} */
					let	recurrenceEnd;
					// build the start and end datetime from the recurrence set, starting by getting the date and creating luxon.DateTime objects
					if ( recurrenceSet.querySelector('select.recurrence_freq')?.value === 'on' ) {
						// get the ON dates rather than the date range
						let selectedDates = recurrenceSet.querySelector('.em-on-selector .em-date-input')?._flatpickr?.selectedDates;
						if ( selectedDates ) {
							selectedDates.sort(function(a, b) { return a - b; });
							// get the first and last dates from the selected dates
							recurrenceStart = DateTime.fromJSDate( selectedDates[0] );
							recurrenceEnd = DateTime.fromJSDate( selectedDates[selectedDates.length - 1] );
						}
					} else {
						// get the regular date range
						recurrenceSet.querySelectorAll('.em-recurrence-advanced .em-datepicker .em-date-input.flatpickr-input').forEach( input => {
							if ( input._flatpickr?.selectedDates.length ) {
								if (input.closest('.em-datepicker-until')) {
									if (input.classList.contains('em-date-input-start')) {
										recurrenceStart = DateTime.fromJSDate( input._flatpickr.selectedDates[0] );
									} else if (input.classList.contains('em-date-input-end')) {
										recurrenceEnd = DateTime.fromJSDate( input._flatpickr.selectedDates[0] );
									}
								} else if (input.closest('.em-datepicker-range')) {
									recurrenceStart = DateTime.fromJSDate( input._flatpickr.selectedDates[0] );
									if ( input._flatpickr.selectedDates.length >= 2 ) {
										recurrenceEnd = DateTime.fromJSDate( input._flatpickr.selectedDates[1] );
									} else {
										recurrenceEnd = recurrenceStart;
									}
								}
								defaultStartDate ??= recurrenceStart;
								defaultEndDate ??= recurrenceEnd;
							}
						});
					}
					// make sure we have recurrence dates and the timezones are correctly set
					recurrenceStart ??= defaultStartDate;
					recurrenceEnd ??= defaultEndDate || defaultStartDate;
					recurrenceStart = recurrenceStart?.setZone( recurrenceTimezone, { keepLocalTime: true } );
					recurrenceEnd = recurrenceEnd?.setZone( recurrenceTimezone, { keepLocalTime: true } );

					// proceed if we have start/end dates
					if ( recurrenceStart && recurrenceEnd ) {
						// add the time to the start/end dates
						let timeRange = recurrenceSet.querySelector( '.em-timeranges' );
						if ( timeRange && ( recurrenceSet.dataset.primary || recurrenceSet.querySelector( '.recurrences-timeranges-default-trigger')?.checked ) ) {
							let $recurrenceStartTime = jQuery( timeRange.querySelector( '.em-time-input.earliest-time' ) );
							let $recurrenceEndTime = jQuery( timeRange.querySelector( '.em-time-input.latest-time' ) );

							// Get times based on whether all day or normal
							if ( timeRange.dataset.allday === "1" ) {
								recurrenceEnd = recurrenceEnd.endOf( 'day' );
								// set default start/end times first time for the timepicker for future recurrences
								defaultStartTimeSeconds |= 0;
								defaultEndTimeSeconds |= 86399; // 23:59:59
							} else {
								allRecurrencesAllDay = false;
								let secondsFromMidnight = $recurrenceStartTime.em_timepicker( 'getSecondsFromMidnight' );
								if ( $recurrenceStartTime.val() ) {
									recurrenceStart = recurrenceStart.plus( { seconds: secondsFromMidnight } );
								} else {
									recurrenceStart = recurrenceStart.plus( { seconds: defaultStartTimeSeconds || 0 } );
								}
								if ( $recurrenceEndTime.val() ) {
									let secondsFromMidnight = $recurrenceEndTime.em_timepicker( 'getSecondsFromMidnight' );
									recurrenceEnd = recurrenceEnd.plus( { seconds: secondsFromMidnight } );
								} else {
									recurrenceEnd = recurrenceEnd.plus( { seconds: defaultEndTimeSeconds || 0 } );
								}
								// set default start/end times first time for the timepicker for future recurrences
								defaultStartTimeSeconds |= $recurrenceStartTime.em_timepicker( 'getSecondsFromMidnight' );
								defaultEndTimeSeconds |= $recurrenceEndTime.em_timepicker( 'getSecondsFromMidnight' );
							}

							// account for duration
							let duration = recurrenceSet.querySelector( '.recurrence_duration' )?.value;
							if ( duration ) {
								recurrenceEnd = recurrenceEnd.plus( { days: duration } );
							}
							// Now we have the luxon.DateTime dates/times in correct timezone, we can compare them accurately
							if ( recurrenceStart.isValid && ( !startDateTime || recurrenceStart < startDateTime ) ) {
								startDateTime = recurrenceStart.setZone( timezone );
							}
							if ( recurrenceEnd.isValid && (!endDateTime || recurrenceEnd > endDateTime) ) {
								endDateTime = recurrenceEnd.setZone( timezone );
							}
						}
					}
				});
				if ( startDateTime?.isValid && endDateTime?.isValid ) {

					// set the datepicker and timepickers of the main event form
					let startDate = startDateTime.setZone( "system", { keepLocalTime: true } ).toJSDate();
					let endDate = endDateTime.setZone( "system", { keepLocalTime: true } ).toJSDate();
					if ( eventDatePicker.classList.contains('em-datepicker-range') ) {
						// set the date range with both dates, even if endDate didn't change
						eventDatePicker.querySelector( '.em-date-input.flatpickr-input' )?._flatpickr?.setDate( [ startDate, endDate ], true );
					} else {
						eventDatePicker.querySelector( '.em-date-input-start.flatpickr-input' )?._flatpickr?.setDate( startDate, true );
						eventDatePicker.querySelector( '.em-date-input-end.flatpickr-input' )?._flatpickr?.setDate( endDate, true );
					}
					$eventStartTime.em_timepicker( 'setTime', startDate );
					$eventEndTime.em_timepicker( 'setTime', endDate );
					
					// Update recurring summary dates
					let recurringSection = eventDateTimes.querySelector('.recurring-summary-dates');
					if (recurringSection) {
						// Remove 'hidden' class if present
						recurringSection.classList.remove('hidden');
						
						// Update start date and time - use the right format from EM settings
						let datePickerFormat = 'D';
						let timeFormat = EM.show24hours == 1 ? 'H:mm':'h:mm a';
						
						// Update start date element
						let startDateElem = recurringSection.querySelector('.date.start-date');
						if (startDateElem) {
							startDateElem.textContent = startDateTime.toFormat(datePickerFormat);
						}
						
						// Update start time element
						let startTimeElem = recurringSection.querySelector('.time.start-time');
						if (startTimeElem) {
							startTimeElem.textContent = ' @ ' + startDateTime.toFormat(timeFormat);
						}
						
						// Update end date element
						let endDateElem = recurringSection.querySelector('.date.end-date');
						if (endDateElem) {
							endDateElem.textContent = endDateTime.toFormat(datePickerFormat);
						}
						
						// Update end time element
						let endTimeElem = recurringSection.querySelector('.time.end-time');
						if (endTimeElem) {
							endTimeElem.textContent = ' @ ' + endDateTime.toFormat(timeFormat);
						}
						
						// Update classes based on all-day status
						recurringSection.classList.remove('is-all-day', 'has-all-day');
						
						if ( eventTimeRange.dataset.allday === '1' ) {
							// True all-day event (all checkboxes checked and times match pattern)
							recurringSection.classList.add('is-all-day');
						} else if ( allRecurrencesAllDay ) {
							// All checkboxes are checked, but start/end times don't match all-day times in the primary timezone
							recurringSection.classList.add('has-all-day');
						}
						
						// Update timezone
						let timezoneElem = recurringSection.querySelector('.recurring-timezone .timezone');
						if (timezoneElem && timezone) {
							timezoneElem.textContent = timezone;
						}
						
						 // Add 'has-multiple-timezones' class if multiple timezones are detected
						if (uniqueTimezones.size > 1) {
							recurringSection.classList.add('has-multiple-timezones');
						} else {
							recurringSection.classList.remove('has-multiple-timezones');
						}
						
						// Hide the missing info message
						let missingInfoElem = eventDateTimes.querySelector('.recurring-summary-missing');
						if (missingInfoElem) {
							missingInfoElem.classList.add('hidden');
						}
					}
				}
			}
		});
	});

	let breakpoints = { 'small' : 500, 'large' : false, };
	let recurringSummaries = document.querySelectorAll('.em-recurring-summary .recurring-summary-dates');
	if ( recurringSummaries.length > 0 ) {
		EM_ResizeObserver( breakpoints, recurringSummaries );
	}
});

// this section deals with functions that handle display of text, counting sets and redisplaying forms
let emRecurrenceEditor = {
	updateIntervalDescriptor : function( container ) {
		let sets = container.matches('.em-recurrence-sets') ? container.querySelectorAll('.em-recurrence-set') : [ container.closest('.em-recurrence-set') ];
		sets.forEach( function( set ) {
			set.querySelectorAll(".interval-desc").forEach( el => el.classList.add('hidden') );
			let number = "-plural";
			let input = set.querySelector('input.em-recurrence-interval');
			if ( input ) {
				if ( input.value === "1" || input.value === "" ) {
					number = "-singular";
				}
			}
			let select = set.querySelector("select.em-recurrence-frequency");
			let freq = select ? select.value : "";
			let descriptorSelector = "span.interval-desc.interval-" + freq + number;
			set.querySelectorAll( descriptorSelector ).forEach( el => el.classList.remove('hidden') );
			set.querySelectorAll('.interval-desc-intro').forEach( el => el.classList.toggle('hidden', freq === 'on') );
		});
	},

	updateDurationDescriptor : function( container ) {
		let sets = container.matches('.em-recurrence-sets') ? container.querySelectorAll('.em-recurrence-set') : [ container.closest('.em-recurrence-set') ];
		sets.forEach( function( set ) {
			set.querySelectorAll(".recurrence-days-desc").forEach( el => el.classList.add('hidden') );
			let input = set.querySelector('input.em-recurrence-duration');
			let number = input && (input.value === "1" || (input.value === '' && input.placeholder === '1')) ? 'singular' : 'plural';
			set.querySelectorAll( ".recurrence-days-desc.em-" + number ).forEach( el => el.classList.remove('hidden') );
		});
	},

	updateIntervalSelectors : function ( container ) {
		let sets = container.matches('.em-recurrence-sets') ? container.querySelectorAll('.em-recurrence-set') : [ container.closest('.em-recurrence-set') ];
		sets.forEach( function( set ) {
			set.querySelectorAll('.alternate-selector').forEach( el => el.classList.add('hidden') );
			let select = set.querySelector("select.em-recurrence-frequency");
			let freq = select ? select.value : "";
			set.querySelectorAll('.em-' + freq + '-selector').forEach( el => el.classList.remove('hidden') );
			set.querySelectorAll('.em-recurrence-interval').forEach( el => el.classList.toggle('hidden', freq === 'on') );
		});
	}
}

document.addEventListener('em_event_editor_recurrences', function( e ) {
	let recurrenceSets = e.detail.recurrenceSets;
	/**
	 * Sets placeholders for advanced fields in non-main recurrences so as to show informative recurrence set defaults and descriptions if left blank, since the main recurrence is the default values.
	 */
	recurrenceSets.addEventListener('setAdvancedDefaults', function () {
		// get the first recurrence set
		let recurrenceSetPrimary = recurrenceSets.querySelector('.em-recurrence-type-include .em-recurrence-set:first-child');
		let selector = '.em-recurrence-type-include .em-recurrence-set:not(:first-child) .em-recurrence-advanced';

		// set all recurrence sets to have a 0 value flag to detect modifications of primary
		recurrenceSets.querySelectorAll('.em-recurrence-set').forEach( recurrenceSet => { recurrenceSet.dataset.primaryModified = '0'; });

		// check for modified values and if so set flag that this overrides primary set
		recurrenceSets.querySelectorAll('.em-recurrence-set').forEach(recurrenceSet => {
			if (recurrenceSet !== recurrenceSetPrimary) {
				if ( recurrenceSet.querySelector('.recurrences-timeranges-default-trigger')?.checked ) {
					recurrenceSet.dataset.primaryModified = '1';
				}
			}
		});

		// Recurse recurrenceSets by recurrence set (.em-recurrence-set) to begin with
		recurrenceSets.querySelectorAll('.em-recurrence-set').forEach( function ( recurrenceSet ) {
			if ( !recurrenceSet.matches('.em-recurrence-type-include .em-recurrence-set:first-child') ) {
				// loop each flatpickr input and set placeholders and detect if default value has changed
				recurrenceSetPrimary.querySelectorAll('.em-recurrence-advanced .em-datepicker .em-date-input.flatpickr-input').forEach(function (input) {
					let datePicker = input.closest('.em-datepicker');
					let value = input._flatpickr.altInput.value;
					let modifiedDefault = input._flatpickr._inputData.some( input => input.value !== input.dataset.undo );

					// get the text format directly, we assume it's the same as the datepicker type for events, it's an EM setting (if dev customizations change the template, they'll need to account for it here)
					let datesSelector = '.em-recurrence-dates .em-date-input.form-control';
					if (datePicker.classList.contains('em-datepicker-range')) {
						recurrenceSet.querySelectorAll(datesSelector).forEach(function (dp) {
							dp.previousElementSibling.placeholder ||= dp.placeholder;
							dp.placeholder = value ? value : dp.previousElementSibling.placeholder;
							if ( dp.value === '' && modifiedDefault ) {
								dp.closest('.em-recurrence-set').dataset.primaryModified = '1';
							}
						});
					} else if (datePicker.classList.contains('em-datepicker-until')) {
						datesSelector += input.classList.contains('em-date-input-start') ? '.em-date-input-start' : '.em-date-input-end';
						recurrenceSet.querySelectorAll(datesSelector).forEach(function (dp) {
							dp.placeholder = value ? value : dp.previousElementSibling.placeholder;
							if ( dp.value === '' && modifiedDefault ) {
								dp.closest('.em-recurrence-set').dataset.primaryModified = '1';
							}
						});
					}
				});
			}
		});

		// Handle timezone and status dropdowns using a shared function
		['timezone', 'status'].forEach( function( selectType ) {
			const classPrefix = '.em-recurrence-' + selectType;
			let select = recurrenceSetPrimary.querySelector(classPrefix + ' select');
			if (select) {
				// Set placeholder for other recurrences - timezones will also affect the exclude section
				let selectors = selectType === 'timezone' ? [ selector, '.em-recurrence-type-exclude .em-recurrence-set .em-recurrence-advanced'] : [ selector ];
				selectors.forEach( function( selector ) {
					recurrenceSets.querySelectorAll(selector + ' ' + classPrefix + ' select').forEach( function( otherSelect ) {
						if ( otherSelect.selectize ) {
							if ( select.value ) {
								otherSelect.selectize.settings.placeholder = select.querySelector(`option[value="${select.value}"]`)?.textContent || select.value;
								otherSelect.selectize.updatePlaceholder();
								// no value selected therefore overriden by primary
								if ( otherSelect.value === '' && select.value !== select.dataset.undo ) {
									otherSelect.closest('.em-recurrence-set').dataset.primaryModified = '1';
								}
							} else {
								otherSelect.selectize.settings.placeholder = select.selectize?.settings.placeholder;
								otherSelect.selectize.updatePlaceholder();
							}
						}
					});
				});
			}
		});

		// Handle recurrence duration input
		let durationInput = recurrenceSetPrimary.querySelector('input.em-recurrence-duration');
		if (durationInput && durationInput.value.trim()) {
			recurrenceSets.querySelectorAll(selector + ' input.em-recurrence-duration').forEach(function(otherInput) {
				otherInput.placeholder = durationInput.value.trim();
				if ( otherInput.value === '' && durationInput.value !== durationInput.dataset.undo ) {
					otherInput.closest('.em-recurrence-set').dataset.primaryModified = '1';
				}
			});
		}

		// check primary overriding values and set additional flags for date ranges which we can reference and detect overriding changes
		recurrenceSets.querySelectorAll('.em-recurrence-set').forEach( function( recurrenceSet ) {
			// check if each recurrence set is affected by primary modifications
			recurrenceSet.classList.toggle('advanced-modified-primary', recurrenceSet.dataset.primaryModified === '1');
			if ( recurrenceSet.dataset.primaryModified ) {
				recurrenceSet.dispatchEvent( new Event('change', { bubbles: true }) );
			}
			delete recurrenceSet.dataset.primaryModified;

			// check the start/end dates specifically, if they are both set then we need to set a flag so we know they were modified too
			let hasDates = 0;
			let hasStartDate = false, hasStartDateModified = false;
			let hasEndDate = false, hasEndDateModified = false;
			let hasModifiedDates;
			if ( recurrenceSet.querySelector('select.em-recurrence-frequency')?.value === 'on' ) {
				hasDates = 2; // fake this as we don't need a date range for 'on' frequency
			} else {
				// check if there is a complete date range set (i.e. two dates) and if any of the dates were modified
				recurrenceSet.querySelectorAll(`.em-recurrence-dates .em-datepicker-data input[name]`).forEach(function ( input ) {
					hasDates += input.value ? 1 : 0;
					if ( input.matches(':first-of-type') ) {
						hasStartDate = !!input.value;
						hasStartDateModified = input.value !== input.dataset.undo;
					}
					if ( input.matches(':last-of-type') ) {
						hasEndDate = !!input.value;
						hasEndDateModified = input.value !== input.dataset.undo;
					}
					hasModifiedDates ||= input.value !== input.dataset.undo;
				});
			}
			recurrenceSet.classList.toggle('has-date-range', hasDates >= 2);
			if ( hasDates < 2 ) {
				recurrenceSet.classList.toggle( 'has-date-range-start', hasStartDate );
				recurrenceSet.classList.toggle( 'has-date-range-end', hasEndDate );
			}
			if ( hasStartDateModified && hasEndDateModified ) {
				recurrenceSet.classList.toggle('has-modified-date-range', true);
				recurrenceSet.classList.toggle('has-modified-date-range-start', false);
				recurrenceSet.classList.toggle('has-modified-date-range-end', false);
			} else {
				recurrenceSet.classList.toggle('has-modified-date-range', false);
				recurrenceSet.classList.toggle('has-modified-date-range-start', hasStartDateModified);
				recurrenceSet.classList.toggle('has-modified-date-range-end', hasEndDateModified);
			}
		});

		// update the recurrence summary
		recurrenceSets.dispatchEvent( new Event('updateRecurrenceSummary', { bubbles: true }) );
	});

	// update the count elements so CSS can do its thing
	recurrenceSets.addEventListener('updateSetsCount', function() {
		['include', 'exclude'].forEach( function ( recurrenceType ) {
			// show or hide remove button
			let recurrenceTypeSets = recurrenceSets.querySelector('.em-recurrence-type-' + recurrenceType);
			if ( recurrenceTypeSets ) {
				let count = recurrenceTypeSets.querySelectorAll('.em-recurrence-set').length;
				recurrenceSets.setAttribute('data-' + recurrenceType + '-count', count);
				recurrenceTypeSets.dataset.count = count; // CSS will hide things
			}
		});
	});

	// reset order of items as per reordering
	recurrenceSets.addEventListener('updateRecurrenceOrder', function() {
		let primaryRecurrence;
		recurrenceSets.querySelectorAll('.em-recurrence-type-include .em-recurrence-set').forEach( function( recurrenceSet, index) {
			let order_input = recurrenceSet.querySelector('.em-recurrence-order');
			if (order_input) {
				order_input.value = index + 1;
			}
			recurrenceSet.classList.toggle('show-advanced', index === 0);
			if ( recurrenceSet !== primaryRecurrence && index === 0 ) {
				// copy all the date/time/duration advanced values from primaryRecurrence to here
				primaryRecurrence = recurrenceSet;
				// set default placehodlers
				primaryRecurrence.querySelectorAll('[data-placeholder]').forEach( el => { el.placeholder = el.dataset.placeholder } );
				primaryRecurrence.querySelectorAll('.em-datepicker .em-date-input-end.form-control').forEach( el => { el.placeholder = el.previousElementSibling.placeholder });
				primaryRecurrence.querySelectorAll('.em-datepicker .em-date-input-start.form-control').forEach( el => { el.placeholder = el.previousElementSibling.placeholder });
				recurrenceSets.dispatchEvent( new CustomEvent('updateSetsCount') );
				recurrenceSets.dispatchEvent( new CustomEvent('setAdvancedDefaults') );
				recurrenceSets.dispatchEvent( new CustomEvent('updateRecurrenceSummary') );
			}
			if ( recurrenceSet.matches(':first-child') ) {
				recurrenceSet.dataset.primary = '1';
				recurrenceSet.querySelectorAll('.em-time-all-day').forEach( el => { el.indeterminate = false; } );
			} else {
				delete recurrenceSet.dataset.primary;
			}
		});
	} );

	// show/hide remove button
	recurrenceSets.dispatchEvent( new CustomEvent('updateSetsCount') );
	// Initialize recurrence descriptor and selectors for this recurrenceSets container
	emRecurrenceEditor.updateIntervalDescriptor(recurrenceSets);
	emRecurrenceEditor.updateIntervalSelectors(recurrenceSets);
	emRecurrenceEditor.updateDurationDescriptor(recurrenceSets);

});


document.addEventListener('em_event_editor_recurrences', function( e ) {
	let recurrenceSets = e.detail.recurrenceSets;

	// Attach delegated listeners for interval/duration inputs and frequency select within this container
	recurrenceSets.addEventListener('keyup', function (e) {
		if ( e.target.matches('input.em-recurrence-interval') ) {
			emRecurrenceEditor.updateIntervalDescriptor( e.target.closest('.em-recurrence-set') );
		} else if (e.target.matches('input.em-recurrence-duration')) {
			emRecurrenceEditor.updateDurationDescriptor( e.target.closest('.em-recurrence-set') );
		}
	});

	// recurrency descriptors and selectors that change upon frequency changes
	recurrenceSets.addEventListener('change', function (e) {
		if (e.target.matches('select.em-recurrence-frequency')) {
			let recurrenceSet = e.target.closest('.em-recurrence-set');
			emRecurrenceEditor.updateIntervalDescriptor( recurrenceSet );
			emRecurrenceEditor.updateIntervalSelectors( recurrenceSet );
		}
	});
});

//Event Editor
// Recurrence Warnings
document.querySelectorAll('form.em-event-admin-recurring').forEach(form => {
	form.addEventListener('submit', function (event) {
		let warning_text;
		let recreateInput = form.querySelector('input[name="event_recreate_tickets"]');

		if (recreateInput && recreateInput.value === "1") {
			warning_text = EM.event_recurrence_bookings;
		}

		if ( warning_text && !confirm(warning_text) ) {
			event.preventDefault();
		}
	});
});

//Buttons for recurrence warnings within event editor forms. Delegated on document rather
//than bound per-element at load, so it also catches buttons injected after this script ran —
//e.g. the Bookings tab cloned into the Gutenberg canvas iframe, where the old one-time
//querySelectorAll left the "Modify Recurring Event Tickets" button with no handler.
document.addEventListener('click', function (e) {
	const el = e.target.closest('.em-reschedule-trigger, .em-reschedule-cancel');
	if ( ! el ) return;
	e.preventDefault();
	const show = el.matches('.em-reschedule-trigger');
	el.closest('.em-recurrence-reschedule')?.querySelector(el.dataset.target)?.classList.toggle('reschedule-hidden', !show);
	el.parentElement.querySelectorAll('[data-nonce]').forEach( node => { node.disabled = !show } );
	el.parentElement.querySelectorAll('button').forEach( link => link.classList.remove('reschedule-hidden') );
	el.classList.add('reschedule-hidden');
});

document.addEventListener('em_event_editor_recurrences', function( e ) {
	let recurrenceSets = e.detail.recurrenceSets;

	let setAdvancedDefaults = () => recurrenceSets.dispatchEvent( new CustomEvent('setAdvancedDefaults') );
	let updateRecurrenceSummary = ( recurrenceSet ) => recurrenceSet.dispatchEvent( new CustomEvent('updateRecurrenceSummary', { bubbles: true }) )
	let setDateTimes = () => recurrenceSets.dispatchEvent( new CustomEvent('setDateTimes') );

	// ADVANCED TOGGLE/SECTION

	// Open/Close Advanced Section
	recurrenceSets.addEventListener('click', function(e) {
		const toggleButton = e.target.closest('.em-recurrence-set-action-advanced');
		if (!toggleButton) return;

		const recurrenceSet = toggleButton.closest('.em-recurrence-set');
		recurrenceSet.classList.toggle('show-advanced');
		if( '_tippy' in toggleButton ){
			if ( recurrenceSet.classList.contains('show-advanced') ) {
				toggleButton._tippy.setContent( toggleButton.getAttribute('data-label-hide') );
			} else {
				toggleButton._tippy.setContent( toggleButton.getAttribute('data-label-show') );
			}
		}
	});

	// Function to check advanced inputs and set icon color
	let updateAdvancedIcon = function( recurrenceSet ) {
		const advancedSection = recurrenceSet.querySelector('.em-recurrence-advanced');
		const advancedIcon = recurrenceSet.querySelector('.em-recurrence-set-action-advanced');

		if ( !advancedSection || !advancedIcon) return;

		const inputs = advancedSection.querySelectorAll('input, select, textarea');
		let hasValue = Array.from(inputs).some( input => {
			if ( input.type === 'checkbox' ) {
				return input.checked;
			} else {
				return input.value.trim() !== '';
			}
		});

		recurrenceSet.classList.toggle('has-advanced-value', hasValue);
	};

	// Event listener scoped to current recurrenceSets container
	recurrenceSets.addEventListener('change', function(e) {
		if ( e.target.closest('.em-recurrence-advanced') ) {
			updateAdvancedIcon( e.target.closest('.em-recurrence-set') );
		}
	});

	// Initialize advanced icons on page load for current recurrenceSets container
	recurrenceSets.querySelectorAll('.em-recurrence-set').forEach( recurrenceSet => updateAdvancedIcon( recurrenceSet ));

	// Track the first recurrence set and update placeholders accordingly
	recurrenceSets.querySelectorAll('.em-recurrence-type').forEach( function( recurrenceSetType ) {
		recurrenceSetType.addEventListener('change', function(e ){
			let recurrenceSet = e.target.closest('.em-recurrence-set');
			if ( e.target.closest('.em-recurrence-advanced') ) {
				// check changes to main/first recurrence
				if ( recurrenceSetType.classList.contains('em-recurrence-type-include') ) {
					if ( recurrenceSet === recurrenceSet.parentElement?.firstElementChild ) {
						setAdvancedDefaults();
					}
					setDateTimes();
				}
				updateRecurrenceSummary( recurrenceSet );
			} else if ( recurrenceSet?.querySelector('select.recurrence_freq')?.value === 'on' ) {
				// account for 'on' frequency changes
				if ( e.target.closest('.em-datepicker.em-on-selector') ) {
					// update the regular range datepicker to reflect date range from the 'on' selector datepicker
					let selectedDates = e.target.closest('.em-date-input')?._flatpickr?.selectedDates;
					if ( selectedDates ) {
						selectedDates.sort(function(a, b) { return a - b; });
						// set the dates

						let datepickerDates = recurrenceSet.querySelector('.em-recurrence-dates.em-datepicker');
						if ( datepickerDates ) {
							if ( datepickerDates.classList.contains( 'em-datepicker-until' ) ) {
								// we set start and end datepickers individually
								datepickerDates.querySelector( `.em-date-input-start` )?._flatpickr?.setDate( selectedDates[0] );
								datepickerDates.querySelector( `.em-date-input-end` )?._flatpickr?.setDate( selectedDates[selectedDates.length - 1] );
							} else if ( datepickerDates.classList.contains( 'em-datepicker-range' ) ) {
								// set an array of first/last selectedDates
								let selectedDatesArray = [ selectedDates[0], selectedDates[selectedDates.length - 1] ];
								datepickerDates.querySelector( `.em-date-input` )?._flatpickr?.setDate( selectedDatesArray );
							}
						}
						if ( recurrenceSetType.classList.contains('em-recurrence-type-include') ) {
							if ( recurrenceSet === recurrenceSet.parentElement?.firstElementChild ) {
								setAdvancedDefaults();
							}
						}
					}
				}
				setDateTimes();
			}
		});
	});

	// Track changes to the advanced section, for undo logic and other validation
	recurrenceSets.addEventListener('change', function(e) {
		if ( e.target.closest('.em-recurrence-advanced') ) {
			let recurrenceSet = e.target.closest('.em-recurrence-set');
			// go through each input with a name property and check if it different to the data-undo property (which may not be set)
			let isModified = false;
			recurrenceSet.querySelectorAll('.em-recurrence-advanced [name]:not([disabled]):not([data-nonce]').forEach( input => {
				if ( input.name && input.dataset.undo ) {
					if ( input.type === 'checkbox' ) {
						if ( input.checked && input.dataset.undo !== '1' ) {
							isModified = true;
						}
					} else {
						if ( input.value !== input.dataset.undo ) {
							isModified = true;
						}
					}
				} else if ( recurrenceSets.dataset.event_id && input.value ) {
					isModified = true;
				}
			});
			recurrenceSet.classList.toggle('advanced-modified', isModified);
		}

		// Listen for changes to .em-time-range on non-primary recurrence sets
		if ( e.target.matches('.em-recurrence-timeranges *') ) {
			let recurrenceSet = e.target.closest('.em-recurrence-set');
			let timeranges = recurrenceSet.querySelector('.em-recurrence-timeranges .em.timeranges');
			let startTimeInput = recurrenceSet.querySelector('.em-time-input.em-time-start.earliest-time');
			let endTimeInput = recurrenceSet.querySelector('.em-time-input.em-time-end.latest-time');
			let durationInput = recurrenceSet.querySelector('input.em-recurrence-duration');
			let isMultiDay = durationInput?.value > 0 || durationInput?.placeholder > 0 || false;

			if ( !isMultiDay ) {
				let startTime = startTimeInput.dataset.seconds ? parseInt(startTimeInput.dataset.seconds) : null;
				let endTime = endTimeInput.dataset.seconds ? parseInt(endTimeInput.dataset.seconds) : null;

				if ( !startTime || !endTime ) {
					// Select the first recurrence set of type "include" within recurrenceSets
					let recurrenceSetPrimary = recurrenceSets.querySelector('.em-recurrence-set[data-type="include"]:first-child');
					if ( recurrenceSetPrimary ) {
						if ( startTime === null ) {
							let seconds = recurrenceSetPrimary.querySelector('.em-time-input.em-time-start')?.dataset.seconds;
							startTime = seconds === undefined ? null : parseInt( recurrenceSetPrimary.querySelector('.em-time-input.em-time-start')?.dataset.seconds || 0 );
						}
						if ( endTime === null ) {
							let seconds = recurrenceSetPrimary.querySelector('.em-time-input.em-time-end')?.dataset.seconds;
							endTime = seconds === undefined ? null : parseInt( recurrenceSetPrimary.querySelector('.em-time-input.em-time-end')?.dataset.seconds || 0 );
						}
					}
				}

				// Ensure end time is not earlier than start time
				if ( startTime !== null && endTime !== null ) {
					if ( e.target.matches('.em-time-start') && startTime > endTime ) {
						endTimeInput.value = startTimeInput.value;
						endTimeInput.dispatchEvent(new Event('change'));
					}

					// Ensure start time is not later than end time
					if ( e.target.matches('.em-time-end') && startTime > endTime ) {
						startTimeInput.value = endTimeInput.value;
						startTimeInput.dispatchEvent(new Event('change'));
					}
				}
			}
		}

		// if duration is changed, trigger a change for the end time and make sure we're not at 0 with bad start/end times
		if ( e.target.matches('input.em-recurrence-duration') ) {
			if ( e.target.value === '0' || ( e.target.value === '' && e.target.placeholder === '0' ) ) {
				let recurrenceSet = e.target.closest('.em-recurrence-set');
				let sets = recurrenceSet.dataset.primary ? recurrenceSet : recurrenceSets;
				sets.querySelectorAll('.em-recurrence-times .em-time-end').forEach( el => el.dispatchEvent(new Event('change')));
			}
		}

		// listen for all-day checkbox changes within the non-primary recurrences
		let primaryCb = recurrenceSets.querySelector('.em-recurrence-set[data-primary] .em-time-all-day');
		if ( e.target.matches('.em-time-all-day') ) {
			let cb = e.target;
			if ( cb.matches('.em-recurrence-set[data-primary] .em-time-all-day') ) {
				if ( cb.readOnly ) {
					cb.checked = true;
					cb.readOnly = false;
				}
			} else {
				if ( cb.readOnly ) {
					cb.checked = true;
					cb.readOnly = false;
				} else if ( cb.checked && primaryCb.checked ) {
					cb.readOnly = true
					cb.indeterminate = true;
					// unset both times
					cb.closest('.em-time-range').querySelectorAll('.em-time-input').forEach( el => { el.value = '' } );
				}
			}
		}
	});

	// Update the recurrence summary of recurrences
	recurrenceSets.addEventListener('updateRecurrenceSummary', function( e ) {
		let sets = e.target.matches('.em-recurrence-set') ? [ e.target ] : e.target.querySelectorAll('.em-recurrence-set');
		let timerangeDefault = recurrenceSets.querySelector('.em-recurrence-set[data-primary] .em-recurrence-timeranges .em-timeranges');

		sets.forEach( function ( recurrenceSet ){
			let advancedSummary = recurrenceSet.querySelector('.advanced-summary');
			if ( advancedSummary ) {
				// Initialize objects for values as one-liners
				let dateValues = { start: '', end: '', startIsSet: false, endIsSet: false };
				let timeValues = { start: timerangeDefault.dataset.start, end: timerangeDefault.dataset.end, startIsSet: false, endIsSet: false };

				// Get date values with a loop
				if ( recurrenceSet.querySelector('select.recurrence_freq')?.value === 'on' ) {
					// get the ON dates rather than the date range
					let selectedDates = recurrenceSet.querySelector('.em-on-selector .em-date-input')?._flatpickr?.selectedDates;
					if ( selectedDates ) {
						selectedDates.sort(function(a, b) { return a - b; });
						// get the first and last dates from the selected dates
						dateValues['start'] = selectedDates[0];
						dateValues['startIsSet'] = true;
						dateValues['end'] = selectedDates[selectedDates.length - 1];
						dateValues['endIsSet'] = true;
					}
				} else {
					// not On dates so we look at traditional date range
					let datepickerDates = recurrenceSet.querySelector('.em-recurrence-dates.em-datepicker');
					if ( datepickerDates.classList.contains('em-datepicker-until') ) {
						['start', 'end'].forEach(function(type) {
							let dateInput = datepickerDates.querySelector(`.em-date-input-${type}`);
							if (dateInput) {
								if (dateInput._flatpickr && dateInput._flatpickr.altInput && dateInput._flatpickr.selectedDates.length) {
									// If flatpickr has a selected date, use that
									dateValues[type] = dateInput._flatpickr.altInput.value;
									dateValues[type + 'IsSet'] = true;
								} else if (dateInput.nextElementSibling) {
									// Otherwise use the visible input's value or placeholder
									dateValues[type] = dateInput.nextElementSibling.value ||
									dateInput.nextElementSibling.placeholder;
								}
							}
						});
					} else if ( datepickerDates.classList.contains('em-datepicker-range') ) {
						let dateInput = datepickerDates.querySelector(`.em-date-input`);
						if ( dateInput ) {
							// get the dates from flatpickr, formatted into the altinput format
							if (dateInput._flatpickr && dateInput._flatpickr.altInput && dateInput._flatpickr.selectedDates.length) {
								// If flatpickr has a selected date, use that
								dateValues['start'] = dateInput._flatpickr.altInput.value;
								dateValues['startIsSet'] = true;
							} else if (dateInput.nextElementSibling) {
								// Otherwise use the visible input's value or placeholder
								dateValues['start'] = dateInput.nextElementSibling.value ||
									dateInput.nextElementSibling.placeholder;
							}
						}
					}
				}

				// Get time values with a loop
				if ( recurrenceSet.querySelector('.em-recurrence-timeranges .recurrence-timeranges-default input:checked') ) {
					timeranges = recurrenceSet.querySelector('.em-recurrence-timeranges .em.timeranges');
					['start', 'end'].forEach(function(type) {
						let timeInput = recurrenceSet.querySelector(`.em-recurrence-times .em-time-${type}`);
						if (timeInput) {
							timeValues[type] = timeranges.dataset[type];
							if ( timeInput.value ) {
								timeValues[type + 'IsSet'] = !!timeValues[type];
							}
						}
					});
				}

				// Get timezone from select
				let timezoneSelect = recurrenceSet.querySelector('.em-recurrence-timezone select');
				let timezoneValue = '';

				if ( timezoneSelect ) {
					let value = timezoneSelect.value;

					if (value) {
						// If there's a value, get the text of the selected option (using null-coalescing)
						timezoneValue = timezoneSelect.querySelector(`option[value="${value}"]`)?.textContent || '';
					} else {
						// If no value, try to get the placeholder (using null-coalescing)
						timezoneValue = recurrenceSet.querySelector('.em-recurrence-timezone .selectize-input input')?.placeholder || '';
					}
				}

				// Get duration
				let durationInput = recurrenceSet.querySelector('.em-recurrence-duration input.em-recurrence-duration');
				let durationValue = durationInput ? (durationInput.value.trim() || durationInput.placeholder || '0') : '0';
				emRecurrenceEditor.updateDurationDescriptor( recurrenceSet );

				// Update elements with direct one-liners
				if ( Object.entries(dateValues).length === 4 ) {
					advancedSummary.querySelectorAll('.start-date').forEach(el => { el.textContent = dateValues.start; el.classList.toggle('is-set', dateValues.startIsSet); });
					advancedSummary.querySelectorAll('.end-date').forEach(el => { el.textContent = dateValues.end; el.classList.toggle('is-set', dateValues.endIsSet); });
				} else {
					advancedSummary.querySelectorAll('.dates').forEach(el => { el.textContent = dateValues.start; el.classList.toggle('is-set', dateValues.startIsSet); });
				}
				advancedSummary.querySelectorAll('.times').forEach( function( el ) {
					el.innerHTML = `<span class="start-time">${timeValues.start}</span> - <span class="end-time">${timeValues.end}</span>`;
					el.firstElementChild.classList.toggle('is-set', timeValues.startIsSet);
					el.lastElementChild.classList.toggle('is-set', timeValues.endIsSet);
				});
				advancedSummary.querySelector('.all-day')?.classList.toggle('is-set', recurrenceSet.querySelector('.em-time-all-day')?.checked );
				advancedSummary.querySelectorAll('.timezone').forEach(el => { el.textContent = timezoneValue; el.classList.toggle('is-set', timezoneSelect?.value); });
				advancedSummary.querySelectorAll('.duration').forEach(el => { el.textContent = durationValue; el.classList.toggle('is-set', durationInput && durationInput.value !== ''); });
			}
		});
	});
});

document.addEventListener('em_event_editor_recurrences', function( e ) {
	let recurrenceSets = e.detail.recurrenceSets;

	let setup_ui_elements = function( container ) {
		// clean up template of UI elements so they can be rebuilt when cloned
		if ( container === document ) {
			let template = recurrenceSets.querySelector('.em-recurrence-set-template');
			em_unsetup_ui_elements( template );
		}

		recurrenceSets.dispatchEvent( new CustomEvent('setAdvancedDefaults') );

		let eventType = emRecurrenceFormRoot( recurrenceSets ).querySelector('input[name="event_type"]')?.value;

		// Add change handlers for selectize dropdowns in first recurrence set
		// track selectize changes assuming recurrences are enabled
		if ( container === document && ( eventType === 'recurring' || eventType === 'repeating' ) ) {
			// Get the first recurrence set
			let firstRecurrenceSet = recurrenceSets.querySelector('.em-recurrence-type-include .em-recurrence-set:first-child');

			// Map of recurrence field selectors to event field selectors
			const fieldMappings = {
				'.em-recurrence-timezone select': 'select[name="event_timezone"]',
				'.em-recurrence-status select': 'select[name="event_active_status"]'
			};

			// Handle each field type
			Object.entries(fieldMappings).forEach( function([recurrenceSelector, eventSelector]) {
				let recurrenceField = firstRecurrenceSet.querySelector(recurrenceSelector);

				// Find the corresponding event field
				let eventFormWhen = emRecurrenceFormRoot( recurrenceSets ).querySelector('.event-form-when');
				let eventField = eventFormWhen?.querySelector(eventSelector);

				if ( recurrenceField && eventField ) {
					// Set up change handler using selectize API if available
					if (recurrenceField.selectize) {
						// For selectize fields
						recurrenceField.selectize.on('change', function (value) {
							if (eventField.selectize) {
								// If event field is also selectize
								eventField.selectize.setValue(value, true);
							} else {
								// If event field is a regular select
								eventField.value = value;
								eventField.dispatchEvent(new Event('change', {bubbles: true}));
							}
						});
					} else {
						// Fallback for regular select fields
						recurrenceField.addEventListener('change', function () {
							if (eventField.selectize) {
								eventField.selectize.setValue(recurrenceField.value, true);
							} else {
								eventField.value = recurrenceField.value;
								eventField.dispatchEvent(new Event('change', {bubbles: true}));
							}
						});
					}

					// Also handle initial sync (if recurrence field already has a value)
					let initialValue = recurrenceField.selectize ? recurrenceField.selectize.getValue() : recurrenceField.value;
					if (initialValue) {
						if (eventField.selectize) {
							eventField.selectize.setValue(initialValue, true);
						} else {
							eventField.value = initialValue;
						}
					}
				}
			});
		}
	}

	document.addEventListener('em_setup_ui_elements', function(e) {
		setup_ui_elements( e.detail.container );
	});

	// If already loaded, we trigger a first-time setup
	if (document.readyState === 'complete' || document.readyState === 'interactive') {
		setup_ui_elements( document );
	}
});

//Tickets & Bookings - legacy stuff needing some rewrites
document.addEventListener('em_event_editor_loaded', function(e){
	const $ = jQuery.noConflict();
	if ( $( "#em-tickets-form" ).length > 0 ) {
		//Enable/Disable Bookings
		document.getElementById('event-rsvp').addEventListener('click', function (event) {
			const nonceInput = this.parentElement.querySelector('input.event_rsvp_delete[data-nonce]');
			const rsvpOptions = document.getElementById('event-rsvp-options');
			if (!this.checked) {
				const confirmation = confirm(EM.disable_bookings_warning);
				if (!confirmation) {
					event.preventDefault();
				} else {
					rsvpOptions.classList.add('hidden');
					nonceInput.disabled = false;
				}
			} else {
				rsvpOptions.classList.remove('hidden');
				nonceInput.disabled = true;
			}
		});
		if ( $( 'input#event-rsvp' ).is( ":checked" ) ) {
			$( "div#rsvp-data" ).fadeIn();
		} else {
			$( "div#rsvp-data" ).hide();
		}
		//Ticket(s) UI
		var reset_ticket_forms = function () {
			$( '#em-tickets-form table tbody tr.em-tickets-row' ).show();
			$( '#em-tickets-form table tbody tr.em-tickets-row-form' ).hide();
		};
		// handle indeterminate checkboxes and the hidden inputs they associate with
		document.querySelectorAll('#em-tickets-form input.possibly-indeterminate[type="checkbox"], #em-tickets-form input[type="checkbox"][indeterminate]').forEach( cb => {
			if ( cb.hasAttribute('indeterminate') && cb.readOnly ) {
				cb.indeterminate = true;
			}
			cb.addEventListener('click', () => {
				if ( cb.hasAttribute('indeterminate') && !cb.classList.contains('determinate') ) {
					if ( cb.readOnly ) {
						cb.checked = true;
						cb.readOnly = false;
					} else if ( cb.checked ) {
						cb.readOnly = true
						cb.indeterminate = true;
					}
					if ( cb.classList.contains('possibly-indeterminate') ) {
						cb.nextElementSibling.value = cb.indeterminate ? 'default' : ( cb.checked ? 1 : 0 );
					}
				} else {
					cb.nextElementSibling.value = cb.checked ? 1 : 0;
				}
			});
		});
		//Add a new ticket
		$( "#em-tickets-add" ).on( 'click', function ( e ) {
			e.preventDefault();
			reset_ticket_forms();
			//create copy of template slot, insert so ready for population
			var tickets = $( '#em-tickets-form table tbody' );
			tickets.first( '.em-ticket-template' ).find( 'input.em-date-input.flatpickr-input' ).each( function () {
				if ( '_flatpickr' in this ) {
					this._flatpickr.destroy();
				}
			} ); //clear all datepickers, should be done first time only, next times it'd be ignored
			var rowNo = tickets.length + 1;
			var slot = tickets.first( '.em-ticket-template' ).clone( true ).attr( 'id', 'em-ticket-' + rowNo ).removeClass( 'em-ticket-template' ).addClass( 'em-ticket' ).appendTo( $( '#em-tickets-form table' ) );
			//change the index of the form element names
			slot.find( '*[name]' ).each( function ( index, el ) {
				el = $( el );
				el.attr( 'name', el.attr( 'name' ).replace( 'em_tickets[0]', 'em_tickets[' + rowNo + ']' ) );
			} );
			// sort out until datepicker ids
			let start_datepicker = slot.find( '.ticket-dates-from-normal' ).first();
			if ( start_datepicker.attr( 'data-until-id' ) ) {
				let until_id = start_datepicker.attr( 'data-until-id' ).replace( '-0', '-' + rowNo );
				start_datepicker.attr( 'data-until-id', until_id );
				slot.find( '.ticket-dates-to-normal' ).attr( 'id', start_datepicker.attr( 'data-until-id' ) );

			}
			//show ticket and switch to editor
			slot.show().find( '.ticket-actions-edit' ).trigger( 'click' );
			//refresh datepicker and values
			slot.find( '.em-time-input' ).off().each( function ( index, el ) {
				if ( typeof this.em_timepickerObj == 'object' ) {
					this.em_timepicker( 'remove' );
				}
			} ); //clear all em_timepickers - consequently, also other click/blur/change events, recreate the further down
			em_setup_ui_elements( slot );
			$( 'html, body' ).animate( { scrollTop: slot.offset().top - 30 } ); //sends user to form
			check_ticket_sortability();
			// set up a UUID for this ticket
			slot.find('.ticket_uuid').val(
				"10000000-1000-4000-8000-100000000000".replace(/[018]/g, c =>
					(+c ^ crypto.getRandomValues(new Uint8Array(1))[0] & 15 >> +c / 4).toString(16)
				)
			)
		} );
		//Edit a Ticket
		$( document ).on( 'click', '.ticket-actions-edit', function ( e ) {
			e.preventDefault();
			reset_ticket_forms();
			var tbody = $( this ).closest( 'tbody' );
			tbody.find( 'tr.em-tickets-row' ).hide();
			tbody.find( 'tr.em-tickets-row-form' ).fadeIn();
			return false;
		} );
		$( document ).on( 'click', '.ticket-actions-edited', function ( e ) {
			e.preventDefault();
			var tbody = $( this ).closest( 'tbody' );
			var rowNo = tbody.attr( 'id' ).replace( 'em-ticket-', '' );
			tbody.find( '.em-tickets-row' ).fadeIn();
			tbody.find( '.em-tickets-row-form' ).hide();
			tbody.find( '*[name]' ).each( function ( index, el ) {
				el = $( el );
				if ( el.attr( 'name' ) == 'ticket_start_pub' ) {
					tbody.find( 'span.ticket_start' ).text( el.val() );
				} else if ( el.attr( 'name' ) == 'ticket_end_pub' ) {
					tbody.find( 'span.ticket_end' ).text( el.val() );
				} else if ( el.attr( 'name' ) == 'em_tickets[' + rowNo + '][ticket_type]' ) {
					if ( el.find( ':selected' ).val() == 'members' ) {
						tbody.find( 'span.ticket_name' ).prepend( '* ' );
					}
				} else if ( el.attr( 'name' ) == 'em_tickets[' + rowNo + '][ticket_start_recurring_days]' ) {
					var text = tbody.find( 'select.ticket-dates-from-recurring-when' ).val() == 'before' ? '-' + el.val() : el.val();
					if ( el.val() != '' ) {
						tbody.find( 'span.ticket_start_recurring_days' ).text( text );
						tbody.find( 'span.ticket_start_recurring_days_text, span.ticket_start_time' ).removeClass( 'hidden' ).show();
					} else {
						tbody.find( 'span.ticket_start_recurring_days' ).text( ' - ' );
						tbody.find( 'span.ticket_start_recurring_days_text, span.ticket_start_time' ).removeClass( 'hidden' ).hide();
					}
				} else if ( el.attr( 'name' ) == 'em_tickets[' + rowNo + '][ticket_end_recurring_days]' ) {
					var text = tbody.find( 'select.ticket-dates-to-recurring-when' ).val() == 'before' ? '-' + el.val() : el.val();
					if ( el.val() != '' ) {
						tbody.find( 'span.ticket_end_recurring_days' ).text( text );
						tbody.find( 'span.ticket_end_recurring_days_text, span.ticket_end_time' ).removeClass( 'hidden' ).show();
					} else {
						tbody.find( 'span.ticket_end_recurring_days' ).text( ' - ' );
						tbody.find( 'span.ticket_end_recurring_days_text, span.ticket_end_time' ).removeClass( 'hidden' ).hide();
					}
				} else {
					var classname = el.attr( 'name' ).replace( 'em_tickets[' + rowNo + '][', '' ).replace( ']', '' ).replace( '[]', '' );
					tbody.find( '.em-tickets-row .' + classname ).text( el.val() );
				}
			} );
			//allow for others to hook into this
			$( document ).triggerHandler( 'em_maps_tickets_edit', [ tbody, rowNo, true ] );
			$( 'html, body' ).animate( { scrollTop: tbody.parent().offset().top - 30 } ); //sends user back to top of form
			return false;
		} );
		$( document ).on( 'change', '.em-ticket-form select.ticket_type', function ( e ) {
			//check if ticket is for all users or members, if members, show roles to limit the ticket to
			var el = $( this );
			let ticketForm = el.closest( '.em-ticket-form' );
			if ( this.value === 'members' || ( this.value === '-1' && this.dataset.default === 'members' ) ) {
				el.closest( '.em-ticket-form' ).find( '.ticket-roles' ).fadeIn();
			} else {
				el.closest( '.em-ticket-form' ).find( '.ticket-roles' ).hide();
			}
			if ( this.value === '-1' && this.dataset.default === 'members' ) {
				// set all checkboxes with indeterminate prop to indeterminate
				ticketForm[0].querySelectorAll( '.ticket-roles input[type="checkbox"][indeterminate]' ).forEach( el => {
					el.indeterminate = true;
					el.classList.remove( 'determinate' )
				} );
				ticketForm[0].querySelectorAll( '.ticket-roles input[type="checkbox"]:not([indeterminate])' ).forEach( el => { el.checked = false; } );
			}else if ( this.value === 'members' ) {
				// remove indeterminate prop from all checkboxes
				ticketForm[0].querySelectorAll( '.ticket-roles input[type="checkbox"][indeterminate]' ).forEach( el => {
					el.indeterminate = false;
					el.readOnly = false;
					el.checked = true;
					el.classList.add( 'determinate' )
				} );
			}
		});
		$('.em-ticket-form select.ticket_type').trigger('change');
		$( document ).on( 'change', '.em-ticket-form .ticket-roles input[type="checkbox"]', function ( e ) {
			let ticketForm = this.closest( '.em-ticket-form' );
			let select = ticketForm.querySelector( '.em-ticket-form select.ticket_type' )
			if ( select.dataset.default === 'members' && select.value === '-1' ) {
				select.value = 'members';
				ticketForm.querySelectorAll( '.ticket-roles input[type="checkbox"][indeterminate]' ).forEach( el => {
					el.indeterminate = false;
					el.readOnly = false;
					el.checked = true;
					el.classList.add( 'determinate' )
				} );
			}
		});
		$( document ).on( 'click', '.em-ticket-form .ticket-options-advanced', function ( e ) {
			//show or hide advanced tickets, hidden by default
			e.preventDefault();
			var el = $( this );
			if ( el.hasClass( 'show' ) ) {
				el.closest( '.em-ticket-form' ).find( '.em-ticket-form-advanced' ).fadeIn();
				el.find( '.show,.show-advanced' ).hide();
				el.find( '.hide,.hide-advanced' ).show();
			} else {
				el.closest( '.em-ticket-form' ).find( '.em-ticket-form-advanced' ).hide();
				el.find( '.show,.show-advanced' ).show();
				el.find( '.hide,.hide-advanced' ).hide();
			}
			el.toggleClass( 'show' );
		} );
		$( '.em-ticket-form' ).each( function () {
			//check whether to show advanced options or not by default for each ticket
			var show_advanced = false;
			var el = $( this );
			el.find( '.em-ticket-form-advanced input[type="text"]' ).each( function () {
				if ( this.value != '' ) show_advanced = true;
			} );
			if ( el.find( '.em-ticket-form-advanced input[type="checkbox"]:checked' ).length > 0 ) {
				show_advanced = true;
			}
			el.find( '.em-ticket-form-advanced option:selected' ).each( function () {
				if ( this.value != '' ) show_advanced = true;
			} );
			if ( show_advanced ) el.find( '.ticket-options-advanced' ).trigger( 'click' );
		} );
		//Delete a ticket
		$( document ).on( 'click', '.ticket-actions-delete', function ( e ) {
			e.preventDefault();
			var el = $( this );
			var tbody = el.closest( 'tbody' );
			if ( tbody.find( 'input.ticket_id' ).val() > 0 ) {
				//only will happen if no bookings made, we set the ticket as deleted and enable the delete nonce
				let warning = this.classList.contains( 'parent-ticket' ) ? EM.eventEditor.deleteTicketParentWarning : EM.eventEditor.deleteTicketWarning;
				if ( confirm( warning ) ) {
					tbody.find( 'input.delete[data-nonce]' ).prop('disabled', false);
					tbody.closest( '.em-ticket' ).addClass( 'ticket-deleted' );
				}
			} else {
				//not saved to db yet, so just remove
				tbody.remove();
			}
			check_ticket_sortability();
			return false;
		} );
		//Sort Tickets
		$( '#em-tickets-form.em-tickets-sortable table' ).sortable( {
			items: '> tbody',
			placeholder: "em-ticket-sortable-placeholder",
			handle: '.ticket-status',
			helper: function ( event, el ) {
				var helper = $( el ).clone().addClass( 'em-ticket-sortable-helper' );
				var tds = helper.find( '.em-tickets-row td' ).length;
				helper.children().remove();
				helper.append( '<tr class="em-tickets-row"><td colspan="' + tds + '" style="text-align:left; padding-left:15px;"><span class="dashicons dashicons-tickets-alt"></span></td></tr>' );
				return helper;
			},
		} );
		var check_ticket_sortability = function () {
			var em_tickets = $( '#em-tickets-form table tbody.em-ticket' );
			if ( em_tickets.length == 1 ) {
				em_tickets.find( '.ticket-status' ).addClass( 'single' );
				$( '#em-tickets-form.em-tickets-sortable table' ).sortable( "option", "disabled", true );
			} else {
				em_tickets.find( '.ticket-status' ).removeClass( 'single' );
				$( '#em-tickets-form.em-tickets-sortable table' ).sortable( "option", "disabled", false );
			}
		};
		check_ticket_sortability();
	}
});
//# sourceMappingURL=events-manager-event-editor.js.map