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