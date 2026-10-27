declare module "foliate-js/view.js" {
  export interface FoliateBook {
    transformTarget?: EventTarget;
  }

  export function makeBook(file: File): Promise<FoliateBook>;
}
