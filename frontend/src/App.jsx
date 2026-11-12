import React, { useState, useEffect } from 'react';
import Header from './components/common/Header';
import Sidebar from './components/common/Sidebar';
import LoginView from './components/LoginView';
import AdminDashboard from './components/AdminDashboard';
import TeacherDashboard from './components/TeacherDashboard';
import StudentDashboard from './components/StudentDashboard';
import SplashScreen from './components/SplashScreen';
import LearningWorkspace from './components/common/LearningWorkspace';
import { removeAuthToken, getAuthToken, api, setStoredUser } from './api';

const roleTabs = {
  ADMIN: new Set(['overview', 'users', 'academic', 'timetable', 'defaulters', 'audit', 'curriculum', 'assignments', 'assessments', 'risks', 'documents', 'notifications', 'profile']),
  TEACHER: new Set(['overview', 'my-classes', 'timetable', 'start-session', 'live-monitor', 'records', 'corrections', 'reports', 'curriculum', 'assignments', 'submissions', 'assessments', 'risks', 'activities', 'documents', 'notifications', 'profile']),
  STUDENT: new Set(['overview', 'mark-attendance', 'subject-breakdown', 'risk-calculator', 'timetable', 'history', 'curriculum', 'assignments', 'assessments', 'activities', 'progress', 'assistant', 'notifications', 'profile']),
};

export default function App() {
  const [currentUser, setCurrentUser] = useState(null);
  const [activeTab, setActiveTab] = useState('overview');
  const [sidebarOpenMobile, setSidebarOpenMobile] = useState(false);
  const [isMobile, setIsMobile] = useState(false);
  const [showSplash, setShowSplash] = useState(true);
  const [authLoading, setAuthLoading] = useState(true);
  const [theme, setTheme] = useState(() => localStorage.getItem('jspm_theme') || 'dark');

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('jspm_theme', theme);
  }, [theme]);

  const toggleTheme = () => {
    setTheme((prev) => (prev === 'dark' ? 'light' : 'dark'));
  };

  useEffect(() => {
    // Mobile detection
    const handleResize = () => {
      setIsMobile(window.innerWidth < 768);
    };
    handleResize();
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  useEffect(() => {
    let active = true;
    const token = getAuthToken();
    const handleUnauthorized = () => {
      setCurrentUser(null);
      setAuthLoading(false);
    };
    window.addEventListener('unauthorized', handleUnauthorized);
    if (!token) {
      setAuthLoading(false);
    } else {
      api.getMe()
        .then((user) => {
          if (!active) return;
          setStoredUser(user);
          setCurrentUser(user);
        })
        .catch(() => {
          removeAuthToken();
          if (active) setCurrentUser(null);
        })
        .finally(() => {
          if (active) setAuthLoading(false);
        });
    }
    return () => {
      active = false;
      window.removeEventListener('unauthorized', handleUnauthorized);
    };
  }, []);

  // Hash-based URL routing sync
  useEffect(() => {
    if (!currentUser) return;

    const handleHashChange = () => {
      const hash = window.location.hash.replace('#/', '').replace('#', '');
      const allowedTabs = roleTabs[currentUser.role];
      if (hash && allowedTabs?.has(hash)) {
        setActiveTab(hash);
      } else {
        setActiveTab('overview');
        if (hash) window.location.hash = '#/overview';
      }
    };

    handleHashChange();
    window.addEventListener('hashchange', handleHashChange);
    return () => window.removeEventListener('hashchange', handleHashChange);
  }, [currentUser]);

  const handleSelectTab = (tabId) => {
    if (!roleTabs[currentUser?.role]?.has(tabId)) {
      setActiveTab('overview');
      window.location.hash = '#/overview';
      return;
    }
    setActiveTab(tabId);
    window.location.hash = `#/${tabId}`;
  };

  const handleLoginSuccess = (user) => {
    setCurrentUser(user);
    setActiveTab('overview');
    window.location.hash = '#/overview';
  };

  const handleLogout = () => {
    removeAuthToken();
    setCurrentUser(null);
    window.location.hash = '';
  };

  return (
    <>
      {showSplash && (
        <SplashScreen onComplete={() => setShowSplash(false)} />
      )}

      {authLoading ? (
        <div className="app-loading" role="status">Restoring your secure session…</div>
      ) : !currentUser ? (
        <LoginView onLoginSuccess={handleLoginSuccess} />
      ) : (
        <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column', background: 'var(--bg-primary)', color: 'var(--text-primary)' }}>
          {/* Top App Header */}
          <Header
            currentUser={currentUser}
            onLogout={handleLogout}
            toggleSidebar={() => setSidebarOpenMobile(!sidebarOpenMobile)}
            isMobile={isMobile}
            theme={theme}
            onToggleTheme={toggleTheme}
          />

          {/* Main Body with Sidebar + Subviews */}
          <div style={{ flex: 1, display: 'flex', maxWidth: '1440px', width: '100%', margin: '0 auto' }}>
            {/* Role-based Sidebar */}
            <Sidebar
              role={currentUser.role}
              activeTab={activeTab}
              onSelectTab={handleSelectTab}
              isOpen={sidebarOpenMobile}
              isMobile={isMobile}
              onCloseMobile={() => setSidebarOpenMobile(false)}
              onLogout={handleLogout}
            />

            {/* Dynamic Portal Sub-View */}
            <main style={{ flex: 1, padding: '2rem 1.5rem', minWidth: 0 }}>
              {currentUser.role === 'ADMIN' && (
                <AdminDashboard user={currentUser} activeTab={activeTab} onNavigate={handleSelectTab} />
              )}

              {currentUser.role === 'TEACHER' && (
                <TeacherDashboard user={currentUser} activeTab={activeTab} onNavigate={handleSelectTab} />
              )}

              {currentUser.role === 'STUDENT' && (
                <StudentDashboard user={currentUser} activeTab={activeTab} onNavigate={handleSelectTab} />
              )}
              <LearningWorkspace role={currentUser.role} user={currentUser} activeTab={activeTab} />
            </main>
          </div>

          {/* Footer */}
          <footer style={{
            textAlign: 'center',
            padding: '1.25rem',
            color: 'var(--text-muted)',
            fontSize: '0.82rem',
            borderTop: '1px solid var(--border-glass)',
            background: 'rgba(15, 23, 42, 0.4)',
          }}>
            © 2026 Shri Vaishnav Vidyapeeth Vishwavidyalaya • Attendance & Academic Portal
          </footer>
        </div>
      )}
    </>
  );
}
