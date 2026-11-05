(function($){
	$(function(){
		var $table = $('#em-archetypes-select');
		if( !$table.length ) return;

		function setDefaultToSingleChecked(){
			var $checked = $table.find('tbody input[type="checkbox"]:checked');
			if( $checked.length === 1 ){
				$checked.closest('tr').find('input[type="radio"]').prop('checked', true);
			}
		}

		$table.on('change', 'tbody input[type="checkbox"]', function(){
			var $row = $(this).closest('tr');
			if( !this.checked ){
				// if this row was default, and now unchecked, pick a new default if exactly one remains
				var wasDefault = $row.find('input[type="radio"]').is(':checked');
				if( wasDefault ){
					var $remaining = $table.find('tbody input[type="checkbox"]:checked');
					if( $remaining.length === 1 ){
						$remaining.closest('tr').find('input[type="radio"]').prop('checked', true);
					}else if( $remaining.length === 0 ){
						$table.find('tbody input[type="radio"]').prop('checked', false);
					}
				}
			}
			setDefaultToSingleChecked();
		});

		// selecting a default should also ensure the checkbox is ticked
		$table.on('change', 'tbody input[type="radio"]', function(){
			$(this).closest('tr').find('input[type="checkbox"]').prop('checked', true);
		});

		// on load: if no default selected and only one is checked, set it as default
		if( !$table.find('tbody input[type="radio"]:checked').length ){
			setDefaultToSingleChecked();
		}
	});
})(jQuery);
