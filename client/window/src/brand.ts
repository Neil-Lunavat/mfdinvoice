/* The product's name and the website's address. Not written here: the build reads them from the app's one copy,
   client/src/client/brand.json (vite.config.ts), so the window and the Python half can never disagree. */
declare const __BRAND__: { name: string; site: string };

export const NAME: string = __BRAND__.name;
export const SITE: string = __BRAND__.site;
