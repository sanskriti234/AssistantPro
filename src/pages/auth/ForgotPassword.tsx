import { useState } from 'react';
import { Link } from 'react-router-dom';

import { Button } from '../../components/common/Button';
import { forgotPassword } from '../../api/auth';

export default function ForgotPassword() {
  const [email, setEmail] = useState('');
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

  async function handleSubmit(
    e: React.FormEvent<HTMLFormElement>
  ) {
    e.preventDefault();

    setLoading(true);
    setError('');
    setMessage('');

    try {
      const response = await forgotPassword({ email });

      setMessage(
        response.message ||
          'If an account exists with this email, a reset link has been sent.'
      );
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : 'Unable to process your request.'
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
            Reset password
          </h1>

          <p className="text-sm text-text-dim mt-2 mb-6">
            Enter your registered email address and we'll send you a password
            reset link.
          </p>

          <form onSubmit={handleSubmit} className="space-y-4">

            <div>
              <label className="text-xs text-text-dim">
                Email
              </label>

              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@coresight.edu"
                className="w-full mt-1.5 bg-surface-2 border border-border rounded-lg px-3 py-2.5 text-sm text-text outline-none focus:border-accent"
              />
            </div>

            {error && (
              <p className="text-xs text-blocked">
                {error}
              </p>
            )}

            {message && (
              <p className="text-xs text-accent">
                {message}
              </p>
            )}

            <Button
              type="submit"
              className="w-full"
              disabled={loading}
            >
              {loading ? 'Sending…' : 'Send reset link'}
            </Button>

          </form>

          <div className="mt-5 text-center">
            <Link
              to="/login"
              className="text-xs text-text-dim hover:text-accent"
            >
              ← Back to login
            </Link>
          </div>

        </div>
      </div>
    </div>
  );
}