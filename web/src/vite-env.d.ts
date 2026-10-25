/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** WebSocket of the stream service (contracts/stream.schema.json). Unset: the deployed one. Empty: no Live option. */
  readonly VITE_STREAM_URL?: string;
  /** POST /api/ask of the chat service (contracts/chat.schema.json). Unset: the deployed one. Empty: chat shows it is not connected. */
  readonly VITE_ASK_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
