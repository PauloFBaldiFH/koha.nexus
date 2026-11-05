document.querySelectorAll('#em-booking-form').forEach( el => el.classList.add('em-booking-form') ); //backward compatability


// Add event listeners
var em_booking_form_observer;
document.addEventListener("em_booking_form_js_loaded", function( e ) {
	let container = e.detail.container;
	container.querySelectorAll('form.em-booking-form').forEach( function( booking_form ){
		// backwards compatibility tweaks
		if( !('id' in booking_form.dataset) ){
			// find event id and give some essential ids
			let event_id_el = booking_form.querySelector('input[name="event_id"]');
			if( event_id_el ){
				let event_id = event_id_el.value;
				booking_form.setAttribute('data-id', event_id);
				booking_form.setAttribute('id', 'em-booking-form-' + event_id);
				booking_form.parentElement.setAttribute('data-id', event_id);
				booking_form.parentElement.setAttribute('id', 'event-booking-form-' + event_id);
				booking_form.querySelectorAll('.em-booking-submit, input[type="submit"]').forEach( button => button.classList.add('em-form-submit') );
			}
		}
		em_booking_form_init( booking_form );
	});

	// if you have an AJAX-powered site, set EM.bookings_form_observer = true before DOMContentLoaded and EM will detect dynamically added booking forms
	if( 'bookings_form_observer' in EM && EM.bookings_form_observer ) {
		em_booking_form_observer = new MutationObserver( function( mutationList ) {
			mutationList.forEach( function( mutation ) {
				if ( mutation.type === 'childList' ){
					mutation.addedNodes.forEach( function( node ){
						if ( node instanceof HTMLDivElement && node.classList.contains('em-event-booking-form') ) {
							em_booking_form_init( node.querySelector('form.em-booking-form') );
						}
					});
				}
			});
		});
		em_booking_form_observer.observe( container, { childList: true, attributes: false, subtree: true, } );
	}

	// add a listener to close the recurring booking picker upon a successful booking
	container.addEventListener( 'em_booking_success', ( e ) => {
		if ( e.detail.response.success ) {
			e.target.closest('.em-booking-recurrence-form')?.querySelector( '.em-booking-recurrence-picker' )?.classList.add( 'hidden' );
		}
	});

	em_init_booking_recurring_form( container );
});

// Shared, page-cached fetch of the booking form nonces from the uncached endpoint, used on cached sites where the inline nonces are stale. Fetched once per page and reused by both the recurring form loader and each booking form's init. Resolves to null when the site is not in cache mode.
var em_booking_nonces_promise;
var em_get_booking_nonces = function(){
	if ( ! EM.cached ) {
		return Promise.resolve( null );
	}
	if ( ! em_booking_nonces_promise ) {
		em_booking_nonces_promise = fetch( EM.bookingajaxurl, {
			method : 'POST',
			body : new URLSearchParams({ action : 'booking_form_nonces' })
		} ).then( response => response.json() )
		   .catch( function( error ){ console.log('Error fetching booking form nonces:', error); return null; } );
	}
	return em_booking_nonces_promise;
};

