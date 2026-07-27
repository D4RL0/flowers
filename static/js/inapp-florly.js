(function () {
  const body = document.body;
  const sidebar = document.getElementById('sidebar');
  const desktopButton = document.getElementById('sidebarToggle');
  const mobileButton = document.getElementById('menuToggle');
  const overlay = document.getElementById('sidebarOverlay');

  document.querySelectorAll('.side-link, .module-toggle').forEach(function (item) {
    Array.from(item.childNodes).forEach(function (node) {
      if (node.nodeType !== Node.TEXT_NODE || !node.textContent.trim()) return;
      const label = document.createElement('span');
      label.className = 'nav-text';
      label.textContent = node.textContent.trim();
      node.replaceWith(label);
    });
  });

  if (localStorage.getItem('florly-sidebar') === 'collapsed' && window.innerWidth >= 992) {
    body.classList.add('sidebar-collapsed');
  }

  desktopButton?.addEventListener('click', function () {
    body.classList.toggle('sidebar-collapsed');
    localStorage.setItem('florly-sidebar', body.classList.contains('sidebar-collapsed') ? 'collapsed' : 'expanded');
  });

  mobileButton?.addEventListener('click', function () {
    sidebar?.classList.toggle('open');
    overlay?.classList.toggle('show', sidebar?.classList.contains('open'));
  });

  overlay?.addEventListener('click', function () {
    sidebar?.classList.remove('open');
    overlay.classList.remove('show');
  });

  document.addEventListener('click', function (event) {
    if (window.innerWidth >= 992 || !sidebar?.classList.contains('open')) return;
    if (!sidebar.contains(event.target) && !mobileButton?.contains(event.target)) {
      sidebar.classList.remove('open');
      overlay?.classList.remove('show');
    }
  });
})();
