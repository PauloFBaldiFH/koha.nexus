/*
* CALENDAR
*/
jQuery(document).ready( function($){

	const em_calendar_init = function( calendar ){
		calendar = $(calendar);
		if( !calendar.attr('id') || !calendar.attr('id').match(/^em-calendar-[0-9]+$/) ){
			calendar.attr('id', 'em-calendar-' + Math.floor(Math.random() * 10000)); // retroactively add id to old templates
		}
		calendar.find('a').off("click");
		calendar.on('click', 'a.em-calnav, a.em-calnav-today', function(e){
			e.preventDefault();
			const el = $(this);
			if( el.attr('href') === '') return; // do nothing if disabled or no link provided
			el.closest('.em-calendar').prepend('<div class="loading" id="em-loading"></div>');
			let url = el.attr('href');
			const view_id = el.closest('[data-view-id]').data('view-id');
			const custom_data = $('form#em-view-custom-data-calendar-'+ view_id);
			let form_data = new FormData();
			if( custom_data.length > 0 ){
				form_data = new FormData(custom_data[0]);
				let $URL = new URL(url, window.location.origin);
				let url_params = $URL.searchParams;
				for (const [key, value] of url_params.entries()) {
					if( key === 'mo' ) {
						form_data.set('month', value);
					} else if ( key === 'yr' ) {
						form_data.set('year', value);
					} else {
						form_data.set(key, value);
					}
				}
				// remove mo and yr from URL
				$URL.searchParams.delete('mo');
				$URL.searchParams.delete('yr');
				url = $URL.toString();
			}
			if ( calendar.attr('data-timezone') ) {
				form_data.set('calendar_timezone', calendar.attr('data-timezone') );
			}
			form_data.set('id', view_id);
			form_data.set('ajaxCalendar', 1); // AJAX trigger
			form_data.set('em_ajax', 1); // AJAX trigger
			// check advanced trigger
			if( calendar.hasClass('with-advanced') ){
				form_data.set('has_advanced_trigger', 1);
			}
			$.ajax({
				url: url,
				data: form_data,
				processData: false,
				contentType: false,
				method: 'POST',
				success: function( data ){
					let view = EM_View_Updater( calendar, data );
					if( view.hasClass('em-view-container') ){
						calendar = view.find('.em-calendar');
					}else{
						calendar = view;
					}
					calendar[0].dispatchEvent( new CustomEvent( 'em_calendar_load', { bubbles: true } ) );
				},
				dataType: 'html'
			});
		} );
		calendar[0].addEventListener('reload', () => {
			calendar_trigger_ajax( calendar, calendar.attr('data-year'), calendar.attr('data-month') );
		});
		let calendar_trigger_ajax = function( calendar, year, month ){
			let link = calendar.find('.em-calnav-next');
			let url = new URL(link.attr('href'), window.location.origin);
			url.searchParams.set('mo', month);
			url.searchParams.set('yr', year);
			link.attr('href', url.toString()).trigger('click');
		};
		let calendar_resize_monthpicker = function( instance, text ){
			let span = $('<span class="marker">'+ text +'</span>');
			span.insertAfter(instance);
			let width = span.width() + 40;
			span.remove();
			instance.style.setProperty('width', width+'px', 'important');
		}
		let calendar_month_init = function(){
			let month_form = calendar.find('.month form');
			calendar.find('.event-style-pill .em-cal-event').on('click', function( e ){
				e.preventDefault();
				if( !(calendar.hasClass('preview-tooltips') && calendar.data('preview-tooltips-trigger')) && !(calendar.hasClass('preview-modal')) ) {
					let link = this.getAttribute('data-event-url');
					if (link !== null) {
						window.location.href = link;
					}
				}
				// select this date, all others no
				e.target.closest('.em-cal-body').querySelectorAll('.em-cal-day-date').forEach( calDate => calDate.classList.remove('selected') );
				e.target.closest('.em-cal-day').querySelector('.em-cal-day-date')?.classList.add('selected');
			});
			if( month_form.length > 0 ){
				month_form.find('input[type="submit"]').hide();
				let select = $('<select style="display:none;visibility:hidden;"></select>').appendTo(month_form);
				let option = $('<option></option>').appendTo(select);
				let current_datetime = calendar.find('select[name="month"]').val() + calendar.find('select[name="year"]').val();
				let month = calendar.find('select[name="month"]');
				let year = calendar.find('select[name="year"]');
				let monthpicker = calendar.find('.em-month-picker');
				let monthpicker_value = monthpicker.val() + '-02'; // store this for further down before we change the value below
				let month_value = monthpicker.data('month-value');
				monthpicker.prop('type', 'text').prop('value', month_value);
				calendar_resize_monthpicker( monthpicker[0], month_value );
				let monthpicker_wrapper = $('#em-flatpickr');
				if( monthpicker_wrapper.length === 0 ) {
					monthpicker_wrapper = $('<div class="em pixelbones" id="em-flatpickr"></div>').appendTo('body');
				}
				let minDate = null;
				if( calendar.data('scope') === 'future' ){
					minDate = new Date();
					minDate.setMonth(minDate.getMonth()-1);
				}
				// locale
				if( 'locale' in EM.datepicker ){
					flatpickr.localize(flatpickr.l10ns[EM.datepicker.locale]);
					flatpickr.l10ns.default.firstDayOfWeek = EM.firstDay;
				}
				let fp = monthpicker.flatpickr({
					appendTo : monthpicker_wrapper[0],
					dateFormat : EM?.calendar?.month_format,
					minDate : minDate,
					disableMobile: "true",
					plugins: [
						new monthSelectPlugin({
							shorthand: true,
							dateFormat: EM?.calendar?.month_format || 'F Y',
							altFormat: EM?.calendar?.month_format || 'F Y',
						})
					],
					onChange: function(selectedDates, dateStr, instance) {
						calendar_resize_monthpicker( instance.input, dateStr );
						calendar_trigger_ajax( calendar, selectedDates[0].getFullYear(), selectedDates[0].getMonth()+1);
					},
				});
				// this bit fixes issues if the supplied text value has a mismatch with the real text value due to localization differences between WP and flatpickr
				fp.setDate( new Date( monthpicker_value ) );
				// add classes to month picker
				monthpicker.addClass('select-toggle');
			}
			if( calendar.hasClass('preview-tooltips') ){
				let tooltip_vars = {
					theme : 'light-border',
					allowHTML : true,
					interactive : true,
					trigger : 'mouseenter focus click',
					content(reference) {
						return document.createElement('div');
					},
					onShow( instance ){
						const id = instance.reference.getAttribute('data-event-id');
						const template = calendar.find('section.em-cal-events-content .em-cal-event-content[data-event-id="'+id+'"]');
						instance.props.content.append(template.first().clone()[0]);
					},
					onHide( instance ){
						instance.props.content.innerHTML = '';
					}
				};
				if( calendar.data('preview-tooltips-trigger') ) {
					tooltip_vars.trigger = calendar.data('preview-tooltips-trigger');
				}
				$(document).trigger('em-tippy-cal-event-vars',[tooltip_vars]);
				tippy(calendar.find('.em-cal-event').toArray(), tooltip_vars);
			}else if( calendar.hasClass('preview-modal') ){
				// Modal
				calendar.find('.em-cal-event').on('click', function( e ){
					const id = this.getAttribute('data-event-id');
					const modal = calendar.find('section.em-cal-events-content .em-cal-event-content[data-event-id="'+id+'"]');
					modal.attr('data-calendar-id', calendar.attr('id'));
					openModal(modal);
					// select this date, all others no
					e.target.closest('.em-cal-body').querySelectorAll('.em-cal-day-date').forEach( calDate => calDate.classList.remove('selected') );
					e.target.closest('.em-cal-day').querySelector('.em-cal-day-date')?.classList.add('selected');
				});
			}
			// responsive mobile view for date clicks
			if( calendar.hasClass('responsive-dateclick-modal') ){
				calendar.find('.eventful .em-cal-day-date, .eventful-post .em-cal-day-date, .eventful-pre .em-cal-day-date').on('click', function( e ){
					//if( calendar.hasClass('size-small') || calendar.hasClass('size-medium') ){
					e.preventDefault();
					const id = this.getAttribute('data-timestamp');
					const modal = calendar.find('.em-cal-date-content[data-calendar-date="'+id+'"], .em-cal-date-content[data-timestamp="'+id+'"]');
					modal.attr('data-calendar-id', calendar.attr('id'));
					openModal(modal);
					// select this date, all others no
					e.target.closest('.em-cal-body').querySelectorAll('.em-cal-day-date').forEach( calDate => calDate.classList.remove('selected') );
					e.target.closest('.em-cal-day').querySelector('.em-cal-day-date')?.classList.add('selected');
				});
			}
			// observe resizing if not fixed
			if( !calendar.hasClass('size-fixed') ){
				EM_ResizeObserver( EM.calendar.breakpoints, [calendar[0], calendar[0]]);
			}
			// even aspect, because aspect ratio can screw up widths vs row template heights
			let calendar_body = calendar.find('.em-cal-body');
			if( calendar_body.hasClass('even-aspect') ) {
				let ro_function = function (el) {
					let width = el.firstElementChild.getBoundingClientRect().width;
					if (width > 0) {
						el.style.setProperty('--grid-auto-rows', 'minmax(' + width + 'px, auto)');
					}
				}
				let ro = new ResizeObserver(function (entries) {
					for (let entry of entries) {
						ro_function(entry.target);
					}
				});
				ro.observe(calendar_body[0]);
				ro_function(calendar_body[0]);
			}

			// figure out colors
			calendar.find('.date-day-colors').each( function(){
				let colors = JSON.parse(this.getAttribute('data-colors'));
				let day = $(this).siblings('.em-cal-day-date.colored');
				let sides = {
					1 : { 1 : '--date-border-color', 'class' : 'one' },
					2 : { 1 : '--date-border-color-top', 2 : '--date-border-color-bottom', 'class' : 'two' },
					3 : { 1 : '--date-border-color-top', 2 : '--date-border-color-right', 3 : '--date-border-color-bottom', 'class' : 'three' },
					4 : { 1 : '--date-border-color-top', 2 : '--date-border-color-right', 3 : '--date-border-color-bottom', 4 : '--date-border-color-left', 'class' : 'four' },
				};
				for (let i = 0; i < colors.length; i += 4) {
					const ring_colors = colors.slice(i, i + 4);
					// add a ring
					let outer_ring = day.children().first();
					let new_ring = $('<div class="ring"></div>').prependTo(day);
					outer_ring.appendTo(new_ring);
					new_ring.addClass( sides[ring_colors.length].class );
					for ( let it = 0; it < ring_colors.length; it++ ){
						new_ring.css(sides[ring_colors.length][it+1], ring_colors[it]);
					}
				}
			});

			if( calendar.hasClass('with-advanced') ){
				const trigger = calendar.find('.em-search-advanced-trigger');
				const search_advanced = $('#'+trigger.attr('data-search-advanced-id'));
				search_advanced.triggerHandler('update_trigger_count');
			}
		}
		calendar_month_init();
		$(document).triggerHandler('em_calendar_loaded', [calendar]);
	};
	$('.em-calendar').each( function(){
		let calendar = $(this);
		em_calendar_init( calendar );
	});
	$(document).on('em_calendar_load', '.em-calendar', function(){
		em_calendar_init( this );
	});
	$(document).on('em_view_loaded_calendar', function( e, view, form ){
		let calendar;
		if( view.hasClass('em-calendar') ){
			calendar = view;
		}else {
			calendar = view.find('.em-calendar').first();
		}
		em_calendar_init( calendar );
	});
});