var em_init_booking_recurring_form = function( container ) {
	// handle size breakpoints
	let fetchEM = function( data, responseType = 'text' ){
		// Fetch the booking form
		return fetch( EM.bookingajaxurl, {
			method: "POST",
			body: data
		}).then( function(response) {
			if (response.ok) {
				return responseType === 'json' ? response.json() : response.text();
			}
			return Promise.reject(response);
		});
	}

	let breakpoints = { 'xsmall': 425, 'small' : 650, 'medium' : 890, 'large' : false }
	EM_ResizeObserver( breakpoints, container.querySelectorAll( '.em-booking-recurrence-picker' ) );

	// handle the booking calendar for recurring events
	container.querySelectorAll('.em-booking-recurring').forEach( function( recurringBooking ){
		let nonces;
		let recurrenceBooking = recurringBooking.querySelector('.em-booking-recurrence-form');
		let recurrenceDates = recurringBooking.querySelector('.em-booking-recurrences');

		// load the nonces here, once, so we share them and also load them if in cache mode
		if ( !( nonces instanceof Object ) ) {
			if ( EM.cached ) {
				// get the nonces via the shared, page-cached fetch, set to an object so we don't double-dip
				nonces = {};
				em_get_booking_nonces().then( json => { if ( json ) { nonces = json; } } );
			} else {
				// nonces will be set already, get them directly
				nonces = {
					booking_form : recurrenceBooking.dataset.nonce,
					booking_recurrences : recurringBooking.querySelector('.em-booking-recurrence-picker')?.dataset.nonce,
				};
			}
		}

		// catch clicks to the calendar so that we load up dates on the side
		let gettingRecurrences;
		recurringBooking.addEventListener('click', function( e ){
			if ( e.target.closest('.em-calendar .eventful, .em-calendar .eventful-pre, .em-calendar .eventful-post, .em-calendar .eventful-today') ){
				// get the recurrence dates for this day
				e.preventDefault();
				if ( !gettingRecurrences ) {
					let date = e.target.closest('.em-cal-day-date');
					if ( date && recurrenceDates.dataset.date !== date?.dataset.date ) {
						// select this date, all others no
						date.closest('.em-cal-body').querySelectorAll('.em-cal-day-date').forEach( calDate => calDate.classList.toggle( 'selected', calDate === date ) );
						gettingRecurrences = getDateRecurrences( date?.dataset.date ).finally( () => { gettingRecurrences = null } );
					}
				}
			}
		});
		let getDateRecurrences = function( date = false ){
			// prepare data
			let data = {
				action: 'booking_recurrences',
				event_id: recurringBooking.dataset.event,
				day: date || '',
				nonce: nonces.booking_recurrences,
				timezone: recurringBooking.querySelector('.em-calendar')?.dataset.timezone || '',
			}
			// Check for skeleton template
			let skeleton = recurringBooking.querySelector('.em-booking-recurrences-skeleton')?.content.cloneNode(true);
			if ( skeleton ) {
				// count how many dates we have and add/remove that may from skeleton
				let count = recurrenceDates.querySelectorAll('.em-booking-recurrence').length;
				let skeletonRecurrenceDates = skeleton.querySelectorAll('.em-booking-recurrence');
				if ( count && count !== skeletonRecurrenceDates.length ) {
					// go through the skeleton dates and remove/add so it matches length
					if ( skeletonRecurrenceDates.length > count ) {
						for ( let i = count; i < skeletonRecurrenceDates.length; i++ ) {
							skeletonRecurrenceDates[i].remove();
						}
					} else if ( skeletonRecurrenceDates.length < count ) {
						let templateDate = skeletonRecurrenceDates[0];
						for ( let i = skeletonRecurrenceDates.length; i < count; i++ ) {
							skeleton.querySelector( '.em-booking-recurrence' ).append( templateDate.cloneNode( true ) );
						}
					}

				}
				// replace contents of bookingRecurrence with skeleton
				recurrenceDates.innerHTML = '';
				recurrenceDates.append(skeleton);
				recurrenceDates.classList.add('skeleton');
			}
			// Fetch the booking form
			return fetchEM( new URLSearchParams( data ) )
				.then( function( html ) {
					recurrenceDates.innerHTML = html;
					recurrenceDates.innerHTML = recurrenceDates.firstElementChild.innerHTML;
					recurrenceDates.dataset.date = date;
				})
				.catch( (error) => console.log('Error fetching booking form recurrences:', error) )
				.finally( () => {
					if ( recurrenceDates ) {
						// clean things up
						recurrenceDates.classList.remove('skeleton');
						em_setup_selectize( recurrenceDates );
						// select things if previously selected, otherwise remove classes/props
						let selected;
						if ( recurrenceDates.classList.contains('selected') && recurrenceDates.dataset.selectedEvent ) {
							// check if selectedEvent exists and reselect it, otherwise remove event
							selected = recurrenceDates.querySelector(`[data-event="${recurrenceDates.dataset.selectedEvent}"]`);
						}
						if ( selected ) {
							selected.classList.add('selected');
						} else {
							recurrenceDates.classList.remove('selected');
							delete recurrenceDates.dataset.selectedEvent;
						}
						// fire the loaded event
						recurrenceDates.dispatchEvent( new CustomEvent( 'booking_recurrences_loaded', {
							bubbles: true,
							detail: {
								date: date[0],
								time: date[1] || null
							}
						} ) );
					}
				});
		}

		// catch selection of timezone
		recurringBooking.addEventListener('change', function( e ){
			if ( e.target.matches('.em-booking-recurrences .em-timezone') && e.detail.target.value ) {
				// set timezone and reload calendar
				let calendar = recurringBooking.querySelector('.em-calendar');
				if ( calendar ) {
					calendar.dataset.timezone = e.detail.selectize.getValue();
					calendar.dispatchEvent( new CustomEvent( 'reload', { bubbles: true } ) );
				}
				// reload the current date
				getDateRecurrences( recurrenceDates.dataset.date ).finally( function() {
					if ( recurrenceDates.dataset.selectedEvent ) {
						recurrenceDates.querySelector(`[data-event="${recurrenceDates.dataset.selectedEvent}"]`).classList.add('selected');
					}
				});
			}
		})

		// get the booking form
		let fetchBookingForm = function( event_id ){
			if ( !event_id.match(/^\d+(:\d+)?$/) ) {
				recurrenceBooking.innerHTML = '';
			} else if ( recurrenceBooking && recurrenceBooking.dataset.event !== event_id ) {
				let data = {
					action: 'booking_form',
					event_id: event_id,
					nonce: nonces.booking_form,
				}

				// Check for skeleton template
				let skeleton = recurringBooking.querySelector('.em-booking-summary-skeleton')?.content.cloneNode(true);
				if ( skeleton ) {
					// replace contents of bookingRecurrence with skeleton
					recurrenceBooking.innerHTML = '';
					recurrenceBooking.append(skeleton);
					window.scroll({
						top: recurrenceBooking.getBoundingClientRect().top +  window.scrollY - EM.booking_offset,
						behavior : 'smooth',
					});
				}
				// set up recurrence data
				if ( recurrenceDates ) {
					recurrenceDates.classList.add('selected');
					recurrenceDates.dataset.selectedEvent = event_id;
					recurrenceDates.querySelectorAll('.em-booking-recurrence').forEach( function( recurrenceDate ) {
						recurrenceDate.classList.toggle('selected', recurrenceDate.dataset.event === `${event_id}` );
					});
				}

				// Fetch the booking form
				fetchEM ( new URLSearchParams(data) )
					.then(function(html) {
						// Initialize the new booking form
						recurrenceBooking.innerHTML = html;
						recurrenceBooking.dataset.event = event_id;
						// Find and execute inline scripts -- backward compatible
						const scripts = recurrenceBooking.querySelectorAll('script:not([type]), script[type="text/javascript"]');
						scripts.forEach(script => {
							if (!script.src) { // Only handle inline scripts
								const newScript = document.createElement('script');
								newScript.textContent = script.textContent;
								script.parentElement.replaceChild(newScript, script);
							}
						});
						// Initialize the forms
						let bookingForm = recurrenceBooking.querySelector('form.em-booking-form');
						if ( bookingForm) {
							em_setup_ui_elements( bookingForm );
							em_setup_scripts( bookingForm );
							em_booking_form_init( bookingForm );
						}
					})
					.catch( (error) => console.log('Error fetching booking form recurrences:', error) )
			}
		}

		recurringBooking.querySelector('.em-booking-recurrence-picker.mode-select')?.addEventListener('change', function( e ) {
			fetchBookingForm( e.detail.target.value );
		});
		// catch clicks on the recurrence dates and load booking form
		recurringBooking.querySelector('.em-booking-recurrences')?.addEventListener('click', function( e ){
			let recurrenceDate = e.target.closest('.em-booking-recurrence');
			if ( recurrenceDate && !recurrenceDate.hasAttribute('disabled') ){
				// get the recurrence dates for this day
				fetchBookingForm( recurrenceDate.dataset.event );
			}
		});

		// Function to handle URL hash for date format linking to specific recurrences
		let handleHashChange = function(e) {
		    // Skip if the hash change came from a link click
			if (e && e.type === 'hashchange' && window.lastClickedHashLink) {
				window.lastClickedHashLink = false;
				return;
			}
			// get the hash and see if it's a date we need to feed to the recurrence picker
		    let hash = window.location.hash.substring(1);
		    if ( hash.match(/^\d{4}-\d{2}-\d{2}(@\d{2}:\d{2}:\d{2})?$/) ) {
		        let date = hash.split('@')[0];
				if ( recurrenceDates ) {
					let recurrenceDate = recurringBooking.querySelector( `.em-booking-recurrence[href="#${ hash }"]` );
					if ( recurrenceDate ) {
						recurrenceDate.click();
					} else {
						if ( recurrenceDates?.dataset.date !== date ) {
							getDateRecurrences( date ).then( () => {
								recurringBooking.querySelector( `.em-booking-recurrence[href="#${ hash }"]` )?.click();
							} );
						}
					}
					// load calendar to match month/year we're after
					let calendar = recurringBooking.querySelector('.em-calendar');
					if ( calendar ) {
						let dateObj = new Date(date);
						if (calendar.dataset.year !== dateObj.getFullYear() || calendar.dataset.month !== dateObj.getMonth() + 1) {
							calendar.dataset.month = dateObj.getMonth() + 1;
							calendar.dataset.year = dateObj.getFullYear();
						}
						calendar.dispatchEvent(new CustomEvent('reload', { bubbles: true }));
					}
				}
		    }
		};
		// Track hash links being clicked
		container.addEventListener('click', function(e) {
		    if ( e.target.closest('a[href^="#"]') ) {
		        window.lastClickedHashLink = true;
		        // Reset flag after short delay in case hashchange event doesn't trigger
		        setTimeout( () => { window.lastClickedHashLink = false }, 100 );
		    }
		});

		// Check URL hash on initial load
		handleHashChange();

		// Add event listener for hash changes
		window.addEventListener('hashchange', handleHashChange);

	});
};

