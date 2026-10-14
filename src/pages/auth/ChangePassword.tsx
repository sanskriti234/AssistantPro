import { useState, type FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from '../../components/common/Button';
import { changePassword } from '../../api/auth';

export default function ChangePassword() {
  const navigate = useNavigate();

  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();

    setError('');

    if (newPassword.length < 8) {
      setError('Password must contain at least 8 characters.');
      return;
    }

    if (newPassword !== confirmPassword) {
      setError('Passwords do not match.');
      return;
    }

    setLoading(true);

    try {
      await changePassword(newPassword);

      navigate('/login', {
        replace: true,
      });
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : 'Unable to change password.'
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

          <span className="font-display text-xl font-semibold">
            CoreSight
          </span>
        </div>

        <div className="mb-6">
          <h1 className="font-display text-2xl font-semibold">
            Create your password
          </h1>

          <p className="mt-2 text-sm text-text-dim">
            Your account is using a temporary password.
            Create a new secure password to continue.
          </p>
        </div>

        <form
          onSubmit={handleSubmit}
          className="bg-surface border border-border-soft rounded-2xl p-6 space-y-4"
        >

          <div>
            <label className="text-xs text-text-dim">
              New password
            </label>

            <input
              type="password"
              required
              minLength={8}
              value={newPassword}
              onChange={(e) =>
                setNewPassword(e.target.value)
              }
              className="w-full mt-1.5 bg-surface-2 border border-border rounded-lg px-3 py-2.5 text-sm text-text outline-none focus:border-accent"
            />
          </div>

          <div>
            <label className="text-xs text-text-dim">
              Confirm password
            </label>

            <input
              type="password"
              required
              minLength={8}
              value={confirmPassword}
              onChange={(e) =>
                setConfirmPassword(e.target.value)
              }
              className="w-full mt-1.5 bg-surface-2 border border-border rounded-lg px-3 py-2.5 text-sm text-text outline-none focus:border-accent"
            />
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
            {loading
              ? 'Updating password…'
              : 'Create password'}
          </Button>

        </form>
      </div>
    </div>
  );
}