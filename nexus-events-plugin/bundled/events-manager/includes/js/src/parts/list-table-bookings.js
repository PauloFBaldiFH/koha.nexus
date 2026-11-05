// add extra setup to bookings list table
document.addEventListener('em_list_table_setup'  , function(e){
	let listTable = e.detail.listTable;
	let listTableForm = e.detail.listTableForm;
	if( listTable.classList.contains('em-bookings-table') ) {

		// handle submitting the settings modal form with booking-speficic extras
		listTable.addEventListener('em_list_table_settings_submitted', function(e){
			let form = e.detail.form;
			let listTableForm = e.detail.listTableForm;
			// get the views ddm and sync it to the table filter
			let views_select = form.querySelector('select[name="view"]');
			if ( views_select ) {
				let view_radio = listTableForm.querySelector('[name="view"][value="' + views_select.value + '"]');
				if( view_radio ) {
					view_radio.checked = true; // this doesn't trigger an event as we don't want that
				}
				let view_option = listTableForm.querySelector('button.em-bookings-table-view-option[data-view]');
				if ( view_option ) {
					view_option.setAttribute('data-view', views_select.value);
					view_option.innerText = views_select.options[views_select.selectedIndex].innerText;
				}
			}
		});

		// setup views dropdown to switch between different booking table views
		let views_ddm_options = {
			theme : 'light-border',
			allowHTML : true,
			interactive : true,
			trigger : 'manual',
			placement : 'bottom',
			zIndex : 1000000,
			touch: true,
		};
		let tooltip_vars = { theme : 'light-border', appendTo : 'parent', touch : false, };

		// TODO unify this with the search view dropdown JS to remove redundant code
		listTable.querySelectorAll('.em-bookings-table-views-trigger').forEach( function( trigger ){
			tooltip_vars.content = trigger.parentElement.getAttribute('aria-label');
			let views_tooltip = tippy(trigger.parentElement, tooltip_vars);
			let views_content = trigger.parentElement.querySelector('.em-bookings-table-views-options');
			let views_content_parent = views_content.parentElement;
			let tippy_content = document.createElement('div');
			views_ddm_options.content = tippy_content;
			let views_ddm = tippy(trigger, views_ddm_options);
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
				trigger._tippy.show();
				views_tooltip.hide();
			}
			trigger.addEventListener('click', tippy_listener);
			trigger.addEventListener('keydown', tippy_listener);
			trigger.firstElementChild.addEventListener('focus', function(e){
				views_ddm.hide();
				views_tooltip.enable();
				views_tooltip.show();
			});
			trigger.firstElementChild.addEventListener('blur', function(){
				views_tooltip.hide();
			});

			// TODO Remove this dependence on jQuery. Copied it from the search.js file, but it seems that even a vanilla document.addEventListener('blur') isn't intercepting these blur/focus events.
			let $ = jQuery;
			$views = $(listTable).find('.em-bookings-table-views');
			$views.on('focus blur', '.em-bookings-table-views-options input', function(){
				if( document.activeElement === this ){
					this.parentElement.classList.add('focused');
				}else{
					this.parentElement.classList.remove('focused');
				}
			});

			$views.on('keydown click', '.em-bookings-table-views-options input', function( e ){
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
				let views_wrapper = $(this).closest('.em-bookings-table-views');
				let view_type = this.value;
				let trigger = views_wrapper.children('.em-bookings-table-views-trigger');
				let trigger_option = trigger.children('.em-search-view-option');
				// change view, if different
				if( view_type !== trigger_option.attr('data-view') ){
					trigger_option.attr('data-view', this.value).text(this.parentElement.innerText);
					// remove cols value if it's just a switch in view, so we get default cols (if there is one)
					listTableForm.querySelector('input[name="cols"][type="hidden"]').value = '';
					// set the view type and trigger a form submit
					listTableForm.requestSubmit();
				}
				views_ddm.hide();
			});
		});
	}
});

// backcompat for em_bookings_filtered jQuery trigger
document.addEventListener('em_list_table_filtered', function( e ){
	if( e.detail.listTable.classList.contains('em-bookings-table') && window.jQuery ) {
		jQuery(document).triggerHandler('em_bookings_filtered', [jQuery(e.detail.data), e.detail.listTable, jQuery(e.detail.form)]); // backwards compatibility
	}
})