let EM_View_Updater = function( element, html ){
	let content = jQuery(html);
	let view = element.hasClass('em-view-container') ? element : element.parent('.em-view-container');
	if( view.length > 0 ){
		if( content.hasClass('em-view-container') ){
			view.replaceWith(content);
			view = content;
		}else{
			view.empty().append(content);
		}
	}else{
		// create a view if possible
		if( content.hasClass('em-view-container') ){
			element.replaceWith(content);
			view = content;
		}else if( content.attr('data-view-id') ){
			let view = jQuery('<div class="em em-view-container"></div>');
			let view_id = content.attr('data-view-id');
			view.attr('data-view-id', view_id);
			view.attr('id', 'em-view-'+ view_id);
			view.attr('data-view-type', content.attr('data-view-type'));
			view.append(content);
			element.replaceWith(view);
		}
	}
	em_setup_ui_elements( view[0] );
	return view;
}

/**
 * Resize watcher for EM elements. Supply an object (localized array) of name > breakpoint, in order of least to largest and it'll add size-{name} class name according to the breakpoint.
 * An object item with value false will represent any screensize, i.e. it should be the last value when all breakpoints aren't met.
 * @param breakpoints
 * @param elements
 * @constructor
 */
let EM_ResizeObserver = function( breakpoints, elements ){
	const ro = new ResizeObserver( function( entries ){
		for (let entry of entries) {
			let el = entry.target;
			if( !el.classList.contains('size-fixed') ) {
				for (const [name, breakpoint] of Object.entries(breakpoints)) {
					if (el.offsetWidth <= breakpoint || breakpoint === false) {
						for (let breakpoint_name of Object.keys(breakpoints)) {
							if (breakpoint_name !== name) el.classList.remove('size-' + breakpoint_name);
						}
						// add class and trigger event only once
						if(	!el.classList.contains('size-' + name) ) {
							el.classList.add('size-' + name);
							el.dispatchEvent( new CustomEvent('em_resize') );
						}
						break;
					}
				}
			}
		}
	});
	elements.forEach( function( el ){
		if( typeof el !== 'undefined' ){
			ro.observe(el);
		}
	});
	return ro;
};

