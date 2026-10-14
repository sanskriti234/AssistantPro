import { request } from './client';

export type Department = {
  id: string;
  code: string;
  name: string;
};

export type FacultyRegistrationRequest = {
  full_name: string;
  employee_id: string;
  email: string;
  department_id: string;
  designation?: string | null;
  phone?: string | null;
};

export type FacultyRegistrationResponse = FacultyRegistrationRequest & {
  id: string;
  status: string;
  requested_at: string;
};

export type FacultyRegistrationAdminRequest = {
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
};

export function getDepartments() {
  return request<Department[]>('/departments');
}

export function registerFaculty(payload: FacultyRegistrationRequest) {
  return request<FacultyRegistrationResponse>('/auth/faculty/register', {
    method: 'POST',
    body: payload,
  });
}


export function getFacultyRegistrationRequests() {
  return request<FacultyRegistrationAdminRequest[]>(
    '/auth/admin/faculty/requests',
  );
}
