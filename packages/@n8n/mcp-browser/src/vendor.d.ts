declare module '@joplin/turndown-plugin-gfm' {
	import type TurndownService from 'turndown';
	export function gfm(service: TurndownService): void;
}

// Minimal ambient declarations for 'jsdom'.  @types/jsdom is not in the
// workspace lockfile; these stubs give TypeScript enough information to resolve
// dom.window.document as the built-in Document type so that querySelectorAll
// returns properly-typed NodeLists.  Runtime behaviour is unchanged.
declare module 'jsdom' {
	interface DOMWindow {
		document: Document;
		[key: string]: unknown;
	}
	interface JSDOMOptions {
		virtualConsole?: InstanceType<typeof VirtualConsole>;
		url?: string;
		referrer?: string;
		contentType?: string;
		includeNodeLocations?: boolean;
		runScripts?: 'dangerously' | 'outside-only';
		resources?: string | object;
		pretendToBeVisual?: boolean;
	}
	class JSDOM {
		constructor(html: string, options?: JSDOMOptions);
		readonly window: DOMWindow;
		serialize(): string;
	}
	class VirtualConsole {
		sendTo(console: Partial<Console>, options?: { omitJSDOMErrors?: boolean }): this;
		on(event: string, listener: (...args: unknown[]) => void): this;
	}
	export { JSDOM, VirtualConsole };
}
