let em_close_other_selectized = function(){
	// find all other selectized items and close them
	let control = this.classList.contains('selectize-control') ? this.closest('.em-selectize.selectize-control') : this;
	document.querySelectorAll('.em-selectize.dropdown-active').forEach( function( el ){
		if( el !== control && 'selectize' in el.previousElementSibling) {
			el.previousElementSibling.selectize.close();
		}
	});
}

document.addEventListener('events_manager_js_loaded', function(){
	EM_Selectize.define('multidropdown', function( options ) {
		if( !this.$input.hasClass('multidropdown') ) return;
		let s = this;
		let s_setup = s.setup;
		let s_refreshOptions = s.refreshOptions;
		let s_open = s.open;
		let s_close = s.close;
		let placeholder;
		let placeholder_text
		let placeholder_default;
		let placeholder_label;
		let counter;
		let isClosing = false;
		this.changeFunction = function() {
			let items = s.getValue();
			let selected_text = this.$input.attr('data-selected-text') ? this.$input.attr('data-selected-text') : '%d Selected';
			counter.children('span.selected-text').text(selected_text.replace('%d', items.length));
			if( items.length > 0 ) {
				counter.removeClass('hidden');
				placeholder_text.text( placeholder_label );
				s.$control_input.attr('placeholder', s.$input.attr('placeholder'));
			} else {
				counter.addClass('hidden');
				placeholder_text.text( placeholder_default );
			}
		}
		this.setup = function() {
			s_setup.apply(s);
			s.isDropdownClosingPlaceholder = false;
			// add section to top of selection to show the dropdown text
			placeholder = jQuery('<div class="em-selectize-placeholder"></div>').prependTo(s.$wrapper);
			let clear_text = this.$input.attr('data-clear-text') ? this.$input.attr('data-clear-text') : 'Clear Selection';
			counter = jQuery('<span class="placeholder-count hidden"><a href="#" class="remove" tabindex="-1">X</a><span class="selected-text"></span><span class="clear-selection">' + clear_text + '</span></div>').prependTo(placeholder);
			placeholder_text = jQuery('<span class="placeholder-text"></span>').appendTo(placeholder);
			placeholder_default = s.$input.attr('data-default') ? s.$input.attr('data-default') : s.$input.attr('placeholder');
			placeholder_label = s.$input.attr('data-label') ? s.$input.attr('data-label') : s.$input.attr('placeholder');
			placeholder_text.text( placeholder_default );
			s.$dropdown.prepend(s.$control_input.parent());
			s.on('dropdown_close', function() {
				s.$wrapper.removeClass('dropdown-active');
			});
			s.on('dropdown_open', function() {
				s.$wrapper.addClass('dropdown-active');
				s.$control_input.val('');
			});
			s.on('change', this.changeFunction);
			placeholder.on('focus blur click', function (e) {
				// only if we're clicking on the placeholder
				if( this.matches('.em-selectize-placeholder') ) {
					if ( !s.isOpen && e.type !== 'blur' ){
						s.open();
					} else if ( s.isOpen && e.type !== 'focus' ) {
						s.close();
					}
				}
			}).on('focus blur click mousedown mouseup', function( e ){
				if( this.matches('.em-selectize-placeholder') ) {
					// stope selectize doing anything to our own open/close actions
					e.stopPropagation();
					e.preventDefault();
					if( e.type === 'click' ) {
						em_close_other_selectized.call( this.closest('.selectize-control') );
						if ( s.isOpen && s.$control_input.val() && !this.matches('.placeholder-count') && !this.closest('.placeholder-count') ) {
							isClosing = true;
							s.close();
						}
					} else {
						isClosing = false;
					}
					return false;
				}
			});
			counter.on( 'click' , function( e ){
				e.preventDefault();
				e.stopPropagation();
				s.clear();
				if( s.isOpen ) s.refreshOptions();
			});
			this.changeFunction();
		}

		// prevent dropdown from closing when no options are found, because the search input shows within the dropdown in multidropdown
		this.refreshOptions = function ( ...args ) {
			s_refreshOptions.apply(s, args);
			if ( !this.hasOptions && this.lastQuery ) {
				// intervene on closing only if not in a closing process caused by our own listeners
				if( isClosing === false ) {
					this.$wrapper.addClass("dropdown-active");
					s.isOpen = true;
				}
				this.$wrapper.addClass("no-options");
				isClosing = false;
			} else {
				this.$wrapper.removeClass("no-options");
			}
		};
	});
});

