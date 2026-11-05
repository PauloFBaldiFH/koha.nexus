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