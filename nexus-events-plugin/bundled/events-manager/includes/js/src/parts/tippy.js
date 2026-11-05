function em_setup_tippy( container_element ){
	let container = jQuery(container_element);
	var tooltip_vars = {
		theme : 'light-border',
		appendTo : 'parent',
		content(reference) {
			if( reference.dataset.content ){
				try {
					let content = container[0].querySelector(reference.dataset.content);
					if (content) {
						content.classList.remove('hidden');
						return content;
					}
				} catch ( error ) {
					console.log('Invlid tooltip selector in %o : %o', reference, error);
				}
			};
			return reference.getAttribute('aria-label') ?? reference.title ?? '';
		},
		'touch' : ['hold', 300],
		allowHTML : true,
	};
	jQuery(document).trigger('em-tippy-vars',[tooltip_vars, container]);
	container.find('.em-tooltip').each( ( i, tooltip ) => tippy( tooltip, tooltip_vars ) );
	// Set up Tippy DDMs
	let tippy_ddm_options = {
		theme : 'light-border',
		arrow : false,
		allowHTML : true,
		interactive : true,
		trigger : 'manual',
		placement : 'bottom',
		zIndex : 1000000,
		touch : true,
	};
	jQuery(document).trigger('em-tippy-ddm-vars',[tippy_ddm_options, container]);
	container.find('.em-tooltip-ddm').each( function(){
		let ddm_content, ddm_content_sibling;
		if( this.getAttribute('data-content') ){
			ddm_content = document.getElementById(this.getAttribute('data-content'))
			ddm_content_sibling = ddm_content.previousElementSibling;
		}else{
			ddm_content = this.nextElementSibling;
			ddm_content_sibling = ddm_content.previousElementSibling;
		}
		let tippy_content = document.createElement('div');
		// allow for custom width
		let button_width = this.getAttribute('data-button-width');
		if( button_width ){
			if( button_width == 'match' ){
				tippy_ddm_options.maxWidth = this.clientWidth;
				ddm_content.style.width = this.clientWidth + 'px';
			}else{
				tippy_ddm_options.maxWidth = this.getAttribute('data-button-width');
			}
		}
		tippy_ddm_options.content = tippy_content;
		let tippy_ddm = tippy(this, tippy_ddm_options);
		tippy_ddm.props.distance = 50;
		tippy_ddm.setProps({
			onShow(instance){
				if( instance.reference.getAttribute('data-tooltip-class') ) {
					instance.popper.classList.add( instance.reference.getAttribute('data-tooltip-class') );
				}
				instance.popper.classList.add( 'em-tooltip-ddm-display' );
				tippy_content.append(ddm_content);
				ddm_content.classList.remove('em-tooltip-ddm-content');
			},
			onShown(instance){ // keyboard support
				ddm_content.firstElementChild.focus();
			},
			onHidden(instance){
				if( ddm_content.previousElementSibling !== ddm_content_sibling ) {
					ddm_content_sibling.after(ddm_content);
					ddm_content.classList.add('em-tooltip-ddm-content');
				}
			},
		});
		let tippy_listener = function(e){
			if( e.type === 'keydown' && !(e.which === 13 || e.which === 40) ) return false;
			e.preventDefault();
			e.stopPropagation();
			this._tippy.show();
		}
		this.addEventListener('click', tippy_listener);
		this.addEventListener('keydown', tippy_listener);
		tippy_content.addEventListener('blur', function(){
			tippy_content.hide();
		});
		tippy_content.addEventListener('mouseover', function(){
			ddm_content.firstElementChild.blur();
		});
	});
}

function em_unsetup_tippy( container ) {
	container.querySelectorAll('.em-tooltip-ddm').forEach( function( el ){
		if ( '_tippy' in el ) {
			el._tippy.destroy();
		}
	});
}