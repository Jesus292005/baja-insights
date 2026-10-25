/**
 * Public endpoints of the deployed services (docs/despliegue.md). They are not secrets.
 * They live in code because the repo ignores every .env file. VITE_STREAM_URL and VITE_ASK_URL
 * override them at build time, for example with a local stream in web/.env.local.
 */
const DEPLOYED_STREAM_URL = 'wss://baja-stream.wonderfulmoss-802940a2.centralus.azurecontainerapps.io/ws';
const DEPLOYED_ASK_URL = 'https://baja-chat.wonderfulmoss-802940a2.centralus.azurecontainerapps.io/api/ask';

/** An empty variable (VITE_ASK_URL=) turns the service off, e.g. to test the "not connected" state. */
const pick = (value: string | undefined, fallback: string) => (value === undefined ? fallback : value || null);

export const streamUrl: string | null = pick(import.meta.env.VITE_STREAM_URL, DEPLOYED_STREAM_URL);
export const askUrl: string | null = pick(import.meta.env.VITE_ASK_URL, DEPLOYED_ASK_URL);
