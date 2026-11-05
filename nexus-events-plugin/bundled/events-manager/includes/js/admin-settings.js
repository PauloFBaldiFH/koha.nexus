jQuery(document).ready(function($){

	//Meta Box Options
	var open_close = $('<a href="#" style="display:block; float:right; clear:right; margin:10px;">'+EM.open_text+'</a>');
	$('#em-options-title').before(open_close);
	open_close.on('click', function(e){
		e.preventDefault();
		if($(this).text() == EM.close_text){
			$(".postbox").addClass('closed');
			$(this).text(EM.open_text);
		}else{
			$(".postbox").removeClass('closed');
			$(this).text(EM.close_text);
		} 
	});
	$(".postbox > h3").on('click', function(){ $(this).parent().toggleClass('closed'); });
	$(".postbox").addClass('closed');

	//Navigation Tabs
	$('.tabs-active .nav-tab-wrapper .nav-tab').on('click', function(e){
		e.preventDefault();
		el = $(this);
		elid = el.attr('id');
		$('.em-menu-group').hide(); 
		$('.'+ elid).show();
		$(".postbox").addClass('closed');
		open_close.text(EM.open_text);
		// preserve existing :suffix in hash when switching tabs
		let newHash = em_build_settings_hash( { tab: elid.replace(/^em-menu-/, ''), 'section' : false } );
		if( newHash !== window.location.hash ){
			window.location.hash = newHash;
		}
	});
	$('.nav-tab-wrapper .nav-tab').on('click', function(){
		$('.nav-tab-wrapper .nav-tab').removeClass('nav-tab-active').blur();
		$(this).addClass('nav-tab-active');
	});
	let hash = em_get_settings_hash();
	if ( hash.tab ) { //anchor-based navigation
		let current_tab = 'a#em-menu-' + hash.tab;
		$( current_tab ).trigger('click');
		if( hash.section ){
			let section = $("#em-opt-"+ hash.section);
			if( section.length > 0 ){
				section.children('h3').trigger('click');
				$('html, body').animate({ scrollTop: section.offset().top - 30 }); //sends user back to current section
			}
		}
	}else{
		//set to general tab by default, so we can also add clicked subsections
		window.location.hash = "#general";
	}
	$('.nav-tab-link').on('click', function(){ $($(this).attr('rel')).trigger('click'); }); //links to mimick tabs


	//Page Options
	$('input[name="dbem_cp_events_has_archive"]').on('change', function(){ //event archives
		if( $('input:radio[name="dbem_cp_events_has_archive"]:checked').val() == 1 ){
			$('tbody.em-event-archive-sub-options').show();
		}else{
			$('tbody.em-event-archive-sub-options').hide();
		}
	}).trigger('change');
	$('select[name="dbem_events_page"]').on('change', function(){
		if( $('select[name="dbem_events_page"]').val() == 0 ){
			$('tbody.em-event-page-options').hide();
		}else{
			$('tbody.em-event-page-options').show();
		}
	}).trigger('change');
	$('input[name="dbem_cp_locations_has_archive"]').on('change', function(){ //location archives
		if( $('input:radio[name="dbem_cp_locations_has_archive"]:checked').val() == 1 ){
			$('tbody.em-location-archive-sub-options').show();
		}else{
			$('tbody.em-location-archive-sub-options').hide();
		}
	}).trigger('change');
	$('select[name="dbem_search_form_advanced_mode"]').on('change', function(){ //location archives
		if( $(this).val() === 'modal' ){
			$('tbody.em-search-form-advanced-hidden').hide().find('#dbem_search_form_advanced_trigger_yes').prop('checked', true);
		}else{
			$('tbody.em-search-form-advanced-hidden').show();
		}
	}).trigger('change');

	//For rewrite titles
	$('input:radio[name=dbem_disable_title_rewrites]').on('change',function(){
		checked_check = $('input:radio[name=dbem_disable_title_rewrites]:checked');
		if( checked_check.val() == 1 ){
			$('#dbem_title_html_row').show();
		}else{
			$('#dbem_title_html_row').hide();	
		}
	});
	$('input:radio[name=dbem_disable_title_rewrites]').trigger('change');
	//for event grouping
	$('select[name="dbem_event_list_groupby"]').on('change', function(){
		if( $('select[name="dbem_event_list_groupby"]').val() == 0 ){
			$('tr#dbem_event_list_groupby_header_format_row, tr#dbem_event_list_groupby_format_row').hide();
		}else{
			$('tr#dbem_event_list_groupby_header_format_row, tr#dbem_event_list_groupby_format_row').show();
		}
	}).trigger('change');

	//ML Stuff
	$('.em-translatable').on('click', function(){
		$(this).nextAll('.em-ml-options').toggle();
	});

	//radio triggers
	document.querySelectorAll( 'input:is([type="radio"], [type="checkbox"]):is(.em-trigger, .em-untrigger)' ).forEach( el => {
		el.addEventListener( 'change', function ( e ) {
			let input = e.target;
			let condition = input.classList.contains( 'em-trigger' ) ? input.value === '1' : input.value === '0';
			document.querySelectorAll( input.getAttribute( 'data-trigger' ) ).forEach( trigger => {
				let shouldHide = input.value === '' || !condition;
				trigger.classList.toggle( 'hidden', shouldHide );
				if ( trigger.classList.contains('am-af') || trigger.closest('.am-af') ) {
					em_af_apply_submit_state( trigger, shouldHide );
				}
				// unset related values if trigger is false
				let archetype = input.closest('.em-archetype-option')?.dataset.archetype;
				if ( archetype ) {
					trigger.querySelectorAll( '.em-archetype-option[data-archetype="' + archetype + '"]:not(.option-checkboxes) [name]' ).forEach( el => { el.disabled = input.value === '' } );
				}
			} );
		} );
	} );
	document.querySelectorAll( 'input:is([type="checkbox"]):is(.em-trigger, .em-untrigger)' ).forEach( el => {
		el.addEventListener( 'change', function ( e ) {
			let input = e.target;
			let condition = input.classList.contains( 'em-trigger' ) ? input.checked : !input.checked;
			document.querySelectorAll( input.getAttribute( 'data-trigger' ) ).forEach( trigger => {
				let shouldHide = !condition;
				trigger.classList.toggle( 'hidden', shouldHide );
				if ( trigger.classList.contains('am-af') || trigger.closest('.am-af') ) {
					em_af_apply_submit_state( trigger, shouldHide );
				}
			} );
		} );
	} );

	// select triggers
	$('select.em-trigger').on('change', function(e){
		// hide all other option selectors
		let el = $(this)
		el.find('option:not(:selected)').each( function(){
			if( this.getAttribute('data-trigger') ){
				$( this.getAttribute('data-trigger') ).hide();
			}
		});
		if( this.selectedOptions.length > 0  && this.selectedOptions[0].getAttribute('data-trigger') ){
			$( this.selectedOptions[0].getAttribute('data-trigger') ).show();
		}
	}).trigger('change');

	//admin tools confirm
	$('a.admin-tools-db-cleanup').on('click', function( e ){
		if( !confirm(EM.admin_db_cleanup_warning) ){
			e.preventDefault();
			return false;
		}
	});

	// specific triggers
	// geolocation search form default distance options (main & advanced)
	$('input[name="dbem_search_form_geo"],input[name="dbem_search_form_geo_advanced"]').on( 'change', function(){
		let defaults = $('#dbem_search_form_geo_distance_default_row, #dbem_search_form_geo_unit_default_row');
		if ( document.getElementById('dbem_search_form_main_yes').checked && document.getElementById('dbem_search_form_geo_yes').checked ) {
			// just move the current default options to main setting, regardelss where they are
			$('#em-search-form-geo').append( defaults );
		} else {
			if ( document.getElementById('dbem_search_form_geo_advanced_yes').checked ){
				// move to advanced section and show
				$('#em-search-form-geo-advanced').append( defaults );
				$('#em-search-form-geo-advanced tr').show();
			}else{
				// hide all advanced options, because we have no geo searches here
				$('#em-search-form-geo-advanced tr:not(.em-subheader, #dbem_search_form_geo_advanced_row)').hide();
				// append to main, in case not already and hide
				$('#em-search-form-geo').append( defaults );
			}
		}
	}).filter(':checked').first().trigger('change');

	//color pickers
	$('#dbem_category_default_color, #dbem_tag_default_color').wpColorPicker();

	// handle em-archetype-option-default clicks to copy template value to preceding input/textarea
	document.addEventListener( 'click', function ( e ) {
		if ( !e.target.closest( '.em-archetype-option-default' ) ) return;

		let button = e.target.closest( '.em-archetype-option-default' );
		let template = button.querySelector( 'template' );

		if ( template ) {
			let templateValue = template.innerHTML.trim();
			// Find the preceding textarea or input text element
			let target = button.previousElementSibling?.matches( 'textarea, input[type="text"]' ) ? button.previousElementSibling : null;

			if ( target ) {
				if ( target.type === 'text' ) {
					target.value = templateValue;
				} else {
					target.innerHTML = templateValue;
				}
				// Trigger change event in case other handlers need to respond
				target.dispatchEvent( new Event( 'change' ) );
			}
		}
	} );

	// reset admin setting via ajax
	$( '.em-option-resettable' ).on( 'click', function( e ){
		e.preventDefault();
	    let el = $(this);
	    let name = el.attr('data-name');
		let inputs = el.closest('tr').find('input[name="'+name+'"], textarea[name="'+name+'"]');
		if ( document.getElementById('em-options-page')?.dataset.archetype !== 'all' ) {
			let archetype = document.getElementById('em-options-page').dataset.archetype
			inputs = el.closest('tr').find('input[name="em_archetype_options['+archetype+']['+name+']"], textarea[name="em_archetype_options['+archetype+']['+name+']"]');
		}
		$.get({
	        url : EM.ajaxurl,
	        data : {
	            action : 'em_admin_get_option_default',
	            option_name : name,
	            nonce : el.attr('data-nonce'),
	        },
            success : function(data){
                inputs.val(data);
                inputs.prop('disabled', false);
                alert(EM.option_reset);
            },
            beforeSend: function(){
                inputs.prop('disabled', true);
            },
            error : function(){
                inputs.prop('disabled', false);
                alert('Error - could not revert.');
            },
	        dataType: 'text',
	    })
	});

    // Disable hidden formatting fields so they're not POSTed. Some hosting
    // WAFs (Hostinger, SiteGround, Wordfence) flag raw HTML template POSTs
    // as XSS payloads. Hidden = unchanged = nothing to submit.
    let em_af_apply_submit_state = function( container, shouldHide ){
        container.querySelectorAll('input[name], textarea[name], select[name]').forEach( el => {
            el.disabled = shouldHide;
        });
    };

    let af_toggle_action = function( af ){
        const am = af.find('input').val();
        if( am === '0' ){
            $('.am-af').addClass('hidden');
            document.querySelectorAll('.am-af').forEach( el => em_af_apply_submit_state(el, true) );
        }else if( am === '1' ){
            $('.am-af').removeClass('hidden');
            document.querySelectorAll('.am-af').forEach( el => em_af_apply_submit_state(el, false) );
            $('.dbem_advanced_formatting_modes_row').show(); // show toggles
	        // trigger radio and chckboxes with triggers to show/hide based on selected archetype
	        let selectorBase = archetype === 'all' ? '.am-af .em-default-option' : '.am-af .em-archetype-option[data-archetype="' + archetype +'"]';
	        document.querySelectorAll( selectorBase + ' input:is([type="radio"], ' + selectorBase + '[type="checkbox"]):is(.em-trigger, .em-untrigger):checked' ).forEach( el => {
		        el.dispatchEvent( new Event( 'change' ) );
	        });
        }else{
            $('.am-af').removeClass('hidden') // show everything
            document.querySelectorAll('.am-af').forEach( el => em_af_apply_submit_state(el, false) );
            $('.dbem_advanced_formatting_modes_row').hide().find('input[type="radio"]').attr('data-trigger', false); // hide toggles
	        $('.am-af [name]:disabled').prop('disabled', false);
        }
        af.find('.em-af-toggle, .em-af-status span').hide();
        af.find('.em-af-toggle.show-'+ am).show();
        af.find('.em-af-status-'+ am).show();
        if( af.find('.em-af-status').attr('data-status') != am ){
            af.find('.em-af-status .em-af-status-save').show();
        }else{
            af.find('.em-af-status .em-af-status-save').hide();
        }
    };
	$('.em-af-toggle').on('click', function(e){
	    e.preventDefault();
		let af = $( e.target.closest('.em-advanced-formatting') );
        af.find('input').val( this.getAttribute('data-set-status') );
        af_toggle_action( af );
	});

	let archetype = document.getElementById('em-options-page').dataset.archetype;
	if ( archetype === 'all' ) {
		af_toggle_action( $('#em-opt-advanced-formatting .em-advanced-formatting.em-default-option') );
	} else {
		af_toggle_action( $('#em-opt-advanced-formatting .em-advanced-formatting.em-archetype-option[data-archetype="'+archetype+'"]') );
	}

    if( typeof EM.admin === 'object' && 'settings' in EM.admin ){
        tippy( $('.dbem_advanced_formatting_modes_row th').toArray(), {
            content : EM.admin.settings.option_override_tooltip,
        });
    }

    // code editor for formats section
    if( 'codeEditor' in wp ){
        let codeEditorToggled = Cookies.get('em_codeEditor');
        let toggle = document.getElementById('em-enable-codeEditor');
        if( toggle ){
            toggle.checked = codeEditorToggled != 1;
            toggle.addEventListener('change', function(e){
                let checked = !e.target.checked ? 1:0;
                Cookies.set('em_codeEditor', checked);
            });
        }

        var editorSettings = wp.codeEditor.defaultSettings ? _.clone( wp.codeEditor.defaultSettings ) : {};
        editorSettings.codemirror = _.extend( {}, editorSettings.codemirror, {
                autofocus: true,
        });
        $('.em-menu-formats textarea').on('focus', function(){
            if( document.getElementById('em-enable-codeEditor').checked ){
                var editor = wp.codeEditor.initialize( this, editorSettings );
                editor.codemirror.on('blur', function( cm ){
                    cm.toTextArea();
                })
            }
        });
    }

	// MultiSite Stuff
	//events
	$('input[name="dbem_ms_global_events"]').on('change', function(){
		if( $('input:radio[name="dbem_ms_global_events"]:checked').val() == 1 ){
			$("tr#dbem_ms_global_events_links_row").show();
			$('input:radio[name="dbem_ms_global_events_links"]:checked').trigger('change');
		}else{
			$("tr#dbem_ms_global_events_links_row, tr#dbem_ms_events_slug_row").hide();
		}
	}).first().trigger('change');
	$('input[name="dbem_ms_global_events_links"]').on('change', function(){
		if( $('input:radio[name="dbem_ms_global_events_links"]:checked').val() == 1 ){
			$("tr#dbem_ms_events_slug_row").hide();
		}else{
			$("tr#dbem_ms_events_slug_row").show();
		}
	}).first().trigger('change');
	//locations
	$('input[name="dbem_ms_mainblog_locations"]').on('change', function(){
		if( $('input:radio[name="dbem_ms_mainblog_locations"]:checked').val() == 1 ){
			$("tbody.em-global-locations").hide();
		}else{
			$("tbody.em-global-locations").show();
		}
	}).first().trigger('change');
	$('input[name="dbem_ms_global_locations"]').on('change', function(){
		if( $('input:radio[name="dbem_ms_global_locations"]:checked').val() == 1 ){
			$("tr#dbem_ms_global_locations_links_row").show();
			$('input:radio[name="dbem_ms_global_locations_links"]:checked').trigger('change');
		}else{
			$("tr#dbem_ms_global_locations_links_row, tr#dbem_ms_locations_slug_row").hide();
		}
	}).first().trigger('change');
	$('input[name="dbem_ms_global_locations_links"]').on('change', function(){
		if( $('input:radio[name="dbem_ms_global_locations_links"]:checked').val() == 1 ){
			$("tr#dbem_ms_locations_slug_row").hide();
		}else{
			$("tr#dbem_ms_locations_slug_row").show();
		}
	});
	//MS Mode selection hiders
	$('input[name="dbem_ms_global_table"]').on('change', function(){ //global
		if( $('input:radio[name="dbem_ms_global_table"]:checked').val() == 1 ){
			$("tbody.em-global-options").show();
			$('input:radio[name="dbem_ms_mainblog_locations"]:checked').trigger('change');
		}else{
			$("tbody.em-global-options").hide();
		}
	}).first().trigger('change');
});

