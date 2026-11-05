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