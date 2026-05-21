/**
 * LoginPage — Q.31.G.2.
 *
 * Login real por password (decisão D3 do Luis). POST /v1/auth/login,
 * guarda os tokens JWT em localStorage (`auth_token` é a chave que o
 * `request()` de lib/api.ts lê para o header Authorization) e redirige
 * para `/`.
 *
 * Página standalone — fica FORA do `<Layout>` (sem sidebar/topbar).
 */

import { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { LogIn, Lock } from 'lucide-react';
import { authApi } from '../../lib/api';
import { setSecure } from '../../lib/secureStorage';

export default function LoginPage() {
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');

  const mutation = useMutation({
    mutationFn: () => authApi.login(email.trim(), password),
    onSuccess: async (resp) => {
      // Q.68.5.C — tokens encriptados via Web Crypto. user_id/role
      // continuam em plaintext (são identificadores, não segredos).
      await setSecure('auth_token', resp.access_token);
      if (resp.refresh_token) {
        await setSecure('refresh_token', resp.refresh_token);
      }
      if (resp.user_id) localStorage.setItem('user_id', resp.user_id);
      if (resp.role) localStorage.setItem('user_role', resp.role);
      navigate('/', { replace: true });
    },
  });

  function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (!email.trim() || !password) return;
    mutation.mutate();
  }

  const disabled = !email.trim() || !password || mutation.isPending;
  const fieldClass =
    'w-full h-12 px-4 rounded-lg bg-dark-700 border border-white/10 text-sm ' +
    'text-text-dark-primary placeholder:text-text-dark-tertiary focus:outline-none ' +
    'focus:ring-2 focus:ring-accent-500/40 focus:border-accent-500/60';

  return (
    <div
      className="min-h-screen flex items-center justify-center px-4"
      style={{ background: 'var(--bg-0)' }}
    >
      <form
        onSubmit={handleSubmit}
        className="w-full max-w-sm space-y-5"
        style={{
          padding: 32,
          background: 'var(--bg-1)',
          border: '1px solid var(--bd-1)',
          borderRadius: 16,
        }}
      >
        <div className="flex items-center gap-2">
          <Lock size={20} className="text-accent-400" />
          <div>
            <div className="text-lg font-semibold text-text-dark-primary">
              ProdPlan ONE
            </div>
            <div className="text-xs text-text-dark-tertiary">
              Entra com o teu email e password.
            </div>
          </div>
        </div>

        <label className="block">
          <span className="text-xs text-text-dark-secondary">Email</span>
          <input
            type="email"
            autoComplete="username"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="nome@nelo.eu"
            className={`mt-1 ${fieldClass}`}
            required
          />
        </label>

        <label className="block">
          <span className="text-xs text-text-dark-secondary">Password</span>
          <input
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="••••••••"
            className={`mt-1 ${fieldClass}`}
            required
          />
        </label>

        {mutation.isError ? (
          <div className="text-xs text-danger" role="alert">
            Email ou password inválidos.
          </div>
        ) : null}

        <button
          type="submit"
          disabled={disabled}
          className="inline-flex w-full items-center justify-center gap-2 h-12 rounded-lg text-white text-sm font-semibold disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          style={{ background: 'var(--blue)', border: '1px solid var(--blue)' }}
        >
          <LogIn size={16} />
          {mutation.isPending ? 'A entrar…' : 'Entrar'}
        </button>
      </form>
    </div>
  );
}
