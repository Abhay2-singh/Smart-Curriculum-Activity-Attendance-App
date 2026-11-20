import React, { useState } from 'react';
import { AlertCircle, LogIn, UserCheck, UserPlus } from 'lucide-react';
import { api, setAuthToken, setStoredUser } from '../api';

export default function LoginView({ onLoginSuccess }) {
  const [mode, setMode] = useState('login');
  const [role, setRole] = useState('STUDENT');
  const [fullName, setFullName] = useState('');
  const [username, setUsername] = useState('');
  const [enrollmentNumber, setEnrollmentNumber] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    setNotice('');

    try {
      if (mode === 'login') {
        const res = await api.login(username, password, role);
        setAuthToken(res.access_token);
        setStoredUser(res.user);
        onLoginSuccess(res.user);
        return;
      }

      if (password !== confirmPassword) {
        setError('Passwords do not match.');
        return;
      }

      const registration = {
        full_name: fullName,
        email: username,
        password,
        confirm_password: confirmPassword,
      };
      if (role === 'STUDENT') registration.enrollment_number = enrollmentNumber;

      if (role === 'STUDENT') {
        await api.registerStudent(registration);
      } else {
        await api.registerTeacher(registration);
      }

      setMode('login');
      setPassword('');
      setConfirmPassword('');
      setNotice('Registration successful. Sign in with your registered email and password.');
    } catch (err) {
      setError(err.message || (mode === 'login' ? 'Login failed.' : 'Registration failed.'));
    } finally {
      setLoading(false);
    }
  };

  const switchMode = (nextMode) => {
    setMode(nextMode);
    setError('');
    setNotice('');
    if (nextMode === 'register' && role === 'ADMIN') setRole('STUDENT');
  };

  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      minHeight: '100vh',
      padding: '1.5rem',
    }}>
      <div className="glass-card" style={{
        width: '100%',
        maxWidth: '460px',
        padding: '2.5rem',
        borderRadius: '24px',
        boxShadow: '0 20px 50px rgba(0,0,0,0.5)',
      }}>
        <div style={{ textAlign: 'center', marginBottom: '2rem' }}>
          <div style={{
            display: 'inline-flex',
            alignItems: 'center',
            justifyContent: 'center',
            width: '64px',
            height: '64px',
            borderRadius: '20px',
            background: 'linear-gradient(135deg, var(--accent-primary), #4338ca)',
            boxShadow: 'var(--shadow-glow)',
            marginBottom: '1rem',
          }}>
            <UserCheck size={32} color="#ffffff" />
          </div>
          <div style={{ fontSize: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.1em', color: 'var(--accent-primary)', fontWeight: 700, marginBottom: '0.2rem' }}>
            Shri Vaishnav Vidyapeeth Vishwavidyalaya
          </div>
          <h1 style={{ fontSize: '1.75rem', fontWeight: 800, color: 'var(--text-primary)', margin: 0 }}>
            Attendance MS
          </h1>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.88rem', marginTop: '0.35rem' }}>
            {mode === 'login' ? 'Sign in to access your portal' : 'Create your account'}
          </p>
        </div>

        {(error || notice) && (
          <div role={error ? 'alert' : 'status'} style={{
            display: 'flex',
            alignItems: 'center',
            gap: '0.6rem',
            padding: '0.85rem 1rem',
            background: error ? 'rgba(239, 68, 68, 0.15)' : 'rgba(16, 185, 129, 0.15)',
            border: `1px solid ${error ? 'rgba(239, 68, 68, 0.3)' : 'rgba(16, 185, 129, 0.3)'}`,
            borderRadius: 'var(--radius-md)',
            color: error ? '#fca5a5' : '#6ee7b7',
            fontSize: '0.88rem',
            marginBottom: '1.5rem',
          }}>
            {error && <AlertCircle size={18} />}
            <span>{error || notice}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1.1rem' }}>
          <div>
            <label htmlFor="account-role" style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.4rem' }}>
              {mode === 'login' ? 'Sign in as' : 'Register as'}
            </label>
            <select
              id="account-role"
              className="glass-input"
              value={role}
              onChange={(e) => setRole(e.target.value)}
            >
              <option value="STUDENT">Student</option>
              <option value="TEACHER">Teacher</option>
              {mode === 'login' && <option value="ADMIN">Administrator</option>}
            </select>
          </div>

          {mode === 'register' && (
            <div>
              <label htmlFor="register-name" style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.4rem' }}>
                Full Name
              </label>
              <input
                type="text"
                id="register-name"
                className="glass-input"
                autoComplete="name"
                maxLength={100}
                required
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
              />
            </div>
          )}

          <div>
            <label htmlFor="login-email" style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.4rem' }}>
              {mode === 'login' ? 'Email Address or Username' : 'Email Address'}
            </label>
            <input
              type={mode === 'register' ? 'email' : 'text'}
              id="login-email"
              className="glass-input"
              placeholder={mode === 'login' ? 'Enter your email or username' : 'name@example.com'}
              autoComplete="username"
              required
              value={username}
              onChange={(e) => setUsername(e.target.value)}
            />
          </div>

          {mode === 'register' && role === 'STUDENT' && (
            <div>
              <label htmlFor="register-enrollment" style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.4rem' }}>
                Enrollment Number
              </label>
              <input
                type="text"
                id="register-enrollment"
                className="glass-input"
                autoComplete="off"
                maxLength={50}
                required
                value={enrollmentNumber}
                onChange={(e) => setEnrollmentNumber(e.target.value)}
              />
            </div>
          )}

          <div>
            <label htmlFor="login-password" style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.4rem' }}>
              Password
            </label>
            <input
              type="password"
              id="login-password"
              className="glass-input"
              placeholder="••••••••"
              autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
              minLength={mode === 'register' ? 8 : undefined}
              maxLength={mode === 'register' ? 72 : undefined}
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </div>

          {mode === 'register' && (
            <div>
              <label htmlFor="register-confirm-password" style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.4rem' }}>
                Confirm Password
              </label>
              <input
                type="password"
                id="register-confirm-password"
                className="glass-input"
                autoComplete="new-password"
                minLength={8}
                maxLength={72}
                required
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
              />
            </div>
          )}

          <button
            type="submit"
            className="btn-primary"
            disabled={loading}
            style={{ width: '100%', marginTop: '0.5rem', height: '48px', fontSize: '1rem' }}
          >
            {loading
              ? (mode === 'login' ? 'Authenticating...' : 'Creating account...')
              : mode === 'login'
                ? <><LogIn size={18} /> Sign In</>
                : <><UserPlus size={18} /> Create Account</>}
          </button>
        </form>

        <div style={{ marginTop: '1.5rem', textAlign: 'center', fontSize: '0.88rem', color: 'var(--text-secondary)' }}>
          {mode === 'login' ? "Don't have an account? " : 'Already registered? '}
          <button
            type="button"
            onClick={() => switchMode(mode === 'login' ? 'register' : 'login')}
            style={{ border: 0, padding: 0, background: 'none', color: 'var(--accent-primary)', font: 'inherit', fontWeight: 700, cursor: 'pointer' }}
          >
            {mode === 'login' ? 'Register' : 'Sign in'}
          </button>
        </div>

        <div style={{ marginTop: '1.75rem', textAlign: 'center', fontSize: '0.75rem', color: 'var(--text-muted)' }}>
          © 2026 Shri Vaishnav Vidyapeeth Vishwavidyalaya<br />
          Attendance & Academic Portal
        </div>
      </div>
    </div>
  );
}
