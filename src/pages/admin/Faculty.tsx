import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { AppLayout } from '../../components/layout/AppLayout';
import { Card } from '../../components/common/Card';
import { fetchBatches, fetchFacultyList } from '../../api/batches';
import {
  getFacultyRegistrationRequests,
  type FacultyRegistrationAdminRequest,
} from '../../api/faculty';
import type { Batch, FacultyRecord } from '../../types';

export default function Faculty() {
  const [facultyList, setFacultyList] = useState<FacultyRecord[]>([]);
  const [batches, setBatches] = useState<Batch[]>([]);
  const [requests, setRequests] = useState<FacultyRegistrationAdminRequest[]>([]);
  const [loadingRequests, setLoadingRequests] = useState(true);
  const [requestError, setRequestError] = useState('');

  useEffect(() => {
    fetchFacultyList().then(setFacultyList);
    fetchBatches().then(setBatches);

    async function loadRequests() {
      try {
        setRequestError('');
        const data = await getFacultyRegistrationRequests();
        setRequests(data);
      } catch (err) {
        setRequestError(
          err instanceof Error
            ? err.message
            : 'Unable to load registration requests.'
        );
      } finally {
        setLoadingRequests(false);
      }
    }

    loadRequests();
  }, []);

  function batchNames(ids: string[]) {
    return ids
      .map((id) => batches.find((b) => b.id === id)?.name ?? id)
      .join(', ');
  }

  const pendingRequests = requests.filter(
    (request) => request.status === 'PENDING'
  );

  return (
    <AppLayout role="admin" title="Faculty">

      {/* Registration Requests */}
      <section className="mb-8">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="font-display text-base font-semibold">
              Registration Requests
            </h2>
            <p className="text-xs text-text-dim mt-1">
              Faculty access requests awaiting review.
            </p>
          </div>

          {pendingRequests.length > 0 && (
            <span className="px-2.5 py-1 rounded-full bg-accent/10 text-accent text-xs font-medium">
              {pendingRequests.length} pending
            </span>
          )}
        </div>

        {loadingRequests && (
          <Card className="p-4">
            <p className="text-sm text-text-dim">
              Loading requests…
            </p>
          </Card>
        )}

        {!loadingRequests && requestError && (
          <Card className="p-4">
            <p className="text-sm text-blocked">
              {requestError}
            </p>
          </Card>
        )}

        {!loadingRequests &&
          !requestError &&
          pendingRequests.length === 0 && (
            <Card className="p-4">
              <p className="text-sm text-text-dim">
                No pending faculty registration requests.
              </p>
            </Card>
          )}

        {!loadingRequests &&
          !requestError &&
          pendingRequests.length > 0 && (
            <div className="space-y-2">
              {pendingRequests.map((request) => (
                <Card
                  key={request.id}
                  className="px-4 py-3"
                >
                  <div className="flex items-center gap-4">

                    {/* Name */}
                    <div className="min-w-0 flex-1">
                      <p className="font-display text-sm font-semibold truncate">
                        {request.full_name}
                      </p>
                    </div>

                    {/* Faculty ID */}
                    <div className="hidden sm:block w-24">
                      <p className="text-xs text-text-dim">
                        {request.employee_id}
                      </p>
                    </div>

                    {/* Department */}
                    <div className="hidden md:block w-32">
                      <p className="text-xs text-text-dim truncate">
                        {request.department_code}
                      </p>
                    </div>

                    {/* Status */}
                    <div className="w-20">
                      <span className="inline-flex px-2 py-1 rounded-full bg-accent/10 text-accent text-[10px] font-medium uppercase tracking-wider">
                        Pending
                      </span>
                    </div>

                    {/* View */}
                    <Link
                      to={`/admin/faculty/requests/${request.id}`}
                      className="text-xs text-accent hover:underline shrink-0"
                    >
                      View
                    </Link>

                  </div>
                </Card>
              ))}
            </div>
          )}
      </section>

      {/* Existing Faculty */}
      <section>
        <div className="mb-4">
          <h2 className="font-display text-base font-semibold">
            Faculty
          </h2>

          <p className="text-xs text-text-dim mt-1">
            Faculty members currently registered in CoreSight.
          </p>
        </div>

        {facultyList.length === 0 ? (
          <Card className="p-5">
            <p className="text-sm text-text-dim">
              No faculty members registered yet.
            </p>
          </Card>
        ) : (
          <div className="grid sm:grid-cols-2 gap-3">
            {facultyList.map((f) => (
              <Card key={f.id} className="p-4">
                <p className="font-display text-sm font-semibold">
                  {f.name}
                </p>

                <p className="text-xs text-text-dim mt-0.5">
                  {f.email}
                </p>

                <p className="text-xs text-text-faint mt-3 uppercase tracking-wider">
                  Assigned batches
                </p>

                <p className="text-sm text-text-dim mt-1">
                  {batchNames(f.assignedBatchIds) || 'None assigned'}
                </p>
              </Card>
            ))}
          </div>
        )}
      </section>

    </AppLayout>
  );
}