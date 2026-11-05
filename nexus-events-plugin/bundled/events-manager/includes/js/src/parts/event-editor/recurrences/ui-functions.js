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