import { Link } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';

export default function Unauthorized() {
  const { user } = useAuth();
  return (
    <div className="min-h-screen flex items-center justify-center bg-base px-5 text-center">
      <div>
        <p className="font-mono text-xs text-blocked mb-2">403</p>
        <h1 className="font-display text-lg font-semibold">You don't have access to this page</h1>
        <p className="text-sm text-text-dim mt-2">This area is outside your role's permissions.</p>
        <Link
          to={user ? `/${user.role}` : '/login'}
          className="inline-block mt-5 text-sm text-accent hover:underline"
        >
          Back to your dashboard
        </Link>
      </div>
    </div>
  );
}
