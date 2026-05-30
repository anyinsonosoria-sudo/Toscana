export type ResidentTokenType = 'Bearer';

export interface ResidentTokenBundle {
    token_type: ResidentTokenType;
    access_token: string;
    refresh_token: string;
    access_expires_in: number;
    refresh_expires_in: number;
}

export interface ResidentProfile {
    id: number;
    username: string;
    email: string;
    full_name: string | null;
    phone: string | null;
    role: 'resident';
    apartment_count: number;
    pending_invitation_count: number;
}

export interface ResidentSession {
    tokenType: ResidentTokenType;
    accessToken: string;
    refreshToken: string;
    accessExpiresIn: number;
    refreshExpiresIn: number;
    issuedAt: number;
}

export interface ResidentSessionStorage {
    load(): Promise<ResidentSession | null>;
    save(session: ResidentSession | null): Promise<void>;
}

export interface ResidentApiClientOptions {
    baseUrl: string;
    storage: ResidentSessionStorage;
    fetchImpl?: typeof fetch;
    onSessionExpired?: () => Promise<void> | void;
}

export interface ResidentProfileResponse {
    success: true;
    profile: ResidentProfile;
    totals: {
        apartments: number;
        pending_invoices: number;
        invoice_count: number;
        balance: number;
        total_invoiced: number;
        total_paid: number;
    };
}

export class ResidentApiError extends Error {
    readonly status: number;
    readonly payload: unknown;

    constructor(message: string, status: number, payload?: unknown) {
        super(message);
        this.name = 'ResidentApiError';
        this.status = status;
        this.payload = payload;
    }
}


function normalizeSession(tokens: ResidentTokenBundle): ResidentSession {
    return {
        tokenType: tokens.token_type,
        accessToken: tokens.access_token,
        refreshToken: tokens.refresh_token,
        accessExpiresIn: tokens.access_expires_in,
        refreshExpiresIn: tokens.refresh_expires_in,
        issuedAt: Date.now(),
    };
}


export class ResidentApiClient {
    private readonly baseUrl: string;
    private readonly storage: ResidentSessionStorage;
    private readonly fetchImpl: typeof fetch;
    private readonly onSessionExpired?: () => Promise<void> | void;
    private session: ResidentSession | null = null;
    private refreshInFlight: Promise<ResidentSession | null> | null = null;

    constructor(options: ResidentApiClientOptions) {
        this.baseUrl = options.baseUrl.replace(/\/$/, '');
        this.storage = options.storage;
        this.fetchImpl = options.fetchImpl ?? fetch;
        this.onSessionExpired = options.onSessionExpired;
    }

    async restoreSession(): Promise<ResidentSession | null> {
        this.session = await this.storage.load();
        if (!this.session) {
            return null;
        }
        return this.refreshSession();
    }

    async login(identifier: string, password: string): Promise<ResidentProfileResponse> {
        const payload = await this.requestJson<{ success: true; tokens: ResidentTokenBundle; profile: ResidentProfile; totals: ResidentProfileResponse['totals']; }>(
            '/auth/login',
            {
                method: 'POST',
                body: JSON.stringify({ identifier, password }),
            },
            { requiresAuth: false },
        );

        await this.storeSession(normalizeSession(payload.tokens));
        return {
            success: true,
            profile: payload.profile,
            totals: payload.totals,
        };
    }

    async logout(options: { allSessions?: boolean } = {}): Promise<void> {
        const session = await this.ensureSessionForLogout();
        if (!session) {
            await this.clearSession();
            return;
        }

        try {
            await this.requestJson(
                '/auth/logout',
                {
                    method: 'POST',
                    body: JSON.stringify({
                        refresh_token: session.refreshToken,
                        all_sessions: Boolean(options.allSessions),
                    }),
                },
                { requiresAuth: true, retryOnUnauthorized: false },
            );
        } finally {
            await this.clearSession();
        }
    }

    async refreshSession(): Promise<ResidentSession | null> {
        if (this.refreshInFlight) {
            return this.refreshInFlight;
        }

        this.refreshInFlight = this.refreshSessionInternal();
        try {
            return await this.refreshInFlight;
        } finally {
            this.refreshInFlight = null;
        }
    }

    async getProfile(): Promise<ResidentProfileResponse> {
        return this.requestJson<ResidentProfileResponse>('/profile');
    }

    async getApartments(): Promise<{ success: true; apartments: Array<Record<string, unknown>> }> {
        return this.requestJson('/apartments');
    }

    async getInvitations(): Promise<{ success: true; invitations: Array<Record<string, unknown>> }> {
        return this.requestJson('/invitations');
    }

    async activateInvitation(code: string): Promise<{ success: true; apartment: Record<string, unknown>; profile: ResidentProfile }> {
        return this.requestJson('/invitations/activate', {
            method: 'POST',
            body: JSON.stringify({ code }),
        });
    }