// event list and event page (inc. some extra booking form logic) - todo/cleanup
jQuery(document).ready( function($){
	// Events List
	let breakpoints = {
		'small' : 600,
		'large' : false,
	}
	const events_ro = EM_ResizeObserver( breakpoints, $('.em-list').toArray() );
	$(document).on('em_page_loaded em_view_loaded_list em_view_loaded_list-grouped em_view_loaded_grid', function( e, view ){
		let new_elements = view.find('.em-list').each( function(){
			if( !this.classList.contains('size-fixed') ){
				events_ro.observe( this );
			}
		});
	});

	$(document).on('click', '.em-grid .em-item[data-href]', function(e){
		if( e.target.type !== 'a' ){
			window.location.href = this.getAttribute('data-href');
		}
	});

	// Single event area
	breakpoints = {
		'small' : 600,
		'medium' : 900,
		'large' : false,
	}
	const event_ro = EM_ResizeObserver( breakpoints, $('.em-item-single').toArray() );
	$(document).on('em_view_loaded', function( e, view ){
		let new_elements = view.find('.em-event-single').each( function(){
			if( !this.classList.contains('size-fixed') ){
				event_ro.observe( this );
			}
		});
	});
	// booking form area (WIP)
	$(document).on("click", ".em-event-booking-form .em-login-trigger a", function( e ){
		e.preventDefault();
		var parent = $(this).closest('.em-event-booking-form');
		parent.find('.em-login-trigger').hide();
		parent.find('.em-login-content').fadeIn();
		let login_form = parent.find('.em-login');
		login_form[0].scrollIntoView({
			behavior: 'smooth'
		});
		login_form.first().find('input[name="log"]').focus();

	});
	$(document).on("click", ".em-event-booking-form .em-login-cancel", function( e ){
		e.preventDefault();
		let parent = $(this).closest('.em-event-booking-form');
		parent.find('.em-login-content').hide();
		parent.find('.em-login-trigger').show();
	});
	EM_ResizeObserver( {'small': 500, 'large' : false}, $('.em-login').toArray());

});

