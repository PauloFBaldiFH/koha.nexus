// Modal Open/Close
let openModal = function( modal, onOpen = null ){
	modal = jQuery(modal);
	modal.appendTo(document.body);
	setTimeout( function(){
		modal.addClass('active').find('.em-modal-popup').addClass('active');
		jQuery(document).triggerHandler('em_modal_open', [modal]);
		document.dispatchEvent( new CustomEvent('em_modal_open', { detail: { modal: modal } }) );
		if( typeof onOpen === 'function' ){
			setTimeout( onOpen, 200); // timeout allows css transition
		}
	}, 100); // timeout allows css transition
};
let closeModal = function( modal, onClose = null ){
	modal = jQuery(modal);
	modal.removeClass('active').find('.em-modal-popup').removeClass('active');
	setTimeout( function(){
		if( modal.attr('data-parent') ){
			let wrapper = jQuery('#' + modal.attr('data-parent') );
			if( wrapper.length ) {
				modal.appendTo(wrapper);
			}
		}
		modal[0].dispatchEvent( new CustomEvent('em_modal_close', { bubbles: true, detail: { modal: modal } } ) );
		if( typeof onClose === 'function' ){
			onClose();
		}
	}, 500); // timeout allows css transition
}
jQuery(document).on('click', '.em-modal .em-close-modal', function(e){
	let modal = jQuery(this).closest('.em-modal');
	if( !modal.attr('data-prevent-close') ) {
		closeModal(modal);
	}
});
jQuery(document).on('click', '.em-modal', function(e){
	var target = jQuery(e.target);
	if( target.hasClass('em-modal') ) {
		let modal = jQuery(this);
		if( !modal.attr('data-prevent-close') ){
			closeModal(modal);
		}
	}
});

function EM_Alert( content ){
	// find the alert modal, create if not
	let modal = document.getElementById('em-alert-modal');
	if( modal === null ){
		modal = document.createElement('div');
		modal.setAttribute('class', "em pixelbones em-modal");
		modal.id = 'em-alert-modal';
		modal.innerHTML = '<div class="em-modal-popup"><header><a class="em-close-modal"></a><div class="em-modal-title">&nbsp;</div></header><div class="em-modal-content" id="em-alert-modal-content"></div></div>';
		document.body.append(modal);
	}
	document.getElementById('em-alert-modal-content').innerHTML = content;
	openModal(modal);
};