var em_booking_form_count_spaces = function( booking_form ){
	// count spaces booked, if greater than 0 show booking form
	let tickets_selected = 0;
	let booking_data = new FormData(booking_form);
	for ( const pair of booking_data.entries() ) {
		if( pair[0].match(/^em_tickets\[[0-9]+\]\[spaces\]/) && parseInt(pair[1]) > 0 ){
			tickets_selected++;
		}
	}
	booking_form.setAttribute('data-spaces', tickets_selected);
	return tickets_selected;
};

/**
 * The form action whose fresh nonce belongs in this form's _wpnonce, or false if the payload has none for it.
 * The wp-admin single-booking editor reuses this markup but submits booking_save with a
 * booking_save_{id} nonce in the same input, so refreshing it there swaps a valid nonce for
 * a wrong one and every save fails. Admin pages are never served from cache, so they never
 * needed the refresh in the first place.
 *
 * @param {HTMLFormElement} booking_form
 * @param {Object|null} nonces
 * @return {string|boolean}
 */
var em_booking_form_nonce_refreshable = function( booking_form, nonces ){
	var form_action = booking_form.querySelector('input[name="action"]');
	var action = form_action ? form_action.value : 'booking_add';
	return nonces && nonces[action] ? action : false;
};

var em_booking_form_init = function( booking_form ){
	booking_form.dispatchEvent( new CustomEvent('em_booking_form_init', {
		bubbles : true,
	}) );

	// On cached sites the booking_add nonce is baked into the cached page HTML and would be rejected server-side once it ages out; refresh it from the shared uncached endpoint so the submission carries a valid nonce. Harmless for recurring forms (already loaded fresh via AJAX) since the shared fetch is only made once per page, and a no-op when the site is not cached.
	em_get_booking_nonces().then( function( nonces ){
		var nonce_action = em_booking_form_nonce_refreshable( booking_form, nonces );
		if ( nonce_action ) {
			booking_form.querySelectorAll('input[name="_wpnonce"]').forEach( function( input ){ input.value = nonces[nonce_action]; } );
		}
	});

	/**
	 * When ticket selection changes, trigger booking form update event
	 */
	booking_form.addEventListener("change", function( e ){
		if ( e.target.matches('.em-ticket-select') || (EM.bookings.update_listener && e.target.matches(EM.bookings.update_listener)) ){
			// trigger spaces refresh
			em_booking_form_count_spaces( booking_form );
			// let others do similar stuff
			booking_form.dispatchEvent( new CustomEvent('em_booking_form_updated') );
		}
	});

	let em_booking_form_updated_listener; // prevents double-check due to jQuery listener
	/**
	 * When booking form is updated, get a booking intent
	 */
	booking_form.addEventListener("em_booking_form_updated", function( e ){
		em_booking_form_updated_listener = true;
		em_booking_summary_ajax( booking_form ).finally( function(){
			em_booking_form_updated_listener = false;
		});
	});
	if( jQuery ) {
		// check for jQuery-fired legacy JS, but check above isn't already in progress due to new JS elements
		jQuery(booking_form).on('em_booking_form_updated', function () {
			if( !em_booking_form_updated_listener ){
				em_booking_summary_ajax(booking_form);
			}
		})
	}


	/**
	 * When booking summary is updated, get a booking intent if supplied and trigger the updated intent option
	 */
	booking_form.addEventListener("em_booking_summary_updated", function( e ){
		let booking_intent = e.detail.response.querySelector('input.em-booking-intent');
		em_booking_form_update_booking_intent( booking_form, booking_intent );
	});

	/**
	 * When booking is submitted
	 */
	booking_form.addEventListener("submit", function( e ){
		if ( typeof booking_form.dataset.noajax === 'undefined' ) {
			e.preventDefault();
			em_booking_form_submit( e.target );
		}
	});

	// trigger an intent update
	let booking_intent = booking_form.querySelector('input.em-booking-intent');
	em_booking_form_update_booking_intent( booking_form, booking_intent );

	booking_form.dispatchEvent( new CustomEvent('em_booking_form_loaded', {
		bubbles : true,
	}) );
}

