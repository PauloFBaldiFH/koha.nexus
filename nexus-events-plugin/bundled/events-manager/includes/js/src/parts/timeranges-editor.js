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