    async getInvoices(status: 'all' | 'pending' | 'paid' = 'all'): Promise<{ success: true; invoices: Array<Record<string, unknown>> }> {
        const query = new URLSearchParams({ status });
        return this.requestJson(`/invoices?${query.toString()}`);
    }

    async getStatementSummary(): Promise<{ success: true; summary: Record<string, unknown> }> {
        return this.requestJson('/statement-summary');
    }

    async fetchAuthorized(path: string, init: RequestInit = {}, retryOnUnauthorized = true): Promise<Response> {
        return this.request(path, init, { requiresAuth: true, retryOnUnauthorized });
    }

    async fetchInvoicePdf(invoiceId: number): Promise<Response> {
        return this.fetchAuthorized(`/invoices/${invoiceId}/pdf`);
    }

    async fetchStatementPdf(unitId: number): Promise<Response> {
        return this.fetchAuthorized(`/apartments/${unitId}/statement.pdf`);
    }

    private async refreshSessionInternal(): Promise<ResidentSession | null> {
        const persistedSession = this.session ?? await this.storage.load();
        if (!persistedSession?.refreshToken) {
            await this.clearSession();
            return null;
        }

        try {
            const payload = await this.requestJson<{ success: true; tokens: ResidentTokenBundle }>(
                '/auth/refresh',
                {
                    method: 'POST',
                    body: JSON.stringify({ refresh_token: persistedSession.refreshToken }),
                },
                { requiresAuth: false, retryOnUnauthorized: false },
            );
            const nextSession = normalizeSession(payload.tokens);
            await this.storeSession(nextSession);
            return nextSession;
        } catch (error) {
            await this.clearSession();
            if (this.onSessionExpired) {
                await this.onSessionExpired();
            }
            if (error instanceof ResidentApiError && error.status === 401) {
                return null;
            }
            throw error;
        }
    }

    private async ensureSessionForLogout(): Promise<ResidentSession | null> {
        if (this.session && !this.isAccessExpired(this.session)) {
            return this.session;
        }
        const refreshed = await this.refreshSession();
        return refreshed;
    }

    private async ensureAccessToken(): Promise<string> {
        if (this.session && !this.isAccessExpired(this.session)) {
            return this.session.accessToken;
        }

        const refreshedSession = await this.refreshSession();
        if (refreshedSession?.accessToken) {
            return refreshedSession.accessToken;
        }

        throw new ResidentApiError('Sesion expirada', 401);
    }

    private isAccessExpired(session: ResidentSession): boolean {
        const expiresAt = session.issuedAt + Math.max(session.accessExpiresIn - 30, 0) * 1000;
        return Date.now() >= expiresAt;
    }

    private buildUrl(path: string): string {
        if (path.startsWith('http://') || path.startsWith('https://')) {
            return path;
        }
        return `${this.baseUrl}${path.startsWith('/') ? path : `/${path}`}`;
    }

    private async storeSession(session: ResidentSession): Promise<void> {
        this.session = session;
        await this.storage.save(session);
    }

    private async clearSession(): Promise<void> {
        this.session = null;
        await this.storage.save(null);
    }

    private async requestJson<T>(path: string, init: RequestInit = {}, options?: { requiresAuth?: boolean; retryOnUnauthorized?: boolean }): Promise<T> {
        const response = await this.request(path, init, options);
        const data = await response.json().catch(() => null);

        if (!response.ok) {
            throw new ResidentApiError(
                (data as { error?: string } | null)?.error ?? `Error HTTP ${response.status}`,
                response.status,
                data,
            );
        }

        return data as T;
    }

    private async request(path: string, init: RequestInit = {}, options?: { requiresAuth?: boolean; retryOnUnauthorized?: boolean }): Promise<Response> {
        const requiresAuth = options?.requiresAuth ?? true;
        const retryOnUnauthorized = options?.retryOnUnauthorized ?? true;
        const headers = new Headers(init.headers ?? {});

        if (!headers.has('Content-Type') && init.body) {
            headers.set('Content-Type', 'application/json');
        }

        if (requiresAuth) {
            const accessToken = await this.ensureAccessToken();
            headers.set('Authorization', `Bearer ${accessToken}`);
        }

        const response = await this.fetchImpl(this.buildUrl(path), {
            ...init,
            headers,
        });

        if (response.status === 401 && requiresAuth && retryOnUnauthorized) {
            const refreshedSession = await this.refreshSession();
            if (!refreshedSession?.accessToken) {
                return response;
            }

            const retryHeaders = new Headers(init.headers ?? {});
            if (!retryHeaders.has('Content-Type') && init.body) {
                retryHeaders.set('Content-Type', 'application/json');
            }
            retryHeaders.set('Authorization', `Bearer ${refreshedSession.accessToken}`);

            return this.fetchImpl(this.buildUrl(path), {
                ...init,
                headers: retryHeaders,
            });
        }

        return response;
    }
}