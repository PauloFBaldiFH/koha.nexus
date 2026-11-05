//Tickets & Bookings - legacy stuff needing some rewrites
document.addEventListener('em_event_editor_loaded', function(e){
	const $ = jQuery.noConflict();
	if ( $( "#em-tickets-form" ).length > 0 ) {
		//Enable/Disable Bookings
		document.getElementById('event-rsvp').addEventListener('click', function (event) {
			const nonceInput = this.parentElement.querySelector('input.event_rsvp_delete[data-nonce]');
			const rsvpOptions = document.getElementById('event-rsvp-options');
			if (!this.checked) {
				const confirmation = confirm(EM.disable_bookings_warning);
				if (!confirmation) {
					event.preventDefault();
				} else {
					rsvpOptions.classList.add('hidden');
					nonceInput.disabled = false;
				}
			} else {
				rsvpOptions.classList.remove('hidden');
				nonceInput.disabled = true;
			}
		});
		if ( $( 'input#event-rsvp' ).is( ":checked" ) ) {
			$( "div#rsvp-data" ).fadeIn();
		} else {
			$( "div#rsvp-data" ).hide();
		}
		//Ticket(s) UI
		var reset_ticket_forms = function () {
			$( '#em-tickets-form table tbody tr.em-tickets-row' ).show();
			$( '#em-tickets-form table tbody tr.em-tickets-row-form' ).hide();
		};
		// handle indeterminate checkboxes and the hidden inputs they associate with
		document.querySelectorAll('#em-tickets-form input.possibly-indeterminate[type="checkbox"], #em-tickets-form input[type="checkbox"][indeterminate]').forEach( cb => {
			if ( cb.hasAttribute('indeterminate') && cb.readOnly ) {
				cb.indeterminate = true;
			}
			cb.addEventListener('click', () => {
				if ( cb.hasAttribute('indeterminate') && !cb.classList.contains('determinate') ) {
					if ( cb.readOnly ) {
						cb.checked = true;
						cb.readOnly = false;
					} else if ( cb.checked ) {
						cb.readOnly = true
						cb.indeterminate = true;
					}
					if ( cb.classList.contains('possibly-indeterminate') ) {
						cb.nextElementSibling.value = cb.indeterminate ? 'default' : ( cb.checked ? 1 : 0 );
					}
				} else {
					cb.nextElementSibling.value = cb.checked ? 1 : 0;
				}
			});
		});
		//Add a new ticket
		$( "#em-tickets-add" ).on( 'click', function ( e ) {
			e.preventDefault();
			reset_ticket_forms();
			//create copy of template slot, insert so ready for population
			var tickets = $( '#em-tickets-form table tbody' );
			tickets.first( '.em-ticket-template' ).find( 'input.em-date-input.flatpickr-input' ).each( function () {
				if ( '_flatpickr' in this ) {
					this._flatpickr.destroy();
				}
			} ); //clear all datepickers, should be done first time only, next times it'd be ignored
			var rowNo = tickets.length + 1;
			var slot = tickets.first( '.em-ticket-template' ).clone( true ).attr( 'id', 'em-ticket-' + rowNo ).removeClass( 'em-ticket-template' ).addClass( 'em-ticket' ).appendTo( $( '#em-tickets-form table' ) );
			//change the index of the form element names
			slot.find( '*[name]' ).each( function ( index, el ) {
				el = $( el );
				el.attr( 'name', el.attr( 'name' ).replace( 'em_tickets[0]', 'em_tickets[' + rowNo + ']' ) );
			} );
			// sort out until datepicker ids
			let start_datepicker = slot.find( '.ticket-dates-from-normal' ).first();
			if ( start_datepicker.attr( 'data-until-id' ) ) {
				let until_id = start_datepicker.attr( 'data-until-id' ).replace( '-0', '-' + rowNo );
				start_datepicker.attr( 'data-until-id', until_id );
				slot.find( '.ticket-dates-to-normal' ).attr( 'id', start_datepicker.attr( 'data-until-id' ) );

			}
			//show ticket and switch to editor
			slot.show().find( '.ticket-actions-edit' ).trigger( 'click' );
			//refresh datepicker and values
			slot.find( '.em-time-input' ).off().each( function ( index, el ) {
				if ( typeof this.em_timepickerObj == 'object' ) {
					this.em_timepicker( 'remove' );
				}
			} ); //clear all em_timepickers - consequently, also other click/blur/change events, recreate the further down
			em_setup_ui_elements( slot );
			$( 'html, body' ).animate( { scrollTop: slot.offset().top - 30 } ); //sends user to form
			check_ticket_sortability();
			// set up a UUID for this ticket
			slot.find('.ticket_uuid').val(
				"10000000-1000-4000-8000-100000000000".replace(/[018]/g, c =>
					(+c ^ crypto.getRandomValues(new Uint8Array(1))[0] & 15 >> +c / 4).toString(16)
				)
			)
		} );
		//Edit a Ticket
		$( document ).on( 'click', '.ticket-actions-edit', function ( e ) {
			e.preventDefault();
			reset_ticket_forms();
			var tbody = $( this ).closest( 'tbody' );
			tbody.find( 'tr.em-tickets-row' ).hide();
			tbody.find( 'tr.em-tickets-row-form' ).fadeIn();
			return false;
		} );
		$( document ).on( 'click', '.ticket-actions-edited', function ( e ) {
			e.preventDefault();
			var tbody = $( this ).closest( 'tbody' );
			var rowNo = tbody.attr( 'id' ).replace( 'em-ticket-', '' );
			tbody.find( '.em-tickets-row' ).fadeIn();
			tbody.find( '.em-tickets-row-form' ).hide();
			tbody.find( '*[name]' ).each( function ( index, el ) {
				el = $( el );
				if ( el.attr( 'name' ) == 'ticket_start_pub' ) {
					tbody.find( 'span.ticket_start' ).text( el.val() );
				} else if ( el.attr( 'name' ) == 'ticket_end_pub' ) {
					tbody.find( 'span.ticket_end' ).text( el.val() );
				} else if ( el.attr( 'name' ) == 'em_tickets[' + rowNo + '][ticket_type]' ) {
					if ( el.find( ':selected' ).val() == 'members' ) {
						tbody.find( 'span.ticket_name' ).prepend( '* ' );
					}
				} else if ( el.attr( 'name' ) == 'em_tickets[' + rowNo + '][ticket_start_recurring_days]' ) {
					var text = tbody.find( 'select.ticket-dates-from-recurring-when' ).val() == 'before' ? '-' + el.val() : el.val();
					if ( el.val() != '' ) {
						tbody.find( 'span.ticket_start_recurring_days' ).text( text );
						tbody.find( 'span.ticket_start_recurring_days_text, span.ticket_start_time' ).removeClass( 'hidden' ).show();
					} else {
						tbody.find( 'span.ticket_start_recurring_days' ).text( ' - ' );
						tbody.find( 'span.ticket_start_recurring_days_text, span.ticket_start_time' ).removeClass( 'hidden' ).hide();
					}
				} else if ( el.attr( 'name' ) == 'em_tickets[' + rowNo + '][ticket_end_recurring_days]' ) {
					var text = tbody.find( 'select.ticket-dates-to-recurring-when' ).val() == 'before' ? '-' + el.val() : el.val();
					if ( el.val() != '' ) {
						tbody.find( 'span.ticket_end_recurring_days' ).text( text );
						tbody.find( 'span.ticket_end_recurring_days_text, span.ticket_end_time' ).removeClass( 'hidden' ).show();
					} else {
						tbody.find( 'span.ticket_end_recurring_days' ).text( ' - ' );
						tbody.find( 'span.ticket_end_recurring_days_text, span.ticket_end_time' ).removeClass( 'hidden' ).hide();
					}
				} else {
					var classname = el.attr( 'name' ).replace( 'em_tickets[' + rowNo + '][', '' ).replace( ']', '' ).replace( '[]', '' );
					tbody.find( '.em-tickets-row .' + classname ).text( el.val() );
				}
			} );
			//allow for others to hook into this
			$( document ).triggerHandler( 'em_maps_tickets_edit', [ tbody, rowNo, true ] );
			$( 'html, body' ).animate( { scrollTop: tbody.parent().offset().top - 30 } ); //sends user back to top of form
			return false;
		} );
		$( document ).on( 'change', '.em-ticket-form select.ticket_type', function ( e ) {
			//check if ticket is for all users or members, if members, show roles to limit the ticket to
			var el = $( this );
			let ticketForm = el.closest( '.em-ticket-form' );
			if ( this.value === 'members' || ( this.value === '-1' && this.dataset.default === 'members' ) ) {
				el.closest( '.em-ticket-form' ).find( '.ticket-roles' ).fadeIn();
			} else {
				el.closest( '.em-ticket-form' ).find( '.ticket-roles' ).hide();
			}
			if ( this.value === '-1' && this.dataset.default === 'members' ) {
				// set all checkboxes with indeterminate prop to indeterminate
				ticketForm[0].querySelectorAll( '.ticket-roles input[type="checkbox"][indeterminate]' ).forEach( el => {
					el.indeterminate = true;
					el.classList.remove( 'determinate' )
				} );
				ticketForm[0].querySelectorAll( '.ticket-roles input[type="checkbox"]:not([indeterminate])' ).forEach( el => { el.checked = false; } );
			}else if ( this.value === 'members' ) {
				// remove indeterminate prop from all checkboxes
				ticketForm[0].querySelectorAll( '.ticket-roles input[type="checkbox"][indeterminate]' ).forEach( el => {
					el.indeterminate = false;
					el.readOnly = false;
					el.checked = true;
					el.classList.add( 'determinate' )
				} );
			}
		});
		$('.em-ticket-form select.ticket_type').trigger('change');
		$( document ).on( 'change', '.em-ticket-form .ticket-roles input[type="checkbox"]', function ( e ) {
			let ticketForm = this.closest( '.em-ticket-form' );
			let select = ticketForm.querySelector( '.em-ticket-form select.ticket_type' )
			if ( select.dataset.default === 'members' && select.value === '-1' ) {
				select.value = 'members';
				ticketForm.querySelectorAll( '.ticket-roles input[type="checkbox"][indeterminate]' ).forEach( el => {
					el.indeterminate = false;
					el.readOnly = false;
					el.checked = true;
					el.classList.add( 'determinate' )
				} );
			}
		});
		$( document ).on( 'click', '.em-ticket-form .ticket-options-advanced', function ( e ) {
			//show or hide advanced tickets, hidden by default
			e.preventDefault();
			var el = $( this );
			if ( el.hasClass( 'show' ) ) {
				el.closest( '.em-ticket-form' ).find( '.em-ticket-form-advanced' ).fadeIn();
				el.find( '.show,.show-advanced' ).hide();
				el.find( '.hide,.hide-advanced' ).show();
			} else {
				el.closest( '.em-ticket-form' ).find( '.em-ticket-form-advanced' ).hide();
				el.find( '.show,.show-advanced' ).show();
				el.find( '.hide,.hide-advanced' ).hide();
			}
			el.toggleClass( 'show' );
		} );
		$( '.em-ticket-form' ).each( function () {
			//check whether to show advanced options or not by default for each ticket
			var show_advanced = false;
			var el = $( this );
			el.find( '.em-ticket-form-advanced input[type="text"]' ).each( function () {
				if ( this.value != '' ) show_advanced = true;
			} );
			if ( el.find( '.em-ticket-form-advanced input[type="checkbox"]:checked' ).length > 0 ) {
				show_advanced = true;
			}
			el.find( '.em-ticket-form-advanced option:selected' ).each( function () {
				if ( this.value != '' ) show_advanced = true;
			} );
			if ( show_advanced ) el.find( '.ticket-options-advanced' ).trigger( 'click' );
		} );
		//Delete a ticket
		$( document ).on( 'click', '.ticket-actions-delete', function ( e ) {
			e.preventDefault();
			var el = $( this );
			var tbody = el.closest( 'tbody' );
			if ( tbody.find( 'input.ticket_id' ).val() > 0 ) {
				//only will happen if no bookings made, we set the ticket as deleted and enable the delete nonce
				let warning = this.classList.contains( 'parent-ticket' ) ? EM.eventEditor.deleteTicketParentWarning : EM.eventEditor.deleteTicketWarning;
				if ( confirm( warning ) ) {
					tbody.find( 'input.delete[data-nonce]' ).prop('disabled', false);
					tbody.closest( '.em-ticket' ).addClass( 'ticket-deleted' );
				}
			} else {
				//not saved to db yet, so just remove
				tbody.remove();
			}
			check_ticket_sortability();
			return false;
		} );
		//Sort Tickets
		$( '#em-tickets-form.em-tickets-sortable table' ).sortable( {
			items: '> tbody',
			placeholder: "em-ticket-sortable-placeholder",
			handle: '.ticket-status',
			helper: function ( event, el ) {
				var helper = $( el ).clone().addClass( 'em-ticket-sortable-helper' );
				var tds = helper.find( '.em-tickets-row td' ).length;
				helper.children().remove();
				helper.append( '<tr class="em-tickets-row"><td colspan="' + tds + '" style="text-align:left; padding-left:15px;"><span class="dashicons dashicons-tickets-alt"></span></td></tr>' );
				return helper;
			},
		} );
		var check_ticket_sortability = function () {
			var em_tickets = $( '#em-tickets-form table tbody.em-ticket' );
			if ( em_tickets.length == 1 ) {
				em_tickets.find( '.ticket-status' ).addClass( 'single' );
				$( '#em-tickets-form.em-tickets-sortable table' ).sortable( "option", "disabled", true );
			} else {
				em_tickets.find( '.ticket-status' ).removeClass( 'single' );
				$( '#em-tickets-form.em-tickets-sortable table' ).sortable( "option", "disabled", false );
			}
		};
		check_ticket_sortability();
	}
});