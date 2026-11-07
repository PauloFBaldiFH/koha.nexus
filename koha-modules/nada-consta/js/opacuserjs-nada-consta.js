/*
 * Koha.Nexus - Nada Consta: botão na conta do leitor.
 *
 * Colar em: Administração > Preferências do sistema > OpacUserJS
 * (conteúdo puro, sem <script>). Só age na página opac-user.pl.
 */
(function () {
    'use strict';

    if (!/opac-user\.pl$/.test(window.location.pathname)) return;
    if (document.getElementById('kn-nada-consta')) return;

    var target = document.querySelector('#usersummary, #opac-user-account, .userSummary, #main');
    if (!target) return;

    var href = window.location.pathname.replace(/opac-user\.pl$/, 'opac-nadaconsta.pl');

    var box = document.createElement('div');
    box.id = 'kn-nada-consta';
    box.style.cssText = 'margin:16px 0;padding:12px;border:1px solid #ccc;border-radius:4px;';

    var text = document.createElement('p');
    text.style.margin = '0 0 8px';
    text.textContent = 'Precisa de uma certidão negativa de débito (Nada Consta)? ' +
        'Ela é emitida só quando não há pendências.';

    var link = document.createElement('a');
    link.href = href;
    link.className = 'btn btn-primary';
    link.textContent = 'Emitir Nada Consta';
    link.setAttribute('role', 'button');

    box.appendChild(text);
    box.appendChild(link);

    if (target.id === 'main') {
        target.insertBefore(box, target.firstChild);
    } else {
        target.parentNode.insertBefore(box, target);
    }
})();
