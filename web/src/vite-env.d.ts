/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** WebSocket of the stream service (contracts/stream.schema.json). Unset: replay the demo match. */
  readonly VITE_STREAM_URL?: string;
  /** POST endpoint of the Ask-the-match agent (contracts/chat.schema.json). Unset: chat shows it is not connected. */
  readonly VITE_ASK_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
