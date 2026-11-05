//Events Search
jQuery(document).ready( function($){
	// handle the views tip/ddm
	let views_ddm_options = {
		theme : 'light-border',
		allowHTML : true,
		interactive : true,
		trigger : 'manual',
		placement : 'bottom',
		zIndex : 1000000,
		touch: true,
	};
	$(document).trigger('em-search-views-trigger-vars',[views_ddm_options]);
	let tooltip_vars = { theme : 'light-border', appendTo : 'parent', touch : false, };
	$(document).trigger('em-tippy-vars',[tooltip_vars]);

	// sync main search texts to advanced search
	let search_forms = $('.em-search:not(.em-search-advanced)');
	search_forms.each( function(){
		/*
		 * Important references we'll reuse in scope
		 */
		let search = $(this);
		let search_id = search.attr('id').replace('em-search-', '');
		let search_form = search.find('.em-search-form').first();
		let search_advanced = search.find('.em-search-advanced'); // there should only be one anyway

		/*
		 * Counter functions
		 */
		const update_input_count = function( input, qty = 1 ){
			let el = jQuery(input);
			let total = qty > 0 ? qty : null;
			el.attr('data-advanced-total-input', total);
			update_search_totals();
		};

		const update_search_totals = function( applied = false ){
			// set everything to 0, recount
			search.find('span.total-count').remove();
			// find all fields with total attributes and sum them up
			let total = 0;
			search_advanced.find('[data-advanced-total-input]').each( function(){
				let total_input = this.getAttribute('data-advanced-total-input');
				total += Math.abs( total_input );
			});
			search.attr('data-advanced-total', total);
			update_trigger_count( applied );
			// find all sections with totals and display them (added above)
			search_advanced.find('.em-search-advanced-section').each( function(){
				let section = $(this);
				let section_total = 0;
				section.attr('data-advanced-total', 0);
				// go through all set qtys and calculate
				section.find('[data-advanced-total-input]').each( function(){
					let total_input = this.getAttribute('data-advanced-total-input');
					section_total += Math.abs( total_input );
				});
				section.attr('data-advanced-total', section_total);
				update_section_count(section);
			});
			// update triggers, search, clear button etc.
			if( total > 0 || !search.attr('data-advanced-previous-total') || total != search.attr('data-advanced-previous-total') ){
				update_submit_buttons( true );
			}
			update_clear_button_count();
		}

		const update_trigger_count = function( applied = false ){
			let triggers = jQuery('.em-search-advanced-trigger[data-search-advanced-id="em-search-advanced-'+ search_id +'"]'); // search like this ato apply to external triggers
			triggers.find('span.total-count').remove();
			let total = search.attr('data-advanced-total');
			if( total > 0 ){
				let trigger_count = jQuery('<span class="total-count">'+ total + '</span>').appendTo(triggers);
				if( !applied ){
					trigger_count.addClass('tentative');
				}
			}
		};

		const update_submit_buttons = function( enabled = false ){
			// update the clear link
			let submit_button = search_advanced.find('button[type="submit"]');
			let main_submit_button = search.find('.em-search-main-bar button[type="submit"]');
			let submit_buttons = submit_button.add( main_submit_button ); // merge together to apply chanegs
			if( enabled ){
				submit_buttons.removeClass('disabled').attr('aria-disabled', 'false');
			}else{
				submit_buttons.addClass('disabled').attr('aria-disabled', 'true');
			}
		};

		const update_section_count = function( section ){
			let section_total = section.attr('data-advanced-total');
			section.find('header span.total-count').remove();
			if( section_total > 0 ){
				$('<span class="total-count">'+ section_total +'</span>').appendTo( section.find('header') );
			}
		};

		const update_clear_button_count = function(){
			// update the clear link
			let clear_link = search_advanced.find('button[type="reset"]');
			if( !clear_link.attr('data-placeholder') ){
				clear_link.attr('data-placeholder', clear_link.text());
			}
			let total = search.attr('data-advanced-total');
			if( total > 0 ){
				clear_link.text( clear_link.attr('data-placeholder') + ' (' + total + ')' ).prop('disabled', false);
				clear_link.removeClass('disabled').attr('aria-disabled', 'false');
			}else{
				clear_link.text( clear_link.attr('data-placeholder') );
				clear_link.addClass('disabled').attr('aria-disabled', 'true');
			}
		};

		/*
		 * Triggers
		 */
		search.find('.em-search-views-trigger').each( function(){
			tooltip_vars.content = this.parentElement.getAttribute('aria-label');
			let views_tooltip = tippy(this.parentElement, tooltip_vars);
			let views_content = this.parentElement.querySelector('.em-search-views-options');
			let views_content_parent = views_content.parentElement;
			let tippy_content = document.createElement('div');
			views_ddm_options.content = tippy_content;
			let views_ddm = tippy(this, views_ddm_options);
			views_ddm.setProps({
				onShow(instance){
					views_tooltip.disable();
					tippy_content.append(views_content);
				},
				onShown(instance){ // keyboard support
					views_content.querySelector('input:checked').focus();
				},
				onHidden(instance){
					views_tooltip.enable();
					if( views_content.parentElement !== views_content_parent ) {
						views_content_parent.append(views_content);
					}
				}
			});
			let tippy_listener = function(e){
				if( e.type === 'keydown' && !(e.which === 13 || e.which === 40) ) return false;
				e.preventDefault();
				e.stopPropagation();
				this._tippy.show();
				views_tooltip.hide();
			}
			this.addEventListener('click', tippy_listener);
			this.addEventListener('keydown', tippy_listener);
			this.firstElementChild.addEventListener('focus', function(e){
				views_ddm.hide();
				views_tooltip.enable();
				views_tooltip.show();
			});
			this.firstElementChild.addEventListener('blur', function(){
				views_tooltip.hide();
			});

			search.on('focus blur', '.em-search-views-options input', function(){
				if( document.activeElement === this ){
					this.parentElement.classList.add('focused');
				}else{
					this.parentElement.classList.remove('focused');
				}
			});

			search[0].addEventListener('change', function(){
				update_submit_buttons(true);
			});

			search.on('keydown click', '.em-search-views-options input', function( e ){
				// get relevant vars
				if( e.type === 'keydown' && e.which !== 13 ){
					if ( [37, 38, 39, 40].indexOf(e.which) !== -1 ) {
						if (e.which === 38) {
							if (this.parentElement.previousElementSibling) {
								this.parentElement.previousElementSibling.focus();
							}
						} else if (e.which === 40) {
							if (this.parentElement.nextElementSibling) {
								this.parentElement.nextElementSibling.focus();
							}
						}
						return false;
					} else if ( e.which === 9 ) {
						// focus out
						views_ddm.hide();
					}
					return true;
				}
				this.checked = true;
				let input = $(this);
				// mark label selected
				input.closest('fieldset').find('label').removeClass('checked');
				input.parent().addClass('checked');
				// get other reference elements we need
				let views_wrapper = $(this).closest('.em-search-views');
				let view_type = this.value;
				let trigger = views_wrapper.children('.em-search-views-trigger');
				let trigger_option = trigger.children('.em-search-view-option');
				// change view, if different
				if( view_type !== trigger_option.attr('data-view') ){
					trigger_option.attr('data-view', this.value).text(this.parentElement.innerText);
					// remove custom search vals from current view so it's not used into another view
					$('#em-view-'+search_id).find('#em-view-custom-data-search-'+search_id).remove();
					// trigger custom event in case form disabled due to no search vals
					search_form.find('button[type="submit"]').focus();
					search_form.trigger('forcesubmit');
				}
				views_ddm.hide();
			});
		});

		search.find('.em-search-sort-trigger').each( function(){
			tooltip_vars.content = this.parentElement.getAttribute('aria-label');
			let views_tooltip = tippy(this.parentElement, tooltip_vars);
			search.on('keydown click', '.em-search-sort-option', function( e ){
				// get other reference elements we need
				let order = this.dataset.sort === 'ASC' ? 'DESC' : 'ASC';
				this.setAttribute('data-sort', order);
				this.parentElement.querySelector('input[name="order"]').value = order;
				// trigger custom event in case form disabled due to no search vals
				search_form.find('button[type="submit"]').focus();
				search_form.trigger('forcesubmit');
			});
		});

		// add trigger logic for advanced popup modal
		let search_advanced_trigger_click = function( e ){
			if( search.hasClass('advanced-mode-inline') ){
				// inline
				if( !search_advanced.hasClass('visible') ){
					search_advanced.slideDown().addClass('visible');
					if( '_tippy' in this ){
						this._tippy.setContent(this.getAttribute('data-label-hide'));
					}
				}else{
					search_advanced.slideUp().removeClass('visible');
					if( '_tippy' in this ){
						this._tippy.setContent(this.getAttribute('data-label-show'));
					}
				}
			}else{
				// wrap modal popup element in a form, so taht it's 'accessible' with keyboard
				if( !search_advanced.hasClass('active') ) {
					let form_wrapper = $('<form action="" method="post" class="em-search-advanced-form" id="em-search-form-advanced-' + search_id + '"></form>');
					form_wrapper.appendTo(search_advanced);
					search_advanced.find('.em-modal-popup').appendTo(form_wrapper);
					// open modal
					let button = this;
					openModal(search_advanced, function () {
						// Do this instead
						button.blur();
						search_advanced.find('input.em-search-text').focus();
					});
				}
			}
		};
		search.on('click', 'button.em-search-advanced-trigger:not([data-search-advanced-id],[data-parent-trigger])', search_advanced_trigger_click);
		search_form.on('search_advanced_trigger', search_advanced_trigger_click);

		search_advanced.on('em_modal_close', function(){
			search_advanced.find('.em-modal-popup').appendTo(search_advanced);
			search_advanced.children('form').remove();
			let trigger = search.find('button.em-search-advanced-trigger').focus();
			if( trigger.length > 0 && '_tippy' in trigger[0] ){
				trigger[0]._tippy.hide();
			}
		});

		// add header toggle logic to expand/collapse sections - add directly to elements since they move around the DOM due to modal
		search_advanced.find('.em-search-advanced-section > header').on('click', function(){
			let header = $(this);
			let section = header.closest('section');
			let content = header.siblings('.em-search-section-content');
			if( section.hasClass('active') ){
				content.slideUp();
				section.removeClass('active');
			}else{
				content.slideDown();
				section.addClass('active');
			}
		});

		/*
		 *  Advanced Search Field Listeners - Main Search Form
		 */

		let search_form_advanced_calculate_totals_inputs = function( input ){
			// for textboxes we only need to add or remove 1 advanced
			let el = $(input);
			let qty = el.val() !== '' ? 1:0;
			update_input_count( el, qty );
		};

		// These are for the main search bar, syncing information back into the advanced form
		search.on('change input', '.em-search-main-bar input.em-search-text', function( e ){
			// sync advanced input field with same text
			let advanced_search_input = search_advanced.find('input.em-search-text');
			if ( advanced_search_input.length === 0 ) {
				search_form_advanced_calculate_totals_inputs(this);
			} else {
				advanced_search_input.val( this.value );
				// recalculate totals from here
				search_form_advanced_calculate_totals_inputs(advanced_search_input[0]);
			}
			// any change without advanced form should show the search form still
			update_submit_buttons( true);
		});
		search.on('change', '.em-search-main-bar input.em-search-geo-coords', function(){
			let el = $(this);
			let advanced_geo = search_advanced.find('div.em-search-geo');
			// copy over value and class names
			let advanced_geo_coords = advanced_geo.find('input.em-search-geo-coords');
			if( advanced_geo_coords.length > 0 ) {
				advanced_geo_coords.val(el.val()).attr('class', el.attr('class'));
				let geo_text = el.siblings('input.em-search-geo').first();
				advanced_geo.find('input.em-search-geo').val(geo_text.val()).attr('class', geo_text.attr('class'));
				// calculate totals from here
				search_form_advanced_calculate_totals_inputs(advanced_geo_coords);
			} else {
				// calculate totals from here
				search_form_advanced_calculate_totals_inputs(this);
			}
		});
		search.find('.em-search-main-bar .em-datepicker input.em-search-scope.flatpickr-input').each( function(){
			if( !('_flatpickr' in this) ) return;
			this._flatpickr.config.onClose.push( function( selectedDates, dateStr, instance ) {
				// any change without advanced form should show the search form
				let advanced_datepicker = search_advanced.find('.em-datepicker input.em-search-scope.flatpickr-input');
				if( advanced_datepicker.length === 0 ) {
					// update counter
					let qty = dateStr ? 1:0;
					update_input_count(instance.input, qty);
				} else {
					// update advanced search form datepicker values, trigger a close for it to handle the rest
					advanced_datepicker[0]._flatpickr.setDate( selectedDates, true );
					advanced_datepicker[0]._flatpickr.close();
				}
			});
		});

		search.find('select.em-selectize').each(function () {
			if( 'selectize' in this ) {
				this.selectize.on('change', function () {
					search_advanced_selectize_change(this);
				});
			}
		});

		/*
		 *  Advanced Search Field Listeners - Advanced Search Form
		 */

		// regular text advanced or hidden inputs that represent another ui
		search_advanced.on('change input', 'input.em-search-text', function( e ){
			if( e.type === 'change' ){
				// copy over place info on change only, not on each keystroke
				search.find('.em-search-main input.em-search-text').val( this.value );
			}
			search_form_advanced_calculate_totals_inputs(this);
		});
		search_advanced.on('change', 'input.em-search-geo-coords', function( e ){
			search_form_advanced_calculate_totals_inputs(this);
			//update values in main search
			let el = $(this);
			let main = search.find('.em-search-main div.em-search-geo');
			if( main.length > 0 ){
				// copy over value and class names
				main.find('input.em-search-geo-coords').val( el.val() ).attr('class', el.attr('class'));
				let geo_text = el.siblings('input.em-search-geo');
				main.find('input.em-search-geo').val(geo_text.val()).attr('class', geo_text.attr('class'));
			}
		});
		search_advanced.on('clear_search', function(){
			let text = $(this).find('input.em-search-text');
			if( text.length === 0 ) {
				// select geo from main if it exists, so we keep counts synced
				text = search.find('input.em-search-text');
			}
			text.val('').attr('value', null).trigger('change'); // value attr removed as well due to compat issues in Chrome (possibly more)
		});
		/* Not sure we should be calculating this... since it's always set to something.
		search_advanced.on('change', 'select.em-search-geo-unit, select.em-search-geo-distance', function( e ){
			// combine both values into parent, if value set then it's a toggle
			let el = jQuery(this);
			let qty = el.val() ? 1 : null;
			el.closest('.em-search-geo-units').attr('data-advanced-total-input', qty);
			update_search_totals();
		});
		 */
		search_advanced.on('change', 'input[type="checkbox"]', function( e ){
			let el = $(this);
			let qty = el.prop('checked') ? 1:0;
			update_input_count( el, qty );
		});
		search_advanced.on('calculate_totals', function(){
			search_advanced.find('input.em-search-text, input.em-search-geo-coords').each( function(){
				search_form_advanced_calculate_totals_inputs(this);
			});
			search_advanced.find('input[type="checkbox"]').trigger('change');
		});
		search_advanced.on('clear_search', function(){
			let geo = $(this).find('input.em-search-geo');
			if( geo.length === 0 ) {
				// select geo from main if it exists, so we keep counts synced
				geo = search.find('input.em-search-geo');
			}
			geo.removeClass('off').removeClass('on').val('');
			geo.siblings('input.em-search-geo-coords').val('').trigger('change');
			search_advanced.find('input[type="checkbox"]').prop("checked", false).trigger('change').prop("checked", false); // set checked after trigger because something seems to be checking during event
		});

		// datepicker advanced logic
		search_advanced.find('.em-datepicker input.em-search-scope.flatpickr-input').each( function(){
			if( !('_flatpickr' in this) ) return;
			this._flatpickr.config.onClose.push( function( selectedDates, dateStr, instance ) {
				// check previous value against current value, no change, no go
				let previous_value = instance.input.getAttribute('data-previous-value');
				if( previous_value !== dateStr ){
					// update counter
					let qty = dateStr ? 1:0;
					update_input_count(instance.input, qty);
					// update main search form datepicker values
					let main_datepicker = search.find('.em-search-main-bar .em-datepicker input.em-search-scope.flatpickr-input');
					if( main_datepicker.length > 0 ) {
						main_datepicker[0]._flatpickr.setDate(selectedDates, true);
					}
					// set for next time
					instance.input.setAttribute('data-previous-value', dateStr);
				}
			});
		});
		search_advanced.on('calculate_totals', function(){
			search_advanced.find('.em-datepicker input.em-search-scope.flatpickr-input').first().each( function(){
				let qty = this._flatpickr.selectedDates.length > 0 ? 1 : 0;
				update_input_count(this, qty);
			});
		});
		search_advanced.on('clear_search', function(){
			let datepickers = search_advanced.find('.em-datepicker input.em-search-scope.flatpickr-input');
			if( datepickers.length === 0 ) {
				// find datepickers on main form so syncing is sent up
				datepickers = search.find('.em-datepicker input.em-search-scope.flatpickr-input');
			}
			datepickers.each(function () {
				this._flatpickr.clear();
				update_input_count(this, 0);
			});
		});
		// clear the date total for calendars, before anything is done
		let scope_calendar_check = function(){
			search.find('.em-datepicker input.em-search-scope.flatpickr-input').each( function(){
				if( search.attr('data-view') == 'calendar' ){
					this.setAttribute('data-advanced-total-input', 0);
					this._flatpickr.input.disabled = true;
				}else{
					this._flatpickr.input.disabled = false;
					let qty = this._flatpickr.selectedDates.length > 0 ? 1 : 0;
					this.setAttribute('data-advanced-total-input', qty);
				}
			});
		};
		$(document).on('em_search_loaded', scope_calendar_check);
		scope_calendar_check();

		// selectize advanced
		let search_advanced_selectize_change = function( selectize ){
			let qty = selectize.items.length;
			// handle 'all' default values
			if( qty == 1 && !selectize.items[0] ){
				qty = 0;
			}
			if ( selectize.$input.closest('.em-search-advanced').length === 0 ) {
				// sync advanced input field with same text
				let classSearch = '.' + selectize.$input.attr('class').replaceAll(' ', '.').trim();
				let advanced_search_input = search_advanced.find( classSearch );
				if ( advanced_search_input.length > 0 ) {
					// copy over values
					advanced_search_input[0].selectize.setValue( selectize.items );
					// recalculate totals from here
					search_advanced_selectize_change(advanced_search_input[0].selectize);
				}
			}
			update_input_count( selectize.$input, qty );
		};

		search_advanced.find('select.em-selectize').each(function () {
			if( 'selectize' in this ) {
				this.selectize.on('change', function () {
					search_advanced_selectize_change(this);
				});
			}
		});
		search_advanced.on('calculate_totals', function(){
			$(this).find('select.em-selectize').each( function(){
				search_advanced_selectize_change(this.selectize);
			});
		});
		search_advanced.on('clear_search', function(){
			let clearSearch = function(){
				this.selectize.clear();
				this.selectize.refreshItems();
				this.selectize.refreshOptions(false);
				this.selectize.blur();
			};
			search_advanced.find('select.em-selectize').each( clearSearch );
			search.find('.em-search-main-bar select.em-selectize').each( clearSearch );
		});

		// location-specific stuff for dropdowns (powered by selectize)
		let locations_selectize_load_complete = function(){
			if( 'selectize' in this ) {
				this.selectize.settings.placeholder = this.selectize.settings.original_placeholder;
				this.selectize.updatePlaceholder();
				// get options from select again
				let options = [];
				this.selectize.$input.find('option').each( function(){
					let value = this.value !== null ? this.value : this.innerHTML;
					options.push({ value : value, text: this.innerHTML});
				});
				this.selectize.addOption(options);
				this.selectize.refreshOptions(false);
			}
		};
		let locations_selectize_load_start = function(){
			if( 'selectize' in this ){
				this.selectize.clearOptions();
				if( !('original_placeholder' in this.selectize.settings) ) this.selectize.settings.original_placeholder = this.selectize.settings.placeholder;
				this.selectize.settings.placeholder = EM.txt_loading;
				this.selectize.updatePlaceholder();
			}
		};
		$('.em-search-advanced select[name=country], .em-search select[name=country]').on('change', function(){
			var el = $(this);
			let wrapper = el.closest('.em-search-location');
			wrapper.find('select[name=state]').html('<option value="">'+EM.txt_loading+'</option>');
			wrapper.find('select[name=region]').html('<option value="">'+EM.txt_loading+'</option>');
			wrapper.find('select[name=town]').html('<option value="">'+EM.txt_loading+'</option>');
			wrapper.find('select[name=state], select[name=region], select[name=town]').each( locations_selectize_load_start );
			if( el.val() != '' ){
				wrapper.find('.em-search-location-meta').slideDown();
				var data = {
					action : 'search_states',
					country : el.val(),
					return_html : true,
				};
				wrapper.find('select[name=state]').load( EM.ajaxurl, data, locations_selectize_load_complete );
				data.action = 'search_regions';
				wrapper.find('select[name=region]').load( EM.ajaxurl, data, locations_selectize_load_complete );
				data.action = 'search_towns';
				wrapper.find('select[name=town]').load( EM.ajaxurl, data, locations_selectize_load_complete );
			}else{
				wrapper.find('.em-search-location-meta').slideUp();
			}
		});
		$('.em-search-advanced select[name=region], .em-search select[name=region]').on('change', function(){
			var el = $(this);
			let wrapper = el.closest('.em-search-location');
			wrapper.find('select[name=state]').html('<option value="">'+EM.txt_loading+'</option>');
			wrapper.find('select[name=town]').html('<option value="">'+EM.txt_loading+'</option>');
			wrapper.find('select[name=state], select[name=town]').each( locations_selectize_load_start );
			var data = {
				action : 'search_states',
				region : el.val(),
				country : wrapper.find('select[name=country]').val(),
				return_html : true
			};
			wrapper.find('select[name=state]').load( EM.ajaxurl, data, locations_selectize_load_complete );
			data.action = 'search_towns';
			wrapper.find('select[name=town]').load( EM.ajaxurl, data, locations_selectize_load_complete );
		});
		$('.em-search-advanced select[name=state], .em-search select[name=state]').on('change', function(){
			var el = $(this);
			let wrapper = el.closest('.em-search-location');
			wrapper.find('select[name=town]').html('<option value="">'+EM.txt_loading+'</option>').each( locations_selectize_load_start );
			var data = {
				action : 'search_towns',
				state : el.val(),
				region : wrapper.find('select[name=region]').val(),
				country : wrapper.find('select[name=country]').val(),
				return_html : true
			};
			wrapper.find('select[name=town]').load( EM.ajaxurl, data, locations_selectize_load_complete );
		});

		/*
		 *  Clear & Search Actions
		 */
		// handle clear link for advanced
		search_advanced.on( 'click', 'button[type="reset"]', function(){
			// clear text search advanced, run clear hook for other parts to hook into
			if( search.attr('data-advanced-total') == 0 ) return;
			// search text and geo search
			search_advanced.find('input.em-search-text, input.em-search-geo').val('').attr('data-advanced-total-input', null).trigger('change');
			// other implementations hook here and do what you need
			search.trigger('clear_search');
			search_advanced.trigger('clear_search');
			// remove counters, set data counters to 0, hide section and submit form without search settings
			update_search_totals(true); // in theory, this is 0 and removes everything
			if( search_advanced.hasClass('em-modal') ) {
				search_advanced_trigger_click();
			}
			search_advanced.append('<input name="clear_search" type="hidden" value="1">');
			search_advanced.find('button[type="submit"]').trigger('forceclick');
			update_clear_button_count();
		}).each( function(){
			search_advanced.trigger('calculate_totals');
			update_search_totals(true);
		});
		const on_update_trigger_count = function(e, applied = true){
			update_trigger_count( applied );
		};
		search.on('update_trigger_count', on_update_trigger_count);
		search_advanced.on('update_trigger_count', on_update_trigger_count);

		// handle submission for advanced
		search_advanced.on( 'click forceclick', 'button[type="submit"]', function(e){
			e.preventDefault();
			if( this.classList.contains('disabled') && e.type !== 'forceclick' ) return false;
			// close attach back to search form
			if( search_advanced.hasClass('em-modal') ) {
				closeModal(search_advanced, function () {
					// submit for search
					search_form.submit();
				});
			}else{
				search_form.submit();
			}
			return false; // we handled it
		});

		search.on('submit forcesubmit', '.em-search-form', function(e){
			if ( search.hasClass('no-ajax') ) {
				return true;
			}
			e.preventDefault();
			let form = $(this);
			let submit_buttons = form.find('button[type="submit"]');
			if( e.type !== 'forcesubmit' && submit_buttons.hasClass('disabled') ) return false;
			let wrapper = form.closest('.em-search');
			if( wrapper.hasClass('em-search-legacy') ){
				em_submit_legacy_search_form(form);
			}else{
				let view = $('#em-view-'+search_id);
				let view_type = form.find('[name="view"]:checked, [name="view"][type="hidden"], .em-search-view-option-hidden').val();
				if( Array.isArray(view_type) ) view_type = view_type.shift();
				// copy over custom view information, remove it further down
				let custom_view_data = view.find('#em-view-custom-data-search-'+search_id).clone();
				let custom_view_data_container = $('<div class="em-view-custom-data"></div>');
				custom_view_data.children().appendTo(custom_view_data_container);
				custom_view_data.remove();
				custom_view_data_container.appendTo(form);
				// add loading stuff
				view.append('<div class="em-loading"></div>');
				submit_buttons.each( function(){
					if( EM.txt_searching !== this.innerHTML ) {
						this.setAttribute('data-button-text', this.innerHTML);
						this.innerHTML = EM.txt_searching;
					}
				});
				var vars = form.serialize();
				$.ajax( EM.ajaxurl, {
					type : 'POST',
					dataType : 'html',
					data : vars,
					success : function(responseText){
						submit_buttons.each( function(){
							this.innerHTML = this.getAttribute('data-button-text');
						});
						view = EM_View_Updater( view, responseText );
						// update view definitions
						view.attr('data-view', view_type);
						search.attr('data-view', view_type);
						search_advanced.attr('data-view', view_type);
						jQuery(document).triggerHandler('em_view_loaded_'+view_type, [view, form, e]);
						jQuery(document).triggerHandler('em_search_loaded', [view, form, e]); // ajax has loaded new results
						jQuery(document).triggerHandler('em_search_result', [vars, view, e]); // legacy for backcompat, use the above
						wrapper.find('.count.tentative').removeClass('tentative');
						// deactivate submit button until changes are made again
						submit_buttons.addClass('disabled').attr('aria-disabled', 'true');
						// update search totals
						update_search_totals(true);
						search.attr('data-advanced-previous-total', search.attr('data-advanced-total')); // so we know if filters were used in previous search
						update_submit_buttons(false);
						custom_view_data_container.remove(); // remove data so it's reloaded again later
						search.find('input[name="clear_search"]').remove();
					}
				});
			}
			return false;
		});

		// observe resizing
		EM_ResizeObserver( EM.search.breakpoints, [search[0]]);
	});

	// handle external triggers, e.g. a calendar shortcut for a hidden search form
	$(document).on('click', '.em-search-advanced-trigger[data-search-advanced-id], .em-search-advanced-trigger[data-parent-trigger]', function(){
		if( this.getAttribute('data-search-advanced-id') ){
			// trigger the search form by parent
			let search_advanced_form = document.getElementById( this.getAttribute('data-search-advanced-id') );
			if( search_advanced_form ){
				let search_form = search_advanced_form.closest('form.em-search-form');
				if( search_form ){
					search_form.dispatchEvent( new CustomEvent('search_advanced_trigger') );
					return;
				}
			}
		} else if( this.getAttribute('data-parent-trigger') ) {
			let trigger = document.getElementById(this.getAttribute('data-parent-trigger'));
			if ( trigger ) {
				trigger.click();
				return;
			}
		}
		console.log('Cannot locate a valid advanced search form trigger for %o', this);
	});

	$(document).on('click', '.em-view-container .em-ajax.em-pagination a.page-numbers', function(e){
		let a = $(this);
		let view = a.closest('.em-view-container');
		let href = a.attr('href');
		//add data-em-ajax att if it exists
		let data = a.closest('.em-pagination').attr('data-em-ajax');
		if( data ){
			href += href.includes('?') ? '&' : '?';
			href += data;
		}
		// build querystring from url
		let url_params = new URL(href, window.location.origin).searchParams;
		if( view.attr('data-view') ) {
			url_params.set('view', view.attr('data-view'));
		}
		// start ajax
		view.append('<div class="loading" id="em-loading"></div>');
		$.ajax( EM.ajaxurl, {
			type : 'POST',
			dataType : 'html',
			data : url_params.toString(),
			success : function(responseText) {
				view = EM_View_Updater( view, responseText );
				view.find('.em-pagination').each( function(){
					paginationObserver.observe(this);
				});
				jQuery(document).triggerHandler('em_page_loaded', [view]);
				view[0].scrollIntoView({ behavior: "smooth" });
			}
		});
		e.preventDefault();
		return false;
	});

	const paginationObserver = new ResizeObserver( function( entries ){
		for (let entry of entries) {
			let el = entry.target;
			if( !el.classList.contains('observing') ) {
				el.classList.add('observing'); // prevent endless loop on resizing within this check
				// check if any pagination parts are overflowing
				let overflowing = false;
				el.classList.remove('overflowing');
				for ( const item of el.querySelectorAll('.not-current')) {
					if( item.scrollHeight > item.clientHeight || item.scrollWidth > item.clientWidth ){
						overflowing = true;
						break; // break if one has overflown
					}
				};
				// add or remove overflow classes
				if( overflowing ){
					el.classList.add('overflowing')
				}
				el.classList.remove('observing');
			}
		}
	});
	$('.em-pagination').each( function(){
		paginationObserver.observe(this);
	});

	/* START Legacy */
	// deprecated - hide/show the advanced search advanced link - relevant for old template overrides
	$(document).on('click change', '.em-search-legacy .em-toggle', function(e){
		e.preventDefault();
		//show or hide advanced search, hidden by default
		var el = $(this);
		var rel = el.attr('rel').split(':');
		if( el.hasClass('show-search') ){
			if( rel.length > 1 ){ el.closest(rel[1]).find(rel[0]).slideUp(); }
			else{ $(rel[0]).slideUp(); }
			el.find('.show, .show-advanced').show();
			el.find('.hide, .hide-advanced').hide();
			el.removeClass('show-search');
		}else{
			if( rel.length > 1 ){ el.closest(rel[1]).find(rel[0]).slideDown(); }
			else{ $(rel[0]).slideDown(); }
			el.find('.show, .show-advanced').hide();
			el.find('.hide, .hide-advanced').show();
			el.addClass('show-search');
		}
	});
	// handle search form submission
	let em_submit_legacy_search_form = function( form ){
		if( this.em_search && this.em_search.value == EM.txt_search){ this.em_search.value = ''; }
		var results_wrapper = form.closest('.em-search-wrapper').find('.em-search-ajax');
		if( results_wrapper.length == 0 ) results_wrapper = $('.em-search-ajax');
		if( results_wrapper.length > 0 ){
			results_wrapper.append('<div class="loading" id="em-loading"></div>');
			var submitButton = form.find('.em-search-submit button');
			submitButton.attr('data-button-text', submitButton.val()).val(EM.txt_searching);
			var img = submitButton.children('img');
			if( img.length > 0 ) img.attr('src', img.attr('src').replace('search-mag.png', 'search-loading.gif'));
			var vars = form.serialize();
			$.ajax( EM.ajaxurl, {
				type : 'POST',
				dataType : 'html',
				data : vars,
				success : function(responseText){
					submitButton.val(submitButton.attr('data-button-text'));
					if( img.length > 0 ) img.attr('src', img.attr('src').replace('search-loading.gif', 'search-mag.png'));
					results_wrapper.replaceWith(responseText);
					if( form.find('input[name=em_search]').val() == '' ){ form.find('input[name=em_search]').val(EM.txt_search); }
					//reload results_wrapper
					results_wrapper = form.closest('.em-search-wrapper').find('.em-search-ajax');
					if( results_wrapper.length == 0 ) results_wrapper = $('.em-search-ajax');
					jQuery(document).triggerHandler('em_search_ajax', [vars, results_wrapper, e]); //ajax has loaded new results
				}
			});
			e.preventDefault();
			return false;
		}
	};
	if( $('.em-search-ajax').length > 0 ){
		$(document).on('click', '.em-search-ajax a.page-numbers', function(e){
			var a = $(this);
			var data = a.closest('.em-pagination').attr('data-em-ajax');
			var wrapper = a.closest('.em-search-ajax');
			var wrapper_parent = wrapper.parent();
			var qvars = a.attr('href').split('?');
			var vars = qvars[1];
			//add data-em-ajax att if it exists
			if( data != '' ){
				vars = vars != '' ? vars+'&'+data : data;
			}
			vars += '&legacy=1';
			wrapper.append('<div class="loading" id="em-loading"></div>');
			$.ajax( EM.ajaxurl, {
				type : 'POST',
				dataType : 'html',
				data : vars,
				success : function(responseText) {
					wrapper.replaceWith(responseText);
					wrapper = wrapper_parent.find('.em-search-ajax');
					jQuery(document).triggerHandler('em_search_ajax', [vars, wrapper, e]); //ajax has loaded new results
				}
			});
			e.preventDefault();
			return false;
		});
	}
	/* END Legacy */
});