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