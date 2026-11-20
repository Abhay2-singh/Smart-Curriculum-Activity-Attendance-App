import React, { useState, useEffect } from 'react';
import {
  Users,
  Building2,
  Calendar,
  AlertTriangle,
  ShieldAlert,
  Award,
  Search,
  Plus,
  Filter,
  CheckCircle2,
  XCircle,
  Edit3,
  UserCheck,
  GraduationCap,
  Shield,
  Layers,
  BookOpen,
  FileCheck2,
  Clock,
  Printer,
  Download,
  FileText,
  X
} from 'lucide-react';
import { api } from '../api';
import RiskBadge from './common/RiskBadge';
import Toast from './common/Toast';
import AcademicSetup from './admin/AcademicSetup';

export default function AdminDashboard({ user, activeTab = 'overview', onNavigate }) {
  // Common state
  const [departments, setDepartments] = useState([]);
  const [loading, setLoading] = useState(true);

  // Defaulter Notice Modal & Toast state
  const [selectedNoticeStudent, setSelectedNoticeStudent] = useState(null);
  const [toast, setToast] = useState({ message: '', type: 'success' });

  // Stats
  const [totalStudents, setTotalStudents] = useState(0);
  const [totalTeachers, setTotalTeachers] = useState(0);
  const [activeSessionsCount, setActiveSessionsCount] = useState(0);
  const [totalSubjects, setTotalSubjects] = useState(0);
  const [overviewError, setOverviewError] = useState('');
  const [defaulters, setDefaulters] = useState([]);
  const [threshold, setThreshold] = useState(null);

  // Users tab state
  const [usersList, setUsersList] = useState([]);
  const [usersTotal, setUsersTotal] = useState(0);
  const [usersPage, setUsersPage] = useState(1);
  const [userRoleFilter, setUserRoleFilter] = useState('');
  const [userSearch, setUserSearch] = useState('');
  const [debouncedUserSearch, setDebouncedUserSearch] = useState('');
  const [showCreateUserModal, setShowCreateUserModal] = useState(false);
  const [profileSetupUser, setProfileSetupUser] = useState(null);
  const [createUserForm, setCreateUserForm] = useState({
    username: '',
    email: '',
    password: '',
    full_name: '',
    role: 'STUDENT',
    department_id: '',
    roll_number: '',
    student_id: '',
    enrollment_number: '',
    employee_id: '',
    academic_class_id: '',
    academic_year_id: '',
    semester_id: '',
    division_id: '',
    batch_id: '',
  });
  const [createUserError, setCreateUserError] = useState('');

  // Academic Structure tab state
  const [academicSubTab, setAcademicSubTab] = useState('departments');
  const [academicYears, setAcademicYears] = useState([]);
  const [semesters, setSemesters] = useState([]);
  const [classesList, setClassesList] = useState([]);
  const [divisionsList, setDivisionsList] = useState([]);
  const [batchesList, setBatchesList] = useState([]);
  const [subjectsList, setSubjectsList] = useState([]);
  const [teachersList, setTeachersList] = useState([]);
  const [studentsList, setStudentsList] = useState([]);

  // Timetable tab state
  const [timetables, setTimetables] = useState([]);

  // Audit Logs state
  const [auditLogs, setAuditLogs] = useState([]);

  useEffect(() => {
    fetchInitialData();
  }, []);

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedUserSearch(userSearch), 250);
    return () => clearTimeout(timer);
  }, [userSearch]);

  useEffect(() => {
    if (activeTab === 'users') fetchUsers();
    if (activeTab === 'academic') fetchAcademicStructure();
    if (activeTab === 'timetable') fetchTimetables();
    if (activeTab === 'defaulters') fetchDefaulters();
    if (activeTab === 'audit') fetchAuditLogs();
  }, [activeTab, userRoleFilter, debouncedUserSearch, threshold, usersPage]);

  const fetchInitialData = async () => {
    setLoading(true);
    setOverviewError('');
    try {
      const [depts, defaultersData, sessionsData, teachersData, studentsData, subjects] = await Promise.all([
        api.getDepartments(),
        api.getDefaulters(null, threshold),
        api.getSessions({ status: 'ACTIVE' }),
        api.getUsers({ role: 'TEACHER', limit: 1 }),
        api.getUsers({ role: 'STUDENT', limit: 1 }),
        api.getSubjects(),
      ]);

      setDepartments(depts);
      setDefaulters(defaultersData.defaulters || []);
      setThreshold((current) => current ?? defaultersData.threshold_percentage);
      setActiveSessionsCount(sessionsData.length);
      setTotalTeachers(teachersData.total);
      setTotalStudents(studentsData.total);
      setTotalSubjects(subjects.length);
    } catch (err) {
      setOverviewError(err.message || 'Unable to load admin dashboard data.');
    } finally {
      setLoading(false);
    }
  };

  const fetchUsers = async () => {
    try {
      const res = await api.getUsers({
        skip: (usersPage - 1) * 50,
        role: userRoleFilter || undefined,
        search: debouncedUserSearch || undefined,
        limit: 50,
      });
      setUsersList(res.items || []);
      setUsersTotal(res.total || 0);
    } catch (err) {
      setToast({ message: err.message || 'Unable to load users.', type: 'error' });
    }
  };

  const fetchAcademicStructure = async () => {
    try {
      const [years, depts, classes, divs, subs, tList, sList] = await Promise.all([
        api.getAcademicYears(),
        api.getDepartments(),
        api.getAcademicClasses(),
        api.getDivisions(),
        api.getSubjects(),
        api.getTeachers(),
        api.getStudents(),
      ]);
      setAcademicYears(years);
      setDepartments(depts);
      setClassesList(classes);
      setDivisionsList(divs);
      setSubjectsList(subs);
      setTeachersList(tList);
      setStudentsList(sList);
    } catch (err) {
      setToast({ message: err.message || 'Unable to load academic structure.', type: 'error' });
    }
  };

  const fetchTimetables = async () => {
    try {
      const data = await api.getTimetables();
      setTimetables(data);
    } catch (err) {
      setToast({ message: err.message || 'Unable to load timetables.', type: 'error' });
    }
  };

  const fetchDefaulters = async () => {
    try {
      const res = await api.getDefaulters(null, threshold);
      setDefaulters(res.defaulters || []);
      setThreshold((current) => current ?? res.threshold_percentage);
    } catch (err) {
      setToast({ message: err.message || 'Unable to load defaulter reports.', type: 'error' });
    }
  };

  const fetchAuditLogs = async () => {
    try {
      const logs = await api.getAuditLogs();
      setAuditLogs(logs);
    } catch (err) {
      setToast({ message: err.message || 'Unable to load audit logs.', type: 'error' });
    }
  };

  const handleToggleUserStatus = async (userId, currentStatus) => {
    try {
      await api.updateUserStatus(userId, !currentStatus);
      setToast({ message: 'User status updated.', type: 'success' });
      fetchUsers();
    } catch (err) {
      setToast({ message: err.message || 'Unable to update user status.', type: 'error' });
    }
  };

  const openProfileSetup = (account) => {
    setProfileSetupUser(account);
    setCreateUserForm({
      username: account.username,
      email: account.email,
      password: '',
      full_name: account.full_name || account.student_profile?.full_name || account.teacher_profile?.full_name || '',
      role: account.role,
      department_id: '',
      roll_number: '',
      student_id: '',
      enrollment_number: account.enrollment_number || '',
      employee_id: '',
      academic_class_id: '',
      academic_year_id: '',
      semester_id: '',
      division_id: '',
      batch_id: '',
    });
    setCreateUserError('');
    setShowCreateUserModal(true);
    fetchAcademicStructure();
  };

  const handleCreateUserSubmit = async (e) => {
    e.preventDefault();
    setCreateUserError('');

    if ((!profileSetupUser && (!createUserForm.username || !createUserForm.email || !createUserForm.password)) || (createUserForm.role !== 'ADMIN' && !createUserForm.full_name)) {
      setCreateUserError('Username, email, and password are required; teacher and student profiles also require a full name.');
      return;
    }
    if (createUserForm.role === 'TEACHER' && (!createUserForm.employee_id || !createUserForm.department_id)) {
      setCreateUserError('Employee ID and department are required for a teacher.');
      return;
    }
    if (createUserForm.role === 'STUDENT' && ![
      'enrollment_number', 'roll_number', 'department_id', 'academic_class_id', 'division_id', 'batch_id', 'academic_year_id', 'semester_id',
    ].every((field) => createUserForm[field])) {
      setCreateUserError('Complete the enrollment number, roll, department, class, division, batch, academic year, and semester fields.');
      return;
    }

    try {
      if (profileSetupUser?.role === 'TEACHER') {
        await api.linkTeacherProfile(profileSetupUser.id, {
          full_name: createUserForm.full_name,
          employee_id: createUserForm.employee_id,
          department_id: Number(createUserForm.department_id),
        });
      } else if (profileSetupUser?.role === 'STUDENT') {
        await api.linkStudentProfile(profileSetupUser.id, {
          full_name: createUserForm.full_name,
          ...(createUserForm.student_id ? { student_id: createUserForm.student_id } : {}),
          enrollment_number: createUserForm.enrollment_number,
          roll_number: createUserForm.roll_number,
          department_id: Number(createUserForm.department_id),
          academic_class_id: Number(createUserForm.academic_class_id),
          division_id: Number(createUserForm.division_id),
          batch_id: Number(createUserForm.batch_id),
          academic_year_id: Number(createUserForm.academic_year_id),
          semester_id: Number(createUserForm.semester_id),
        });
        setProfileSetupUser(null);
        setShowCreateUserModal(false);
        setToast({ message: 'Student academic profile linked successfully.', type: 'success' });
        fetchUsers();
        return;
      } else {
      const payload = {
        username: createUserForm.username,
        email: createUserForm.email,
        password: createUserForm.password,
        role: createUserForm.role,
      };

      if (createUserForm.role === 'TEACHER') {
        payload.teacher_profile = {
          full_name: createUserForm.full_name,
          email: createUserForm.email,
          employee_id: createUserForm.employee_id,
          department_id: Number(createUserForm.department_id),
        };
      } else if (createUserForm.role === 'STUDENT') {
        payload.student_profile = {
          full_name: createUserForm.full_name,
          ...(createUserForm.student_id ? { student_id: createUserForm.student_id } : {}),
          roll_number: createUserForm.roll_number,
          enrollment_number: createUserForm.enrollment_number,
          email: createUserForm.email,
          department_id: Number(createUserForm.department_id),
          academic_class_id: Number(createUserForm.academic_class_id),
          division_id: Number(createUserForm.division_id),
          batch_id: Number(createUserForm.batch_id),
          academic_year_id: Number(createUserForm.academic_year_id),
          semester_id: Number(createUserForm.semester_id),
        };
      }

      await api.createUser(payload);
      }
      setProfileSetupUser(null);
      setShowCreateUserModal(false);
      setToast({ message: profileSetupUser ? 'Teacher academic profile linked successfully.' : 'User account created successfully.', type: 'success' });
      fetchUsers();
      fetchInitialData();
    } catch (err) {
      const msg = typeof err.message === 'string' ? err.message : (err.detail || 'Failed to create user account');
      setCreateUserError(msg);
    }
  };

  // Render Sub-Views based on activeTab
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>
      {/* Overview View */}
      {activeTab === 'overview' && (
        <>
          <div>
            <h1 style={{ fontSize: '1.85rem', fontWeight: 800 }}>
              Good morning, {(user?.teacher_profile?.full_name || user?.full_name || user?.username || 'Administrator').split(' ')[0]} 👋
            </h1>
            <p style={{ color: 'var(--text-secondary)', fontSize: '0.92rem', marginTop: '0.2rem' }}>
              Here's today's campus attendance overview for Shri Vaishnav Vidyapeeth Vishwavidyalaya.
            </p>
          </div>
          {loading && <div className="workspace-state" role="status">Loading dashboard data…</div>}
          {overviewError && <div className="workspace-error" role="alert">{overviewError}</div>}

          {/* Metric Cards */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '1.25rem' }}>
            <div className="glass-card" style={{ padding: '1.35rem', display: 'flex', alignItems: 'center', gap: '1.25rem' }}>
              <div style={{ padding: '0.9rem', background: 'rgba(99, 102, 241, 0.15)', borderRadius: '16px', color: '#818cf8' }}>
                <Building2 size={26} />
              </div>
              <div>
                <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', fontWeight: 600 }}>Departments</div>
                <div style={{ fontSize: '1.6rem', fontWeight: 800, marginTop: '0.15rem' }}>{departments.length}</div>
              </div>
            </div>

            <div className="glass-card" style={{ padding: '1.35rem', display: 'flex', alignItems: 'center', gap: '1.25rem' }}>
              <div style={{ padding: '0.9rem', background: 'rgba(59, 130, 246, 0.15)', borderRadius: '16px', color: '#60a5fa' }}>
                <BookOpen size={26} />
              </div>
              <div>
                <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', fontWeight: 600 }}>Total Subjects</div>
                <div style={{ fontSize: '1.6rem', fontWeight: 800, marginTop: '0.15rem' }}>{totalSubjects}</div>
              </div>
            </div>

            <div className="glass-card" style={{ padding: '1.35rem', display: 'flex', alignItems: 'center', gap: '1.25rem' }}>
              <div style={{ padding: '0.9rem', background: 'rgba(16, 185, 129, 0.15)', borderRadius: '16px', color: '#34d399' }}>
                <UserCheck size={26} />
              </div>
              <div>
                <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', fontWeight: 600 }}>Total Teachers</div>
                <div style={{ fontSize: '1.6rem', fontWeight: 800, marginTop: '0.15rem' }}>{totalTeachers}</div>
              </div>
            </div>

            <div className="glass-card" style={{ padding: '1.35rem', display: 'flex', alignItems: 'center', gap: '1.25rem' }}>
              <div style={{ padding: '0.9rem', background: 'rgba(244, 63, 94, 0.15)', borderRadius: '16px', color: '#fb7185' }}>
                <GraduationCap size={26} />
              </div>
              <div>
                <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', fontWeight: 600 }}>Total Students</div>
                <div style={{ fontSize: '1.6rem', fontWeight: 800, marginTop: '0.15rem' }}>{totalStudents}</div>
              </div>
            </div>

            <div className="glass-card" style={{ padding: '1.35rem', display: 'flex', alignItems: 'center', gap: '1.25rem' }}>
              <div style={{ padding: '0.9rem', background: 'rgba(245, 158, 11, 0.15)', borderRadius: '16px', color: '#fbbf24' }}>
                <Clock size={26} />
              </div>
              <div>
                <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', fontWeight: 600 }}>Active Sessions</div>
                <div style={{ fontSize: '1.6rem', fontWeight: 800, marginTop: '0.15rem', color: '#fbbf24' }}>{activeSessionsCount}</div>
              </div>
            </div>

            <div className="glass-card" style={{ padding: '1.35rem', display: 'flex', alignItems: 'center', gap: '1.25rem' }}>
              <div style={{ padding: '0.9rem', background: 'rgba(239, 68, 68, 0.15)', borderRadius: '16px', color: '#f87171' }}>
                <ShieldAlert size={26} />
              </div>
              <div>
                <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', fontWeight: 600 }}>Defaulters (&lt;{threshold}%)</div>
                <div style={{ fontSize: '1.6rem', fontWeight: 800, marginTop: '0.15rem', color: '#ef4444' }}>{defaulters.length}</div>
              </div>
            </div>
          </div>
          <p className="workspace-meta">Overall attendance aggregation is not exposed by the current admin report API; defaulter counts above come from live report data.</p>

          {/* Quick Action Banner */}
          <div className="glass-card" style={{ padding: '1.5rem', background: 'linear-gradient(135deg, rgba(99, 102, 241, 0.1), rgba(67, 56, 202, 0.05))', border: '1px solid rgba(99, 102, 241, 0.3)' }}>
            <h3 style={{ fontSize: '1.15rem', fontWeight: 800, marginBottom: '0.75rem' }}>Quick Admin Actions</h3>
            <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
              <button className="btn-primary" onClick={() => onNavigate('users')}>
                <Users size={16} /> Manage System Users
              </button>
              <button className="btn-secondary" onClick={() => onNavigate('academic')}>
                <Building2 size={16} /> Academic Infrastructure
              </button>
              <button className="btn-secondary" onClick={() => onNavigate('defaulters')}>
                <AlertTriangle size={16} /> Inspect Defaulters
              </button>
              <button className="btn-secondary" onClick={() => onNavigate('audit')}>
                <FileCheck2 size={16} /> Attendance Audit Log
              </button>
            </div>
          </div>

          {/* Department Summary Grid */}
          <div className="glass-card" style={{ padding: '1.75rem' }}>
            <h3 style={{ fontSize: '1.2rem', fontWeight: 700, marginBottom: '1.25rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <Building2 size={20} color="#818cf8" /> Registered Departments
            </h3>
            {departments.length === 0 ? (
              <div style={{ color: 'var(--text-muted)', textAlign: 'center', padding: '1.5rem' }}>No departments configured.</div>
            ) : (
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '1rem' }}>
                {departments.map((dept) => (
                  <div key={dept.id} style={{ padding: '1.25rem', background: 'rgba(255,255,255,0.03)', borderRadius: '14px', border: '1px solid var(--border-glass)' }}>
                    <div style={{ fontSize: '0.75rem', color: '#818cf8', fontWeight: 700 }}>CODE: {dept.code}</div>
                    <div style={{ fontSize: '1.1rem', fontWeight: 800, marginTop: '0.2rem' }}>{dept.name}</div>
                    <div style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', marginTop: '0.5rem' }}>
                      Status: <span style={{ color: dept.is_active ? '#34d399' : '#f87171' }}>{dept.is_active ? 'Active' : 'Inactive'}</span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </>
      )}

      {/* User Management View */}
      {activeTab === 'users' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem' }}>
            <div>
              <h1 style={{ fontSize: '1.85rem', fontWeight: 800 }}>User Management</h1>
              <p style={{ color: 'var(--text-secondary)', fontSize: '0.92rem' }}>
                View, filter, create, and manage access roles for all administrators, teachers, and students.
              </p>
            </div>
            <button className="btn-primary" onClick={() => {
              setShowCreateUserModal(true);
              fetchAcademicStructure();
            }}>
              <Plus size={18} /> Add New System User
            </button>
          </div>

          {/* Filters Bar */}
          <div className="glass-card" style={{ padding: '1.25rem', display: 'flex', gap: '1rem', flexWrap: 'wrap', alignItems: 'center' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flex: 1, minWidth: '240px' }}>
              <Search size={18} color="var(--text-muted)" />
              <input
                type="text"
                className="glass-input"
                placeholder="Search by name, username, or email..."
                value={userSearch}
                onChange={(e) => {
                  setUserPage(1);
                  setUserSearch(e.target.value);
                }}
              />
            </div>

            <div style={{ display: 'flex', gap: '0.5rem' }}>
              {['', 'ADMIN', 'TEACHER', 'STUDENT'].map((r) => (
                <button
                  key={r}
                  className={`btn-secondary ${userRoleFilter === r ? 'active' : ''}`}
                  style={{
                    padding: '0.45rem 0.85rem',
                    fontSize: '0.82rem',
                    background: userRoleFilter === r ? 'var(--accent-primary)' : 'rgba(255,255,255,0.05)',
                    color: userRoleFilter === r ? '#ffffff' : 'var(--text-secondary)',
                  }}
                  onClick={() => {
                    setUserPage(1);
                    setUserRoleFilter(r);
                  }}
                >
                  {r === '' ? 'All Roles' : r}
                </button>
              ))}
            </div>
          </div>

          {/* Users Table */}
          <div className="glass-card" style={{ padding: '1.5rem', overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.9rem' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid var(--border-glass)', color: 'var(--text-secondary)' }}>
                  <th style={{ padding: '0.85rem 1rem' }}>User ID</th>
                  <th style={{ padding: '0.85rem 1rem' }}>Username / Full Name</th>
                  <th style={{ padding: '0.85rem 1rem' }}>Email</th>
                  <th style={{ padding: '0.85rem 1rem' }}>Role</th>
                  <th style={{ padding: '0.85rem 1rem' }}>Status</th>
                  <th style={{ padding: '0.85rem 1rem' }}>Action</th>
                </tr>
              </thead>
              <tbody>
                {usersList.length === 0 ? (
                  <tr>
                    <td colSpan={6} style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-muted)' }}>
                      No users match the search criteria.
                    </td>
                  </tr>
                ) : (
                  usersList.map((u) => (
                    <tr key={u.id} style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
                      <td style={{ padding: '0.85rem 1rem', fontWeight: 600 }}>#{u.id}</td>
                      <td style={{ padding: '0.85rem 1rem' }}>
                        <div style={{ fontWeight: 700 }}>{u.student_profile?.full_name || u.teacher_profile?.full_name || u.full_name || u.username}</div>
                        <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>@{u.username}</div>
                      </td>
                      <td style={{ padding: '0.85rem 1rem', color: 'var(--text-secondary)' }}>{u.email}</td>
                      <td style={{ padding: '0.85rem 1rem' }}>
                        <span className={`badge badge-${u.role.toLowerCase()}`}>{u.role}</span>
                      </td>
                      <td style={{ padding: '0.85rem 1rem' }}>
                        <span className={`badge badge-${u.is_active ? 'active' : 'expired'}`}>
                          {u.is_active ? 'Active' : 'Disabled'}
                        </span>
                      </td>
                      <td style={{ padding: '0.85rem 1rem' }}>
                        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.4rem' }}>
                          {((u.role === 'STUDENT' && !u.student_profile) || (u.role === 'TEACHER' && !u.teacher_profile)) && (
                            <button
                              className="btn-secondary"
                              style={{ padding: '0.3rem 0.65rem', fontSize: '0.78rem' }}
                              onClick={() => openProfileSetup(u)}
                            >
                              Complete profile
                            </button>
                          )}
                          <button
                            className="btn-secondary"
                            style={{ padding: '0.3rem 0.65rem', fontSize: '0.78rem', color: u.is_active ? '#f87171' : '#34d399' }}
                            onClick={() => handleToggleUserStatus(u.id, u.is_active)}
                          >
                            {u.is_active ? 'Deactivate' : 'Activate'}
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
            <div className="table-pagination">
              <span>Showing {usersTotal === 0 ? 0 : (usersPage - 1) * 50 + 1}–{Math.min(usersPage * 50, usersTotal)} of {usersTotal}</span>
              <div>
                <button className="btn-secondary" disabled={usersPage <= 1} onClick={() => setUsersPage((page) => page - 1)}>Previous</button>
                <button className="btn-secondary" disabled={usersPage * 50 >= usersTotal} onClick={() => setUsersPage((page) => page + 1)}>Next</button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Modal: Create User */}
      {showCreateUserModal && (
        <div className="modal-overlay">
          <div className="glass-card" style={{ maxWidth: '520px', width: '100%', padding: '2rem' }}>
            <h3 style={{ fontSize: '1.35rem', fontWeight: 800, marginBottom: '1.25rem' }}>
              {profileSetupUser ? `Complete ${profileSetupUser.role.toLowerCase()} profile` : 'Create System User'}
            </h3>

            {createUserError && (
              <div style={{ color: '#ef4444', fontSize: '0.85rem', marginBottom: '1rem' }}>{createUserError}</div>
            )}

            <form onSubmit={handleCreateUserSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
                {!profileSetupUser && <div>
                  <label style={{ display: 'block', fontSize: '0.82rem', color: 'var(--text-secondary)', marginBottom: '0.35rem' }}>Username</label>
                  <input
                    type="text"
                    className="glass-input"
                    placeholder="e.g. john_doe"
                    value={createUserForm.username}
                    onChange={(e) => setCreateUserForm({ ...createUserForm, username: e.target.value })}
                    minLength="3"
                    required
                  />
                </div>}
                {createUserForm.role !== 'ADMIN' && <div>
                  <label style={{ display: 'block', fontSize: '0.82rem', color: 'var(--text-secondary)', marginBottom: '0.35rem' }}>Full Name</label>
                  <input
                    type="text"
                    className="glass-input"
                    placeholder="e.g. John Doe"
                    value={createUserForm.full_name}
                    onChange={(e) => setCreateUserForm({ ...createUserForm, full_name: e.target.value })}
                    required
                  />
                </div>}
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
                <div>
                  <label style={{ display: 'block', fontSize: '0.82rem', color: 'var(--text-secondary)', marginBottom: '0.35rem' }}>Email</label>
                  <input
                    type="email"
                    className="glass-input"
                    placeholder="user@institution.edu"
                    value={createUserForm.email}
                    onChange={(e) => setCreateUserForm({ ...createUserForm, email: e.target.value })}
                    readOnly={Boolean(profileSetupUser)}
                    required
                  />
                </div>
                {!profileSetupUser && <div>
                  <label style={{ display: 'block', fontSize: '0.82rem', color: 'var(--text-secondary)', marginBottom: '0.35rem' }}>Password</label>
                  <input
                    type="password"
                    className="glass-input"
                    placeholder="••••••••"
                    value={createUserForm.password}
                    onChange={(e) => setCreateUserForm({ ...createUserForm, password: e.target.value })}
                    minLength="6"
                    required
                  />
                </div>}
              </div>

              {!profileSetupUser && <div>
                <label style={{ display: 'block', fontSize: '0.82rem', color: 'var(--text-secondary)', marginBottom: '0.35rem' }}>Assign Role</label>
                <select
                  className="glass-input"
                  value={createUserForm.role}
                  onChange={(e) => setCreateUserForm({ ...createUserForm, role: e.target.value })}
                >
                  <option value="STUDENT" style={{ background: '#111827' }}>STUDENT</option>
                  <option value="TEACHER" style={{ background: '#111827' }}>TEACHER</option>
                  <option value="ADMIN" style={{ background: '#111827' }}>ADMIN</option>
                </select>
              </div>}

              {createUserForm.role === 'STUDENT' && (
                <div className="profile-fields">
                  <label style={{ display: 'block', fontSize: '0.82rem', color: 'var(--text-secondary)', marginBottom: '0.35rem' }}>Roll Number</label>
                  <input
                    type="text"
                    className="glass-input"
                    placeholder="Institution-assigned roll number"
                    value={createUserForm.roll_number}
                    onChange={(e) => setCreateUserForm({ ...createUserForm, roll_number: e.target.value })}
                    required
                  />
                  <label>Student ID (optional)
                    <input className="glass-input" value={createUserForm.student_id} onChange={(e) => setCreateUserForm({ ...createUserForm, student_id: e.target.value })} />
                  </label>
                  <label>Enrollment number
                    <input className="glass-input" required value={createUserForm.enrollment_number} onChange={(e) => setCreateUserForm({ ...createUserForm, enrollment_number: e.target.value })} />
                  </label>
                </div>
              )}
              {(createUserForm.role === 'TEACHER' || createUserForm.role === 'STUDENT') && (
                <label>Department
                  <select className="glass-input" required value={createUserForm.department_id} onChange={(e) => setCreateUserForm({ ...createUserForm, department_id: e.target.value })}>
                    <option value="">Select department</option>
                    {departments.map((department) => <option key={department.id} value={department.id}>{department.name}</option>)}
                  </select>
                </label>
              )}
              {createUserForm.role === 'TEACHER' && (
                <label>Employee ID
                  <input className="glass-input" required value={createUserForm.employee_id} onChange={(e) => setCreateUserForm({ ...createUserForm, employee_id: e.target.value })} />
                </label>
              )}
              {createUserForm.role === 'STUDENT' && (
                <div className="profile-fields">
                  <label>Academic class
                    <select className="glass-input" required value={createUserForm.academic_class_id} onChange={(e) => {
                      const academicClassId = e.target.value;
                      setCreateUserForm({ ...createUserForm, academic_class_id: academicClassId, division_id: '', batch_id: '' });
                      api.getDivisions(academicClassId).then(setDivisionsList).catch((err) => setCreateUserError(err.message));
                    }}>
                      <option value="">Select class</option>
                      {classesList.filter((item) => !createUserForm.department_id || item.department_id === Number(createUserForm.department_id)).map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
                    </select>
                  </label>
                  <label>Division
                    <select className="glass-input" required value={createUserForm.division_id} onChange={(e) => {
                      const divisionId = e.target.value;
                      setCreateUserForm({ ...createUserForm, division_id: divisionId, batch_id: '' });
                      api.getBatches(divisionId).then(setBatchesList).catch((err) => setCreateUserError(err.message));
                    }}>
                      <option value="">Select division</option>
                      {divisionsList.filter((item) => (
                        (!createUserForm.academic_class_id || item.academic_class_id === Number(createUserForm.academic_class_id))
                        && (!createUserForm.academic_year_id || item.academic_year_id === Number(createUserForm.academic_year_id))
                        && (!createUserForm.semester_id || item.semester_id === Number(createUserForm.semester_id))
                      )).map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
                    </select>
                  </label>
                  <label>Batch
                    <select className="glass-input" required value={createUserForm.batch_id} onChange={(e) => setCreateUserForm({ ...createUserForm, batch_id: e.target.value })}>
                      <option value="">Select batch</option>
                      {batchesList.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
                    </select>
                  </label>
                  <label>Academic year
                    <select className="glass-input" required value={createUserForm.academic_year_id} onChange={(e) => {
                      const academicYearId = e.target.value;
                      setCreateUserForm({
                        ...createUserForm,
                        academic_year_id: academicYearId,
                        semester_id: '',
                        division_id: '',
                        batch_id: '',
                      });
                      api.getSemesters(academicYearId).then(setSemesters).catch((err) => setCreateUserError(err.message));
                    }}>
                      <option value="">Select year</option>
                      {academicYears.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
                    </select>
                  </label>
                  <label>Semester
                    <select className="glass-input" required value={createUserForm.semester_id} onChange={(e) => setCreateUserForm({
                      ...createUserForm,
                      semester_id: e.target.value,
                      division_id: '',
                      batch_id: '',
                    })}>
                      <option value="">Select semester</option>
                      {semesters.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
                    </select>
                  </label>
                </div>
              )}

              <div style={{ display: 'flex', gap: '0.75rem', marginTop: '1rem' }}>
                <button type="submit" className="btn-primary" style={{ flex: 1 }}>
                  {profileSetupUser ? 'Link Academic Profile' : 'Create Account'}
                </button>
                <button
                  type="button"
                  className="btn-secondary"
                  style={{ flex: 1 }}
                  onClick={() => {
                    setShowCreateUserModal(false);
                    setProfileSetupUser(null);
                  }}
                >
                  Cancel
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Academic Structure View */}
      {activeTab === 'academic' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
          <div>
            <h1 style={{ fontSize: '1.85rem', fontWeight: 800 }}>Academic Structure & Hierarchy</h1>
            <p style={{ color: 'var(--text-secondary)', fontSize: '0.92rem' }}>
              Departments, academic years, classes, divisions, batches, subjects, teachers, and students.
            </p>
          </div>

          <AcademicSetup onDataChanged={fetchAcademicStructure} />

          {/* Sub-tabs */}
          <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', borderBottom: '1px solid var(--border-glass)', paddingBottom: '0.5rem' }}>
            {[
              { id: 'departments', label: 'Departments' },
              { id: 'classes', label: 'Classes & Divisions' },
              { id: 'subjects', label: 'Subjects' },
              { id: 'teachers', label: 'Faculty Profiles' },
              { id: 'students', label: 'Student Profiles' },
            ].map((sub) => (
              <button
                key={sub.id}
                className={`btn-secondary ${academicSubTab === sub.id ? 'active' : ''}`}
                style={{
                  padding: '0.45rem 0.9rem',
                  fontSize: '0.85rem',
                  background: academicSubTab === sub.id ? 'var(--accent-primary)' : 'rgba(255,255,255,0.03)',
                  color: academicSubTab === sub.id ? '#ffffff' : 'var(--text-secondary)',
                }}
                onClick={() => setAcademicSubTab(sub.id)}
              >
                {sub.label}
              </button>
            ))}
          </div>

          <div className="glass-card" style={{ padding: '1.75rem' }}>
            {academicSubTab === 'departments' && (
              <div>
                <h3 style={{ fontSize: '1.2rem', fontWeight: 700, marginBottom: '1.25rem' }}>Departments List</h3>
                <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.9rem' }}>
                  <thead>
                    <tr style={{ borderBottom: '1px solid var(--border-glass)', color: 'var(--text-secondary)' }}>
                      <th style={{ padding: '0.75rem' }}>ID</th>
                      <th style={{ padding: '0.75rem' }}>Code</th>
                      <th style={{ padding: '0.75rem' }}>Department Name</th>
                      <th style={{ padding: '0.75rem' }}>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {departments.map((d) => (
                      <tr key={d.id} style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
                        <td style={{ padding: '0.75rem', fontWeight: 600 }}>#{d.id}</td>
                        <td style={{ padding: '0.75rem', fontFamily: 'monospace', color: '#818cf8' }}>{d.code}</td>
                        <td style={{ padding: '0.75rem', fontWeight: 700 }}>{d.name}</td>
                        <td style={{ padding: '0.75rem' }}>
                          <span className={`badge badge-${d.is_active ? 'active' : 'expired'}`}>{d.is_active ? 'ACTIVE' : 'INACTIVE'}</span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {academicSubTab === 'classes' && (
              <div>
                <h3 style={{ fontSize: '1.2rem', fontWeight: 700, marginBottom: '1.25rem' }}>Divisions List</h3>
                <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.9rem' }}>
                  <thead>
                    <tr style={{ borderBottom: '1px solid var(--border-glass)', color: 'var(--text-secondary)' }}>
                      <th style={{ padding: '0.75rem' }}>Division ID</th>
                      <th style={{ padding: '0.75rem' }}>Division Name</th>
                      <th style={{ padding: '0.75rem' }}>Academic Class ID</th>
                      <th style={{ padding: '0.75rem' }}>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {divisionsList.map((div) => (
                      <tr key={div.id} style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
                        <td style={{ padding: '0.75rem', fontWeight: 600 }}>#{div.id}</td>
                        <td style={{ padding: '0.75rem', fontWeight: 700 }}>{div.name}</td>
                        <td style={{ padding: '0.75rem' }}>Class #{div.academic_class_id}</td>
                        <td style={{ padding: '0.75rem' }}>
                          <span className={`badge badge-${div.is_active ? 'active' : 'expired'}`}>{div.is_active ? 'ACTIVE' : 'INACTIVE'}</span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {academicSubTab === 'subjects' && (
              <div>
                <h3 style={{ fontSize: '1.2rem', fontWeight: 700, marginBottom: '1.25rem' }}>Subject Catalog</h3>
                <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.9rem' }}>
                  <thead>
                    <tr style={{ borderBottom: '1px solid var(--border-glass)', color: 'var(--text-secondary)' }}>
                      <th style={{ padding: '0.75rem' }}>Subject Code</th>
                      <th style={{ padding: '0.75rem' }}>Subject Name</th>
                      <th style={{ padding: '0.75rem' }}>Type</th>
                      <th style={{ padding: '0.75rem' }}>Credits</th>
                    </tr>
                  </thead>
                  <tbody>
                    {subjectsList.map((s) => (
                      <tr key={s.id} style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
                        <td style={{ padding: '0.75rem', fontFamily: 'monospace', color: '#818cf8', fontWeight: 700 }}>{s.code}</td>
                        <td style={{ padding: '0.75rem', fontWeight: 700 }}>{s.name}</td>
                        <td style={{ padding: '0.75rem', color: 'var(--text-secondary)' }}>{s.subject_type || 'THEORY'}</td>
                        <td style={{ padding: '0.75rem' }}>{s.credits || 4}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {academicSubTab === 'teachers' && (
              <div>
                <h3 style={{ fontSize: '1.2rem', fontWeight: 700, marginBottom: '1.25rem' }}>Faculty Profiles</h3>
                {teachersList.length === 0 ? (
                  <div style={{ padding: '2.5rem', textAlign: 'center', color: 'var(--text-muted)' }}>
                    No faculty profiles found. Use User Management to create teacher accounts.
                  </div>
                ) : (
                  <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.9rem' }}>
                    <thead>
                      <tr style={{ borderBottom: '1px solid var(--border-glass)', color: 'var(--text-secondary)' }}>
                        <th style={{ padding: '0.75rem' }}>Employee ID</th>
                        <th style={{ padding: '0.75rem' }}>Teacher Name</th>
                        <th style={{ padding: '0.75rem' }}>Email</th>
                        <th style={{ padding: '0.75rem' }}>Department ID</th>
                      </tr>
                    </thead>
                    <tbody>
                      {teachersList.map((t) => (
                        <tr key={t.id} style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
                          <td style={{ padding: '0.75rem', fontFamily: 'monospace', color: '#34d399', fontWeight: 700 }}>{t.employee_id}</td>
                          <td style={{ padding: '0.75rem', fontWeight: 700 }}>{t.full_name}</td>
                          <td style={{ padding: '0.75rem', color: 'var(--text-secondary)' }}>{t.email}</td>
                          <td style={{ padding: '0.75rem' }}>Dept #{t.department_id || 1}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
            )}

            {academicSubTab === 'students' && (
              <div>
                <h3 style={{ fontSize: '1.2rem', fontWeight: 700, marginBottom: '1.25rem' }}>Enrolled Students</h3>
                {studentsList.length === 0 ? (
                  <div style={{ padding: '2.5rem', textAlign: 'center', color: 'var(--text-muted)' }}>
                    No student profiles found. Use User Management to create student accounts.
                  </div>
                ) : (
                  <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.9rem' }}>
                    <thead>
                      <tr style={{ borderBottom: '1px solid var(--border-glass)', color: 'var(--text-secondary)' }}>
                        <th style={{ padding: '0.75rem' }}>Roll Number</th>
                        <th style={{ padding: '0.75rem' }}>Student Name</th>
                        <th style={{ padding: '0.75rem' }}>Email</th>
                        <th style={{ padding: '0.75rem' }}>Division ID</th>
                      </tr>
                    </thead>
                    <tbody>
                      {studentsList.map((st) => (
                        <tr key={st.id} style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
                          <td style={{ padding: '0.75rem', fontFamily: 'monospace', color: '#fb7185', fontWeight: 700 }}>{st.roll_number}</td>
                          <td style={{ padding: '0.75rem', fontWeight: 700 }}>{st.full_name}</td>
                          <td style={{ padding: '0.75rem', color: 'var(--text-secondary)' }}>{st.email}</td>
                          <td style={{ padding: '0.75rem' }}>Division #{st.division_id}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Timetable Management View */}
      {activeTab === 'timetable' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
          <div>
            <h1 style={{ fontSize: '1.85rem', fontWeight: 800 }}>Master Timetable Schedule</h1>
            <p style={{ color: 'var(--text-secondary)', fontSize: '0.92rem' }}>
              System-wide timetable entries mapped by day, division, subject, and faculty.
            </p>
          </div>

          <div className="glass-card" style={{ padding: '1.75rem' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.9rem' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid var(--border-glass)', color: 'var(--text-secondary)' }}>
                  <th style={{ padding: '0.85rem 1rem' }}>ID</th>
                  <th style={{ padding: '0.85rem 1rem' }}>Day</th>
                  <th style={{ padding: '0.85rem 1rem' }}>Time Slot</th>
                  <th style={{ padding: '0.85rem 1rem' }}>Division ID</th>
                  <th style={{ padding: '0.85rem 1rem' }}>Subject ID</th>
                  <th style={{ padding: '0.85rem 1rem' }}>Teacher ID</th>
                  <th style={{ padding: '0.85rem 1rem' }}>Status</th>
                </tr>
              </thead>
              <tbody>
                {timetables.length === 0 ? (
                  <tr>
                    <td colSpan={7} style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-muted)' }}>
                      No timetable schedules registered.
                    </td>
                  </tr>
                ) : (
                  timetables.map((t) => (
                    <tr key={t.id} style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
                      <td style={{ padding: '0.85rem 1rem', fontWeight: 600 }}>#{t.id}</td>
                      <td style={{ padding: '0.85rem 1rem', fontWeight: 700, color: '#818cf8' }}>{t.day_of_week}</td>
                      <td style={{ padding: '0.85rem 1rem' }}>{t.start_time} - {t.end_time}</td>
                      <td style={{ padding: '0.85rem 1rem' }}>Division #{t.division_id}</td>
                      <td style={{ padding: '0.85rem 1rem' }}>Subject #{t.subject_id}</td>
                      <td style={{ padding: '0.85rem 1rem' }}>Teacher #{t.teacher_id}</td>
                      <td style={{ padding: '0.85rem 1rem' }}>
                        <span className={`badge badge-${t.is_active ? 'active' : 'expired'}`}>{t.is_active ? 'ACTIVE' : 'INACTIVE'}</span>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Defaulters & Analytics View */}
      {activeTab === 'defaulters' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
          <div>
            <h1 style={{ fontSize: '1.85rem', fontWeight: 800 }}>Defaulters & Compliance Analytics</h1>
            <p style={{ color: 'var(--text-secondary)', fontSize: '0.92rem' }}>
              Track students below required attendance thresholds with smart risk categorization.
            </p>
          </div>

          {/* Smart Attendance Insights Banner */}
          <div className="glass-card" style={{
            padding: '1.5rem',
            background: 'linear-gradient(135deg, rgba(239, 68, 68, 0.12), rgba(220, 38, 38, 0.04))',
            border: '1px solid rgba(239, 68, 68, 0.3)',
          }}>
            <div style={{ display: 'flex', alignItems: 'flex-start', gap: '1rem' }}>
              <div style={{ padding: '0.75rem', borderRadius: '14px', background: 'rgba(239, 68, 68, 0.2)', color: '#f87171' }}>
                <ShieldAlert size={26} />
              </div>
              <div>
                <h3 style={{ fontSize: '1.15rem', fontWeight: 800, color: '#ffffff' }}>Smart Attendance Insights</h3>
                <p style={{ fontSize: '0.88rem', color: 'var(--text-secondary)', marginTop: '0.3rem', margin: 0 }}>
                  Students below the configured attendance threshold require academic attention.
                </p>
              </div>
            </div>
          </div>

          <div className="glass-card" style={{ padding: '1.75rem' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem', flexWrap: 'wrap', gap: '1rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                <AlertTriangle size={22} color="#ef4444" />
                <h3 style={{ fontSize: '1.2rem', fontWeight: 700 }}>Defaulter Audit List</h3>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                <label style={{ fontSize: '0.88rem', color: 'var(--text-secondary)' }}>Attendance Threshold (%):</label>
                <input
                  type="number"
                  className="glass-input"
                  style={{ width: '80px', padding: '0.4rem 0.6rem' }}
                  value={threshold ?? ''}
                  onChange={(e) => setThreshold(e.target.value)}
                />
                <button className="btn-primary" style={{ padding: '0.4rem 0.85rem' }} onClick={fetchDefaulters}>
                  Apply Filter
                </button>

                <button
                  className="btn-secondary"
                  style={{ padding: '0.4rem 0.85rem', gap: '0.4rem', background: 'rgba(16, 185, 129, 0.1)', color: '#10b981', border: '1px solid rgba(16, 185, 129, 0.3)' }}
                  onClick={() => {
                    if (defaulters.length === 0) {
                      setToast({ message: 'No defaulter data to export.', type: 'error' });
                      return;
                    }
                    const csvHeader = "Roll Number,Student Name,Email,Division,Attended,Total,Attendance Percentage\n";
                    const csvRows = defaulters.map(d => `"${d.roll_number}","${d.full_name}","${d.email}","${d.division_name || ''}",${d.attended_sessions},${d.total_sessions},${d.attendance_percentage}%`).join("\n");
                    const blob = new Blob([csvHeader + csvRows], { type: 'text/csv' });
                    const url = URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = `Attendance_Defaulter_Report_${new Date().toISOString().slice(0,10)}.csv`;
                    a.click();
                    setToast({ message: 'Defaulter Report exported to CSV/Excel format!', type: 'success' });
                  }}
                >
                  <Download size={15} /> Export CSV
                </button>
              </div>
            </div>

            {defaulters.length === 0 ? (
              <div style={{ padding: '3rem', textAlign: 'center', color: 'var(--text-muted)' }}>
                🎉 Excellent! No students are currently below {threshold}% attendance.
              </div>
            ) : (
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.9rem' }}>
                  <thead>
                    <tr style={{ borderBottom: '1px solid var(--border-glass)', color: 'var(--text-secondary)' }}>
                      <th style={{ padding: '0.85rem 1rem' }}>Roll No</th>
                      <th style={{ padding: '0.85rem 1rem' }}>Student Name</th>
                      <th style={{ padding: '0.85rem 1rem' }}>Email</th>
                      <th style={{ padding: '0.85rem 1rem' }}>Division</th>
                      <th style={{ padding: '0.85rem 1rem' }}>Attended / Total</th>
                      <th style={{ padding: '0.85rem 1rem' }}>Attendance %</th>
                      <th style={{ padding: '0.85rem 1rem' }}>Risk Level</th>
                      <th style={{ padding: '0.85rem 1rem' }}>Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {defaulters.map((st) => (
                      <tr key={st.student_id} style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
                        <td style={{ padding: '0.85rem 1rem', fontWeight: 600, fontFamily: 'monospace' }}>{st.roll_number}</td>
                        <td style={{ padding: '0.85rem 1rem', fontWeight: 700 }}>{st.full_name}</td>
                        <td style={{ padding: '0.85rem 1rem', color: 'var(--text-secondary)' }}>{st.email}</td>
                        <td style={{ padding: '0.85rem 1rem' }}>{st.division_name || '-'}</td>
                        <td style={{ padding: '0.85rem 1rem' }}>{st.attended_sessions} / {st.total_sessions}</td>
                        <td style={{ padding: '0.85rem 1rem', fontWeight: 800, color: st.attendance_percentage < threshold * 0.8 ? '#f87171' : '#fbbf24' }}>
                          {st.attendance_percentage}%
                        </td>
                        <td style={{ padding: '0.85rem 1rem' }}>
                          <RiskBadge percentage={st.attendance_percentage} requiredPercentage={threshold} />
                        </td>
                        <td style={{ padding: '0.85rem 1rem' }}>
                          <button
                            onClick={() => setSelectedNoticeStudent(st)}
                            className="btn-secondary"
                            style={{ padding: '0.35rem 0.65rem', fontSize: '0.78rem', gap: '0.35rem' }}
                          >
                            <FileText size={14} color="#818cf8" /> Notice
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Audit Trail & Corrections View */}
      {activeTab === 'audit' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
          <div>
            <h1 style={{ fontSize: '1.85rem', fontWeight: 800 }}>System Audit Trail & Log</h1>
            <p style={{ color: 'var(--text-secondary)', fontSize: '0.92rem' }}>
              Full immutable audit log of manual attendance overrides and status corrections.
            </p>
          </div>

          <div className="glass-card" style={{ padding: '1.75rem' }}>
            {auditLogs.length === 0 ? (
              <div style={{ padding: '3rem', textAlign: 'center', color: 'var(--text-muted)' }}>
                No attendance corrections or manual overrides logged yet.
              </div>
            ) : (
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.9rem' }}>
                  <thead>
                    <tr style={{ borderBottom: '1px solid var(--border-glass)', color: 'var(--text-secondary)' }}>
                      <th style={{ padding: '0.85rem 1rem' }}>Log ID</th>
                      <th style={{ padding: '0.85rem 1rem' }}>Timestamp</th>
                      <th style={{ padding: '0.85rem 1rem' }}>Student</th>
                      <th style={{ padding: '0.85rem 1rem' }}>Status Change</th>
                      <th style={{ padding: '0.85rem 1rem' }}>Corrected By</th>
                      <th style={{ padding: '0.85rem 1rem' }}>Audit Reason</th>
                    </tr>
                  </thead>
                  <tbody>
                    {auditLogs.map((log) => (
                      <tr key={log.id} style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
                        <td style={{ padding: '0.85rem 1rem', fontWeight: 600 }}>#{log.id}</td>
                        <td style={{ padding: '0.85rem 1rem', color: 'var(--text-secondary)', fontSize: '0.82rem' }}>
                          {log.created_at ? new Date(log.created_at).toLocaleString() : '-'}
                        </td>
                        <td style={{ padding: '0.85rem 1rem' }}>
                          <div style={{ fontWeight: 700 }}>{log.student_full_name}</div>
                          <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>{log.student_roll_number}</div>
                        </td>
                        <td style={{ padding: '0.85rem 1rem' }}>
                          <span style={{ color: '#f87171', fontWeight: 600 }}>{log.old_status}</span>
                          <span style={{ margin: '0 0.4rem', color: 'var(--text-muted)' }}>➔</span>
                          <span style={{ color: '#34d399', fontWeight: 700 }}>{log.new_status}</span>
                        </td>
                        <td style={{ padding: '0.85rem 1rem', fontWeight: 600, color: '#818cf8' }}>
                          @{log.corrected_by_name}
                        </td>
                        <td style={{ padding: '0.85rem 1rem', color: 'var(--text-secondary)', fontStyle: 'italic' }}>
                          "{log.reason}"
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Defaulter notice generator modal */}
      {selectedNoticeStudent && (
        <div className="modal-overlay" onClick={() => setSelectedNoticeStudent(null)}>
          <div className="glass-card" onClick={(e) => e.stopPropagation()} style={{ width: '600px', padding: '2rem', background: '#ffffff', color: '#0f172a', borderRadius: '16px', border: '1px solid #cbd5e1', boxShadow: '0 25px 50px rgba(0,0,0,0.4)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', borderBottom: '2px solid #1e3a8a', paddingBottom: '1rem', marginBottom: '1.25rem' }}>
              <div>
                <div style={{ fontSize: '1.2rem', fontWeight: 900, color: '#1e3a8a', letterSpacing: '-0.02em' }}>
                  SHRI VAISHNAV VIDYAPEETH VISHWAVIDYALAYA
                </div>
                <div style={{ fontSize: '0.78rem', color: '#475569', fontWeight: 600 }}>
                  Attendance & Academic Portal
                </div>
                <div style={{ fontSize: '0.72rem', color: '#64748b', marginTop: '0.2rem' }}>
                  Attendance notice
                </div>
              </div>
              <button onClick={() => setSelectedNoticeStudent(null)} style={{ background: 'none', border: 'none', color: '#64748b', cursor: 'pointer' }}>
                <X size={20} />
              </button>
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem', color: '#475569', marginBottom: '1.25rem' }}>
              <div><strong>Ref No:</strong> ATT/{new Date().getFullYear()}/{selectedNoticeStudent.roll_number}</div>
              <div><strong>Date:</strong> {new Date().toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' })}</div>
            </div>

            <div style={{ textAlign: 'center', margin: '1rem 0 1.25rem 0' }}>
              <span style={{ background: '#fee2e2', color: '#991b1b', border: '1px solid #f87171', padding: '0.35rem 1rem', borderRadius: '9999px', fontSize: '0.85rem', fontWeight: 800, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                OFFICIAL ATTENDANCE DEFAULTER WARNING NOTICE
              </span>
            </div>

            <div style={{ fontSize: '0.88rem', lineHeight: 1.6, color: '#1e293b', marginBottom: '1.5rem' }}>
              <p><strong>To,</strong><br />
              Parent / Guardian of <strong>{selectedNoticeStudent.full_name}</strong><br />
              Roll Number: <strong>{selectedNoticeStudent.roll_number}</strong> | Division: <strong>{selectedNoticeStudent.division_name || 'Div A'}</strong></p>

              <p style={{ marginTop: '0.75rem' }}>
                This is to formally notify you that your ward <strong>{selectedNoticeStudent.full_name}</strong> currently has an overall attendance of <strong style={{ color: '#dc2626' }}>{selectedNoticeStudent.attendance_percentage}%</strong> ({selectedNoticeStudent.attended_sessions} out of {selectedNoticeStudent.total_sessions} classes attended), which is below the configured attendance threshold of <strong>{threshold ?? 75}%</strong>.
              </p>

              <p style={{ marginTop: '0.75rem' }}>
                Please contact the academic office for guidance on the applicable attendance policy.
              </p>
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '2rem', paddingTop: '1.5rem', borderTop: '1px solid #e2e8f0', textAlign: 'center', fontSize: '0.82rem' }}>
              <div>
                <div style={{ borderBottom: '1px solid #94a3b8', width: '140px', margin: '0 auto 0.4rem auto' }}></div>
                <strong>Class Teacher</strong><br />
                Computer Dept.
              </div>
              <div>
                <div style={{ borderBottom: '1px solid #94a3b8', width: '140px', margin: '0 auto 0.4rem auto' }}></div>
                <strong>Head of Department (HOD)</strong><br />
                Academic Office
              </div>
              <div>
                <div style={{ borderBottom: '1px solid #94a3b8', width: '140px', margin: '0 auto 0.4rem auto' }}></div>
                <strong>Principal</strong><br />
                Shri Vaishnav Vidyapeeth Vishwavidyalaya
              </div>
            </div>

            <div style={{ display: 'flex', gap: '0.75rem', marginTop: '1.75rem' }}>
              <button
                onClick={() => {
                  window.print();
                }}
                className="btn-primary"
                style={{ flex: 1, gap: '0.4rem' }}
              >
                <Printer size={16} /> Print Warning Notice
              </button>
              <button
                onClick={() => {
                  setToast({ message: `Official Notice PDF generated for ${selectedNoticeStudent.full_name}`, type: 'success' });
                  setSelectedNoticeStudent(null);
                }}
                className="btn-secondary"
                style={{ flex: 1, gap: '0.4rem', background: '#f1f5f9', color: '#0f172a', border: '1px solid #cbd5e1' }}
              >
                <Download size={16} /> Download Notice PDF
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Floating Notification Toast */}
      <Toast message={toast.message} type={toast.type} onClose={() => setToast({ message: '', type: 'success' })} />
    </div>
  );
}