jQuery(document).on('em_javascript_loaded', function(){
	let settings = document.getElementById('em-phone-settings');
	let phoneContainer = document.getElementById('em-phone-example-container');
	let phone = document.getElementById('em-phone-example');
	let options = {};
	let selectItems = {
		'dbem_phone_default_country' : 'initialCountry',
		'dbem_phone_countries_include[]': 'onlyCountries',
		'dbem_phone_countries_exclude[]': 'excludeCountries'
	};
	const reset = function(){
		let iti = EM.intlTelInput.getInstance(phone);
		if( iti ) iti.destroy();
		// rebuild arrays so they have fresh values not referenced
		for ( const [key, opt] of Object.entries(selectItems) ) {
			let value = settings.querySelector('select[name="' + key + '"]').selectize.getValue();
			options[opt] = JSON.parse(JSON.stringify(value));
		}
		em_setup_phone_inputs( phoneContainer, options );
	}
	for ( const [key, opt] of Object.entries(selectItems) ) {
		settings?.querySelector('select[name="' + key + '"]')?.selectize.on('change', reset);
	}
	let boolItems = {
		'dbem_phone_national_format' : 'nationalMode',
		'dbem_phone_show_selected_code' : 'separateDialCode',
		'dbem_phone_show_flags' : 'showFlags',
		'dbem_phone_detect' : 'detectJS',
	};
	for ( const [key, opt] of Object.entries(boolItems) ) {
		settings?.querySelectorAll('[name="' + key + '"]').forEach((el) => {
			el.addEventListener('click', (e) => {
				options[opt] = e.target.value === '1';
				reset();
			})
		});
	}
});



