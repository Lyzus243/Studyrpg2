/* StudyRPG "Journey" theme helper
   1. Adds the phone navigation (top bar, bottom tab bar, "More" sheet)
   2. Fixes leftover dark panels / light text from older page styles
   3. Wraps wide tables so they scroll instead of breaking the layout   */
(function () {
  'use strict';

  var APP_ROUTES = ['/dashboard', '/inventory', '/analytics', '/badges', '/leveling', '/skills', '/quests',
    '/pomodoro', '/memory', '/shop', '/groups', '/battles/group', '/ai-tools', '/leaderboard', '/flashcards',
    '/practice-test', '/memory-training', '/concepts'];
  var path = location.pathname.replace(/\/+$/, '') || '/';
  var isApp = APP_ROUTES.some(function (r) { return path === r || path.indexOf(r + '/') === 0; }) || path.indexOf('/profile/') === 0;
  var isAdmin = path.indexOf('/admin') === 0;

  var ICONS = {
    home: '<path d="M3 11l9-8 9 8"/><path d="M5 10v10h14V10"/>',
    scroll: '<path d="M8 3h11v14a3 3 0 01-3 3H6a3 3 0 01-3-3v-2h13"/><path d="M8 3v12"/>',
    chart: '<path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/>',
    user: '<circle cx="12" cy="8" r="4"/><path d="M4 21c0-4 4-6 8-6s8 2 8 6"/>',
    more: '<circle cx="5" cy="12" r="1.5"/><circle cx="12" cy="12" r="1.5"/><circle cx="19" cy="12" r="1.5"/>',
    box: '<path d="M21 8l-9-5-9 5v8l9 5 9-5z"/><path d="M3 8l9 5 9-5M12 13v8"/>',
    users: '<circle cx="9" cy="8" r="3.5"/><path d="M2 20c0-3.5 3-5.5 7-5.5s7 2 7 5.5"/><path d="M16 4.5a3.5 3.5 0 010 7M18 14.5c2.5.6 4 2.3 4 5"/>',
    store: '<path d="M3 9l1.5-5h15L21 9"/><path d="M3 9a3 3 0 006 0 3 3 0 006 0 3 3 0 006 0"/><path d="M5 12v8h14v-8"/>',
    trophy: '<path d="M7 4h10v5a5 5 0 01-10 0z"/><path d="M7 6H4v2a3 3 0 003 3M17 6h3v2a3 3 0 01-3 3M12 14v4M8 21h8"/>',
    up: '<path d="M3 17l6-6 4 4 8-8"/><path d="M15 7h6v6"/>',
    tree: '<circle cx="12" cy="5" r="2.5"/><circle cx="6" cy="18" r="2.5"/><circle cx="18" cy="18" r="2.5"/><path d="M12 7.5V12M12 12l-6 3.5M12 12l6 3.5"/>',
    medal: '<circle cx="12" cy="15" r="5"/><path d="M8.5 3l3.5 7 3.5-7"/>',
    brain: '<path d="M9 4a3 3 0 00-3 3v.5A3 3 0 004 10.5a3 3 0 001 2.2A3 3 0 007 17a3 3 0 005 1.5V5.5A2.5 2.5 0 009 4z"/><path d="M15 4a3 3 0 013 3v.5a3 3 0 012 3 3 3 0 01-1 2.2A3 3 0 0117 17a3 3 0 01-5 1.5"/>',
    timer: '<circle cx="12" cy="13" r="8"/><path d="M12 9v4l3 2M9 2h6"/>',
    bot: '<rect x="4" y="8" width="16" height="12" rx="3"/><path d="M12 4v4M9 13v2M15 13v2"/>',
    cards: '<rect x="3" y="6" width="14" height="14" rx="2"/><path d="M7 3h13a1 1 0 011 1v13"/>',
    sword: '<path d="M14 4l6-1-1 6-9 9-3-3z"/><path d="M6 15l-3 3 3 3 3-3"/>',
    out: '<path d="M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4M16 17l5-5-5-5M21 12H9"/>'
  };
  function svg(name) { return '<svg viewBox="0 0 24 24" aria-hidden="true">' + (ICONS[name] || '') + '</svg>'; }

  /* ---------- 1. Navigation ---------- */
  function username() {
    var a = document.querySelector('a[href^="/profile/"]');
    var name = a ? decodeURIComponent(a.getAttribute('href').split('/profile/')[1] || '') : '';
    if (!name && path.indexOf('/profile/') === 0) name = decodeURIComponent(path.split('/profile/')[1] || '');
    try {
      if (name) localStorage.setItem('j_username', name);
      else name = localStorage.getItem('j_username') || '';
    } catch (e) {}
    return name;
  }

  function isActive(href) {
    if (href === '/dashboard') return path === '/dashboard';
    return path === href || path.indexOf(href + '/') === 0 || (href.indexOf('/profile/') === 0 && path.indexOf('/profile/') === 0);
  }

  function doLogout() {
    if (typeof window.logout === 'function') { window.logout(); return; }
    try { localStorage.removeItem('access_token'); sessionStorage.removeItem('access_token'); } catch (e) {}
    location.href = '/login';
  }

  function buildNav() {
    if (!(isApp || isAdmin) || document.querySelector('.j-tabbar')) return;
    var me = username();
    var profileHref = me ? '/profile/' + encodeURIComponent(me) : '/dashboard';

    var adminSide = isAdmin ? [].slice.call(document.querySelectorAll('.sidebar .sidebar-btn')) : [];
    var ADMIN_ICONS = { shop: 'store', quests: 'scroll', users: 'users', groups: 'users', boss: 'sword', broadcast: 'bot', feedback: 'chart', settings: 'tree' };
    function adminIcon(el) {
      var l = (el.textContent || '').trim().toLowerCase();
      for (var k in ADMIN_ICONS) if (l.indexOf(k) === 0) return ADMIN_ICONS[k];
      return 'box';
    }
    var tabs = isAdmin
      ? adminSide.slice(0, 3).map(function (el, i) { return [el.textContent.trim(), '#', adminIcon(el), i]; })
      : [['Home', '/dashboard', 'home'], ['Quests', '/quests', 'scroll'], ['Progress', '/analytics', 'chart'], ['Profile', profileHref, 'user']];

    var bar = document.createElement('nav');
    bar.className = 'j-tabbar';
    bar.setAttribute('aria-label', 'Main navigation');
    bar.innerHTML = tabs.map(function (t) {
      var tag = isAdmin ? 'button type="button" data-admin="' + t[3] + '"' : 'a href="' + t[1] + '"';
      var end = isAdmin ? 'button' : 'a';
      return '<' + tag + ' class="j-tab' + (!isAdmin && isActive(t[1]) ? ' is-active' : '') + '">' + svg(t[2]) + '<span>' + t[0] + '</span></' + end + '>';
    }).join('') + '<button class="j-tab j-more" type="button" aria-haspopup="dialog" aria-expanded="false">' + svg('more') + '<span>More</span></button>';

    var links = isAdmin
      ? adminSide.map(function (el, i) { return [el.textContent.trim(), '#', adminIcon(el), i]; })
      : [
      ['Inventory', '/inventory', 'box'], ['Study Group', '/groups', 'users'], ['Shop', '/shop', 'store'],
      ['Leaderboard', '/leaderboard', 'trophy'], ['Leveling', '/leveling', 'up'], ['Skills', '/skills', 'tree'],
      ['Badges', '/badges', 'medal'], ['Memory', '/memory', 'brain'], ['Pomodoro', '/pomodoro', 'timer'],
      ['AI Tools', '/ai-tools', 'bot'], ['Flashcards', '/flashcards', 'cards'], ['Boss Battles', '/battles/group', 'sword']
    ];
    var scrim = document.createElement('div');
    scrim.className = 'j-drawer-scrim'; scrim.hidden = true;
    var drawer = document.createElement('div');
    drawer.className = 'j-drawer'; drawer.setAttribute('role', 'dialog'); drawer.setAttribute('aria-label', 'All pages');
    drawer.innerHTML = '<div class="j-grab"></div><h4>' + (isAdmin ? 'Admin menu' : 'Explore') + '</h4><div class="j-drawer-grid">' +
      links.map(function (l) {
        return isAdmin
          ? '<button type="button" data-admin="' + l[3] + '">' + svg(l[2]) + '<span>' + l[0] + '</span></button>'
          : '<a href="' + l[1] + '">' + svg(l[2]) + '<span>' + l[0] + '</span></a>';
      }).join('') +
      (isAdmin ? '<a href="/dashboard">' + svg('home') + '<span>Player site</span></a>' : '') +
      '<button type="button" class="j-logout">' + svg('out') + '<span>Log out</span></button></div>';

    var top = document.createElement('header');
    top.className = 'j-topbar';
    function paintTop() {
      var t = function (id) { var e = document.getElementById(id); return e && e.textContent.trim(); };
      var streak = t('stat-streak'), xp = t('stat-xp');
      var esc = function (v) { return String(v).replace(/[&<>"]/g, ''); };
      var hello = me
        ? '<div class="j-hello"><span class="j-avatar">' + esc(me.charAt(0).toUpperCase()) + '</span><div><b>Hi, ' + esc(me) + '!</b><small>StudyRPG</small></div></div>'
        : '<span class="j-brand">StudyRPG</span>';
      var pills = (streak || xp)
        ? '<div class="j-pills">' + (streak ? '<span class="j-pill">\uD83D\uDD25 ' + esc(streak) + '</span>' : '') + (xp ? '<span class="j-pill gold">\u2B50 ' + esc(xp) + '</span>' : '') + '</div>' : '';
      top.innerHTML = hello + pills;
    }
    paintTop(); setTimeout(paintTop, 1200); setTimeout(paintTop, 3000);

    document.body.insertBefore(top, document.body.firstChild);
    document.body.appendChild(scrim); document.body.appendChild(drawer); document.body.appendChild(bar);
    document.body.classList.add('j-has-nav');

    var more = bar.querySelector('.j-more');
    function toggle(open) {
      drawer.classList.toggle('is-open', open); scrim.hidden = !open;
      more.setAttribute('aria-expanded', String(open));
      document.documentElement.style.overflow = open ? 'hidden' : '';
    }
    more.addEventListener('click', function () { toggle(!drawer.classList.contains('is-open')); });
    scrim.addEventListener('click', function () { toggle(false); });
    document.addEventListener('keydown', function (e) { if (e.key === 'Escape') toggle(false); });
    drawer.querySelector('.j-logout').addEventListener('click', doLogout);
    if (isAdmin) {
      [].forEach.call(document.querySelectorAll('.j-tabbar [data-admin], .j-drawer [data-admin]'), function (b) {
        b.addEventListener('click', function () {
          var target = adminSide[+b.getAttribute('data-admin')];
          if (target) target.click();
          toggle(false);
          window.scrollTo({ top: 0, behavior: 'smooth' });
        });
      });
    }
  }

  /* ---------- 2. Colour clean-up for leftover dark styles ---------- */
  function parse(c) {
    var m = c && c.match(/rgba?\(([^)]+)\)/);
    if (!m) return null;
    var p = m[1].split(/[ ,\/]+/).filter(Boolean).map(parseFloat);
    return { r: p[0], g: p[1], b: p[2], a: p.length > 3 ? p[3] : 1 };
  }
  function lum(c) {
    function f(v) { v /= 255; return v <= .03928 ? v / 12.92 : Math.pow((v + .055) / 1.055, 2.4); }
    return .2126 * f(c.r) + .7152 * f(c.g) + .0722 * f(c.b);
  }
  function sat(c) {
    var mx = Math.max(c.r, c.g, c.b), mn = Math.min(c.r, c.g, c.b);
    return mx === 0 ? 0 : (mx - mn) / mx;
  }
  var SKIP = /^(SCRIPT|STYLE|CANVAS|SVG|PATH|IMG|VIDEO|IFRAME|BUTTON|INPUT|SELECT|TEXTAREA|OPTION|I|NOSCRIPT|LINK|META)$/i;

  function bgOf(el) {
    while (el && el.nodeType === 1) {
      var cs = getComputedStyle(el);
      var c = parse(cs.backgroundColor);
      if (c && c.a > .5) return c;
      var img = cs.backgroundImage;
      if (img && img !== 'none') {
        var first = img.match(/rgba?\([^)]+\)/);
        var g = first && parse(first[0]);
        if (g && g.a > .5) return g;
      }
      el = el.parentElement;
    }
    return { r: 246, g: 236, b: 212, a: 1 };
  }

  function normalise(root) {
    var els = (root || document.body).querySelectorAll('*');
    for (var i = 0; i < els.length; i++) {
      var el = els[i];
      if (SKIP.test(el.tagName) || el.closest('.j-keep, .j-tabbar, .j-drawer, .j-topbar, canvas, svg')) continue;
      /* leave 3D stages alone, they rely on their own dark backdrop */
      if (el.querySelector('canvas') || /canvas|scene|three|stage|arena|boss-view/i.test(el.id + ' ' + el.className)) continue;
      var cs = getComputedStyle(el);
      if (cs.display === 'none') continue;

      /* dark, unsaturated containers become cream cards */
      var bg = parse(cs.backgroundColor);
      var gradDark = false;
      if (cs.backgroundImage && cs.backgroundImage !== 'none' && cs.backgroundImage.indexOf('url(') < 0) {
        var fc = cs.backgroundImage.match(/rgba?\([^)]+\)/);
        var gp = fc && parse(fc[0]);
        gradDark = !!(gp && gp.a > .5 && lum(gp) < .2 && sat(gp) < .75);
      }
      var isBig = el.offsetWidth > 90 && el.offsetHeight > 36;
      if (isBig && ((bg && bg.a > .5 && lum(bg) < .2 && sat(bg) < .75) || gradDark)) {
        el.style.setProperty('background', 'var(--j-card)', 'important');
        el.style.setProperty('background-image', 'none', 'important');
        el.style.setProperty('border-color', 'var(--j-line)', 'important');
      }

      /* light text on a light surface becomes readable brown */
      var hasText = false;
      for (var n = el.firstChild; n; n = n.nextSibling) {
        if (n.nodeType === 3 && n.nodeValue.trim()) { hasText = true; break; }
      }
      if (hasText) {
        var col = parse(cs.color);
        if (col && lum(col) > .55) {
          var surface = bgOf(el);
          if (lum(surface) > .45) el.style.setProperty('color', 'var(--j-text)', 'important');
        }
      }
    }
  }

  /* ---------- 3. Wide tables scroll inside their own box ---------- */
  function wrapTables() {
    document.querySelectorAll('table').forEach(function (t) {
      if (t.closest('.j-table-wrap, .table-wrap, .table-responsive')) return;
      var w = document.createElement('div');
      w.className = 'j-table-wrap';
      t.parentNode.insertBefore(w, t); w.appendChild(t);
    });
  }

  var timer;
  function schedule() { clearTimeout(timer); timer = setTimeout(function () { wrapTables(); normalise(); }, 150); }

  function init() {
    buildNav(); wrapTables(); normalise();
    setTimeout(normalise, 600); setTimeout(normalise, 1800);
    if ('MutationObserver' in window) {
      new MutationObserver(function (m) {
        for (var i = 0; i < m.length; i++) if (m[i].addedNodes.length) { schedule(); break; }
      }).observe(document.body, { childList: true, subtree: true });
    }
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();
})();
