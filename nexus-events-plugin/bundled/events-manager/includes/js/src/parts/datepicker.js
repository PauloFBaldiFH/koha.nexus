function em_setup_datepicker( container ){
	wrap = jQuery(container);

	//apply datepickers - jQuery UI (backcompat)
	let dateDivs = wrap.find('.em-date-single, .em-date-range');
	if( dateDivs.length > 0 ){
		//default picker vals
		var datepicker_vals = {
			dateFormat: "yy-mm-dd",
			changeMonth: true,
			changeYear: true,
			firstDay : EM.firstDay,
			yearRange:'c-100:c+15',
			beforeShow : function( el, inst ){
				em_setup_jquery_ui_wrapper();
				inst.dpDiv.appendTo('#em-jquery-ui');
			}
		};
		if( EM.dateFormat ) datepicker_vals.dateFormat = EM.dateFormat;
		if( EM.yearRange ) datepicker_vals.yearRange = EM.yearRange;
		jQuery(document).triggerHandler('em_datepicker', datepicker_vals);
		//apply datepickers to elements
		dateDivs.find('input.em-date-input-loc').each(function(i,dateInput){
			//init the datepicker
			var dateInput = jQuery(dateInput);
			var dateValue = dateInput.nextAll('input.em-date-input').first();
			var dateValue_value = dateValue.val();
			dateInput.datepicker(datepicker_vals);
			dateInput.datepicker('option', 'altField', dateValue);
			//now set the value
			if( dateValue_value ){
				var this_date_formatted = jQuery.datepicker.formatDate( EM.dateFormat, jQuery.datepicker.parseDate('yy-mm-dd', dateValue_value) );
				dateInput.val(this_date_formatted);
				dateValue.val(dateValue_value);
			}
			//add logic for texts
			dateInput.on('change', function(){
				if( jQuery(this).val() == '' ){
					jQuery(this).nextAll('.em-date-input').first().val('');
				}
			});
		});
		//deal with date ranges
		dateDivs.filter('.em-date-range').find('input.em-date-input-loc[type="text"]').each(function(i,dateInput){
			//finally, apply start/end logic to this field
			dateInput = jQuery(dateInput);
			if( dateInput.hasClass('em-date-start') ){
				dateInput.datepicker('option','onSelect', function( selectedDate ) {
					//get corresponding end date input, we expect ranges to be contained in .em-date-range with a start/end input element
					var startDate = jQuery(this);
					var endDate = startDate.parents('.em-date-range').find('.em-date-end').first();
					var startValue = startDate.nextAll('input.em-date-input').first().val();
					var endValue = endDate.nextAll('input.em-date-input').first().val();
					startDate.trigger('em_datepicker_change');
					if( startValue > endValue && endValue != '' ){
						endDate.datepicker( "setDate" , selectedDate );
						endDate.trigger('change').trigger('em_datepicker_change');
					}
					endDate.datepicker( "option", 'minDate', selectedDate );
				});
			}else if( dateInput.hasClass('em-date-end') ){
				var startInput = dateInput.parents('.em-date-range').find('.em-date-start').first();
				if( startInput.val() != '' ){
					dateInput.datepicker('option', 'minDate', startInput.val());
				}
			}
		});
	}

	// datpicker - new format
	let datePickerDivs = wrap.find('.em-datepicker, .em-datepicker-range');
	if( datePickerDivs.length > 0 ){
		// wrappers and locale
		// flatpickr appends its calendar to this wrapper; create it in the SAME document as
		// the container so calendars for inputs inside the Gutenberg editor-canvas iframe
		// render in the iframe, not the parent (where they'd be invisible / mispositioned).
		// In the classic editor container.ownerDocument === document, so behaviour is unchanged.
		let containerDoc = ( container && container.ownerDocument ) || document;
		let wrapperEl = containerDoc.getElementById('em-flatpickr');
		if( ! wrapperEl ){
			wrapperEl = containerDoc.createElement('div');
			wrapperEl.className = 'em pixelbones em-flatpickr';
			wrapperEl.id = 'em-flatpickr';
			containerDoc.body.appendChild( wrapperEl );
		}
		let datepicker_wrapper = jQuery( wrapperEl );
		// locale
		if( 'locale' in EM.datepicker ){
			flatpickr.localize(flatpickr.l10ns[EM.datepicker.locale]);
			flatpickr.l10ns.default.firstDayOfWeek = EM.firstDay;
		}
		//default picker vals
		let datepicker_onChanging;
		let datepicker_options = {
			appendTo : datepicker_wrapper[0],
			dateFormat: "Y-m-d",
			disableMoble : "true",
			allowInput : true,
			onChange : [function( selectedDates, dateStr, instance ){
				if ( datepicker_onChanging !== selectedDates) {
					let wrapper = jQuery(instance.input).closest('.em-datepicker');
					let data_wrapper = wrapper.find('.em-datepicker-data');
					let inputs = data_wrapper.find('input');
					let dateFormat = function(d) {
						let month = '' + (d.getMonth() + 1),
							day = '' + d.getDate(),
							year = d.getFullYear();
						if (month.length < 2) month = '0' + month;
						if (day.length < 2) day = '0' + day;
						return [year, month, day].join('-');
					}
					if ( selectedDates.length === 0 ){
						if ( instance.config.mode === 'single' && wrapper.hasClass('em-datepicker-until') ) {
							let input = instance.input.classList.contains('em-date-input-start') ? inputs[0] : inputs[1];
							input.setAttribute('value', '');
							if ( inputs.filter(input => input.value !== '').length === 0 ) {
								wrapper.removeClass('has-value');
							}
						} else {
							wrapper.removeClass('has-value');
							inputs.attr('value', '');
							if( instance.config.mode === 'multiple' ) {
								// empty pill selection
								let datesEl = instance.input.closest('.em-datepicker').querySelector('.em-datepicker-dates');
								if (datesEl) {
									datesEl.querySelectorAll('.item:not(.clear-all)').forEach( el => el.remove() );
									datesEl.classList.remove('has-value');
								}
							}
						}
					} else {
						wrapper.addClass('has-value');
						if ( instance.config.mode === 'range' && selectedDates[1] !== undefined ) {
							// deal with end date
							inputs[0].setAttribute('value', dateFormat(selectedDates[0]));
							inputs[1].setAttribute('value', dateFormat(selectedDates[1]));
						} else if ( instance.config.mode === 'single' && wrapper.hasClass('em-datepicker-until') ){
							if( instance.input.classList.contains('em-date-input-start') ){
								inputs[0].setAttribute('value', dateFormat(selectedDates[0]));
								// set min-date of other datepicker
								let fp;
								if( wrapper.attr('data-until-id') ){
									let fp_inputData = jQuery('#' + wrapper.attr('data-until-id') + ' .em-date-input-end');
									fp = fp_inputData[0]._flatpickr;
								}else {
									fp = wrapper.find('.em-date-input-end')[0]._flatpickr;
								}
								if( fp.selectedDates[0] !== undefined && fp.selectedDates[0] < selectedDates[0] ){
									fp.setDate(selectedDates[0], false);
									inputs[1].setAttribute('value', dateFormat(fp.selectedDates[0]));
								}
								fp.set('minDate', selectedDates[0]);
							}else{
								inputs[1].setAttribute('value', dateFormat(selectedDates[0]));
							}
						} else if ( instance.config.mode === 'multiple' ){
							inputs[0].setAttribute('value', dateStr);
							// Sort the selected dates chronologically
							selectedDates.sort(function(a, b) { return a - b; });
							// Build pill selection for multiple dates
							let datesEl = instance.input.closest('.em-datepicker').querySelector('.em-datepicker-dates');
							datesEl.classList.add('has-value');
							if ( datesEl ) {
								// Remove existing date pills but preserve the clear-all button
								datesEl.querySelectorAll('.item:not(.clear-all)').forEach(el => el.remove());
	
								// Sort dates chronologically
								selectedDates.sort((a, b) => a - b);
	
								// Group sequential dates into ranges
								let groups = [], currentGroup = [];
								selectedDates.forEach((date, i) => {
									if (currentGroup.length === 0) {
										currentGroup.push(date);
									} else {
										let lastDate = currentGroup[currentGroup.length - 1];
										let diffDays = (date - lastDate) / (1000 * 3600 * 24);
										if (diffDays === 1) {
											currentGroup.push(date);
										} else {
											groups.push(currentGroup);
											currentGroup = [date];
										}
									}
									if (i === selectedDates.length - 1) groups.push(currentGroup);
								});
	
								// Insert pills and maintain date values
								groups.forEach(group => {
									let div = document.createElement('div');
									div.className = 'item';
									let formattedDates = group.map(date => instance.formatDate(date, 'Y-m-d'));
									div.dataset.date = formattedDates.join(',');
									let startText = instance.formatDate(group[0], instance.config.altFormat);
									let endText = instance.formatDate(group[group.length - 1], instance.config.altFormat);
									div.innerHTML = `<span>${group.length > 1 ? startText + ' - ' + endText : startText}</span><a href="#" class="remove" tabindex="-1" title="Remove">×</a>`;
									datesEl.insertBefore(div, datesEl.querySelector('.clear-all'));
								});
							}
						} else {
							inputs[0].setAttribute('value', dateFormat(selectedDates[0]));
						}
					}
					inputs.trigger('change');
					let current_date = data_wrapper.attr('date-value');
					data_wrapper.attr('data-value', inputs.toArray().map(input => input.value).filter(value => value !== '').join(','));
					if( current_date === dateStr ) data_wrapper.trigger('change');
					wrapper[0].dispatchEvent( new CustomEvent('datepicker-onChange', { detail: { selectedDates : selectedDates, dateStr: dateStr, instance: instance } }) );
				}
				datepicker_onChanging = null; // reset regardless, since it's to prevent onClose firing this twice
			}],
			onClose : function( selectedDates, dateStr, instance ){
				// deal with single date choice and clicking out
				if( instance.config.mode === 'range' && selectedDates[1] !== undefined ){
					if(selectedDates.length === 1){
						instance.setDate([selectedDates[0],selectedDates[0]], true); // wouldn't have been triggered with a single date selection
					}
				} else {
					// trigger an onChange
					datepicker_options.onChange[0](selectedDates, dateStr, instance);
					datepicker_onChanging = selectedDates; // set flag to prevent onChange firing twice
				}
			},
			locale : {},
		};
		if( EM.datepicker.format !== datepicker_options.dateFormat ){
			datepicker_options.altFormat = EM.datepicker.format;
			datepicker_options.altInput = true;
		}
		jQuery(document).triggerHandler('em_datepicker_options', datepicker_options);
		//apply datepickers to elements
		datePickerDivs.each( function(i,datePickerDiv) {
			// hide fallback fields, show range or single
			datePickerDiv = jQuery(datePickerDiv);
			datePickerDiv.find('.em-datepicker-data').addClass('hidden');
			let isRange = datePickerDiv.hasClass('em-datepicker-range');
			let altOptions = {};
			if( datePickerDiv.attr('data-datepicker') ){
				altOptions = JSON.parse(datePickerDiv.attr('data-datepicker'));
				if( typeof altOptions !== 'object' ){
					altOptions = {};
				}
			}
			let otherOptions = {};
			if( datePickerDiv.find('script.datepicker-options').length > 0 ){
				otherOptions = JSON.parse( datePickerDiv.find('script.datepicker-options').text() );
				if( typeof altOptions !== 'object' ){
					otherOptions = {};
				}
			}
			let options = Object.assign({}, datepicker_options, altOptions, otherOptions); // clone, mainly shallow concern for 'mode'
			options.mode = isRange ? 'range' : 'single';
			if ( datePickerDiv.hasClass('em-datepicker-multiple') ) {
				options.mode = 'multiple';
			}
			if( isRange && 'onClose' in options ){
				options.onClose = [function( selectedDates, dateStr, instance ){
					if(selectedDates.length === 1){ // deal with single date choice and clicking out
						instance.setDate([selectedDates[0],selectedDates[0]], true);
					}
				}];
			}
			if( datePickerDiv.attr('data-separator') ) options.locale.rangeSeparator = datePickerDiv.attr('data-separator');
			if( datePickerDiv.attr('data-format') ) options.altFormat = datePickerDiv.attr('data-format');
			let FPs = datePickerDiv.find('.em-date-input');
			//if ( FPs.hasClass(flatpickr-input) ) return; // already initialized
			if ( FPs[0].tagName.toLowerCase() === 'input' ) {
				FPs.attr('type', 'text');
			} else {
				options.wrap = true;
				FPs.find('input[type="hidden"]').attr('type', 'text');
			}
			FPs.flatpickr(options);
		});
		em_setup_datepicker_dates( datePickerDivs );
		// fire trigger
		jQuery(document).triggerHandler('em_flatpickr_loaded', [wrap]);
		container.dispatchEvent( new CustomEvent('em_datepicker_loaded', { bubbles: true, detail: { container: wrap, datepickers: datePickerDivs } } ) );
	}
}

