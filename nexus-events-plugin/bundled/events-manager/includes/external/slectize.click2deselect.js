/* Selectize deselect function */
EM_Selectize.define('click2deselect', function(options) {
	var self = this;
	var setup = self.setup;
	this.setup = function() {
		setup.apply(self, arguments);
		// add additional handler
		let just_added;
		self.$dropdown.each( function(){
			// adding direct JS vanilla event to prevent Firefox from firing the click event twice
			this.addEventListener('click', function(e) {
				// check if target is a child of or is the [data-selectable] element
				let target = e.target.matches('.selected[data-selectable]') ? e.target : e.target.closest('.selected[data-selectable]');
				if( target !== null ) {
					let value = target.getAttribute('data-value');
					// ignore click if we just added the item
					if( value !== just_added ) {
						self.removeItem(value);
						self.refreshItems();
						self.refreshOptions();
					}
				}
				// reset temp variable to avoid further click confusion
				just_added = false;
				return false;
			});
		});
		self.on('item_remove', function (value) {
			self.getOption(value).removeClass('selected')
		});
		// save recent added item to temp variable so we can ignore the click event if fired more than once
		self.on('item_add', function (value) {
			just_added = value;
		});
	}
});