// handle generic ajax submission forms vanilla style
document.addEventListener('DOMContentLoaded', function () {
	document.querySelectorAll('form.em-ajax-form').forEach( function(el){
		el.addEventListener('submit', function(e){
			e.preventDefault();
			let form = e.currentTarget;
			let formData =  new FormData(form);
			let button = form.querySelector('button[type="submit"]');
			let loader;

			if( form.classList.contains('no-overlay-spinner') ){
				form.classList.add('loading');
			}else{
				let loader = document.createElement('div');
				loader.id = 'em-loading';
				form.append(loader);
			}

			var request = new XMLHttpRequest();
			if( form.getAttribute('data-api-url') ){
				request.open('POST', form.getAttribute('data-api-url'), true);
				request.setRequestHeader('X-WP-Nonce', EM.api_nonce);
			}else{
				request.open('POST', EM.ajaxurl, true);
			}

			request.onload = function() {
				if( loader ) loader.remove();
				if (this.status >= 200 && this.status < 400) {
					// Success!
					try {
						let data = JSON.parse(this.response);
						let notice;
						if( !form.classList.contains('no-inline-notice') ){
							notice = form.querySelector('.em-notice');
							if( !notice ){
								notice = document.createElement('div');
								form.prepend(notice);
								if( formData.get('action') ){
									form.dispatchEvent( new CustomEvent( 'em_ajax_form_success_' + formData.get('action'), {
										detail : {
											form : form,
											notice : notice,
											response : data,
										}
									}) );
								}
							}
							notice.innerHTML = '';
							notice.setAttribute('class', 'em-notice');
						}
						if( data.result ){
							if( !form.classList.contains('no-inline-notice') ){
								notice.classList.add('em-notice-success');
								notice.innerHTML = data.message;
								form.replaceWith(notice);
							}else{
								form.classList.add('load-successful');
								form.classList.remove('loading');
								if( data.message ){
									EM_Alert(data.message);
								}
							}
						}else{
							if( !form.classList.contains('no-inline-notice') ){
								notice.classList.add('em-notice-error');
								notice.innerHTML = data.errors;
							}else{
								EM_Alert(data.errors);
							}
						}
					} catch(e) {
						alert( 'Error Encountered : ' + e);
					}
				} else {
					alert('Error encountered... please see debug logs or contact support.');
				}
				form.classList.remove('loading');
			};

			request.onerror = function() {
				alert('Connection error encountered... please see debug logs or contact support.');
			};

			request.send( formData );
			return false;
		});
	});
});