function em_setup_datepicker_dates( container ) {
	let datePickerContainer = jQuery(container);
	let datePickerDivs = datePickerContainer.first().hasClass('em-datepicker') ? datePickerContainer : datePickerContainer.find('.em-datepicker, .em-datepicker-range') ;
	// add values to elements, done once all datepickers instantiated so we don't get errors with date range els in separate divs
	datePickerDivs.each( function(i,datePickerDiv) {
		datePickerDiv = jQuery(datePickerDiv);
		let FPs = datePickerDiv.find('.em-date-input');
		//if ( FPs.hasClass(flatpickr-input) ) return;
		let inputs = datePickerDiv.find('.em-datepicker-data input');
		inputs.attr('type', 'hidden'); // hide so not tabbable
		if( datePickerDiv.hasClass('em-datepicker-until') ){
			let start_fp = FPs.filter('.em-date-input-start')[0]._flatpickr;
			let end_fp;
			if( datePickerDiv.attr('data-until-id') ){
				end_fp = jQuery('#' + datePickerDiv.attr('data-until-id') + ' .em-date-input-end')[0]._flatpickr;
			}else{
				end_fp = FPs.filter('.em-date-input-end')[0]._flatpickr;
				if( inputs[1] && inputs[1].value ) {
					end_fp.setDate(inputs[1].value, false, 'Y-m-d');
				}
			}
			if( inputs[0] && inputs[0].value ){
				start_fp.setDate(inputs[0].value, false, 'Y-m-d');
				end_fp.set('minDate', inputs[0].value);
			}
			start_fp._inputData = inputs[0] ? [inputs[0]] : [];
			end_fp._inputData = inputs[1] ? [inputs[1]] : [];
		}else if( datePickerDiv.hasClass('em-datepicker-multiple') ){
			// handle multiple pre-loaded dates
			if( inputs[0] && inputs[0].value ){
				let datesArray = inputs[0].value.split(',');
				FPs[0]._flatpickr.setDate(datesArray, true, 'Y-m-d');
			}
			FPs[0]._flatpickr._inputData = [ inputs[0] ];
		}else{
			let dates = [];
			FPs[0]._flatpickr._inputData = [];
			inputs.each( function( i, input ){
				if( input.value ){
					dates.push(input.value);
					FPs[0]._flatpickr._inputData.push(input);
				}
			});
			FPs[0]._flatpickr.setDate(dates, false, 'Y-m-d');
		}
	});
}

