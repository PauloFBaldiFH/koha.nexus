/**
 * TimePickerJS
 * A jQuery-free implementation of jonthornton/jquery-timepicker
 * with additional support for HTML time elements
 *
 * @author Based on original work by Jon Thornton (https://github.com/jonthornton/jquery-timepicker)
 */

(function(global) {
	'use strict';

	/**
	 * TimePickerJS class
	 */
	class TimePickerJS {
		constructor(element, options = {}) {
			// Store the input element
			this.element = typeof element === 'string' ? document.querySelector(element) : element;

			if (!this.element) {
				throw new Error('TimePickerJS: No element found');
			}

			// Default options
			this.defaults = {
				className: null,
				minTime: null,
				maxTime: null,
				durationTime: null,
				step: 30,
				showDuration: false,
				showOnFocus: true,
				disableTimeRanges: [],
				disableTextInput: false,
				disableTouchKeyboard: false,
				forceRoundTime: false,
				scrollDefault: null,
				selectOnBlur: false,
				typeaheadHighlight: true,
				noneOption: false,
				orientation: 'l',
				timeFormat: 'g:ia',
				dropdown: true,
				dynamicDropdown: false,
				container: document.body,
				useSelect: false,
				closeOnWindowScroll: false,
				appendTo: null,
				useNativeOnMobile: true  // Use native time input on mobile
			};

			// Merge default options with user options
			this.settings = Object.assign({}, this.defaults, options);

			// Initialize variables
			this.selectedValue = null;
			this.list = null;
			this.listCreated = false;
			this.selectedIndex = -1;
			this.isOpen = false;
			this.timeInput = null;  // Reference to native time input if created
			this.originalType = this.element.type; // Store original input type

			// Check if we're on a mobile device
			this.isMobile = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent);

			// Bind methods to instance for event handlers
			this._onFocus = this._onFocus.bind(this);
			this._onBlur = this._onBlur.bind(this);
			this._onInput = this._onInput.bind(this);
			this._onKeydown = this._onKeydown.bind(this);
			this._onClick = this._onClick.bind(this);
			this._onWindowScroll = this._onWindowScroll.bind(this);
			this._onWindowResize = this._onWindowResize.bind(this);
			this._onTimeInputChange = this._onTimeInputChange.bind(this);

			// Initialize the timepicker
			this._init();
		}

		// Add this static method
		static create(selector, options = {}) {
			return TimePickerJSFactory(selector, options);
		}

		/**
		 * Initialize the timepicker
		 * @private
		 */
		_init() {
			// If using native on mobile and is a mobile device
			if (this.settings.useNativeOnMobile && this.isMobile) {
				this._setupNativeTimeInput();
			}

			// Bind event listeners
			this._bindEvents();

			// Set initial value if present
			if (this.element.value) {
				this.setTimeFromString(this.element.value);
			}
		}

		/**
		 * Set up native time input for mobile devices
		 * @private
		 */
		_setupNativeTimeInput() {
			// If it's already a time input, just use it
			if (this.element.type === 'time') {
				this.timeInput = this.element;
				return;
			}

			// Create a time input that's visually hidden but accessible
			this.timeInput = document.createElement('input');
			this.timeInput.type = 'time';
			this.timeInput.className = 'timepickerjs-native-input';

			// Add time input right after the original element
			this.element.parentNode.insertBefore(this.timeInput, this.element.nextSibling);

			// Sync values
			if (this.element.value) {
				// Convert the current value to 24h format for the time input
				const secondsValue = this._timeStringToSeconds(this.element.value);
				if (secondsValue !== null) {
					const hours = Math.floor(secondsValue / 3600);
					const minutes = Math.floor((secondsValue % 3600) / 60);
					this.timeInput.value = `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}`;
				}
			}

			// Listen for changes on the time input
			this.timeInput.addEventListener('change', this._onTimeInputChange);
			this.timeInput.addEventListener('input', this._onTimeInputChange);
		}

		/**
		 * Handle time input change for native mobile time element
		 * @private
		 */
		_onTimeInputChange() {
			if (!this.timeInput || !this.timeInput.value) return;

			// Parse the time from the native input (format: HH:MM)
			const [hours, minutes] = this.timeInput.value.split(':').map(Number);

			// Convert to seconds
			const seconds = (hours * 60 + minutes) * 60;

			// Update the original input with the formatted time
			this.selectedValue = seconds;
			this.element.value = this._formatTime(seconds);

			// Trigger change event
			this._triggerEvent('change');
		}

		/**
		 * Create the dropdown list - now only called when needed
		 * @private
		 */
		_createList() {
			if (this.listCreated) return;

			// Create the dropdown container
			this.list = document.createElement('div');
			this.list.className = 'timepickerjs-list';
			if (this.settings.className) {
				this.list.classList.add(this.settings.className);
			}

			// Style the dropdown with classes only, no inline styles
			this.list.style.display = 'none';

			// Generate time options
			this._generateOptions();

			// Append to the container or document body
			const container = this.settings.appendTo || this.settings.container;
			container.appendChild(this.list);

			this.listCreated = true;
		}

		/**
		 * Generate time options
		 * @private
		 */
		_generateOptions() {
			const startTime = this.settings.minTime ? this._timeStringToSeconds(this.settings.minTime) : 0;
			let endTime = this.settings.maxTime ? this._timeStringToSeconds(this.settings.maxTime) : 24 * 60 * 60 - 1;

			if (endTime <= startTime) {
				endTime += 24 * 60 * 60;
			}

			const step = this.settings.step * 60; // Convert minutes to seconds

			// Clear existing options
			this.list.innerHTML = '';

			// Add "None" option if specified
			if (this.settings.noneOption) {
				const noneItem = document.createElement('div');
				noneItem.className = 'timepickerjs-item';
				noneItem.textContent = typeof this.settings.noneOption === 'string' ? this.settings.noneOption : 'None';
				noneItem.dataset.seconds = '-1';

				// Click handler for "None" option
				noneItem.addEventListener('click', () => {
					this.selectValue(-1);
					this.hideList();
				});

				this.list.appendChild(noneItem);
			}

			// Add time options
			for (let seconds = startTime; seconds <= endTime; seconds += step) {
				// Skip times in disabled ranges
				if (this._isTimeDisabled(seconds)) {
					continue;
				}

				const item = document.createElement('div');
				item.className = 'timepickerjs-item';
				item.dataset.seconds = seconds % (24 * 60 * 60);

				const timeText = this._formatTime(seconds);
				let displayText = timeText;

				if (this.settings.showDuration) {
					const duration = this._formatDuration(seconds - startTime);
					const durationSpan = document.createElement('span');
					durationSpan.className = 'timepickerjs-duration';
					durationSpan.textContent = duration;

					item.textContent = timeText + ' ';
					item.appendChild(durationSpan);
				} else {
					item.textContent = displayText;
				}

				// Click handler
				item.addEventListener('click', () => {
					this.selectValue(item.dataset.seconds);
					this.hideList();
				});

				this.list.appendChild(item);
			}
		}

		/**
		 * Bind event listeners
		 * @private
		 */
		_bindEvents() {
			// If using native time input on mobile, different event handling
			if (this.settings.useNativeOnMobile && this.isMobile && this.timeInput) {
				// Focus on native time input when original is clicked
				this.element.addEventListener('click', (e) => {
					e.preventDefault();
					this.timeInput.focus();
					this.timeInput.click();
				});

				this.element.addEventListener('focus', (e) => {
					e.preventDefault();
					this.timeInput.focus();
					this.timeInput.click();
				});

				return;
			}

			// Standard dropdown behavior
			this.element.addEventListener('click', this._onClick);
			this.element.addEventListener('focus', this._onFocus);
			this.element.addEventListener('blur', this._onBlur);
			this.element.addEventListener('input', this._onInput);
			this.element.addEventListener('keydown', this._onKeydown);

			// Window scroll event
			if (this.settings.closeOnWindowScroll) {
				window.addEventListener('scroll', this._onWindowScroll);
			}

			// Window resize event
			window.addEventListener('resize', this._onWindowResize);
		}

		/**
		 * Click event handler
		 * @private
		 */
		_onClick() {
			if (!this.isOpen) {
				this.showList();
			}
		}

		/**
		 * Focus event handler
		 * @private
		 */
		_onFocus() {
			if (this.settings.showOnFocus && !this.isOpen) {
				this.showList();
			}

			if (this.settings.disableTouchKeyboard) {
				this.element.blur();
			}
		}

		/**
		 * Blur event handler
		 * @private
		 */
		_onBlur(e) {
			// Don't hide the list if it was a click on the list
			if (e.relatedTarget && this.list && (e.relatedTarget === this.list || e.relatedTarget.closest('.timepickerjs-list'))) {
				return;
			}

			setTimeout(() => {
				if (this.settings.selectOnBlur && this.selectedIndex >= 0 && this.list) {
					const items = this.list.querySelectorAll('.timepickerjs-item');
					if (items[this.selectedIndex]) {
						this.selectValue(items[this.selectedIndex].dataset.seconds);
					}
				}
				this.hideList();
			}, 100);
		}

		/**
		 * Input event handler
		 * @private
		 */
		_onInput() {
			if (this.settings.disableTextInput) {
				return;
			}

			this.setTimeFromString(this.element.value);
		}

		/**
		 * Keydown event handler
		 * @private
		 */
		_onKeydown(e) {
			if (!this.listCreated) {
				if (e.key === 'Enter' || e.key === 'ArrowDown' || e.key === 'ArrowUp') {
					this.showList();
					e.preventDefault();
				}
				return;
			}

			if (!this.isOpen) {
				if (e.key === 'Enter' || e.key === 'ArrowDown' || e.key === 'ArrowUp') {
					this.showList();
					e.preventDefault();
				}
				return;
			}

			switch (e.key) {
				case 'Enter':
					if (this.selectedIndex >= 0) {
						const items = this.list.querySelectorAll('.timepickerjs-item');
						if (items[this.selectedIndex]) {
							this.selectValue(items[this.selectedIndex].dataset.seconds);
						}
					}
					this.hideList();
					e.preventDefault();
					break;

				case 'Escape':
					this.hideList();
					e.preventDefault();
					break;

				case 'ArrowDown':
					this.selectedIndex = Math.min(this.selectedIndex + 1, this.list.children.length - 1);
					this.highlightItem(this.selectedIndex);
					this.scrollToItem(this.selectedIndex);
					e.preventDefault();
					break;

				case 'ArrowUp':
					this.selectedIndex = Math.max(this.selectedIndex - 1, 0);
					this.highlightItem(this.selectedIndex);
					this.scrollToItem(this.selectedIndex);
					e.preventDefault();
					break;
			}
		}

		/**
		 * Window scroll event handler
		 * @private
		 */
		_onWindowScroll() {
			if (this.isOpen) {
				this.hideList();
			}
		}

		/**
		 * Window resize event handler
		 * @private
		 */
		_onWindowResize() {
			if (this.isOpen) {
				this.positionList();
			}
		}

		/**
		 * Show the dropdown list
		 * @public
		 */
		showList() {
			// If using native on mobile, defer to native control
			if (this.settings.useNativeOnMobile && this.isMobile && this.timeInput) {
				this.timeInput.focus();
				this.timeInput.click();
				return;
			}

			// Create list if it doesn't exist yet
			if (!this.listCreated) {
				this._createList();
			}

			if (this.isOpen || !this.list) {
				return;
			}

			// Position the list
			this.positionList();

			// Show the list
			this.list.style.display = 'block';
			this.isOpen = true;

			// Highlight the current time if set
			if (this.selectedValue !== null) {
				const items = this.list.querySelectorAll('.timepickerjs-item');
				for (let i = 0; i < items.length; i++) {
					if (parseInt(items[i].dataset.seconds) === this.selectedValue) {
						this.selectedIndex = i;
						this.highlightItem(i);
						this.scrollToItem(i);
						break;
					}
				}
			} else if (this.settings.scrollDefault) {
				const defaultTime = this._timeStringToSeconds(this.settings.scrollDefault);
				const items = this.list.querySelectorAll('.timepickerjs-item');
				for (let i = 0; i < items.length; i++) {
					if (parseInt(items[i].dataset.seconds) >= defaultTime) {
						this.selectedIndex = i;
						this.highlightItem(i);
						this.scrollToItem(i);
						break;
					}
				}
			}

			// Trigger event
			this._triggerEvent('open');
		}

		/**
		 * Hide the dropdown list
		 * @public
		 */
		hideList() {
			if (!this.isOpen || !this.list) {
				return;
			}

			this.list.style.display = 'none';
			this.isOpen = false;

			// Trigger event
			this._triggerEvent('close');
		}

		/**
		 * Position the dropdown list
		 * @public
		 */
		positionList() {
			if (!this.list) return;

			const inputRect = this.element.getBoundingClientRect();
			const scrollTop = window.pageYOffset || document.documentElement.scrollTop;
			const scrollLeft = window.pageXOffset || document.documentElement.scrollLeft;

			this.list.style.position = 'absolute';
			this.list.style.top = `${inputRect.bottom + scrollTop}px`;

			if (this.settings.orientation === 'r') {
				// Align right edge of list with right edge of input
				this.list.style.left = `${inputRect.right - this.list.offsetWidth + scrollLeft}px`;
			} else {
				// Default left alignment
				this.list.style.left = `${inputRect.left + scrollLeft}px`;
			}

			this.list.style.width = `${inputRect.width}px`;
		}

		/**
		 * Highlight a list item
		 * @param {number} index - Index of the item to highlight
		 * @public
		 */
		highlightItem(index) {
			if (!this.list) return;

			const items = this.list.querySelectorAll('.timepickerjs-item');

			// Remove highlight from all items
			items.forEach(item => {
				item.classList.remove('active');
			});

			// Highlight the selected item
			if (index >= 0 && index < items.length) {
				items[index].classList.add('active');
			}
		}

		/**
		 * Scroll to a list item
		 * @param {number} index - Index of the item to scroll to
		 * @public
		 */
		scrollToItem(index) {
			if (!this.list) return;

			const items = this.list.querySelectorAll('.timepickerjs-item');

			if (index >= 0 && index < items.length) {
				const item = items[index];
				const listRect = this.list.getBoundingClientRect();
				const itemRect = item.getBoundingClientRect();

				if (itemRect.top < listRect.top) {
					this.list.scrollTop = this.list.scrollTop - (listRect.top - itemRect.top);
				} else if (itemRect.bottom > listRect.bottom) {
					this.list.scrollTop = this.list.scrollTop + (itemRect.bottom - listRect.bottom);
				}
			}
		}

		/**
		 * Select a time value
		 * @param {number|string} seconds - Time in seconds from midnight
		 * @public
		 */
		selectValue(seconds) {
			seconds = parseInt(seconds);

			if (seconds === -1) {
				// "None" option
				this.element.value = '';
				this.selectedValue = null;

				// Update native time input if present
				if (this.timeInput) {
					this.timeInput.value = '';
				}
			} else {
				this.selectedValue = seconds;
				const formattedTime = this._formatTime(seconds);
				this.element.value = formattedTime;

				// Update native time input if present
				if (this.timeInput) {
					const hours = Math.floor(seconds / 3600);
					const minutes = Math.floor((seconds % 3600) / 60);
					this.timeInput.value = `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}`;
				}
			}

			// Trigger change event
			this._triggerEvent('change');
		}

		/**
		 * Set time from a string
		 * @param {string} timeString - Time string to parse
		 * @public
		 */
		setTimeFromString(timeString) {
			if (!timeString) {
				this.selectedValue = null;

				// Update native time input if present
				if (this.timeInput) {
					this.timeInput.value = '';
				}
				return;
			}

			// Parse the time string to seconds
			const seconds = this._timeStringToSeconds(timeString);

			if (seconds !== null) {
				// Store the seconds value
				this.selectedValue = seconds;

				// Format according to the specified format and update the element's value
				this.element.value = this._formatTime(seconds);

				// Update native time input if present
				if (this.timeInput) {
					const hours = Math.floor(seconds / 3600);
					const minutes = Math.floor((seconds % 3600) / 60);
					this.timeInput.value = `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}`;
				}
			}
		}

		/**
		 * Convert a time string to seconds
		 * @param {string} timeString - Time string to convert
		 * @returns {number|null} - Time in seconds or null if invalid
		 * @private
		 */
		_timeStringToSeconds(timeString) {
			if (!timeString) {
				return null;
			}

			// Handle HH:MM:SS format (00:00:00) - common database/input format
			if (/^\d{1,2}:\d{2}:\d{2}$/.test(timeString)) {
				const [hours, minutes] = timeString.split(':').map(Number);
				return hours * 3600 + minutes * 60;
			}

			// Handle HH:MM format (native time input)
			if (/^\d{1,2}:\d{2}$/.test(timeString)) {
				const [hours, minutes] = timeString.split(':').map(Number);
				return hours * 3600 + minutes * 60;
			}

			// Handle H:MM format (without leading zero)
			if (/^\d{1}:\d{2}$/.test(timeString)) {
				const [hours, minutes] = timeString.split(':').map(Number);
				return hours * 3600 + minutes * 60;
			}

			// Handle 12-hour format with am/pm
			const timeRegex = /(\d+)(?::(\d+))?(?::(\d+))?\s*(am|pm|AM|PM)?/i;
			const match = timeString.toLowerCase().match(timeRegex);

			if (!match) {
				return null;
			}

			let hours = parseInt(match[1]);
			const minutes = match[2] ? parseInt(match[2]) : 0;
			const ampm = match[4];

			if (ampm) {
				if (hours === 12 && ampm.toLowerCase() === 'am') {
					hours = 0;
				} else if (hours !== 12 && ampm.toLowerCase() === 'pm') {
					hours += 12;
				}
			}

			return hours * 3600 + minutes * 60;
		}

		/**
		 * Format seconds into a time string
		 * @param {number} seconds - Time in seconds
		 * @returns {string} - Formatted time string
		 * @private
		 */
		_formatTime(seconds) {
			const totalSeconds = seconds % (24 * 60 * 60);
			const hours = Math.floor(totalSeconds / 3600);
			const minutes = Math.floor((totalSeconds % 3600) / 60);

			// Handle different time formats
			switch (this.settings.timeFormat) {
				case 'g:ia':
					// 12-hour format with am/pm
					const period = hours >= 12 ? 'pm' : 'am';
					const hour12 = hours % 12 || 12;
					return `${hour12}:${minutes.toString().padStart(2, '0')}${period}`;

				case 'g:i A':
					// 12-hour format with AM/PM
					const period2 = hours >= 12 ? 'PM' : 'AM';
					const hour12_2 = hours % 12 || 12;
					return `${hour12_2}:${minutes.toString().padStart(2, '0')} ${period2}`;

				case 'H:i':
					// 24-hour format
					return `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}`;

				case 'h:i A':
					// 12-hour format with leading zero and AM/PM
					const period3 = hours >= 12 ? 'PM' : 'AM';
					const hour12_3 = hours % 12 || 12;
					return `${hour12_3.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')} ${period3}`;

				default:
					// Default 12-hour format
					const period4 = hours >= 12 ? 'pm' : 'am';
					const hour12_4 = hours % 12 || 12;
					return `${hour12_4}:${minutes.toString().padStart(2, '0')}${period4}`;
			}
		}

		/**
		 * Format seconds into a duration string
		 * @param {number} seconds - Duration in seconds
		 * @returns {string} - Formatted duration string
		 * @private
		 */
		_formatDuration(seconds) {
			const hours = Math.floor(seconds / 3600);
			const minutes = Math.floor((seconds % 3600) / 60);

			if (hours > 0) {
				return `${hours}h ${minutes}m`;
			} else {
				return `${minutes}m`;
			}
		}

		/**
		 * Check if a time is in a disabled range
		 * @param {number} seconds - Time in seconds
		 * @returns {boolean} - True if time is disabled
		 * @private
		 */
		_isTimeDisabled(seconds) {
			if (!this.settings.disableTimeRanges || !this.settings.disableTimeRanges.length) {
				return false;
			}

			const timeInSeconds = seconds % (24 * 60 * 60);

			for (const range of this.settings.disableTimeRanges) {
				const startSeconds = this._timeStringToSeconds(range[0]);
				const endSeconds = this._timeStringToSeconds(range[1]);

				if (timeInSeconds >= startSeconds && timeInSeconds < endSeconds) {
					return true;
				}
			}

			return false;
		}

		/**
		 * Trigger a custom event
		 * @param {string} eventName - Name of the event
		 * @private
		 */
		_triggerEvent(eventName) {
			// Create and dispatch a custom event
			const customEvent = new CustomEvent(`timepicker:${eventName}`, {
				bubbles: true,
				detail: {
					time: this.selectedValue,
					formattedTime: this.selectedValue !== null ? this._formatTime(this.selectedValue) : null
				}
			});
			this.element.dispatchEvent(customEvent);

			// Additionally trigger a native event for better compatibility
			if (eventName === 'change') {
				// Create a standard change event
				const changeEvent = new Event('change', { bubbles: true });
				this.element.dispatchEvent(changeEvent);

				// If we have a native time input, also trigger event on it
				if (this.timeInput && this.timeInput !== this.element) {
					this.timeInput.dispatchEvent(new Event('change', { bubbles: true }));
				}
			}
		}

		/**
		 * Get the currently selected time as seconds from midnight
		 * @returns {number|null} - Time in seconds or null if no time selected
		 * @public
		 */
		getTime() {
			return this.selectedValue;
		}

		/**
		 * Get the currently selected time in the specified format
		 * @returns {string|null} - Formatted time string or null if no time selected
		 * @public
		 */
		getFormattedTime() {
			if (this.selectedValue === null) {
				return null;
			}

			return this._formatTime(this.selectedValue);
		}

		/**
		 * Set the time from seconds
		 * @param {number} seconds - Time in seconds from midnight
		 * @public
		 */
		setTime(seconds) {
			this.selectValue(seconds);
		}

		/**
		 * Remove the timepicker and clean up
		 * @public
		 */
		destroy() {
			// Remove dropdown list
			if (this.list && this.list.parentNode) {
				this.list.parentNode.removeChild(this.list);
			}

			// Remove native time input if we created one
			if (this.timeInput && this.timeInput !== this.element && this.timeInput.parentNode) {
				this.timeInput.removeEventListener('change', this._onTimeInputChange);
				this.timeInput.removeEventListener('input', this._onTimeInputChange);
				this.timeInput.parentNode.removeChild(this.timeInput);
			}

			// Remove event listeners
			this.element.removeEventListener('click', this._onClick);
			this.element.removeEventListener('focus', this._onFocus);
			this.element.removeEventListener('blur', this._onBlur);
			this.element.removeEventListener('input', this._onInput);
			this.element.removeEventListener('keydown', this._onKeydown);

			if (this.settings.closeOnWindowScroll) {
				window.removeEventListener('scroll', this._onWindowScroll);
			}

			window.removeEventListener('resize', this._onWindowResize);

			// Remove reference to this instance
			delete this.element._timePickerJS;
		}
	}

	/**
	 * Factory function to create timepicker instances
	 * @param {Element|NodeList|string} selector - DOM element, NodeList, or CSS selector
	 * @param {Object} options - Timepicker options
	 * @returns {TimePickerJS|TimePickerJS[]} - Timepicker instance(s)
	 */
	function TimePickerJSFactory(selector, options = {}) {
		// Handle different types of selectors
		let elements;

		if (typeof selector === 'string') {
			// CSS selector string
			elements = document.querySelectorAll(selector);
		} else if (selector instanceof NodeList || selector instanceof HTMLCollection) {
			// NodeList or HTMLCollection (from querySelectorAll)
			elements = selector;
		} else if (Array.isArray(selector)) {
			// Array of elements
			elements = selector;
		} else {
			// Single DOM element or other
			elements = [selector];
		}

		if (elements.length === 1) {
			const element = elements[0];
			if (element._timePickerJS) {
				return element._timePickerJS;
			}
			const instance = new TimePickerJS(element, options);
			element._timePickerJS = instance;
			return instance;
		} else {
			return Array.from(elements).map(element => {
				if (element._timePickerJS) {
					return element._timePickerJS;
				}
				const instance = new TimePickerJS(element, options);
				element._timePickerJS = instance;
				return instance;
			});
		}
	}

	// Expose TimePickerJS to the global object
	global.TimePickerJS = TimePickerJS;

})(window);