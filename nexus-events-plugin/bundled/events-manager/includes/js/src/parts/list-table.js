// WP List Tables front-end stuff
const setupListTable = function( listTable ) {
	// handle checks of multiple items using shift
	const checkboxes = listTable.querySelectorAll( 'tbody .check-column input[type="checkbox"]' );
	// The export and settings modals carry the same form class, so match the main form only.
	const listTableForm = listTable.querySelector('form.em-list-table-form:not(.em-list-table-export-form):not(.em-list-table-settings-form)');
	if ( !listTableForm ) {
		return;
	}
	let lastChecked;

	//Pagination link clicks
	listTable.querySelectorAll('.tablenav-pages a').forEach( el => {
		el.addEventListener('click', function ( e ) {
			e.preventDefault();
			//get page no from url, change page, submit form
			let match = el.href.match(/#[0-9]+/);
			if ( match != null && match.length > 0 ) {
				let pno = match[0].replace('#', '');
				listTableForm.querySelector('input[name=pno]').val(pno);
			} else {
				// new way
				let url = new URL(el.href);
				if ( url.searchParams.has('paged') ) {
					listTableForm.querySelectorAll('input[name=pno], input[name=paged]').forEach( el => el.value = url.searchParams.get('paged') );
				} else {
					listTableForm.querySelectorAll('input[name=pno], input[name=paged]').forEach( el => el.value = 1 );
				}
			}
			listTableForm.requestSubmit();
			return false;
		});
	});
	// Pagination - Input page number
	listTable.querySelectorAll('.tablenav-pages input[name=paged]').forEach( function ( input ){
		input.addEventListener('change', function (e) {
			e.preventDefault();
			let last = listTableForm.querySelector('.tablenav-pages a.last-page');
			if ( last ) {
				// check val isn't more than last page
				let url = new URL(last.href);
				if ( url.searchParams.has('paged') ) {
					let lastPage = parseInt(url.searchParams.get('paged'));
					if ( parseInt(input.value) > lastPage ) {
						input.value = lastPage;
					}
				}
			} else {
				// make sure it's less than current page, we're on last page already
				let lastPage = listTableForm.querySelector('input[name=pno]');
				if (lastPage && lastPage.value && parseInt(input.value) > parseInt(lastPage.value)) {
					input.value = lastPage.value;
					e.preventDefault();
					return false;
				}
			}
			listTableForm.querySelectorAll('input[name=pno]').forEach( el => el.value = input.value );
			listTableForm.requestSubmit();
			return false;
		});
	});

	// handle checkboxes
	listTable.addEventListener('click', function(e){
		// handle selecting all checkboxes
		if( e.target.matches('.manage-column.column-cb input') ){
			listTable.querySelectorAll('.check-column input').forEach( function( checkbox ){
				checkbox.checked = e.target.checked;
				checkbox.closest('tr').classList.toggle('selected', e.target.checked);
				// enable/disable bulk actions filter
				listTable.querySelector('.tablenav .bulkactions-input').querySelectorAll('input,select,button').forEach( function(el){
					e.target.checked ? el.removeAttribute('disabled') : el.setAttribute('disabled', true);
					e.target.checked ? el.classList.remove('disabled') : el.classList.add('disabled', true);
				});
			});
		} else if ( e.target.matches('tbody .check-column input[type="checkbox"]') ) {
			// handle multiple checks
			let inBetween = false;
			if ( e.shiftKey ) {
				checkboxes.forEach(checkbox => {
					if ( checkbox === e.target || checkbox === lastChecked ) {
						inBetween = !inBetween;
					}
					if ( inBetween || checkbox === lastChecked ) {
						checkbox.checked = lastChecked.checked;
					}
					checkbox.closest('tr').classList.toggle('selected', checkbox.checked);
				});
			} else {
				e.target.closest('tr').classList.toggle('selected', e.target.checked);
			}
			// enable/disable bulk actions filter
			let somethingSelected = e.target.checked || listTable.querySelectorAll( 'tbody .check-column input[type="checkbox"]:checked' ).length > 0;
			listTable.querySelector('.tablenav .bulkactions-input').querySelectorAll('input,select,button').forEach( function(el){
				somethingSelected ? el.removeAttribute('disabled') : el.setAttribute('disabled', true);
				somethingSelected ? el.classList.remove('disabled') : el.classList.add('disabled', true);
			});
			lastChecked = e.target;
		} else if ( e.target.closest('tbody .column-primary') ) {
			// handle row expand/collapse
			if ( e.target.matches('a[href],button:not(.toggle-row)') ) return true; // allow links to pass
			e.preventDefault();
			let rowExpandTrigger = e.target.closest('.column-primary');
			let row = rowExpandTrigger.closest('tr');
			if( row.classList.contains('expanded') ) {
				row.classList.remove('expanded');
				row.classList.add('collapsed');
				rowExpandTrigger.querySelector('button.toggle-row').classList.remove('expanded');
			} else {
				row.classList.add('expanded');
				row.classList.remove('collapsed');
				rowExpandTrigger.querySelector('button.toggle-row').classList.add('expanded');
			}
		}
	});
	// disable filter since no checkboxes initially selected
	listTable.querySelectorAll('.tablenav .bulkactions-input').forEach( (el) => {
		el.querySelectorAll('input,select,button').forEach(function (el) {
			el.setAttribute('disabled', true);
			el.classList.add('disabled', true);
		})
	});

	// Sorting by headers
	listTable.querySelector('thead').addEventListener('click', function( e ) {
		// get th element
		let th = e.target.tagName.toLowerCase() === 'th' ? e.target : e.target.closest('th');
		if( th && (th.classList.contains('sorted') || th.classList.contains('sortable')) ) {
			e.preventDefault();
			// add args to form and submit it
			let params = ( new URL( th.querySelector('a').href) ).searchParams;
			if ( params.get('orderby') ) {
				listTableForm.querySelector('input[name="orderby"]').value = params.get('orderby');
				let order = params.get('order') ? params.get('order') : 'asc';
				listTableForm.querySelector('input[name="order"]').value = order;
				listTableForm.requestSubmit();
			}
		}
	});

	// show/hide filters trigger
	let filterTrigger = listTable.querySelector('button.filters-trigger');
	if( filterTrigger ) {
		filterTrigger.addEventListener('click', function(e){
			e.preventDefault();
			if( filterTrigger.classList.contains('hidden') ) {
				listTable.querySelectorAll('div.actions.filters').forEach( filter => filter.classList.remove('hidden') );
				filterTrigger.classList.remove('hidden');
				filterTrigger.setAttribute('aria-label', filterTrigger.dataset.labelHide);
				if( '_tippy' in filterTrigger ){
					filterTrigger._tippy.setContent( filterTrigger.dataset.labelHide );
				}
			} else {
				listTable.querySelectorAll('div.actions.filters').forEach( filter => filter.classList.add('hidden') );
				filterTrigger.classList.add('hidden');
				filterTrigger.setAttribute('aria-label', filterTrigger.dataset.labelShow);
				if( '_tippy' in filterTrigger ){
					filterTrigger._tippy.setContent( filterTrigger.dataset.labelShow );
				}
			}
		});
		listTable.addEventListener('em_resize', function(){
			if( listTable.classList.contains('size-small') ) {
				filterTrigger.classList.remove('hidden'); // force hide click
				filterTrigger.click();
			}
		});
	}

	// EXPAND/COLLAPSE - RESPONSIVE
	// handle expand/collapse in responsive mode when clicking the expand/collapse (all)
	let expandTrigger = listTable.querySelector('button.small-expand-trigger');
	if( expandTrigger ) {
		// detect click and add expand class to table, expanded class to trigger
		expandTrigger.addEventListener('click', function(e){
			e.preventDefault();
			if( expandTrigger.classList.contains('expanded') ) {
				listTable.querySelectorAll('tbody tr.expanded, tbody button.toggle-row.expanded').forEach( el => el.classList.remove('expanded') );
				listTable.classList.remove('expanded');
				expandTrigger.classList.remove('expanded');
			} else {
				listTable.querySelectorAll('tbody tr, tbody button.toggle-row').forEach( el => {
					el.classList.add('expanded');
					el.classList.remove('collapsed');
				});
				listTable.classList.add('expanded');
				expandTrigger.classList.add('expanded');
			}
		});
	}

	// handle filters when pressing enter, submitting a search
	listTable.querySelectorAll('.tablenav .actions input[type="text"]').forEach( function (input) {
		input.addEventListener('keypress', function (e) {
			let keycode = (e.keyCode ? e.keyCode : e.which);
			if (keycode === 13) {
				e.preventDefault();
				listTableForm.requestSubmit();
			}
		});
	});

	// handle size breakpoints
	let breakpoints = {
		'xsmall' : 465,
		'small' : 640,
		'medium' : 930,
		'large' : false,
	}
	// submissions
	EM_ResizeObserver( breakpoints, [ listTable ] );

	//Widgets and filter submissions
	listTableForm.addEventListener('submit', function (e) {
		e.preventDefault();
		//append loading spinner
		listTable.classList.add('em-working');
		let loadingDiv = document.createElement('div');
		loadingDiv.id = 'em-loading';
		listTable.append(loadingDiv);
		listTable.querySelectorAll('.em-list-table-error-notice').forEach( el => el.remove() );
		//ajax call
		fetch( EM.ajaxurl, { method: 'POST', body: new FormData(listTableForm) } ).then( function( response ) {
			if ( response.ok ) {
				return response.text();
			} else {
				throw new Error('Network Response ' + response.status);
			}
		}).then( function( data ) {
			if ( !data ) {
				throw new Error('Empty string received');
			}
			if (!listTable.classList.contains('frontend')) {
				// remove modals as they are supplied again on the backend
				listTableForm.querySelectorAll('.em-list-table-trigger').forEach(function ( trigger ) {
					let modal = document.querySelector(trigger.rel);
					if( modal ) {
						modal.remove();
					}
				});
			}
			// get new data as DOM object
			let wrapper = document.createElement('div');
			wrapper.innerHTML = data;
			let newListTable = wrapper.firstElementChild;
			// replace old table with new table
			listTable.replaceWith( newListTable );
			// fire hook - note that form and data should not be used! This is for backward compatibility with an old jQuery hook being fired. Expect future consequences if you use them, obtain everything from listTable or prevListTable!
			document.dispatchEvent( new CustomEvent('em_list_table_filtered', { detail: { prevListTable: listTable, listTable: newListTable, form: newListTable.firstElementChild, data: data } }) );
		}).catch( function( error ) {
			let div = document.createElement('div');
			div.innerHTML = '<p>There was an unexpected error retrieving table data with error <code>' + error.message + '</code>, please try again or contact an administrator.</p>';
			div.setAttribute('class', 'em-warning error em-list-table-error-notice');
			listTable.querySelector('.table-wrap').before(div);
			loadingDiv.remove();
			listTable.classList.remove('em-working');
		});
		return false;
	});

	//Settings & Export Modal

	/**
	 * Handle trigger of settings and export modals.
	 */
	listTable.querySelectorAll('.em-list-table-trigger').forEach( trigger => {
		trigger.addEventListener('click', function (e) {
			e.preventDefault();
			let modal = document.querySelector( trigger.getAttribute('rel') );
			openModal(modal);
		});
	});

	/**
	 * Handle submission of settings forms, by copying over hidden input values such as cols and limit to main form.
	 */
	listTable.querySelectorAll('.em-list-table-settings form').forEach( form => {
		form.addEventListener('submit', function (e) {
			e.preventDefault();
			//we know we'll deal with cols, so wipe hidden value from main
			let modal = form.closest('.em-modal');
			let match = listTableForm.querySelector("[name=cols]");
			match.value = '';
			let tableCols = form.querySelectorAll('.em-list-table-cols-selected .item');
			tableCols.forEach( function (item_match) {
				if (!item_match.classList.contains('hidden')) {
					if (match.value !== '') {
						match.value = match.value + ',' + item_match.getAttribute('data-value');
					} else {
						match.value = item_match.getAttribute('data-value');
					}
				}
			});
			// sync row count
			let limit = form.querySelector('select[name="limit"]');
			if( limit ) {
				listTableForm.querySelector('[name="limit"]').value = limit.value;
			}
			// sync custom inputs
			form.querySelectorAll('[data-setting]').forEach( function( input ) {
				listTableForm.querySelectorAll('[name="'+input.name+'"]').forEach( el => el.remove() );
				let persisted = input.cloneNode(true);
				persisted.classList.add('hidden')
				listTableForm.appendChild( persisted );
			});
			closeModal(modal);
			// send events out
			modal.dispatchEvent( new CustomEvent('submitted') );
			listTable.dispatchEvent( new CustomEvent( 'em_list_table_settings_submitted', {
				detail: {
					listTableForm: listTableForm,
					form: form,
					modal: modal
				},
				bubbles: true
			}) );
			// submit main form
			listTableForm.requestSubmit();
		});
	});

	/**
	 * Handle submission of export forms, by copying over filters and hidden inputs with the data-persist attribute from main list table form.
	 */
	listTable.querySelectorAll('.em-list-table-export > form').forEach( function( exportForm ) {
		exportForm.addEventListener('submit', function(e) {
			var formFilters = this.querySelector('.em-list-table-filters');
			if ( formFilters ) {
				// get all filter inputs in main list table form and copy over so export inherits all filters to output right results
				let filters = listTableForm.querySelectorAll('.em-list-table-filters [name]');
				formFilters.innerHTML = ''; // Empty the filters, none to copy over
				if( filters ) {
					filters.forEach( function( filter ) {
						formFilters.appendChild( filter.cloneNode(true) );
					});
				}
				let peristentData = listTableForm.querySelectorAll('[data-persist]');
				if( peristentData ) {
					peristentData.forEach( function( filter ) {
						formFilters.appendChild( filter.cloneNode(true) );
					});
				}
			}
		});
	});

	// sortables
	listTable.querySelectorAll(".em-list-table-cols-sortable").forEach( function(sortable) {
		Sortable.create( sortable );
	});

	// add trigger
	document.dispatchEvent( new CustomEvent('em_list_table_setup', { detail: { listTable: listTable, listTableForm: listTableForm } }) );

	// add extra listeners that we might want to block such as in bulk actions and row actions

	/* ----------------- Row/Bulk Action Handlers ----------------- */

	const actionMessages = listTableForm.dataset.actionMessages ? JSON.parse( listTableForm.dataset.actionMessages ) : {};
	let isBulkAction = false;

	listTable.addEventListener('click', function( e ) {
		if( e.target.matches('a[data-row_action]') ) {
			e.preventDefault();
			let el = e.target;
			let tr = el.closest('tr');

			if( !isBulkAction ) {
				let confirmation = []
				// check if we need to confirm something specific
				if ( el.dataset.confirmation && el.dataset.confirmation in actionMessages ) {
					confirmation.push( actionMessages[el.dataset.confirmation] );
				}
				// check context of action and warn then propagate if upstream
				if ( el.dataset.row_action in actionMessages ) {
					confirmation.push( actionMessages[el.dataset.row_action] );
				}

				if ( confirmation.length > 0 ) {
					if ( !confirm( confirmation.join("\n\n") ) ) {
						return false;
					}
				}
			}

			// close dropdown if applicable
			let dropdown = el.closest('[data-tippy-root], .em-tooltip-ddm-content');
			if ( dropdown ) {
				if ( '_tippy' in dropdown ) {
					dropdown._tippy.hide();
				}
			}

			// handle upstream rows, add a loading class to them so they don't get double-tapped, no checks necessary here since we have clicked a single row item
			if( el.dataset.upstream ) {
				// block any same upstream_id row so it's loading already pending refresh
				listTable.querySelectorAll('tr[data-id="' + tr.dataset.id + '"]').forEach( tr => tr.classList.add('loading') );
			}

			// prep and fetch/refresh
			let formData = new FormData( listTableForm );
			for( const [key, value] of Object.entries(el.dataset) ) {
				formData.set(key, value);
			}
			formData.set('view', listTable.dataset.view);
			formData.set('action', listTable.dataset.basename + '_row');
			listTableRowAction( tr, formData );

			return false; // stop propagation
		}
	});

	// Action links (approve/reject etc.) - circumvent if a warning is required
	listTable.addEventListener( 'click', function( e ) {
		if( e.target.matches('a[data-row_action]') ) {
			e.preventDefault();
		}
	});

	listTable.querySelectorAll('button.em-list-table-bulk-action').forEach( function( button ) {
		button.addEventListener('click', function (e) {
			e.preventDefault(); // override default
			let actionSelector = listTableForm.querySelector('select.bulk-action-selector');
			let action = actionSelector.options[actionSelector.selectedIndex];
			
			// check if we need to confirm
			if ( action.dataset.confirm ) {
				if ( !confirm( action.dataset.confirm ) ) {
					isBulkAction = false; // just in case
					return false;
				}
			}

			isBulkAction = true;
			// find all checked items and perform action on them if the action actually exists for that row (e.g. you can't re-approve an approved booking)
			let rows = listTableForm.querySelectorAll('tbody .check-column input:checked');
			rows.forEach( function ( checkbox ) {
				let actionTrigger = checkbox.parentElement.querySelector('[data-row_action="' + action.value + '"]');
				// check if sibling has the relevant action
				if( actionTrigger ) {
					let tr = checkbox.closest('tr');
					if ( actionTrigger.dataset.upstream ) {
						// check if not already in an upstream process, proceed if not
						if ( !tr.classList.contains('loading') ) { // if loading, already in upstream from another row
							// trigger the first booking id row in this table, it'll handle upstream stuff
							actionTrigger.click();
						}
					} else {
						// regular action, just click it
						actionTrigger.click();
					}
				}
			});
			isBulkAction = false;
		});
	});


	// add a listener to refresh related booking rows if upstream
	listTable.addEventListener('em_list_table_row_action_complete', function(e){
		if ( e.detail.upstream ) {
			// find any rows other than the current one and trigger a refresh
			let currentRow = e.detail.currentRow;
			let formData = e.detail.formData;
			if( formData.get('row_action') === 'delete' ) {
				let feedback = currentRow.querySelector('.column-primary span.em-icon-trash.em-tooltip');
				if ( feedback ) {
					listTable.querySelectorAll('tr[data-id="' + formData.get('row_id') + '"]').forEach( function( tr ) {
						// apply to all rows of same booking_id except the one we just updated
						if ( tr !== currentRow ) {
							let td = tr.querySelector('.column-primary');
							td.prepend(feedback.cloneNode(true));
							em_setup_tippy(td);
						}
						tr.classList.remove('faded-out');
						tr.classList.remove('loading');
					});
				}
			} else if( formData.get('row_action') !== 'refresh' ) {
				let feedback = currentRow.querySelector('.column-primary span.em-icon.em-tooltip').getAttribute('aria-label');
				formData.set('row_action', 'refresh'); // this is a special action that just refreshes the row
				formData.set('feedback', feedback);
				listTable.querySelectorAll('tr[data-id="' + formData.get('row_id') + '"]').forEach( function( tr ) {
					// apply to all rows of same booking_id except the one we just updated
					if( tr !== currentRow ) {
						listTableRowAction(tr, formData);
						// delete current booking_id and reset isUpstreamAction if we're done
						delete isUpstreamAction[e.detail.booking_id];
						if (Object.keys(isUpstreamAction).length) {
							isUpstreamAction = false;
						}
					}
				});
			}
		}
	});

	// setup rows with actions if there are any
	listTable.querySelectorAll('td.column-actions a').forEach( (action) => {
		action.classList.add('em-tooltip');
		action.setAttribute('aria-label', action.innerText);
	});
}

let listTableRowAction = function( tr, formData, upstream = false ){
	let listTable = tr.closest('.em-list-table');
	tr.classList.add('loading');
	formData.set('row_id', tr.dataset.id );
	fetch( EM.ajaxurl, { method: 'post', body : formData } ).then( function( response ) {
		return response.text();
	}).then( function( html ) {
		tr.classList.add('faded-out');
		if ( formData.get('row_action') === 'delete' ) {
			// the text provided is the icon, nothing else
			tr.querySelectorAll('.check-column input[type="checkbox"], .em-list-table-actions').forEach( el => el.remove() );
			let td = tr.querySelector('.column-primary');
			let wrapper = document.createElement('div');
			wrapper.innerHTML = html;
			let icon = wrapper.firstElementChild;
			em_setup_tippy(wrapper); // no actions to set up
			td.prepend(icon);
		} else {
			tr.innerHTML = html
			setupListTableExtras(tr);
		}
		tr.classList.remove('faded-out');
		tr.classList.remove('loading');
		listTable.dispatchEvent( new CustomEvent('em_list_table_row_action_complete', { detail: { currentRow: tr, formData: formData, upstream: upstream } } ) );
	});
}

const setupListTableExtras = function( listTable ) {
	// setup rows with actions if there are any
	listTable.querySelectorAll('td.column-actions a').forEach( (action) => {
		action.classList.add('em-tooltip');
		action.setAttribute('aria-label', action.innerText);
	});
	// remove tooltips within tooltips in cell tooltips
	listTable.querySelectorAll('tbody .em-list-table-col-tooltip .em-list-table-col-tooltip').forEach( (subtip) => {
		subtip.querySelectorAll('.em-tooltip').forEach( el => el.remove() );
		subtip.querySelectorAll('.em-tooltip-content').forEach( el => el.classList.remove('hidden') );
	});
	// set up tippy, selectize etc.
	em_setup_tippy( listTable );
	em_setup_selectize( listTable );
}

document.addEventListener('em_list_table_filtered', function(e){
	setupListTable( e.detail.listTable );
	// re-setup tippy, selectize etc.
	setupListTableExtras( e.detail.listTable );
});

// init
document.addEventListener('DOMContentLoaded', function() {
	// add back-compat stuff
	document.querySelectorAll('.em_obj div.tablenav').forEach( function( tablenav ){
		let em_obj = tablenav.closest('.em_obj');
		em_obj.classList.add('em-list-table','legacy', 'frontend');
		em_obj.querySelector('& > form')?.classList.add('em-list-table-form');
	});
	// find tables, one table failing to set up should not leave the rest of the page unwired
	document.querySelectorAll('.em-list-table').forEach( function( listTable ) {
		try {
			setupListTable( listTable );
		} catch ( error ) {
			console.error( error );
		}
	});
});