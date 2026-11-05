function em_setup_timepicker( container ){
	wrap = jQuery(container);
	var timepicker_options = {
		step:15,
		// Append the dropdown list to the input's OWN document so it renders inside the
		// Gutenberg editor-canvas iframe rather than the parent body. In the classic editor
		// ownerDocument === document, so this matches the plugin's default "body" target.
		appendTo: function( input ){
			var el = input instanceof jQuery ? input[0] : input;
			return jQuery( ( el && el.ownerDocument && el.ownerDocument.body ) || document.body );
		}
	}
	timepicker_options.timeFormat = EM.show24hours == 1 ? 'G:i':'g:i A';
	jQuery(document).triggerHandler('em_timepicker_options', timepicker_options);
	wrap.find(".em-time-input").em_timepicker(timepicker_options).each( function(i, el){
		this.dataset.seconds = this.value ? jQuery(this).em_timepicker('getSecondsFromMidnight') : '';
	});

	/**
	 * A function that retargets an the change event to the .em-time-range enclosing div whilst maintinaing the originally triggered target.
	 * This is done because the em_timepicker short-circuits the bubbling.
	 *
	 * @param {Event} e - The original event to be retargeted.
	 */
	let retargetEvent = function(e) {
		e.stopPropagation();
		const customEvent = new CustomEvent('change', {
			bubbles: true,
			cancelable: true,
			detail: { target: e.target }
		});

		// Override the target getter to return the original element
		Object.defineProperty(customEvent, 'target', {
			configurable: true,
			get: () => e.target,
		});
		e.target.closest('.em-time-range').dispatchEvent( customEvent );
	};

	// Keep the duration between the two inputs.
	wrap.find(".em-time-range input.em-time-start").each( function(i, el){
		var time = jQuery(el);
		time.data('oldTime', time.em_timepicker('getSecondsFromMidnight'));
	}).on('change', function( e ) {
		var start = jQuery(this);
		var wrapper = start.closest('.em-time-range');
		var end = wrapper.find('.em-time-end').first();
		if ( end.val() ) { // Only update when second input has a value.
			// Calculate duration.
			var oldTime = start.data('oldTime');
			var duration = (end.em_timepicker('getSecondsFromMidnight') - oldTime) * 1000;
			var time = start.em_timepicker('getSecondsFromMidnight');
			if(  this.value && end.em_timepicker('getSecondsFromMidnight') >= oldTime ){
				// Calculate and update the time in the second input.
				end.em_timepicker('setTime', new Date(start.em_timepicker('getTime').getTime() + duration));
			}
			start.data('oldTime', time);
		}
		if ( start.val() || end.val() ) {
			wrapper.find('.em-time-all-day').prop('checked', false).prop('indeterminate', false);
		}
		this.dataset.seconds = start.val() ? start.em_timepicker('getSecondsFromMidnight') : '';
		retargetEvent(e);
	});
	// Validate.
	container.querySelectorAll('.em-time-range').forEach( el => el.addEventListener('change', function (e) {
		if ( e.target.matches('input.em-time-end') ) {
			let end = jQuery(e.target);
			e.target.dataset.seconds = end.val() ? end.em_timepicker('getSecondsFromMidnight') : '';
			em_validate_end_time( e.target );
		} else if ( e.target.matches('input.em-time-all-day') ) {
			e.currentTarget.querySelectorAll('.em-time-input').forEach(function (input) {
				input.readOnly = e.target.checked;
			});
			if ( e.target.checked ) {
				// set 12am and 11:59pm for start/end times
				e.currentTarget.querySelectorAll('.em-time-start').forEach( el => jQuery(el).em_timepicker('setTime', new Date('2000-01-01 00:00:00') ) );
				e.currentTarget.querySelectorAll('.em-time-end').forEach( el => jQuery(el).em_timepicker('setTime', new Date('2000-01-01 23:59:59') ) );
			}
		}
	}) );
	// Re-validate on either date changing, so that a multi-day event no longer flags an end time earlier than its start time.
	wrap.find('input[name="event_start_date"], input[name="event_end_date"]').off('change.em_timepicker').on('change.em_timepicker', function () {
		jQuery(this).closest('.event-form-when').find('.em-time-range input.em-time-end').each( function () {
			em_validate_end_time( this );
		});
	});
	// listen to and dispatch the event
	wrap.find(".em-time-range input.em-time-end").on('change', retargetEvent );
}

/**
 * Flags an end time that falls before its start time, which is only an error when the event starts and ends on the same day.
 * Global because the timeranges editor clears the error class off a whole editor and has to put this one back.
 *
 * @param {HTMLInputElement} el
 */
function em_validate_end_time( el ) {
	let range = el.closest('.em-time-range');
	let start = jQuery( range ? range.querySelector('input.em-time-start') : null );
	let end = jQuery(el);
	if ( !start.val() ) {
		return;
	}
	if ( !end.val() ) {
		el.classList.remove('error');
		return;
	}
	// Ticket availability dates its own range, everything else is dated by the event.
	let range_dates = range ? range.querySelectorAll('input[type="date"]') : [];
	let dates_wrapper = el.closest('.event-form-when');
	let start_date_element = range_dates.length === 2 ? range_dates[0] : ( dates_wrapper ? dates_wrapper.querySelector('input[name="event_start_date"]') : null );
	let end_date_element = range_dates.length === 2 ? range_dates[1] : ( dates_wrapper ? dates_wrapper.querySelector('input[name="event_end_date"]') : null );
	let start_date = start_date_element ? start_date_element.value : '';
	let end_date = end_date_element ? end_date_element.value : '';
	// A recurrence set crosses midnight on its duration in days rather than a date range, and reconciles its own times.
	let hasError = !el.closest('.em-recurrence-set') && start.em_timepicker('getTime') > end.em_timepicker('getTime') && ( !end_date || start_date === end_date );
	el.classList.toggle('error', hasError);
}

function em_unsetup_timepicker( container ) {
	jQuery(container).find('.em-time-range input.em-time-end, .em-time-range input.em-time-start').unbind(['click','focus','change']); //clear all timepickers - consequently, also other click/blur/change events, recreate the further down
}