/*
 * On GitHub Pages the address looks like  <user>.github.io/<repo>/ .
 * Point every "GitHub" link at that repository, so the links stay right
 * even if the repository is renamed or forked.
 */
(function () {
  'use strict';

  var host = location.hostname.match(/^([\w-]+)\.github\.io$/i);
  var repo = location.pathname.split('/')[1];
  if (!host || !repo) return;

  var base = 'https://github.com/' + host[1] + '/' + repo;
  var links = document.querySelectorAll('[data-repo-link]');
  for (var i = 0; i < links.length; i++) {
    links[i].href = base + (links[i].getAttribute('data-repo-path') || '');
  }
})();
