# Cliente Movil Residente

Este folder deja listo un cliente minimo para Expo o React Native usando el backend residente ya implementado.

## Archivo principal

- `ResidentApiClient.ts`: cliente TypeScript puro para login, refresh, logout, carga de perfil, apartamentos, invitaciones, facturas y PDFs protegidos.

## Que asume del backend

- Base URL apuntando a `/api/resident`
- Login por `POST /auth/login`
- Rotacion por `POST /auth/refresh`
- Revocacion por `POST /auth/logout`
- Bearer token en el resto de endpoints

## Adaptador sugerido para Expo SecureStore

```ts
import * as SecureStore from 'expo-secure-store';
import type { ResidentSession, ResidentSessionStorage } from './ResidentApiClient';

const STORAGE_KEY = 'toscana.resident.session';

export const secureStoreSessionStorage: ResidentSessionStorage = {
  async load(): Promise<ResidentSession | null> {
    const raw = await SecureStore.getItemAsync(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as ResidentSession) : null;
  },
  async save(session: ResidentSession | null): Promise<void> {
    if (!session) {
      await SecureStore.deleteItemAsync(STORAGE_KEY);
      return;
    }
    await SecureStore.setItemAsync(STORAGE_KEY, JSON.stringify(session));
  },
};
```

## Inicializacion sugerida

```ts
import { ResidentApiClient } from './ResidentApiClient';
import { secureStoreSessionStorage } from './secureStoreSessionStorage';

export const residentApi = new ResidentApiClient({
  baseUrl: 'https://tu-dominio.com/api/resident',
  storage: secureStoreSessionStorage,
  onSessionExpired: () => {
    console.log('Sesion expirada; redirigir al login');
  },
});

await residentApi.restoreSession();
```

## Ejemplos de uso

```ts
await residentApi.login('resident@example.com', 'password123');

const profile = await residentApi.getProfile();
const apartments = await residentApi.getApartments();
const invoices = await residentApi.getInvoices('pending');

await residentApi.activateInvitation('AB12CD34');

const statementPdfResponse = await residentApi.fetchStatementPdf(12);
```

## Notas practicas

- `restoreSession()` intenta refrescar usando el `refreshToken` guardado.
- `fetchAuthorized()` reintenta una vez si recibe `401` y logra refrescar.
- `logout()` primero intenta asegurar un `accessToken` vigente para poder revocar el `refreshToken` en el servidor.
- Si aun no existe un proyecto Expo en este repositorio, copia estos archivos al cliente movil cuando lo abras.