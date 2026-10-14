import { useState } from 'react';
import { Link, Navigate } from 'react-router-dom';

import { useAuth } from '../../context/AuthContext';
import { Button } from '../../components/common/Button';

export default function Login() {
  const { user, login, loading, error } = useAuth();

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');

  if (user) {
    return <Navigate to={`/${user.role}`} replace />;
  }

  async function handleSubmit(
    event: React.FormEvent<HTMLFormElement>
  ) {
    event.preventDefault();

    try {
      await login(email, password);
    } catch {
      // Error is handled and displayed by AuthContext.
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-base px-5">
      <div className="w-full max-w-sm">

        {/* Logo */}
        <div className="flex items-center gap-2 justify-center mb-8">
          <span className="w-8 h-8 rounded-md bg-gradient-to-br from-accent to-accent-2 flex items-center justify-center">
            <span className="w-2.5 h-2.5 rounded-full bg-base" />
          </span>

          <span className="font-display text-xl font-semibold tracking-tight">
            CoreSight
          </span>
        </div>

        {/* Login form */}
        <form
          onSubmit={handleSubmit}
          className="bg-surface border border-border-soft rounded-2xl p-6 space-y-4"
        >
          <div>
            <label className="text-xs text-text-dim">
              Email
            </label>

            <input
              type="email"
              required
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              className="w-full mt-1.5 bg-surface-2 border border-border rounded-lg px-3 py-2.5 text-sm text-text outline-none focus:border-accent"
              placeholder="you@coresight.edu"
              autoComplete="email"
            />
          </div>

          <div>
            <label className="text-xs text-text-dim">
              Password
            </label>

            <input
              type="password"
              required
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              className="w-full mt-1.5 bg-surface-2 border border-border rounded-lg px-3 py-2.5 text-sm text-text outline-none focus:border-accent"
              placeholder="••••••••"
              autoComplete="current-password"
            />
          </div>

          {/* Forgot password */}
          <div className="flex justify-end">
            <Link
              to="/forgot-password"
              className="text-xs text-accent hover:underline"
            >
              Forgot password?
            </Link>
          </div>

          {error && (
            <p className="text-xs text-blocked">
              {error}
            </p>
          )}

          <Button
            type="submit"
            className="w-full"
            disabled={loading}
          >
            {loading ? 'Signing in…' : 'Sign in'}
          </Button>
        </form>

        {/* Faculty registration */}
        <div className="mt-5 text-center text-xs text-text-dim">
          Are you a faculty member?{' '}

          <Link
            to="/faculty/register"
            className="text-accent hover:underline"
          >
            Request faculty access
          </Link>
        </div>

      </div>
    </div>
  );
}