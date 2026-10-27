/**
 * Built from api/openapi.json by npm run api-types.
 * Do not make direct changes to the file.
 */

export interface paths {
    "/api/accounts": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Sign Up */
        post: operations["sign_up_api_accounts_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/books": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Books */
        get: operations["list_books_api_books_get"];
        put?: never;
        /** Upload Book */
        post: operations["upload_book_api_books_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/books/{book_id}/content": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Book Content */
        get: operations["book_content_api_books__book_id__content_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/books/{book_id}/cover": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Book Cover */
        get: operations["book_cover_api_books__book_id__cover_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/books/{book_id}/open-failures": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Book Open Failed */
        post: operations["book_open_failed_api_books__book_id__open_failures_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/sessions": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Sign In */
        post: operations["sign_in_api_sessions_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/sessions/current": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Current */
        get: operations["current_api_sessions_current_get"];
        put?: never;
        post?: never;
        /** Sign Out */
        delete: operations["sign_out_api_sessions_current_delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
}
export type webhooks = Record<string, never>;
export interface components {
    schemas: {
        /**
         * BookOut
         * @description A book as the library list shows it.
         */
        BookOut: {
            /** Author */
            author: string | null;
            /** Cover Url */
            cover_url: string | null;
            failure: components["schemas"]["Failure"] | null;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            status: components["schemas"]["BookStatus"];
            /** Title */
            title: string;
        };
        /**
         * BookStatus
         * @description Where a book is on its way to the library.
         * @enum {string}
         */
        BookStatus: "processing" | "ready" | "failed";
        /**
         * DuplicateOut
         * @description The reject of a file the reader already owns, with a link to that book.
         */
        DuplicateOut: {
            /**
             * Book Id
             * Format: uuid
             */
            book_id: string;
            /** Code */
            code: string;
            /** Title */
            title: string;
        };
        /**
         * ErrorOut
         * @description A refused request. `code` names the reason.
         */
        ErrorOut: {
            /** Code */
            code: string;
        };
        /**
         * Failure
         * @description Why a conversion fails (`ConversionFailed`).
         *
         *     `stuck` comes from the deadline (P2), never from a converter.
         * @enum {string}
         */
        Failure: "malformed" | "unreadable" | "timed_out" | "crashed" | "stuck";
        /**
         * ReaderOut
         * @description A reader as the pages see it.
         */
        ReaderOut: {
            /** Email */
            email: string;
        };
        /**
         * SignInIn
         * @description A sign-in request.
         */
        SignInIn: {
            /** Email */
            email: string;
            /** Password */
            password: string;
        };
        /**
         * SignUpIn
         * @description A sign-up request.
         */
        SignUpIn: {
            /** Email */
            email: string;
            /** Password */
            password: string;
        };
    };
    responses: never;
    parameters: never;
    requestBodies: never;
    headers: never;
    pathItems: never;
}
export type $defs = Record<string, never>;
export interface operations {
    sign_up_api_accounts_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SignUpIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ReaderOut"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorOut"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorOut"];
                };
            };
        };
    };
    list_books_api_books_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: {
                session?: string | null;
            };
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BookOut"][];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorOut"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorOut"];
                };
            };
        };
    };
    upload_book_api_books_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: {
                session?: string | null;
            };
        };
        requestBody: {
            content: {
                "multipart/form-data": {
                    /** Format: binary */
                    file: string;
                };
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BookOut"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorOut"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["DuplicateOut"];
                };
            };
            /** @description Request Entity Too Large */
            413: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorOut"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorOut"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorOut"];
                };
            };
        };
    };
    book_content_api_books__book_id__content_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                book_id: string;
            };
            cookie?: {
                session?: string | null;
            };
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/epub+zip": unknown;
                    "application/pdf": unknown;
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorOut"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorOut"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorOut"];
                };
            };
        };
    };
    book_cover_api_books__book_id__cover_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                book_id: string;
            };
            cookie?: {
                session?: string | null;
            };
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "image/png": unknown;
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorOut"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorOut"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorOut"];
                };
            };
        };
    };
    book_open_failed_api_books__book_id__open_failures_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                book_id: string;
            };
            cookie?: {
                session?: string | null;
            };
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorOut"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorOut"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorOut"];
                };
            };
        };
    };
    sign_in_api_sessions_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SignInIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorOut"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorOut"];
                };
            };
            /** @description Too Many Requests */
            429: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorOut"];
                };
            };
        };
    };
    current_api_sessions_current_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: {
                session?: string | null;
            };
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ReaderOut"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorOut"];
                };
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorOut"];
                };
            };
        };
    };
    sign_out_api_sessions_current_delete: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: {
                session?: string | null;
            };
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Unprocessable Entity */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorOut"];
                };
            };
        };
    };
}