/*! js-cookie v3.0.1 | MIT */
!function(e,t){"object"==typeof exports&&"undefined"!=typeof module?module.exports=t():"function"==typeof define&&define.amd?define(t):(e=e||self,function(){var n=e.Cookies,o=e.Cookies=t();o.noConflict=function(){return e.Cookies=n,o}}())}(this,(function(){"use strict";function e(e){for(var t=1;t<arguments.length;t++){var n=arguments[t];for(var o in n)e[o]=n[o]}return e}return function t(n,o){function r(t,r,i){if("undefined"!=typeof document){"number"==typeof(i=e({},o,i)).expires&&(i.expires=new Date(Date.now()+864e5*i.expires)),i.expires&&(i.expires=i.expires.toUTCString()),t=encodeURIComponent(t).replace(/%(2[346B]|5E|60|7C)/g,decodeURIComponent).replace(/[()]/g,escape);var c="";for(var u in i)i[u]&&(c+="; "+u,!0!==i[u]&&(c+="="+i[u].split(";")[0]));return document.cookie=t+"="+n.write(r,t)+c}}return Object.create({set:r,get:function(e){if("undefined"!=typeof document&&(!arguments.length||e)){for(var t=document.cookie?document.cookie.split("; "):[],o={},r=0;r<t.length;r++){var i=t[r].split("="),c=i.slice(1).join("=");try{var u=decodeURIComponent(i[0]);if(o[u]=n.read(c,u),e===u)break}catch(e){}}return e?o[e]:o}},remove:function(t,n){r(t,"",e({},n,{expires:-1}))},withAttributes:function(n){return t(this.converter,e({},this.attributes,n))},withConverter:function(n){return t(e({},this.converter,n),this.attributes)}},{attributes:{value:Object.freeze(o)},converter:{value:Object.freeze(n)}})}({read:function(e){return'"'===e[0]&&(e=e.slice(1,-1)),e.replace(/(%[\dA-F]{2})+/gi,decodeURIComponent)},write:function(e){return encodeURIComponent(e).replace(/%(2[346BF]|3[AC-F]|40|5[BDE]|60|7[BCD])/g,decodeURIComponent)}},{path:"/"})}));