/**
 * Deregister the datepicker
 * @param wrap
 */
function em_unsetup_datepicker( wrap ) {
	wrap.querySelectorAll(".em-datepicker .em-date-input.flatpickr-input").forEach( function( el ){
		if( '_flatpickr' in el ){
			el._flatpickr.destroy();
		}
	});
}

/**
 * Handle the remove button for each date selection pill
 */
document.addEventListener('click', function(e) {
	if ( !e.target.closest('.em-datepicker-dates .item:not(.clear-all) .remove') ) return;

	e.preventDefault();
	const pill = e.target.closest('.item');
	const datesContainer = pill.closest('.em-datepicker-dates');
	const datepickerContainer = datesContainer.closest('.em-datepicker');
	const dateInput = datepickerContainer.querySelector('.em-date-input');

	// Remove pill
	pill.remove();

	// Rebuild dates array from remaining pills
	const newDates = [];
	datesContainer.querySelectorAll('.item:not(.clear-all)').forEach(item => {
		const dates = item.dataset.date.split(',');
		dates.forEach(date => newDates.push(date));
	});

	// Update Flatpickr instance
	const fp = datepickerContainer.querySelector('.em-date-input')._flatpickr;
	if (fp) fp.setDate(newDates, true, 'Y-m-d');

	// Update hidden input
	const altInput = datepickerContainer.querySelector('.em-datepicker-data input');
	if (altInput) {
		altInput.value = newDates.join(',');
		altInput.dispatchEvent(new Event('change'));
	}
});

/**
 * Handle the Clear All button
 */
document.addEventListener('click', function(e) {
	if ( !e.target.closest('.em-datepicker-dates .clear-all') ) return;

	e.preventDefault();
	const datesContainer = e.target.closest('.em-datepicker-dates');
	const datepickerContainer = datesContainer.closest('.em-datepicker');
	const fp = datepickerContainer.querySelector('.em-date-input')._flatpickr;

	// Remove all pills
	datesContainer.querySelectorAll('.item:not(.clear-all)').forEach( item => item.remove() );

	// Clear Flatpickr instance
	if (fp) fp.clear();

	// Update hidden input
	const altInput = datepickerContainer.querySelector('.em-datepicker-data input');
	if (altInput) {
		altInput.value = '';
		altInput.dispatchEvent(new Event('change'));
	}
});

