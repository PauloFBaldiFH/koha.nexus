
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