function em_get_settings_hash() {
	let hash = {
		tab: 'general',
		section: '',
		archetype: false,
	}
	let base = window.location.hash ? window.location.hash.substring(1) : '';
	let plusParts = base.split('+');
	if ( plusParts.length > 1 ) {
		hash.tab = plusParts[0];
	}
	let colonParts = plusParts.length > 1 ? plusParts[1].split(':') : base.split(':');
	if ( colonParts.length > 1 ) {
		if( plusParts.length === 1 ) {
			hash.tab = colonParts[0];
		} else {
			hash.section = colonParts[0];
		}
		hash.archetype = colonParts[1];
	} else if ( plusParts.length > 1 ) {
		hash.section = plusParts[1];
	} else {
		hash.tab = base;
	}
	return hash;
}

function em_build_settings_hash( hash = {}, base = null ) {
	if ( !base ) {
		base = em_get_settings_hash();
	}
	let newHash = '#' + ( hash.tab ? hash.tab : base.tab );
	if ( hash.section || hash.section === false ) {
		if ( hash.section !== false ) {
			newHash = newHash + '+' + hash.section;
		}
	} else if ( base.section ) {
		newHash = newHash + '+' + base.section;
	}
	if ( hash.archetype || hash.archetype === false ) {
		if ( hash.archetype !== 'all' && hash.archetype !== false ) {
			newHash = newHash + ':' + hash.archetype;
		}
	} else if ( base.archetype ) {
		if ( base.archetype !== 'all' ) {
			newHash = newHash + ':' + base.archetype;
		}
	}
	return newHash;
}