var em_booking_form_scroll_to_message = function ( booking_form ) {
	let messages = booking_form.parentElement.querySelectorAll('.em-booking-message');
	if( messages.length > 0 ) {
		let message = messages[0];
		window.scroll({
			top: message.getBoundingClientRect().top +  window.scrollY - EM.booking_offset,
			behavior : 'smooth',
		});
	}
}

var em_booking_form_add_message = function( booking_form, content = null, opts = {} ){
	let options = Object.assign({
		type : 'success', // or error
		replace : true,
		scroll : content !== null,
	}, opts);

	// replace
	if( options.replace ) {
		booking_form.parentElement.querySelectorAll('.em-booking-message').forEach( message => message.remove() );
	}

	// add message
	if( content !== null ) {
		let div = document.createElement('div');
		div.classList.add('em-booking-message', 'em-booking-message-' + options.type );
		div.innerHTML = content;
		booking_form.parentElement.insertBefore( div, booking_form );
	}

	// scroll if needed
	if( options.scroll ){
		em_booking_form_scroll_to_message( booking_form );
	}
}

var em_booking_form_add_error = function ( booking_form, error, opts = {} ) {
	let options = Object.assign({
		type : 'error',
	}, opts);
	if( error != null ){
		if( (Array.isArray(error) || typeof error === 'object') ){
			let error_msg = '';
			if( typeof error === 'object' ){
				Object.entries(error).forEach( function( entry ){
					let [id, err] = entry;
					error_msg += '<p data-field-id="'+ id + '">' + err + '</p>';
				});
			}else{
				error.forEach(function( err ){
					error_msg += '<p>' + err + '</p>';
				});
			}
			if( error_msg ) {
				em_booking_form_add_message( booking_form, error_msg, options );
			}
			console.log( error );
		}else{
			em_booking_form_add_message( booking_form, error, options );
		}
	}
}

