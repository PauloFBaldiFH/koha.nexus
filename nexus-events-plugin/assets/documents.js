/* Local QR rendering: no external image service, camera access or automatic check-in. */
(function () {
  'use strict';
  document.querySelectorAll('[data-qr]').forEach(function (element) {
    if (typeof qrcode !== 'function') return;
    var code = qrcode(0, 'M');
    code.addData(element.getAttribute('data-qr'), 'Byte');
    code.make();
    element.innerHTML = code.createSvgTag({cellSize: 4, margin: 16, scalable: true});
    var svg = element.querySelector('svg');
    if (svg) { svg.setAttribute('role', 'img'); svg.setAttribute('aria-label', 'QR code'); }
  });
  document.querySelectorAll('[data-print]').forEach(function (button) {
    button.addEventListener('click', function () { window.print(); });
  });
}());
