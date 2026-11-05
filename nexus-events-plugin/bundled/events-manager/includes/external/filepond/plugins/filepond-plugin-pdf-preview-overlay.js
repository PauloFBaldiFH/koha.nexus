/*!
 * FilePondPluginPdfPreviewOverlay 1.0.0
 * Author: Pixelite SL
 * Licensed under MIT, https://opensource.org/licenses/MIT/
 * Please visit https://pqina.nl/filepond/ for details.
 */
(function(global, factory) {
	if (typeof exports === 'object' && typeof module !== 'undefined') {
		module.exports = factory();
	} else if (typeof define === 'function' && define.amd) {
		define(factory);
	} else {
		global.FilePondPluginPdfPreviewOverlay = factory();
	}
})(this, function() {
	'use strict';

	const isPdf = (file) => /pdf$/.test(file.type);

	const openPdfOverlay = (item) => {
		const overlay = document.createElement('div');
		overlay.className = 'filepond--fullsize-overlay';

		const iframeContainer = document.createElement('div');
		iframeContainer.className = 'pdf-container';

		const iframe = document.createElement('iframe');
		iframe.src = URL.createObjectURL(item.file);
		iframe.width = '100%';
		iframe.height = '100%';
		iframe.style.border = 'none';

		iframeContainer.appendChild(iframe);
		overlay.appendChild(iframeContainer);
		document.body.appendChild(overlay);

		overlay.addEventListener('click', () => overlay.remove());
	};

	const registerPdfOverlay = (item, el, labelButtonOverlay) => {
		const info = el.querySelector('.filepond--file-info-main');
		const magnifyIcon = document.createElement('span');
		magnifyIcon.className = 'filepond--magnify-icon';
		magnifyIcon.title = labelButtonOverlay;
		info.append(magnifyIcon);

		magnifyIcon.addEventListener('click', () => openPdfOverlay(item));
	};

	const plugin = (fpAPI) => {
		const { addFilter, utils } = fpAPI;
		const { Type, createRoute } = utils;

		addFilter('CREATE_VIEW', (viewAPI) => {
			const { is, view, query } = viewAPI;

			if (!is('file')) return;

			const didLoadItem = ({ root, props }) => {
				const item = query('GET_ITEM', props.id);
				if (!item || item.archived || !isPdf(item.file)) return;

				const labelButtonOverlay = root.query('GET_LABEL_BUTTON_PDF_OVERLAY');
				registerPdfOverlay(item, root.element, labelButtonOverlay);
			};

			const didFileIconRendered = ({ root, action }) => {
				const { id, file, iconElement } = action;
				const item = root.query('GET_ITEM', id);
				if (!item || item.archived || !isPdf(file)) return;

				iconElement.classList.add('clickable');
				iconElement.addEventListener('click', () => openPdfOverlay(item));
			};

			view.registerWriter(
				createRoute({
					DID_LOAD_ITEM: didLoadItem,
					DID_FILE_ICON_RENDERED: didFileIconRendered,
				})
			);
		});

		return {
			options: {
				allowPdfPreviewOverlay: [true, Type.BOOLEAN],
				labelButtonPdfOverlay: ['Open PDF in overlay', Type.STRING],
			},
		};
	};

	if (typeof window !== 'undefined' && typeof window.document !== 'undefined') {
		document.dispatchEvent(new CustomEvent('FilePond:pluginloaded', { detail: plugin }));
	}

	return plugin;
});
