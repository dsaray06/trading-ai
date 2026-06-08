// Connect / disconnect the user's own Alpaca paper account.
import { type FormEvent, useState } from "react";
import { type AlpacaStatus, connectAlpaca, disconnectAlpaca } from "@/api/alpaca";
import { apiErrorMessage } from "@/api/client";

export function ConnectAlpacaPanel({
  status,
  onChange,
  onClose,
}: {
  status: AlpacaStatus;
  onChange: (s: AlpacaStatus) => void;
  onClose: () => void;
}) {
  const [key, setKey] = useState("");
  const [secret, setSecret] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const connect = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      onChange(await connectAlpaca(key.trim(), secret.trim()));
      onClose();
    } catch (err) {
      setError(apiErrorMessage(err, "Could not connect."));
    } finally {
      setBusy(false);
    }
  };

  const disconnect = async () => {
    setBusy(true);
    try {
      onChange(await disconnectAlpaca());
      onClose();
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="mt-4 rounded-lg border border-slate-200 bg-white p-5">
      <div className="flex items-center justify-between">
        <h3 className="font-semibold text-slate-800">Connect Alpaca (paper)</h3>
        <button onClick={onClose} className="text-sm text-slate-400 hover:text-slate-600">
          Close
        </button>
      </div>

      {status.connected ? (
        <div className="mt-3">
          <p className="text-sm text-slate-600">
            Connected — key <span className="font-mono">{status.api_key_masked}</span>.
            Alpaca portfolios trade your own paper account.
          </p>
          <button
            onClick={disconnect}
            disabled={busy}
            className="mt-3 rounded-md border border-rose-300 px-3 py-1.5 text-sm text-rose-600 disabled:opacity-40"
          >
            Disconnect
          </button>
        </div>
      ) : (
        <form onSubmit={connect} className="mt-3 space-y-2">
          <p className="text-xs text-slate-500">
            Create a free paper account at alpaca.markets → Paper Trading → generate an
            API key + secret. Keys are stored encrypted and used only for your account.
          </p>
          <input
            value={key}
            onChange={(e) => setKey(e.target.value)}
            placeholder="API Key ID (PK…)"
            className="w-full rounded-md border border-slate-300 px-3 py-2 font-mono text-sm"
          />
          <input
            value={secret}
            onChange={(e) => setSecret(e.target.value)}
            placeholder="API Secret"
            type="password"
            className="w-full rounded-md border border-slate-300 px-3 py-2 font-mono text-sm"
          />
          {error && <p className="text-sm text-rose-600">{error}</p>}
          <button
            type="submit"
            disabled={busy || !key.trim() || !secret.trim()}
            className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-40"
          >
            {busy ? "Connecting…" : "Connect"}
          </button>
        </form>
      )}
    </div>
  );
}