function em_setup_selectize( container_element ){
	container = jQuery(container_element); // in case we were given a dom object

	container.find('.em-selectize.selectize-control').on( 'click', em_close_other_selectized );

	let optionRender = function (item, escape) {
		let html = '<div class="option"';
		if( 'data' in item ){
			// any key/value object pairs wrapped in a 'data' key within JSON object in the data-data attribute is added automatically as a data-key="value" attribute
			Object.entries(item.data).forEach( function( item_data ){
				html += ' data-'+ escape(item_data[0]) + '="'+ escape(item_data[1]) +'"';
			});
		}
		html +=	'>';
		if( this.$input.hasClass('checkboxes') ){
			html += item.text.replace(/^(\s+)?/i, '$1<span></span> ');
		}else{
			html += item.text;
		}
		html += '</div>';
		return html;
	};

	// Selectize General
	container.find('select:not([multiple]).em-selectize, .em-selectize select:not([multiple])').em_selectize({
		selectOnTab : false,
		render: {
			option: optionRender,
		},
	}).on('change', ( e ) => {
		e.target.selectize?.$input[0].parentElement.dispatchEvent( new CustomEvent('change', { bubbles: true, cancelable: true, detail : { target: e.target, selectize: e.target.selectize } }) )
	});
	container.find('select[multiple].em-selectize, .em-selectize select[multiple]').em_selectize({
		selectOnTab : false,
		hideSelected : false,
		plugins: ["remove_button", 'click2deselect','multidropdown'],
		diacritics : true,
		render: {
			item: function (item, escape) {
				return '<div class="item"><span>' + item.text.replace(/^\s+/i, '') + '</span></div>';
			},
			option : optionRender,
			optgroup : function (item, escape) {
				let html = '<div class="optgroup" data-group="' + escape(item.label) + '"';
				if( 'data' in item ){
					// any key/value object pairs wrapped in a 'data' key within JSON object in the data-data attribute is added automatically as a data-key="value" attribute
					Object.entries(item.data).forEach( function( item_data ){
						html += ' data-'+ escape(item_data[0]) + '="'+ escape(item_data[1]) +'"';
					});
				}
				html +=	'>';
				return html + item.html + '</div>';
			}

		},
	}).on('change', ( e ) => {
		e.target.selectize?.$input[0].parentElement.dispatchEvent( new CustomEvent('change', { bubbles: true, cancelable: true, detail : { target: e.target, selectize: e.target.selectize } }) )
	});
	container.find('.em-selectize:not(.always-open)').each( function(){
		if( 'selectize' in this ){
			let s = this.selectize;
			this.selectize.$wrapper.on('keydown', function(e) {
				if( e.keyCode === 9 ) {
					s.blur();
				}
			});
		}
	});
	container.find('.em-selectize.always-open').each( function(){
		//extra behaviour for selectize "always open mode"
		if( 'selectize' in this ){
			let s = this.selectize;
			s.open();
			s.advanceSelection = function(){}; // remove odd item shuffling
			s.setActiveItem = function(){}; // remove odd item shuffling
			// add event listener to fix remove button issues due to above hacks
			this.selectize.$control.on('click', '.remove', function(e) {
				if ( s.isLocked  ) return;
				var $item = jQuery(e.currentTarget).parent();
				s.removeItem($item.attr('data-value'));
				s.refreshOptions();
				return false;
			});
		}
	});

	// Sortables - selectize and sorting columns, usually in list tables
	container.find('.em-list-table-modal .em-list-table-cols').each( function(){
		let parent = jQuery(this);
		let sortables = jQuery(this).find('.em-list-table-cols-sortable');
		parent.find('.em-selectize.always-open').each( function() {
			//extra behaviour for selectize column picker
			if ('selectize' in this) {
				let selectize = this.selectize;
				// add event listener to fix remove button issues due to above hacks
				selectize.on('item_add', function (value, item) {
					let col = item.clone();
					let option  = selectize.getOption(value);
					let type = option.attr('data-type');
					col.appendTo(sortables);
					col.attr('data-type', type);
					if( option.attr('data-header') ) {
						col.children('span:first-child').text( option.attr('data-header') );
					}
					jQuery('<input type="hidden" name="cols[' + value + ']" value="1">').appendTo(col);
				});
				selectize.on('item_remove', function (value) {
					parent.find('.item[data-value="'+ value +'"]').remove();
				});
				parent.on('click', '.em-list-table-cols-selected .item .remove', function(){
					let value = this.parentElement.getAttribute('data-value');
					selectize.removeItem(value, true);
				});
			}
		});
	});
}

function em_unsetup_selectize( container ) {
	container.querySelectorAll('.em-selectize').forEach( function( el ) {
		//extra behaviour for selectize "always open mode"
		if ( 'selectize' in el ) {
			el.selectize.destroy();
		}
	});
}