var em_booking_form_add_confirm = function ( booking_form, message, opts = {}) {
	let options = Object.assign({
		hide : false,
	}, opts);
	em_booking_form_add_message( booking_form, message, options );
	if( options.hide ){
		em_booking_form_hide_success( booking_form );
	}
}

var em_booking_form_hide_success = function( booking_form, opts = {} ){
	let options = Object.assign({
		hideLogin : true,
	}, opts);
	let booking_summary_sections = booking_form.querySelectorAll('.em-booking-form-summary-title, .em-booking-form-summary-title');
	if ( booking_summary_sections.length > 0 ) {
		booking_form.querySelectorAll('section:not(.em-booking-form-section-summary)').forEach( section => section.classList.add('hidden') );
		booking_form.parentElement.querySelectorAll('.em-booking-form > h3.em-booking-section-title').forEach( section => section.classList.add('hidden') ); // backcompat
	} else {
		booking_form.classList.add('hidden');
	}
	booking_form.dispatchEvent( new CustomEvent( 'em_booking_form_hide_success', {
		detail : {
			options : options,
		},
		bubbles: true,
	}));
	// hide login
	if ( options.hideLogin ) {
		booking_form.parentElement.querySelectorAll('.em-login').forEach( login => login.classList.add('hidden') );
	}
}

var em_booking_form_unhide_success = function( booking_form, opts = {} ){
	let options = Object.assign({
		showLogin : true,
	}, opts);
	let booking_summary_sections = booking_form.querySelectorAll('.em-booking-form-summary-title, .em-booking-form-summary-title');
	if ( booking_summary_sections.length > 0 ) {
		booking_form.querySelectorAll('section:not(.em-booking-form-section-summary)').forEach( section => section.classList.remove('hidden') );
		booking_form.parentElement.querySelectorAll('.em-booking-form > h3.em-booking-section-title').forEach( section => section.classList.remove('hidden') ); // backcompat
	} else {
		booking_form.classList.remove('hidden');
	}
	booking_form.dispatchEvent( new CustomEvent( 'em_booking_form_unhide_success', {
		detail : {
			options : options,
		},
		bubbles: true,
	}));
	// hide login
	if ( options.showLogin ) {
		booking_form.parentElement.querySelectorAll('.em-booking-login').forEach( login => login.classList.add('hidden') );
	}
};

var em_booking_form_hide_spinner = function( booking_form ){
	booking_form.parentElement.querySelectorAll('.em-loading').forEach( spinner => spinner.remove() );
}

var em_booking_form_show_spinner = function( booking_form ){
	let spinner = document.createElement('div');
	spinner.classList.add('em-loading');
	booking_form.parentElement.append(spinner);
}

var em_booking_form_enable_button = function( booking_form, show = false ){
	let button = booking_form.querySelector('input.em-form-submit');
	button.disabled = false;
	button.classList.remove('disabled');
	if( show ){
		button.classList.remove('hidden');
	}
	return button;
}

var em_booking_form_disable_button = function( booking_form, hide = false ){
	let button = booking_form.querySelector('input.em-form-submit');
	button.disabled = true;
	button.classList.add('disabled');
	if( hide ){
		button.classList.add('hidden');
	}
	return button;
}

