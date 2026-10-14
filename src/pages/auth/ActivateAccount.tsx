import { useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { request } from '../../api/client';

export default function ActivateAccount() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();

  const token = searchParams.get('token');

  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);

  const handleSubmit: React.ComponentProps<'form'>['onSubmit'] = async (
    event
  ) => {
    event.preventDefault();

    setError('');

    if (!token) {
      setError('Invalid or missing activation link.');
      return;
    }

    if (password.length < 8) {
      setError('Password must contain at least 8 characters.');
      return;
    }

    if (password !== confirmPassword) {
      setError('Passwords do not match.');
      return;
    }

    setLoading(true);

    try {
      await request('/auth/activate', {
        method: 'POST',
        body: {
          token,
          newPassword: password,
        },
      });

      setSuccess(true);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : 'Unable to activate your account.'
      );
    } finally {
      setLoading(false);
    }
  };

  if (success) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-surface px-4">
        <div className="w-full max-w-md">
          <div className="text-center">
            <h1 className="font-display text-2xl font-semibold text-text">
              Account activated
            </h1>

            <p className="text-sm text-text-dim mt-2">
              Your CoreSight faculty account is now active.
            </p>

            <button
              type="button"
              onClick={() => navigate('/login')}
              className="mt-6 inline-flex items-center justify-center rounded-lg bg-accent px-5 py-2.5 text-sm font-medium text-white hover:opacity-90"
            >
              Continue to login
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-surface px-4">
      <div className="w-full max-w-md">
        <div className="mb-8 text-center">
          <h1 className="font-display text-2xl font-semibold text-text">
            Activate your account
          </h1>

          <p className="text-sm text-text-dim mt-2">
            Create a password to activate your CoreSight faculty account.
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label
              htmlFor="password"
              className="block text-xs text-text-dim mb-1.5"
            >
              New password
            </label>

            <input
              id="password"
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              autoComplete="new-password"
              required
              minLength={8}
              className="w-full bg-surface-2 border border-border rounded-lg px-3 py-2.5 text-sm text-text outline-none focus:border-accent"
            />
          </div>

          <div>
            <label
              htmlFor="confirmPassword"
              className="block text-xs text-text-dim mb-1.5"
            >
              Confirm password
            </label>

            <input
              id="confirmPassword"
              type="password"
              value={confirmPassword}
              onChange={(event) => setConfirmPassword(event.target.value)}
              autoComplete="new-password"
              required
              minLength={8}
              className="w-full bg-surface-2 border border-border rounded-lg px-3 py-2.5 text-sm text-text outline-none focus:border-accent"
            />
          </div>

          {error && (
            <div className="rounded-lg border border-blocked/20 bg-blocked/5 px-3 py-2.5">
              <p className="text-xs text-blocked">{error}</p>
            </div>
          )}

          <button
            type="submit"
            disabled={loading || !token}
            className="w-full rounded-lg bg-accent px-4 py-2.5 text-sm font-medium text-white hover:opacity-90 disabled:opacity-50"
          >
            {loading ? 'Activating…' : 'Activate account'}
          </button>
        </form>

        <div className="mt-5 text-center">
          <Link
            to="/login"
            className="text-xs text-text-dim hover:text-accent"
          >
            Back to login
          </Link>
        </div>
      </div>
    </div>
  );
}