// ----- Native JS additions for archetype and hash behavior -----
(function(){

	function toggleArchetype( archetype = null ) {
		// get archetype from URL if not supplied
		let hash = em_get_settings_hash();
		if ( archetype ) {
			let newHash = em_build_settings_hash( { archetype: archetype }, hash );
			if ( window.location.hash !== newHash ) {
				window.location.hash =  newHash;
			}
		} else {
			archetype = hash.archetype || 'all';
		}
		let page = document.getElementById('em-options-page');
		if ( page && page.dataset.archetypeMode === 'merged' ) {
			if ( archetype !== page.dataset.archetype ) {
				// show archetype options
				page.dataset.archetype = archetype;
				// set current archetype link
				page.querySelectorAll( '.em-archetype-tabs.subsubsub a' ).forEach( ( a ) => {
					a.classList.toggle( 'current', a.dataset.archetype === archetype );
				} );
				// find first available tab and click it
				if ( archetype !== 'all' ) {
					if ( page.querySelectorAll( '.tabs-active .nav-tab-wrapper .nav-tab.nav-tab-active.has-archetype-option-' + archetype ).length === 0 ) {
						page.querySelector( '.tabs-active .nav-tab-wrapper .nav-tab.has-archetype-option-' + archetype )?.dispatchEvent( new Event( 'click' ) );
					}
				}
			}
		} else {
			// remove archetype selector
			page.querySelector( '.em-archetype-tabs.subsubsub' )?.remove();
			// find first available tab and click it
			archetype = page.dataset.archetype;
			if ( archetype === 'all' ) {
				// remove all archetypes options from the dom
				page.querySelectorAll( '.em-archetype-options' ).forEach( ( el ) => el.remove() );
			} else {
				// find first available tab and click it
				if ( page.querySelectorAll( '.tabs-active .nav-tab-wrapper .nav-tab.nav-tab-active.has-archetype-option-' + archetype ).length === 0 ) {
					page.querySelector( '.tabs-active .nav-tab-wrapper .nav-tab.has-archetype-option-' + archetype )?.dispatchEvent( new Event( 'click' ) );
				}
				// remove all other archetype options, including main archetype options
				page.querySelectorAll('[name]').forEach( el => {
					if ( !el.closest('.em-archetype-option[data-archetype="' + archetype + '"]') && !el.matches('p.submit > input') ) {
						el.remove();
					}
				});
				page.querySelector('[name="_wpnonce"]').disabled = false;
			}
			// set the nonce so we can save

		}
		// trigger radio and chckboxes with triggers to show/hide based on selected archetype
		let selectorBase = archetype === 'all' ? '.em-default-option' : '.em-archetype-option[data-archetype="' + archetype +'"]';
		document.querySelectorAll( selectorBase + ' input:is([type="radio"], ' + selectorBase + ' [type="checkbox"]):is(.em-trigger, .em-untrigger):checked' ).forEach( el => {
			el.dispatchEvent( new Event( 'change' ) );
		});
	}

	// Utility to parse and apply archetype from the current URL hash
	function emUpdateArchetypeFromHash(){
		let hash = em_get_settings_hash();
		let archetype = hash.archetype || 'all';
		document.getElementById('em-options-page')?.setAttribute('data-archetype', archetype);
		document.querySelectorAll('#em-options-page .em-archetype-tabs.subsubsub a').forEach( (a) => {
			a.classList.toggle( 'current', a.dataset.archetype === archetype );
		});
	}

	// Modify hash to include/replace section (+section), preserving colon suffix
	function emSetSectionInHash( sectionIdPart ){
		let newHash = em_build_settings_hash( { section: sectionIdPart } );
		if ( window.location.hash !== newHash ) {
			window.location.hash = newHash;
		}
	}

	// Handle clicks on archetype tabs to set colon suffix
	function onArchetypeClick(e){
		let a = e.target.closest('.em-archetype-tabs.subsubsub a');
		// get current archetype
		let archetype = a?.dataset.archetype;
		if( archetype ) {
			toggleArchetype( archetype );
		}
	}

	function onPostboxHeaderClick(e){
		var h3 = e.target.closest('.postbox > h3');
		if(!h3) return;
		var postbox = h3.parentElement;
		if(!postbox || !postbox.id) return;
		var sectionIdPart = postbox.id.replace(/^em-opt-/, '');
		// Persist section in hash similar to submit behavior
		emSetSectionInHash(sectionIdPart);
	}

	// Scan the page and annotate ancestors and tabs based on archetype option presence
	function setupArchetypeClasses(){
		try{
			document.querySelectorAll('.em-archetype-options').forEach(function(container){
				var targets = [];
				var group = container.closest('div.em-menu-group');
				var postbox = container.closest('div.postbox');
				var table = container.closest('table');
				var tbody = container.closest('tbody');
				var tr = container.closest('tr');
				[group, postbox, table, tbody, tr].forEach(function(el){ if(el && targets.indexOf(el) === -1) targets.push(el); });
				// Find related nav tab based on em-menu-* class on the group
				var navTab = null;
				if(group){
					var cls = Array.prototype.find.call(group.classList, function(c){ return c.indexOf('em-menu-') === 0; });
					if(cls){
						var sel = '#em-options-page #' + cls + '.nav-tab';
						navTab = document.querySelector(sel);
					}
				}
				if (navTab) {
					targets.push(navTab);
				}
				// add groups to targets as well
				if ( tbody && tbody.dataset.group ) {
					document.querySelectorAll('tbody[data-group="' + tbody.dataset.group + '"]').forEach( el => {
						if ( tbody !== el ) {
							targets.push( el )
						}
					});
				}
				// Mark presence of archetype options
				targets.forEach(function(el){ el.classList.add('has-archetype-options'); });
				// For each specific archetype within, add its class to all targets
				container.querySelectorAll('.em-archetype-option[data-archetype]').forEach( function( item ){
					targets.forEach( el => el.classList.add('has-archetype-option-' + item.dataset.archetype) );
				});
			});
		}catch(err){ console.log(err) }
	}

	document.addEventListener('DOMContentLoaded', function(){
		// run archetype option scanner
		setupArchetypeClasses();
		// initialize archetype from current URL
		toggleArchetype();
		// Delegate clicks for archetype tabs
		document.addEventListener('click', onArchetypeClick, false);
		// Add click listeners for postbox headers
		document.addEventListener('click', onPostboxHeaderClick, false);
		// trigger checkboxes and default value functionality
		document.querySelectorAll( '.em-archetype-options .option-checkboxes' ).forEach( checkboxes => {
			checkboxes.addEventListener( 'click', ( e ) => {
				if ( e.target.matches( 'button.em-archetype-checkbox-default' ) || ( e.target === checkboxes && checkboxes.dataset.default === '' ) ) {
					checkboxes.dataset.default = ''; // add the
					checkboxes.querySelectorAll( 'input[type="checkbox"]' ).forEach( cb => {
						cb.checked = cb.dataset.default;
						cb.disabled = true;
					} );
					e.target.disabled = true;
					checkboxes.querySelector( 'button.em-archetype-checkbox-override' ).disabled = false;
				} else if ( e.target.matches( 'button.em-archetype-checkbox-override' ) || e.target === checkboxes ) {
					if ( checkboxes.dataset.default === '' ) {
						delete checkboxes.dataset.default;
						checkboxes.querySelectorAll( 'input[type="checkbox"]' ).forEach( cb => {
							cb.disabled = false;
							cb.checked = cb.dataset.default === '';
						} );
						checkboxes.querySelector( 'button.em-archetype-checkbox-default' ).disabled = false;
						e.target.disabled = true;
					}
				}
			});
			checkboxes.dispatchEvent( new Event( 'click' ) );
		});
	});

	window.addEventListener('hashchange', () => toggleArchetype() , false);
})();