var em_booking_form_update_booking_intent = function( booking_form, booking_intent = null ){
	// remove current booking intent (if not the same as booking_intent and replace
	booking_form.querySelectorAll('input.em-booking-intent').forEach( function( intent ){
		if( booking_intent !== intent ) {
			intent.remove();
		}
	});
	// append to booking form
	if ( booking_intent ) {
		booking_form.append( booking_intent );
	}
	// handle the button and other elements on the booking form
	let button = booking_form.querySelector('input.em-form-submit');
	if( button ){
		if( booking_intent && booking_intent.dataset.spaces > 0 ){
			em_booking_form_enable_button( booking_form )
			if ( booking_intent.dataset.amount > 0 ) {
				// we have a paid booking, show paid booking button text
				if ( button.getAttribute('data-text-payment') ) {
					button.value = EM.bookings.submit_button.text.payment.replace('%s', booking_intent.dataset.amount_formatted);
				}
			} else {
				// we have a free booking, show free booking button
				button.value = EM.bookings.submit_button.text.default;
			}
		} else if ( !booking_intent && em_booking_form_count_spaces( booking_form ) > 0 ){
			// this is in the event that the booking form has minimum spaces selected, but no booking_intent was ever output by booking form
			// fallback / backcompat mainly for sites overriding templates and possibly not incluing the right actions/filters in their template
			button.value = EM.bookings.submit_button.text.default;
			em_booking_form_enable_button( booking_form );
		} else {
			// no booking_intent means no valid booking params yet
			button.value = EM.bookings.submit_button.text.default;
			em_booking_form_disable_button( booking_form );
		}
	}
	// if event is free or paid, show right heading (if avialable)
	booking_form.querySelectorAll('.em-booking-form-confirm-title').forEach( title => title.classList.add('hidden') );
	if( booking_intent && booking_intent.dataset.spaces > 0 ) {
		if (booking_intent.dataset.amount > 0) {
			booking_form.querySelectorAll('.em-booking-form-confirm-title-paid').forEach(title => title.classList.remove('hidden'));
		} else {
			booking_form.querySelectorAll('.em-booking-form-confirm-title-free').forEach(title => title.classList.remove('hidden'));
		}
	}
	// wrap intent into an object
	let intent = {
		uuid : 0,
		event_id : null,
		spaces : 0,
		amount : 0,
		amount_base : 0,
		amount_formatted : '$0',
		taxes : 0,
		currency : '$'
	};
	if( booking_intent ){
		intent = Object.assign(intent, booking_intent.dataset);
		intent.id = booking_intent.id; // the actual element id
	}
	// trigger booking_intent update for others to hook in
	booking_form.dispatchEvent( new CustomEvent('em_booking_intent_updated', {
		detail : {
			intent : intent,
			booking_intent : booking_intent,
		},
		cancellable : true,
		bubbles: true,
	}) );
}

var em_booking_summary_ajax_promise;
var em_booking_summary_ajax = async function ( booking_form ){
	let summary_section = booking_form.querySelector('.em-booking-form-section-summary');
	let summary;
	if( summary_section ) {
		summary = summary_section.querySelector('.em-booking-form-summary');
	}
	let booking_data = new FormData(booking_form);
	booking_data.set('action', 'booking_form_summary');

	if( em_booking_summary_ajax_promise ){
		em_booking_summary_ajax_promise.abort();
	}
	if( summary ){
		booking_form.dispatchEvent( new CustomEvent('em_booking_summary_updating', {
			detail : {
				summary : summary,
				booking_data : booking_data,
			},
			cancellable : true,
			bubbles: true,
		}) );
		let template = booking_form.querySelector('.em-booking-summary-skeleton');
		if ( template ) {
			let skeleton = template.content.cloneNode(true);
			// count tickets, duplicate ticket rows if more than 1
			if ( booking_form.dataset.spaces > 1 ) {
				let tickets = skeleton.querySelector('.em-bs-section-items')
				let ticket_row = tickets.querySelector('.em-bs-row.em-bs-row-item');
				for ( let i = 1; i < booking_form.dataset.spaces; i++ ) {
					tickets.append( ticket_row.cloneNode(true) );
				}
			}
			booking_form.dispatchEvent( new CustomEvent('em_booking_summary_skeleton', {
				detail: { skeleton: skeleton },
				bubbles: true,
			}) );
			summary.replaceChildren(skeleton);
		}
	}
	em_booking_summary_ajax_promise = fetch( EM.bookingajaxurl, {
		method: "POST",
		body: booking_data,
	}).then( function( response ){
		if( response.ok ) {
			return response.text();
		}
		return Promise.reject( response );
	}).then( function( html ){
		let parser = new DOMParser();
		let response = parser.parseFromString( html, 'text/html' );
		let summary_html = response.querySelector('.em-booking-summary');
		if( summary && summary_html ){
			summary.querySelectorAll('.em-loading').forEach( spinner => spinner.remove() );
			// show summary and reset up tippy etc.
			if ( typeof summary.replaceChildren === "function") { // 92% coverage, eventually use exclusively
				summary.replaceChildren(summary_html);
			} else {
				summary.innerHTML = '';
				summary.append(summary_html);
			}
			em_setup_tippy(summary);
			em_booking_summary_ajax_promise = false;
		}
		// dispatch booking summary updated event, which should also be caught and retriggered for a booking_intent update
		booking_form.dispatchEvent( new CustomEvent('em_booking_summary_updated', {
			detail : {
				response : response,
				summary : summary,
			},
			cancellable : true,
			bubbles: true,
		}) );
	}).catch( function( error ){
		// remove all booking inent data - invalid state
		booking_form.querySelectorAll('input.em-booking-intent').forEach( intent => intent.remove() );
		booking_form.dispatchEvent( new CustomEvent('em_booking_summary_ajax_error', {
			detail : {
				error : error,
				summary : summary,
			},
			cancellable : true,
			bubbles: true,
		}) );
	}).finally( function(){
		em_booking_summary_ajax_promise = false;
		if( summary ) {
			summary.querySelectorAll('.em-loading').forEach( spinner => spinner.remove() );
		}
		booking_form.dispatchEvent( new CustomEvent('em_booking_summary_ajax_complete', {
			detail : {
				summary : summary,
			},
			cancellable : true,
			bubbles: true,
		}) );
	});
	return em_booking_summary_ajax_promise;
};

