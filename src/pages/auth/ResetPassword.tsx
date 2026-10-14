import { useState } from 'react';
import { Link, useNavigate, useParams, useSearchParams, } from 'react-router-dom';

import { Button } from '../../components/common/Button';
import { resetPassword } from '../../api/auth';

export default function ResetPassword() {
  const { token: pathToken } = useParams<{ token: string }>();

  const [searchParams] = useSearchParams();

  const token = pathToken || searchParams.get('token');

  const navigate = useNavigate();

  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  async function handleSubmit(
    e: React.FormEvent<HTMLFormElement>
  ) {
    e.preventDefault();

    setError('');
    setSuccess('');

    if (!token) {
      setError('Invalid password reset link.');
      return;
    }

    if (password.length < 8) {
      setError('Password must be at least 8 characters.');
      return;
    }

    if (password !== confirmPassword) {
      setError('Passwords do not match.');
      return;
    }

    setLoading(true);

    try {
      const response = await resetPassword({
        token,
        new_password: password,
      });

      setSuccess(
        response.message || 'Password updated successfully.'
      );

      setTimeout(() => {
        navigate('/login');
      }, 1500);

    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : 'Unable to reset password.'
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-base px-5">
      <div className="w-full max-w-sm">

        <div className="flex items-center gap-2 justify-center mb-8">
          <span className="w-8 h-8 rounded-md bg-gradient-to-br from-accent to-accent-2 flex items-center justify-center">
            <span className="w-2.5 h-2.5 rounded-full bg-base" />
          </span>

          <span className="font-display text-xl font-semibold tracking-tight">
            CoreSight
          </span>
        </div>

        <div className="bg-surface border border-border-soft rounded-2xl p-6">

          <h1 className="font-display text-xl font-semibold">
            Create new password
          </h1>

          <p className="text-sm text-text-dim mt-2 mb-6">
            Choose a new password for your CoreSight account.
          </p>

          <form onSubmit={handleSubmit} className="space-y-4">

            <div>
              <label className="text-xs text-text-dim">
                New password
              </label>

              <input
                type="password"
                required
                minLength={8}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="At least 8 characters"
                className="w-full mt-1.5 bg-surface-2 border border-border rounded-lg px-3 py-2.5 text-sm text-text outline-none focus:border-accent"
              />
            </div>

            <div>
              <label className="text-xs text-text-dim">
                Confirm new password
              </label>

              <input
                type="password"
                required
                minLength={8}
                value={confirmPassword}
                onChange={(e) =>
                  setConfirmPassword(e.target.value)
                }
                placeholder="Repeat your password"
                className="w-full mt-1.5 bg-surface-2 border border-border rounded-lg px-3 py-2.5 text-sm text-text outline-none focus:border-accent"
              />
            </div>

            {error && (
              <p className="text-xs text-blocked">
                {error}
              </p>
            )}

            {success && (
              <p className="text-xs text-accent">
                {success}
              </p>
            )}

            <Button
              type="submit"
              className="w-full"
              disabled={loading || Boolean(success)}
            >
              {loading ? 'Updating…' : 'Update password'}
            </Button>

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
    </div>
  );
}