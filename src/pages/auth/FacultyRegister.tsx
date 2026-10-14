import { useEffect, useState, type FormEvent } from 'react';
import { Link } from 'react-router-dom';
import { Button } from '../../components/common/Button';
import {
  getDepartments,
  registerFaculty,
  type Department,
  type FacultyRegistrationResponse,
} from '../../api/faculty';


export default function FacultyRegister() {
  const [departments, setDepartments] = useState<Department[]>([]);
  const [loadingDepartments, setLoadingDepartments] = useState(true);

  const [fullName, setFullName] = useState('');
  const [employeeId, setEmployeeId] = useState('');
  const [email, setEmail] = useState('');
  const [departmentId, setDepartmentId] = useState('');
  const [designation, setDesignation] = useState('');
  const [phone, setPhone] = useState('');

  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
const [submitted, setSubmitted] =
  useState<FacultyRegistrationResponse | null>(null);
    useEffect(() => {
    async function loadDepartments() {
        try {
        const data = await getDepartments();
        setDepartments(data);
        } catch (err) {
        setError(
            err instanceof Error
            ? err.message
            : 'Unable to load departments. Please try again.'
        );
        } finally {
        setLoadingDepartments(false);
        }
    }

    loadDepartments();
    }, []);

    async function handleSubmit(e: FormEvent) {
    e.preventDefault();

    setError('');
    setSubmitting(true);

    try {
        const data = await registerFaculty({
        full_name: fullName.trim(),
        employee_id: employeeId.trim(),
        email: email.trim().toLowerCase(),
        department_id: departmentId,
        designation: designation.trim() || null,
        phone: phone.trim() || null,
        });

        setSubmitted(data);
    } catch (err) {
        setError(
        err instanceof Error
            ? err.message
            : 'Unable to submit registration request. Please try again.'
        );
    } finally {
        setSubmitting(false);
    }
    }

  if (submitted) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-base px-5">
        <div className="w-full max-w-md">
          <div className="flex items-center gap-2 justify-center mb-8">
            <span className="w-8 h-8 rounded-md bg-gradient-to-br from-accent to-accent-2 flex items-center justify-center">
              <span className="w-2.5 h-2.5 rounded-full bg-base" />
            </span>

            <span className="font-display text-xl font-semibold tracking-tight">
              CoreSight
            </span>
          </div>

          <div className="bg-surface border border-border-soft rounded-2xl p-7 text-center">
            <div className="mx-auto mb-5 w-12 h-12 rounded-full bg-accent/10 flex items-center justify-center">
              <span className="text-accent text-xl">✓</span>
            </div>

            <h1 className="font-display text-xl font-semibold">
              Request submitted
            </h1>

            <p className="mt-2 text-sm text-text-dim leading-6">
              Your faculty registration request has been submitted successfully.
              An administrator will review your request. If approved, your CoreSight
              login credentials will be sent to your registered email address.
            </p>

            <div className="mt-5 rounded-xl bg-surface-2 border border-border-soft p-4 text-left">
              <div className="text-xs text-text-faint">Faculty ID</div>
              <div className="mt-1 text-sm text-text">
                {submitted.employee_id}
              </div>

              <div className="mt-3 text-xs text-text-faint">Email</div>
              <div className="mt-1 text-sm text-text break-all">
                {submitted.email}
              </div>

              <div className="mt-3 text-xs text-text-faint">Status</div>
              <div className="mt-1 text-sm text-accent">
                Pending review
              </div>
            </div>

            <Link
              to="/login"
              className="inline-block mt-6 text-sm text-accent hover:underline"
            >
              Back to sign in
            </Link>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-base px-5 py-10">
      <div className="w-full max-w-md">
        <div className="flex items-center gap-2 justify-center mb-8">
          <span className="w-8 h-8 rounded-md bg-gradient-to-br from-accent to-accent-2 flex items-center justify-center">
            <span className="w-2.5 h-2.5 rounded-full bg-base" />
          </span>

          <span className="font-display text-xl font-semibold tracking-tight">
            CoreSight
          </span>
        </div>

        <div className="mb-6">
          <h1 className="font-display text-2xl font-semibold tracking-tight">
            Faculty registration
          </h1>

          <p className="mt-1.5 text-sm text-text-dim">
            Submit your details to request faculty access.
          </p>
        </div>

        <form
          onSubmit={handleSubmit}
          className="bg-surface border border-border-soft rounded-2xl p-6 space-y-4"
        >
          <div>
            <label className="text-xs text-text-dim">
              Full name
            </label>

            <input
              type="text"
              required
              minLength={2}
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              className="w-full mt-1.5 bg-surface-2 border border-border rounded-lg px-3 py-2.5 text-sm text-text outline-none focus:border-accent"
              placeholder="Enter your full name"
            />
          </div>

          <div>
            <label className="text-xs text-text-dim">
              Faculty / Employee ID
            </label>

            <input
              type="text"
              required
              value={employeeId}
              onChange={(e) => setEmployeeId(e.target.value)}
              className="w-full mt-1.5 bg-surface-2 border border-border rounded-lg px-3 py-2.5 text-sm text-text outline-none focus:border-accent"
              placeholder="e.g. 4221"
            />
          </div>

          <div>
            <label className="text-xs text-text-dim">
              Institutional email
            </label>

            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full mt-1.5 bg-surface-2 border border-border rounded-lg px-3 py-2.5 text-sm text-text outline-none focus:border-accent"
              placeholder="you@college.edu"
            />
          </div>

          <div>
            <label className="text-xs text-text-dim">
              Department
            </label>

            <select
              required
              value={departmentId}
              onChange={(e) => setDepartmentId(e.target.value)}
              disabled={loadingDepartments}
              className="w-full mt-1.5 bg-surface-2 border border-border rounded-lg px-3 py-2.5 text-sm text-text outline-none focus:border-accent disabled:opacity-50"
            >
              <option value="">
                {loadingDepartments
                  ? 'Loading departments…'
                  : 'Select department'}
              </option>

              {departments.map((department) => (
                <option key={department.id} value={department.id}>
                  {department.code} — {department.name}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="text-xs text-text-dim">
              Designation
            </label>

            <input
              type="text"
              value={designation}
              onChange={(e) => setDesignation(e.target.value)}
              className="w-full mt-1.5 bg-surface-2 border border-border rounded-lg px-3 py-2.5 text-sm text-text outline-none focus:border-accent"
              placeholder="e.g. Assistant Professor"
            />
          </div>

          <div>
            <label className="text-xs text-text-dim">
              Phone
            </label>

            <input
              type="tel"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              className="w-full mt-1.5 bg-surface-2 border border-border rounded-lg px-3 py-2.5 text-sm text-text outline-none focus:border-accent"
              placeholder="Enter phone number"
            />
          </div>

          {error && (
            <div className="rounded-lg border border-blocked/20 bg-blocked/5 px-3 py-2.5">
              <p className="text-xs text-blocked">{error}</p>
            </div>
          )}

          <Button
            type="submit"
            className="w-full"
            disabled={submitting || loadingDepartments}
          >
            {submitting ? 'Submitting request…' : 'Request faculty access'}
          </Button>
        </form>

        <div className="mt-5 text-center text-xs text-text-dim">
          Already have a CoreSight account?{' '}
          <Link
            to="/login"
            className="text-accent hover:underline"
          >
            Sign in
          </Link>
        </div>
      </div>
    </div>
  );
}