var em_booking_form_doing_ajax = false;
var em_booking_form_submit = async function( booking_form, opts = {} ){
	let options = em_booking_form_submit_options( opts );

	// before sending
	if ( em_booking_form_doing_ajax ) {
		alert( EM.bookingInProgress );
		return false;
	}
	em_booking_form_doing_ajax = true;

	if ( options.doStart ) {
		em_booking_form_submit_start( booking_form, options );
	}

	let $response = null;

	// On cached sites the baked-in booking_add nonce may have aged out; the form-init refresh is async, so wait for it (and apply the fresh nonce) before building the payload rather than racing it on a fast submit. Resolves to null and no-ops when the site is not cached.
	let nonces = await em_get_booking_nonces();
	let nonce_action = em_booking_form_nonce_refreshable( booking_form, nonces );
	if ( nonce_action ) {
		booking_form.querySelectorAll('input[name="_wpnonce"]').forEach( function( input ){ input.value = nonces[nonce_action]; } );
	}

	let data = new FormData( booking_form );

	if( 'data' in opts && typeof opts.data === 'object') {
		for ( const [key, value] of Object.entries(opts.data) ) {
			data.set(key, value);
		}
	}

	return fetch( EM.bookingajaxurl, {
		method: "POST",
		body: data,
	}).then( function( response ){
		if( response.ok ) {
			return response.json();
		}
		return Promise.reject( response );
	}).then( function( response ){
		// backwards compatibility response
		if ( !('success' in response) && 'result' in response ){
			response.success = response.result;
		}
		// do success logic if set/requested
		if ( options.doSuccess ) {
			$response = response
			em_booking_form_submit_success( booking_form, response, options );
		}
		return response;
	}).catch( function( error ){
		// only interested in network errors, if response was processed, we may be catching a thrown error
		if ( $response ){
			// response was given
			if( options.showErrorMessages === true ){
				let $error = 'errors' in $response && $response.errors ? $response.errors : $response.message;
				em_booking_form_add_error( booking_form,  $error );
			}
		} else {
			if( options.doCatch ){
				em_booking_form_submit_error( booking_form, error );
			}
		}
	}).finally( function(){
		$response = null;
		if( options.doFinally ) {
			em_booking_form_submit_finally( booking_form, options );
		}
	});
}

var em_booking_form_submit_start = function( booking_form ){
	booking_form.querySelectorAll('.em-booking-message').forEach( message => message.remove() );
	em_booking_form_show_spinner( booking_form );
	let booking_intent = booking_form.querySelector('input.em-booking-intent');
	let button = booking_form.querySelector( 'input.em-form-submit' );
	if( button ) {
		button.setAttribute('data-current-text', button.value);
		if ( booking_intent && 'dataset' in booking_intent ) {
			button.value = EM.bookings.submit_button.text.processing.replace('%s', booking_intent.dataset.amount_formatted);
		} else {
			// fallback
			button.value = EM.bookings.submit_button.text.processing;
		}
	}
}

