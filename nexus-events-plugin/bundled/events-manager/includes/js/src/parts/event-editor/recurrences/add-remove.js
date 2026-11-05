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