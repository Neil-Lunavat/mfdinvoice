/* The window's icons, drawn inline: nothing to fetch, nothing to lose offline. From the prototype. */

const s = (w: number, body: string, sw = 1.75, fill = 'none') =>
  `<svg class="icon" width="${w}" height="${w}" viewBox="0 0 24 24" fill="${fill}" stroke="${fill === 'none' ? 'currentColor' : 'none'}" stroke-width="${sw}" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${body}</svg>`;

export const icons = {
  mark: (w: number) => s(w, '<path d="M5 12.5l4.5 4.5L19 7.5"/>', 2.6),
  tickSm: s(11, '<path d="M5 12.5l4.5 4.5L19 7.5"/>', 3.2),
  play: s(14, '<circle cx="12" cy="12" r="9"/><path d="M10 8.5v7l6-3.5z"/>'),
  help: s(14, '<path d="M21 12a8 8 0 0 1-11.6 7.1L4 20l1-4.6A8 8 0 1 1 21 12z"/>'),
  lock: s(13, '<rect x="5" y="11" width="14" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/>', 2),
  win: s(14, '<path d="M3 3h8.5v8.5H3zM12.5 3H21v8.5h-8.5zM3 12.5h8.5V21H3zM12.5 12.5H21V21h-8.5z"/>', 0, 'currentColor'),
  image: s(22, '<rect x="3" y="4" width="18" height="16" rx="2"/><circle cx="9" cy="10" r="2"/><path d="M21 16l-5-5-9 9"/>'),
  rot: s(14, '<path d="M20 11a8 8 0 1 0-2.3 5.7"/><path d="M20 4v7h-7"/>'),
  cal: s(18, '<rect x="3" y="4" width="18" height="17" rx="2"/><path d="M3 9h18M8 2v4M16 2v4"/>'),
  doc: s(18, '<path d="M6 3h9l4 4v14H6z"/><path d="M9 12h7M9 16h5"/>'),
  chart: s(18, '<path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/>'),
  book: s(18, '<path d="M5 4.5A1.5 1.5 0 0 1 6.5 3H19v15H6.5A1.5 1.5 0 0 0 5 19.5z"/><path d="M5 19.5A1.5 1.5 0 0 0 6.5 21H19"/><path d="M9 8h6"/>'),
  gear: s(18, '<circle cx="12" cy="12" r="3"/><path d="M12 2v3M12 19v3M4.2 4.2l2.1 2.1M17.7 17.7l2.1 2.1M2 12h3M19 12h3M4.2 19.8l2.1-2.1M17.7 6.3l2.1-2.1"/>'),
  playFill: s(16, '<path d="M7 4.5v15l13-7.5z"/>', 0, 'currentColor'),
  folder: s(16, '<path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>'),
  dl: s(16, '<path d="M12 3v12M7 10l5 5 5-5M4 20h16"/>'),
  copy: s(14, '<rect x="9" y="9" width="12" height="12" rx="2"/><path d="M5 15V5a2 2 0 0 1 2-2h10"/>'),
  sync: s(16, '<path d="M20 11a8 8 0 0 0-14.3-4.9L4 8M4 13a8 8 0 0 0 14.3 4.9L20 16"/><path d="M4 3v5h5M20 21v-5h-5"/>'),
  bell: s(17, '<path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9"/><path d="M10.3 21a1.9 1.9 0 0 0 3.4 0"/>'),
  close: '<svg class="icon" width="10" height="10" viewBox="0 0 10 10" aria-hidden="true"><path d="M0 0l10 10M10 0L0 10" stroke="currentColor"/></svg>',
  caret: s(14, '<path d="M6 9l6 6 6-6"/>', 2.2),
  chevDown: s(12, '<path d="M6 9l6 6 6-6"/>', 2),
  back: s(18, '<path d="M15 6l-6 6 6 6"/>', 2),
  prev: s(16, '<path d="M15 6l-6 6 6 6"/>', 2),
  next: s(16, '<path d="M9 6l6 6-6 6"/>', 2),
  chev: s(16, '<path d="M9 6l6 6-6 6"/>', 2),
  bang: s(14, '<path d="M12 7v6M12 17h.01"/>', 2.6),
  stop: s(14, '<rect x="7" y="7" width="10" height="10" rx="1.5"/>', 0, 'currentColor'),
  drawn: '<svg class="dt" width="20" height="20" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="11"/><path d="M7 12.5l3.5 3.5L17 9"/></svg>'
} as const;
