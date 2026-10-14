import type { User } from '../types';
import { request, setToken } from './client';

interface LoginResponse {
  user: User;
  accessToken: string;
}

export async function login(email: string, password: string): Promise<User> {
  const data = await request<LoginResponse>('/auth/login', { body: { email, password } });
  setToken(data.accessToken);
  return data.user;
}

export function logout() {
  setToken(null);
}

// Restores a session on page load if a token is already stored (e.g. after
// a refresh). Returns null if there is no valid session.
export async function restoreSession(): Promise<User | null> {
  try {
    return await request<User>('/auth/me');
  } catch {
    setToken(null);
    return null;
  }
}

export async function fetchCurrentUser(_id: string): Promise<User | null> {
  return restoreSession();
}


export interface ForgotPasswordPayload {
  email: string;
}

export interface ResetPasswordPayload {
  token: string;
  new_password: string;
}

export function forgotPassword(payload: ForgotPasswordPayload) {
  return request<{ message: string }>('/auth/forgot-password', {
    method: 'POST',
    body: payload,
  });
}

export function resetPassword(payload: ResetPasswordPayload) {
  return request<{ message: string }>('/auth/reset-password', {
    method: 'POST',
    body: payload,
  });
}

export async function changePassword(
  newPassword: string
) {
  const token = localStorage.getItem('accessToken');

  const response = await fetch(
    'http://localhost:8000/api/auth/change-password',
    {
      method: 'POST',

      headers: {
        'Content-Type': 'application/json',

        Authorization: `Bearer ${token}`,
      },

      body: JSON.stringify({
        new_password: newPassword,
      }),
    }
  );

  const data = await response.json();

  if (!response.ok) {
    throw new Error(
      data.detail || 'Unable to change password'
    );
  }

  return data;
}