var em_booking_form_submit_success = function( booking_form, response, opts = {} ){
	let options = em_booking_form_submit_options( opts );
	// hide the spinner
	if ( options.hideSpinner === true ) {
		em_booking_form_hide_spinner( booking_form );
	}
	// backcompat
	if( 'result' in response && !('success' in response) ){
		response.success = response.result;
	}
	// show error or success message
	if ( response.success ) {
		// show message
		if( options.showSuccessMessages === true ){
			em_booking_form_add_confirm( booking_form, response.message );
		}
		// hide form elements
		if ( options.hideForm === true ) {
			em_booking_form_hide_success( booking_form, options );
		}
		// trigger success event
		if( options.triggerEvents === true ){
			if( jQuery ) { // backcompat jQuery events, use regular JS events instaed
				jQuery(document).trigger('em_booking_success', [response, booking_form]);
				if( response.gateway !== null ){
					jQuery(document).trigger('em_booking_gateway_add_'+response.gateway, [response]);
				}
			}
			booking_form.dispatchEvent( new CustomEvent('em_booking_success', {
				detail: {
					response : response,
				},
				cancellable : true,
				bubbles: true,
			}));
		}
		if( (options.redirect === true) && response.redirect ){ //custom redirect hook
			window.location.href = response.redirect;
		}
	}else{
		// output error message
		if( options.showErrorMessages === true ){
			if( response.errors != null ){
				em_booking_form_add_error( booking_form,  response.errors );
			}else{
				em_booking_form_add_error( booking_form,  response.message );
			}
		}
		// trigger error event
		if( options.triggerEvents === true ) {
			if( jQuery ) { // backcompat jQuery events, use regular JS events instaed
				jQuery(document).trigger('em_booking_error', [response, booking_form]);
			}
			booking_form.dispatchEvent( new CustomEvent('em_booking_error', {
				detail: {
					response : response,
				},
				cancellable : true,
				bubbles: true,
			}));
		}
	}
	// reload recaptcha if available (shoud move this out)
	if ( !response.success && typeof Recaptcha != 'undefined' && typeof RecaptchaState != 'undefined') {
		try {
			Recaptcha.reload();
		} catch (error) {
			// do nothing
		}
	}else if ( !response.success && typeof grecaptcha != 'undefined' ) {
		try {
			grecaptcha.reset();
		} catch (error) {
			// do nothing
		}
	}
	// trigger final success event
	if ( options.triggerEvents === true ) {
		if( jQuery ) { // backcompat jQuery events, use regular JS events instaed
			jQuery(document).trigger('em_booking_complete', [response, booking_form]);
		}
		booking_form.dispatchEvent( new CustomEvent('em_booking_complete', {
			detail: {
				response : response,
			},
			cancellable : true,
			bubbles: true,
		}));
	}
}

var em_booking_form_submit_error = function( booking_form, error ){
	if( jQuery ) { // backcompat jQuery events, use regular JS events instaed
		jQuery(document).trigger('em_booking_ajax_error', [null, null, null, booking_form]);
	}
	booking_form.dispatchEvent( new CustomEvent('em_booking_ajax_error', {
		detail: {
			error : error,
		},
		cancellable : true,
		bubbles: true,
	}));
	em_booking_form_add_error( booking_form,  'There was an unexpected network error, please try again or contact a site administrator.' );
	console.log( error );
};

var em_booking_form_submit_finally = function( booking_form, opts = {} ){
	let options = em_booking_form_submit_options( opts );
	em_booking_form_doing_ajax = false;

	let button = booking_form.querySelector( 'input.em-form-submit' );
	if ( button ) {
		if ( button.getAttribute( 'data-current-text' ) ) {
			button.value = button.getAttribute('data-current-text');
			button.removeAttribute('data-current-text');
		} else {
			button.value = EM.bookings.submit_button.text.default;
		}
	}
	if( options.hideSpinner === true ) {
		em_booking_form_hide_spinner( booking_form );
	}
	if( options.showForm === true ) {
		em_booking_form_unhide_success( booking_form, opts );
	}

	if( jQuery ) { // backcompat jQuery events, use regular JS events instaed
		jQuery(document).trigger('em_booking_ajax_complete', [null, null, booking_form]);
	}
	booking_form.dispatchEvent( new CustomEvent('em_booking_complete', {
		cancellable : true,
	}));
};

var em_booking_form_submit_options = function( opts ){
	return Object.assign({
		doStart : true,
		doSuccess : true,
		doCatch : true,
		doFinally : true,
		showErrorMessages : true,
		showSuccessMessages : true,
		hideForm : true,
		hideLogin : true,
		showForm : false,
		hideSpinner : true,
		redirect : true, // can be redirected, not always
		triggerEvents : true
	}, opts);
};