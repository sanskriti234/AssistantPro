import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { AppLayout } from '../../components/layout/AppLayout';
import { Card } from '../../components/common/Card';
import { Button } from '../../components/common/Button';
import { request } from '../../api/client';

type FacultyRequest = {
  id: string;
  full_name: string;
  employee_id: string;
  email: string;
  department_id: string;
  department_code: string;
  department_name: string;
  designation: string | null;
  phone: string | null;
  status: string;
  requested_at: string;
  reviewed_at: string | null;
  rejection_reason: string | null;
};

export default function FacultyRequestDetails() {
  const { id } = useParams<{ id: string }>();

  const [data, setData] = useState<FacultyRequest | null>(null);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [error, setError] = useState('');

  const [showReject, setShowReject] = useState(false);
  const [rejectionReason, setRejectionReason] = useState('');
  const [approved, setApproved] = useState(false);

  useEffect(() => {
    async function loadRequest() {
      try {
        const result = await request<FacultyRequest>(
          `/auth/admin/faculty/requests/${id}`
        );

        setData(result);
      } catch (err) {
        setError(
          err instanceof Error
            ? err.message
            : 'Unable to load registration request.'
        );
      } finally {
        setLoading(false);
      }
    }

    if (id) {
      loadRequest();
    }
  }, [id]);

  async function handleApprove() {
    if (!id || !data) return;

    const confirmed = window.confirm(
      `Approve ${data.full_name}'s faculty registration request?`
    );

    if (!confirmed) return;

    setError('');
    setActionLoading(true);

    try {
      await request<{
        message: string;
        user_id: string;
        email: string;
      }>(`/auth/admin/faculty/requests/${id}/approve`, {
        method: 'POST',
      });

      setApproved(true);

      setData({
        ...data,
        status: 'APPROVED',
        reviewed_at: new Date().toISOString(),
      });
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : 'Unable to approve this request.'
      );
    } finally {
      setActionLoading(false);
    }
  }

  async function handleReject() {
    if (!id || !data) return;

    if (!rejectionReason.trim()) {
      setError('Please provide a reason for rejecting this request.');
      return;
    }

    setError('');
    setActionLoading(true);

    try {
      const result = await request<{
        message: string;
        request_id: string;
        status: string;
      }>(`/auth/admin/faculty/requests/${id}/reject`, {
        method: 'POST',
        body: {
          reason: rejectionReason.trim(),
        },
      });

      setData({
        ...data,
        status: result.status,
        reviewed_at: new Date().toISOString(),
        rejection_reason: rejectionReason.trim(),
      });

      setShowReject(false);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : 'Unable to reject this request.'
      );
    } finally {
      setActionLoading(false);
    }
  }

  if (loading) {
    return (
      <AppLayout role="admin" title="Faculty Request">
        <Card className="p-5">
          <p className="text-sm text-text-dim">
            Loading request…
          </p>
        </Card>
      </AppLayout>
    );
  }

  if (error && !data) {
    return (
      <AppLayout role="admin" title="Faculty Request">
        <Card className="p-5">
          <p className="text-sm text-blocked">{error}</p>

          <Link
            to="/admin/faculty"
            className="inline-block mt-4 text-sm text-accent hover:underline"
          >
            Back to Faculty
          </Link>
        </Card>
      </AppLayout>
    );
  }

  if (!data) {
    return null;
  }

  const pending = data.status === 'PENDING';

  return (
    <AppLayout role="admin" title="Faculty Request">
      <div className="max-w-3xl">
        <Link
          to="/admin/faculty"
          className="text-xs text-text-dim hover:text-accent"
        >
          ← Back to Faculty
        </Link>

        <div className="mt-5">
          <Card className="p-6">
            {/* Header */}
            <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4">
              <div>
                <h1 className="font-display text-xl font-semibold">
                  {data.full_name}
                </h1>

                <p className="text-sm text-text-dim mt-1">
                  Faculty registration request
                </p>
              </div>

              <span
                className={`inline-flex self-start px-2.5 py-1 rounded-full text-[10px] font-medium uppercase tracking-wider ${
                  data.status === 'PENDING'
                    ? 'bg-accent/10 text-accent'
                    : data.status === 'APPROVED'
                      ? 'bg-emerald-500/10 text-emerald-400'
                      : 'bg-blocked/10 text-blocked'
                }`}
              >
                {data.status}
              </span>
            </div>

            {/* Details */}
            <div className="mt-7 grid sm:grid-cols-2 gap-x-8 gap-y-5">
              <Detail
                label="Full name"
                value={data.full_name}
              />

              <Detail
                label="Faculty / Employee ID"
                value={data.employee_id}
              />

              <Detail
                label="Email"
                value={data.email}
              />

              <Detail
                label="Phone"
                value={data.phone || 'Not provided'}
              />

              <Detail
                label="Department"
                value={`${data.department_code} — ${data.department_name}`}
              />

              <Detail
                label="Designation"
                value={data.designation || 'Not provided'}
              />

              <Detail
                label="Requested"
                value={new Date(data.requested_at).toLocaleString()}
              />

              {data.reviewed_at && (
                <Detail
                  label="Reviewed"
                  value={new Date(data.reviewed_at).toLocaleString()}
                />
              )}
            </div>

            {/* Rejection reason */}
            {data.rejection_reason && (
              <div className="mt-6 rounded-xl border border-blocked/20 bg-blocked/5 p-4">
                <p className="text-[10px] uppercase tracking-wider text-text-faint">
                  Rejection reason
                </p>

                <p className="text-sm text-text-dim mt-1.5">
                  {data.rejection_reason}
                </p>
              </div>
            )}

            {/* Error */}
            {error && (
              <div className="mt-5 rounded-lg border border-blocked/20 bg-blocked/5 px-3 py-2.5">
                <p className="text-xs text-blocked">
                  {error}
                </p>
              </div>
            )}

            {/* Actions */}
            {pending && !approved && (
              <div className="mt-8 pt-5 border-t border-border-soft">
                {!showReject ? (
                  <div className="flex flex-col-reverse sm:flex-row sm:justify-end gap-2">
                    <Button
                      type="button"
                      onClick={() => setShowReject(true)}
                      disabled={actionLoading}
                      className="border border-blocked/30 bg-transparent text-blocked hover:bg-blocked/5"
                    >
                      Reject
                    </Button>

                    <Button
                      type="button"
                      onClick={handleApprove}
                      disabled={actionLoading}
                    >
                      {actionLoading ? 'Approving…' : 'Accept'}
                    </Button>
                  </div>
                ) : (
                  <div>
                    <label
                      htmlFor="rejectionReason"
                      className="text-xs text-text-dim"
                    >
                      Rejection reason
                    </label>

                    <textarea
                      id="rejectionReason"
                      value={rejectionReason}
                      onChange={(event) =>
                        setRejectionReason(event.target.value)
                      }
                      rows={3}
                      className="w-full mt-1.5 bg-surface-2 border border-border rounded-lg px-3 py-2.5 text-sm text-text outline-none focus:border-accent resize-none"
                      placeholder="Explain why this request is being rejected."
                    />

                    <div className="flex justify-end gap-2 mt-3">
                      <Button
                        type="button"
                        onClick={() => {
                          setShowReject(false);
                          setRejectionReason('');
                          setError('');
                        }}
                        disabled={actionLoading}
                        className="border border-border bg-transparent"
                      >
                        Cancel
                      </Button>

                      <Button
                        type="button"
                        onClick={handleReject}
                        disabled={actionLoading}
                        className="border border-blocked/30 bg-transparent text-blocked"
                      >
                        {actionLoading
                          ? 'Rejecting…'
                          : 'Confirm rejection'}
                      </Button>
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Approval success */}
            {approved && (
              <div className="mt-8 rounded-xl border border-accent/20 bg-accent/5 p-5">
                <h2 className="font-display text-sm font-semibold">
                  Faculty approved
                </h2>

                <p className="text-xs text-text-dim mt-1.5">
                  The faculty account has been created successfully.
                  An activation email has been sent to:
                </p>

                <p className="text-sm text-text mt-3 font-medium">
                  {data.email}
                </p>

                <p className="text-xs text-text-dim mt-3">
                  The faculty member can use the activation link in
                  the email to create their password and activate their
                  account.
                </p>
              </div>
            )}
          </Card>
        </div>
      </div>
    </AppLayout>
  );
}

function Detail({
  label,
  value,
}: {
  label: string;
  value: string;
}) {
  return (
    <div>
      <p className="text-[10px] uppercase tracking-wider text-text-faint">
        {label}
      </p>

      <p className="text-sm text-text mt-1 break-words">
        {value}
      </p>
    </div>
  );
}