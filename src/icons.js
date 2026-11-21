// Ícones SVG (traço 2px, viewBox 24) — os mesmos da versão 1.x.
const S_ = 'fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"';
const ICONS = {
  add: `<rect x="4" y="3" width="16" height="18" rx="3" ${S_}/><path d="M12 8v8M8 12h8" ${S_}/>`,
  gamepad: `<path d="M6.5 8h11a4.5 4.5 0 0 1 4.3 5.8l-1 3.4a2.4 2.4 0 0 1-4 1L14.6 16H9.4l-2.2 2.2a2.4 2.4 0 0 1-4-1l-1-3.4A4.5 4.5 0 0 1 6.5 8z" ${S_}/><path d="M7.5 11v3M6 12.5h3" ${S_}/><circle cx="15.5" cy="11.5" r=".6" fill="currentColor"/><circle cx="17.5" cy="13.5" r=".6" fill="currentColor"/>`,
  folder: `<path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" ${S_}/>`,
  settings: `<circle cx="12" cy="12" r="3" ${S_}/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z" ${S_}/>`,
  play: `<path d="M7 4.5v15a1 1 0 0 0 1.5.86l12.4-7.5a1 1 0 0 0 0-1.72L8.5 3.64A1 1 0 0 0 7 4.5z" fill="currentColor"/>`,
  fullscreen: `<path d="M4 9V5a1 1 0 0 1 1-1h4M15 4h4a1 1 0 0 1 1 1v4M20 15v4a1 1 0 0 1-1 1h-4M9 20H5a1 1 0 0 1-1-1v-4" ${S_}/>`,
  edit: `<path d="M12 20h9M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4z" ${S_}/>`,
  close: `<path d="M6 6l12 12M18 6L6 18" ${S_}/>`,
  clock: `<circle cx="12" cy="12" r="9" ${S_}/><path d="M12 7v5l3 2" ${S_}/>`,
  calendar: `<rect x="3" y="5" width="18" height="16" rx="2" ${S_}/><path d="M16 3v4M8 3v4M3 10h18" ${S_}/>`,
  users: `<circle cx="9" cy="8" r="3.5" ${S_}/><path d="M2.5 20a6.5 6.5 0 0 1 13 0M16 4.6a3.5 3.5 0 0 1 0 6.8M18.5 14a6.5 6.5 0 0 1 3 6" ${S_}/>`,
  user: `<circle cx="12" cy="8" r="4" ${S_}/><path d="M4.5 21a7.5 7.5 0 0 1 15 0" ${S_}/>`,
  grid_small: `<g fill="currentColor"><rect x="4" y="4" width="4" height="4" rx="1"/><rect x="10" y="4" width="4" height="4" rx="1"/><rect x="16" y="4" width="4" height="4" rx="1"/><rect x="4" y="10" width="4" height="4" rx="1"/><rect x="10" y="10" width="4" height="4" rx="1"/><rect x="16" y="10" width="4" height="4" rx="1"/><rect x="4" y="16" width="4" height="4" rx="1"/><rect x="10" y="16" width="4" height="4" rx="1"/><rect x="16" y="16" width="4" height="4" rx="1"/></g>`,
  grid_big: `<g fill="currentColor"><rect x="3" y="3" width="8" height="8" rx="2"/><rect x="13" y="3" width="8" height="8" rx="2"/><rect x="3" y="13" width="8" height="8" rx="2"/><rect x="13" y="13" width="8" height="8" rx="2"/></g>`,
  search: `<circle cx="11" cy="11" r="7" ${S_}/><path d="M20 20l-3.5-3.5" ${S_}/>`,
  image: `<rect x="3" y="4" width="18" height="16" rx="2" ${S_}/><circle cx="8.5" cy="9.5" r="1.5" ${S_}/><path d="M21 16l-5-5-9 9" ${S_}/>`,
  trash: `<path d="M4 7h16M10 11v6M14 11v6M5 7l1 12a2 2 0 0 0 2 2h8a2 2 0 0 0 2-2l1-12M9 7V4h6v3" ${S_}/>`,
  check: `<path d="M5 12.5l4.5 4.5L19 7.5" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>`,
  refresh: `<path d="M20 11a8 8 0 0 0-14.9-3.5M4 4v4h4M4 13a8 8 0 0 0 14.9 3.5M20 20v-4h-4" ${S_}/>`,
  cart: `<path d="M5 3h14v12l-2 2v4H7v-4l-2-2z" ${S_}/><path d="M8 7h8M8 10h8" ${S_}/>`,
  chevron: `<path d="M6 9l6 6 6-6" ${S_}/>`,
  database: `<ellipse cx="12" cy="5.5" rx="8" ry="3" ${S_}/><path d="M4 5.5v13c0 1.7 3.6 3 8 3s8-1.3 8-3v-13M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3" ${S_}/>`,
  list: `<path d="M9 6h11M9 12h11M9 18h11" ${S_}/><circle cx="4.5" cy="6" r="1" fill="currentColor"/><circle cx="4.5" cy="12" r="1" fill="currentColor"/><circle cx="4.5" cy="18" r="1" fill="currentColor"/>`,
};

function icon(name, size) {
  const s = size ? ` width="${size}" height="${size}"` : '';
  return `<svg class="i" viewBox="0 0 24 24"${s} aria-hidden="true">${ICONS[name] || ''}</svg>`;
}

function hydrateIcons(root) {
  (root || document).querySelectorAll('[data-icon]').forEach(el => {
    if (!el.firstChild) el.innerHTML = icon(el.dataset.icon);
  });
}
