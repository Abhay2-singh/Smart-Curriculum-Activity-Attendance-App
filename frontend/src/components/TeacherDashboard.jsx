import React, { useState, useEffect, useRef } from 'react';
import { QRCodeSVG } from 'qrcode.react';
import {
  Plus,
  QrCode,
  XCircle,
  CheckCircle,
  Clock,
  Users,
  Edit3,
  AlertCircle,
  Calendar,
  Layers,
  BookOpen,
  FileCheck2,
  BarChart3,
  Search,
  CheckSquare,
  ShieldCheck,
  Radio,
  Play,
  RefreshCw,
  Check,
  X
} from 'lucide-react';
import { api } from '../api';
import CountdownTimer from './common/CountdownTimer';
import RiskBadge from './common/RiskBadge';
import Toast from './common/Toast';

function getAttendanceOptions(assignments, timetables, divisions) {
  const options = [];
  assignments.filter((assignment) => assignment.is_active).forEach((assignment) => {
    divisions
      .filter((division) => (
        division.academic_class_id === assignment.academic_class_id
        && division.academic_year_id === assignment.academic_year_id
        && division.semester_id === assignment.semester_id
        && (assignment.division_id == null || division.id === assignment.division_id)
      ))
      .forEach((division) => {
        options.push({
          academic_year_id: assignment.academic_year_id,
          semester_id: assignment.semester_id,
          division_id: division.id,
          batch_id: assignment.batch_id,
          subject_id: assignment.subject_id,
        });
      });
  });
  timetables.filter((entry) => entry.is_active).forEach((entry) => {
    options.push({
      academic_year_id: entry.academic_year_id,
      semester_id: entry.semester_id,
      division_id: entry.division_id,
      batch_id: entry.batch_id,
      subject_id: entry.subject_id,
    });
  });
  return [...new Map(options.map((option) => [
    `${option.academic_year_id}:${option.semester_id}:${option.division_id}:${option.batch_id ?? ''}:${option.subject_id}`,
    option,
  ])).values()];
}

export default function TeacherDashboard({ user, activeTab = 'overview', onNavigate }) {
  const [sessions, setSessions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [dataError, setDataError] = useState('');
  const [activeQrSession, setActiveQrSession] = useState(null);
  const [monitorData, setMonitorData] = useState(null);
  const [toast, setToast] = useState({ message: '', type: 'success' });
  const tokenRefreshInFlight = useRef(false);

  // Form states for creating session
  const [academicYears, setAcademicYears] = useState([]);
  const [semesters, setSemesters] = useState([]);
  const [divisions, setDivisions] = useState([]);
  const [batches, setBatches] = useState([]);
  const [subjects, setSubjects] = useState([]);
  const [timetables, setTimetables] = useState([]);
  const [attendanceOptions, setAttendanceOptions] = useState([]);

  const [form, setForm] = useState({
    academic_year_id: '',
    semester_id: '',
    division_id: '',
    batch_id: '',
    subject_id: '',
    duration_minutes: '15',
  });
  const [createError, setCreateError] = useState('');
  const [createSuccessMsg, setCreateSuccessMsg] = useState('');

  // Live monitor / Records state
  const [selectedSessionRecords, setSelectedSessionRecords] = useState(null);
  const [records, setRecords] = useState([]);
  const [recordLoading, setRecordLoading] = useState(false);
  const [studentSearch, setStudentSearch] = useState('');
  const [sessionSubjectFilter, setSessionSubjectFilter] = useState('');
  const [sessionDateFilter, setSessionDateFilter] = useState('');

  // Correction Modal
  const [correctingRecord, setCorrectingRecord] = useState(null);
  const [newStatus, setNewStatus] = useState('PRESENT');
  const [reason, setReason] = useState('');
  const [corrError, setCorrError] = useState('');

  // Audit logs state
  const [auditLogs, setAuditLogs] = useState([]);

  // Defaulters report state
  const [defaulters, setDefaulters] = useState([]);
  const [threshold, setThreshold] = useState(null);

  useEffect(() => {
    fetchTeacherData();
  }, [activeTab]);

  useEffect(() => {
    if (form.division_id) {
      api.getBatches(form.division_id)
        .then(setBatches)
        .catch((err) => setDataError(err.message || 'Unable to load batches.'));
    } else {
      setBatches([]);
    }
  }, [form.division_id]);

  useEffect(() => {
    if (!activeQrSession || activeQrSession.status !== 'ACTIVE') return undefined;
    const intervalSeconds = activeQrSession.qr_refresh_interval_seconds;
    if (!intervalSeconds) return undefined;
    const interval = setInterval(async () => {
      if (tokenRefreshInFlight.current) return;
      tokenRefreshInFlight.current = true;
      try {
        const refreshed = await api.refreshSessionToken(activeQrSession.id);
        setActiveQrSession(refreshed);
        setSessions((current) => current.map((session) => (
          session.id === refreshed.id ? refreshed : session
        )));
        setToast({ message: 'QR token refreshed securely.', type: 'success' });
      } catch (err) {
        setToast({ message: err.message || 'QR token refresh failed. Reopen the session or retry.', type: 'error' });
        setActiveQrSession(null);
        api.getSessions().then(setSessions).catch((refreshError) => {
          setDataError(refreshError.message || 'Unable to refresh attendance sessions.');
        });
      } finally {
        tokenRefreshInFlight.current = false;
      }
    }, intervalSeconds * 1000);
    return () => clearInterval(interval);
  }, [activeQrSession?.id, activeQrSession?.qr_refresh_interval_seconds, activeQrSession?.status]);

  useEffect(() => {
    if (!selectedSessionRecords || selectedSessionRecords.status !== 'ACTIVE') return undefined;
    const refreshMonitor = async () => {
      try {
        const [currentMonitor, currentRecords] = await Promise.all([
          api.getSessionMonitor(selectedSessionRecords.id),
          api.getSessionRecords(selectedSessionRecords.id),
        ]);
        setMonitorData(currentMonitor);
        setRecords(currentRecords);
      } catch (err) {
        setDataError(err.message || 'Unable to refresh the live attendance monitor.');
      }
    };
    const interval = setInterval(refreshMonitor, 5000);
    return () => clearInterval(interval);
  }, [selectedSessionRecords?.id, selectedSessionRecords?.status]);

  const fetchTeacherData = async () => {
    setLoading(true);
    setDataError('');
    try {
      const teacherId = user.teacher_profile?.id;
      const [sessData, years, divs, allSubjects, ttData, assignments] = await Promise.all([
        api.getSessions(),
        api.getAcademicYears(),
        api.getDivisions(),
        api.getSubjects(),
        api.getTimetables(),
        teacherId ? api.getSubjectAssignments(teacherId) : Promise.resolve([]),
      ]);

      setSessions(sessData);
      setAcademicYears(years);
      const semesterGroups = await Promise.all(years.map((year) => api.getSemesters(year.id)));
      const allSemesters = semesterGroups.flat();
      const teacherTimetables = teacherId
        ? ttData.filter((item) => item.teacher_id === teacherId && item.is_active)
        : [];
      const attendanceAssignments = assignments.filter((item) => item.is_active);
      const options = getAttendanceOptions(attendanceAssignments, teacherTimetables, divs);
      const teacherDivisions = divs.filter((division) => (
        options.some((option) => option.division_id === division.id)
      ));
      const assignedSubjectIds = new Set(options.map((option) => option.subject_id));
      setSemesters(allSemesters);
      setAttendanceOptions(options);
      setDivisions(teacherDivisions);
      setSubjects(allSubjects.filter((subject) => assignedSubjectIds.has(subject.id)));
      setTimetables(teacherTimetables);

      setForm((previous) => {
        const existingOption = options.find((option) => (
          option.academic_year_id === Number(previous.academic_year_id)
          && option.semester_id === Number(previous.semester_id)
          && option.division_id === Number(previous.division_id)
          && option.subject_id === Number(previous.subject_id)
          && (option.batch_id == null || option.batch_id === Number(previous.batch_id))
        ));
        const selection = existingOption || options[0];
        return {
          ...previous,
          academic_year_id: selection ? String(selection.academic_year_id) : '',
          semester_id: selection ? String(selection.semester_id) : '',
          division_id: selection ? String(selection.division_id) : '',
          batch_id: selection?.batch_id == null ? '' : String(selection.batch_id),
          subject_id: selection ? String(selection.subject_id) : '',
        };
      });

      if (activeTab === 'corrections') {
        const logs = await api.getAuditLogs();
        setAuditLogs(logs);
      }

      if (activeTab === 'reports') {
        const defData = await api.getDefaulters(null, threshold);
        setDefaulters(defData.defaulters || []);
        setThreshold((current) => current ?? defData.threshold_percentage);
      }
    } catch (err) {
      setDataError(err.message || 'Unable to load teacher dashboard data.');
    } finally {
      setLoading(false);
    }
  };

  const handleCreateSession = async (e) => {
    e.preventDefault();
    setCreateError('');
    setCreateSuccessMsg('');

    if (!hasValidAttendanceSelection) {
      setCreateError(
        attendanceOptions.length
          ? 'Choose a class, subject, and batch combination assigned to your account.'
          : 'No active class or subject assignment was found. Ask an administrator to assign you to a class and subject first.'
      );
      return;
    }

    if (!form.academic_year_id || !form.semester_id || !form.division_id || !form.subject_id) {
      setCreateError('Please select Academic Year, Semester, Division, and Subject');
      return;
    }

    try {
      if (!user.teacher_profile?.id) {
        setCreateError('Your account does not have a teacher profile. Ask an administrator to link one.');
        return;
      }
      const now = new Date();
      const localDate = new Date(now.getTime() - now.getTimezoneOffset() * 60000);
      const todayStr = localDate.toISOString().split('T')[0];
      const startTime = `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}:00`;
      const endTimeDate = new Date(now.getTime() + Number(form.duration_minutes) * 60000);
      const endTime = `${String(endTimeDate.getHours()).padStart(2, '0')}:${String(endTimeDate.getMinutes()).padStart(2, '0')}:00`;
      const expiresAt = new Date(now.getTime() + parseInt(form.duration_minutes) * 60000).toISOString();

      const teacherId = user.teacher_profile.id;

      const payload = {
        academic_year_id: parseInt(form.academic_year_id),
        semester_id: parseInt(form.semester_id),
        division_id: parseInt(form.division_id),
        batch_id: form.batch_id ? parseInt(form.batch_id) : null,
        subject_id: parseInt(form.subject_id),
        teacher_id: teacherId,
        session_date: todayStr,
        start_time: startTime,
        end_time: endTime,
        expires_at: expiresAt,
      };

      const newSess = await api.createSession(payload);
      setActiveQrSession(newSess);
      setCreateSuccessMsg('Attendance Session successfully created and live!');
      fetchTeacherData();
    } catch (err) {
      setCreateError(err.message);
    }
  };

  const handleCloseSession = async (id) => {
    try {
      const closed = await api.closeSession(id);
      fetchTeacherData();
      if (selectedSessionRecords?.id === id) setSelectedSessionRecords(closed);
      if (activeQrSession && activeQrSession.id === id) {
        setActiveQrSession(null);
      }
      setToast({ message: 'Attendance session closed.', type: 'success' });
    } catch (err) {
      setToast({ message: err.message || 'Unable to close attendance session.', type: 'error' });
    }
  };

  const handleShowQr = async (session) => {
    try {
      let current = await api.getAttendanceSession(session.id);
      const secondsUntilExpiry = (
        new Date(current.qr_token_expires_at || current.expires_at).getTime() - Date.now()
      ) / 1000;
      const refreshWindow = current.qr_token_ttl_seconds
        - current.qr_refresh_interval_seconds + 2;
      if (secondsUntilExpiry <= refreshWindow) {
        current = await api.refreshSessionToken(session.id);
      }
      setActiveQrSession(current);
      setSessions((existing) => existing.map((item) => item.id === current.id ? current : item));
    } catch (err) {
      setToast({ message: err.message || 'Unable to display a valid QR code.', type: 'error' });
    }
  };

  const handleCancelSession = async (id) => {
    if (!window.confirm('Are you sure you want to cancel this session?')) return;
    try {
      await api.cancelSession(id);
      fetchTeacherData();
      if (activeQrSession && activeQrSession.id === id) {
        setActiveQrSession(null);
      }
    } catch (err) {
      alert(err.message);
    }
  };

  const handleViewRecords = async (sess) => {
    setSelectedSessionRecords(sess);
    setRecordLoading(true);
    try {
      const [data, monitor] = await Promise.all([
        api.getSessionRecords(sess.id),
        api.getSessionMonitor(sess.id),
      ]);
      setRecords(data);
      setMonitorData(monitor);
    } catch (err) {
      setDataError(err.message || 'Unable to load attendance records.');
    } finally {
      setRecordLoading(false);
    }
  };

  const handleApplyCorrection = async (e) => {
    e.preventDefault();
    setCorrError('');
    if (!reason) {
      setCorrError('Reason for correction is required for audit trail logging');
      return;
    }

    try {
      await api.correctAttendance(correctingRecord.id, newStatus, reason);
      setCorrectingRecord(null);
      setReason('');
      if (selectedSessionRecords) {
        handleViewRecords(selectedSessionRecords);
      }
      fetchTeacherData();
    } catch (err) {
      setCorrError(err.message);
    }
  };

  const activeSessionsList = sessions.filter((s) => s.status === 'ACTIVE');
  const availableYears = academicYears.filter((year) => (
    attendanceOptions.some((option) => option.academic_year_id === year.id)
  ));
  const availableSemesters = semesters.filter((semester) => (
    semester.academic_year_id === Number(form.academic_year_id)
    && attendanceOptions.some((option) => (
      option.academic_year_id === semester.academic_year_id
      && option.semester_id === semester.id
    ))
  ));
  const availableDivisions = divisions.filter((division) => (
    division.academic_year_id === Number(form.academic_year_id)
    && division.semester_id === Number(form.semester_id)
    && attendanceOptions.some((option) => (
      option.academic_year_id === division.academic_year_id
      && option.semester_id === division.semester_id
      && option.division_id === division.id
    ))
  ));
  const scopedAttendanceOptions = attendanceOptions.filter((option) => (
    option.academic_year_id === Number(form.academic_year_id)
    && option.semester_id === Number(form.semester_id)
    && option.division_id === Number(form.division_id)
  ));
  const availableBatches = batches.filter((batch) => (
    scopedAttendanceOptions.some((option) => option.batch_id == null || option.batch_id === batch.id)
  ));
  const availableSubjects = subjects.filter((subject) => (
    subject.semester_id === Number(form.semester_id)
    && scopedAttendanceOptions.some((option) => (
      option.subject_id === subject.id
      && (option.batch_id == null || option.batch_id === Number(form.batch_id))
    ))
  ));
  const hasValidAttendanceSelection = scopedAttendanceOptions.some((option) => (
    option.subject_id === Number(form.subject_id)
    && (option.batch_id == null || option.batch_id === Number(form.batch_id))
  ));
  const classAssignmentItems = timetables.length > 0
    ? timetables
    : attendanceOptions.map((option) => ({
      ...option,
      division_name: divisions.find((division) => division.id === option.division_id)?.name,
      subject_name: subjects.find((subject) => subject.id === option.subject_id)?.name,
      subject_code: subjects.find((subject) => subject.id === option.subject_id)?.code,
    }));
  const filteredSessions = sessions.filter((session) => (
    (!sessionSubjectFilter || String(session.subject_id) === sessionSubjectFilter)
    && (!sessionDateFilter || session.session_date === sessionDateFilter)
  ));

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>
      {dataError && <div className="workspace-error" role="alert">
        {dataError} <button className="btn-secondary" onClick={fetchTeacherData}>Retry</button>
      </div>}
      {/* Overview View */}
      {activeTab === 'overview' && (
        <>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem' }}>
            <div>
              <h1 style={{ fontSize: '1.85rem', fontWeight: 800 }}>
                Good morning, {user.full_name || user.username} 👋
              </h1>
              <p style={{ color: 'var(--text-secondary)', fontSize: '0.92rem', marginTop: '0.2rem' }}>
                Here is your teaching and attendance overview.
              </p>
            </div>

            <button className="btn-primary" onClick={() => onNavigate('start-session')}>
              <QrCode size={18} /> Start New Attendance Session
            </button>
          </div>

          {/* Quick Metrics */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '1.25rem' }}>
            <div className="glass-card" style={{ padding: '1.35rem', display: 'flex', alignItems: 'center', gap: '1.25rem' }}>
              <div style={{ padding: '0.9rem', background: 'rgba(99, 102, 241, 0.15)', borderRadius: '16px', color: '#818cf8' }}>
                <Clock size={26} />
              </div>
              <div>
                <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', fontWeight: 600 }}>Active Sessions</div>
                <div style={{ fontSize: '1.6rem', fontWeight: 800, marginTop: '0.15rem', color: activeSessionsList.length > 0 ? '#34d399' : 'var(--text-primary)' }}>
                  {activeSessionsList.length}
                </div>
              </div>
            </div>

            <div className="glass-card" style={{ padding: '1.35rem', display: 'flex', alignItems: 'center', gap: '1.25rem' }}>
              <div style={{ padding: '0.9rem', background: 'rgba(16, 185, 129, 0.15)', borderRadius: '16px', color: '#34d399' }}>
                <Calendar size={26} />
              </div>
              <div>
                <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', fontWeight: 600 }}>Total Timetable Slots</div>
                <div style={{ fontSize: '1.6rem', fontWeight: 800, marginTop: '0.15rem' }}>{timetables.length}</div>
              </div>
            </div>

            <div className="glass-card" style={{ padding: '1.35rem', display: 'flex', alignItems: 'center', gap: '1.25rem' }}>
              <div style={{ padding: '0.9rem', background: 'rgba(244, 63, 94, 0.15)', borderRadius: '16px', color: '#fb7185' }}>
                <CheckSquare size={26} />
              </div>
              <div>
                <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', fontWeight: 600 }}>Total Sessions Conducted</div>
                <div style={{ fontSize: '1.6rem', fontWeight: 800, marginTop: '0.15rem' }}>{sessions.length}</div>
              </div>
            </div>
          </div>

          {/* Active Sessions Banner */}
          {activeSessionsList.length > 0 && (
            <div className="glass-card" style={{ padding: '1.5rem', background: 'linear-gradient(135deg, rgba(16, 185, 129, 0.15), rgba(5, 150, 105, 0.05))', border: '1px solid rgba(16, 185, 129, 0.3)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.85rem' }}>
                  <Radio size={24} color="#34d399" />
                  <div>
                    <div style={{ fontWeight: 800, fontSize: '1.1rem', color: '#ffffff' }}>Active Attendance Session Running</div>
                    <div style={{ fontSize: '0.82rem', color: 'var(--text-secondary)' }}>
                      Session #{activeSessionsList[0].id} • Dynamic QR rotates automatically
                    </div>
                  </div>
                </div>

                <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center' }}>
                  <CountdownTimer expiresAt={activeSessionsList[0].qr_token_expires_at || activeSessionsList[0].expires_at} expiredLabel="QR TOKEN EXPIRED" />
                  <button
                    className="btn-primary"
                    style={{ padding: '0.45rem 0.9rem', fontSize: '0.82rem' }}
                    onClick={() => handleShowQr(activeSessionsList[0])}
                  >
                    <QrCode size={16} /> Show QR Code
                  </button>
                  <button
                    className="btn-secondary"
                    style={{ padding: '0.45rem 0.9rem', fontSize: '0.82rem', color: '#ef4444' }}
                    onClick={() => handleCloseSession(activeSessionsList[0].id)}
                  >
                    Close Session
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* Today's Timetable Preview */}
          <div className="glass-card" style={{ padding: '1.75rem' }}>
            <h3 style={{ fontSize: '1.2rem', fontWeight: 700, marginBottom: '1.25rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <Calendar size={20} color="#818cf8" /> Teaching Schedule Overview
            </h3>

            {timetables.length === 0 ? (
              <div style={{ padding: '1.5rem', textAlign: 'center', color: 'var(--text-muted)' }}>
                No timetable entries assigned for your faculty profile.
              </div>
            ) : (
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.9rem' }}>
                  <thead>
                    <tr style={{ borderBottom: '1px solid var(--border-glass)', color: 'var(--text-secondary)' }}>
                      <th style={{ padding: '0.75rem' }}>Day</th>
                      <th style={{ padding: '0.75rem' }}>Time Slot</th>
                      <th style={{ padding: '0.75rem' }}>Division ID</th>
                      <th style={{ padding: '0.75rem' }}>Subject ID</th>
                      <th style={{ padding: '0.75rem' }}>Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {timetables.map((t) => (
                      <tr key={t.id} style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
                        <td style={{ padding: '0.75rem', fontWeight: 700, color: '#818cf8' }}>{t.day_of_week}</td>
                        <td style={{ padding: '0.75rem' }}>{t.start_time} - {t.end_time}</td>
                        <td style={{ padding: '0.75rem' }}>Division #{t.division_id}</td>
                        <td style={{ padding: '0.75rem' }}>Subject #{t.subject_id}</td>
                        <td style={{ padding: '0.75rem' }}>
                          <button
                            className="btn-secondary"
                            style={{ padding: '0.3rem 0.65rem', fontSize: '0.78rem' }}
                            onClick={() => {
                              setForm({
                                ...form,
                                academic_year_id: String(t.academic_year_id),
                                semester_id: String(t.semester_id),
                                division_id: String(t.division_id),
                                batch_id: t.batch_id ? String(t.batch_id) : '',
                                subject_id: String(t.subject_id),
                              });
                              onNavigate('start-session');
                            }}
                          >
                            <Play size={12} /> Launch Session
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </>
      )}

      {/* Start Attendance Session View */}
      {activeTab === 'start-session' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem', paddingTop: '0.5rem' }}>
          <div>
            <h1 style={{ fontSize: '1.85rem', fontWeight: 800 }}>Start Attendance Session</h1>
            <p style={{ color: 'var(--text-secondary)', fontSize: '0.92rem' }}>
              Select target class division and subject to generate a secure QR code and active token.
            </p>
          </div>

          {/* Active Session Warning Banner */}
          {activeSessionsList.length > 0 && !activeQrSession && (
            <div style={{
              padding: '1rem 1.25rem',
              background: 'rgba(52, 211, 153, 0.08)',
              border: '1px solid rgba(52, 211, 153, 0.25)',
              borderRadius: '16px',
              display: 'flex',
              justify: 'space-between',
              alignItems: 'center',
              flexWrap: 'wrap',
              gap: '0.75rem'
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                <div style={{ width: '10px', height: '10px', borderRadius: '50%', background: '#34d399', boxShadow: '0 0 10px #34d399' }} />
                <span style={{ fontSize: '0.9rem', color: '#34d399', fontWeight: 700 }}>
                  You currently have {activeSessionsList.length} ACTIVE attendance session live!
                </span>
              </div>
              <button
                className="btn-secondary"
                style={{ fontSize: '0.8rem', padding: '0.4rem 0.85rem' }}
                onClick={() => handleShowQr(activeSessionsList[0])}
              >
                View Live QR Code
              </button>
            </div>
          )}

          <div style={{ display: 'grid', gridTemplateColumns: activeQrSession ? '1fr 1fr' : '1fr', gap: '1.5rem' }}>
            {/* Form */}
            <div className="glass-card" style={{ padding: '2rem' }}>
              <h3 style={{ fontSize: '1.25rem', fontWeight: 800, marginBottom: '1.25rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <QrCode size={22} color="#818cf8" /> Session Configuration
              </h3>

              {/* Quick Fill Presets from Timetable */}
              {timetables.length > 0 && (
                <div style={{ marginBottom: '1.25rem' }}>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.04em', marginBottom: '0.5rem' }}>
                    ⚡ Quick Fill From Timetable
                  </div>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
                    {timetables.slice(0, 4).map((tt) => (
                      <button
                        key={tt.id}
                        type="button"
                        className="btn-secondary"
                        onClick={() => {
                          setForm((prev) => ({
                            ...prev,
                            academic_year_id: String(tt.academic_year_id),
                            semester_id: String(tt.semester_id),
                            division_id: String(tt.division_id),
                            batch_id: tt.batch_id ? tt.batch_id.toString() : '',
                            subject_id: String(tt.subject_id),
                          }));
                          setToast({ message: `Pre-filled ${tt.subject_name || 'Subject'} (${tt.division_name || 'Division'})`, type: 'success' });
                        }}
                        style={{ padding: '0.35rem 0.75rem', fontSize: '0.78rem', borderRadius: '20px', background: 'rgba(99, 102, 241, 0.1)', border: '1px solid rgba(99, 102, 241, 0.25)', color: '#a5b4fc', cursor: 'pointer' }}
                      >
                        {tt.subject_code || 'CS'} • {tt.division_name || 'Div'}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {createError && <div style={{ color: '#ef4444', fontSize: '0.85rem', marginBottom: '1rem' }}>{createError}</div>}
              {createSuccessMsg && <div style={{ color: '#34d399', fontSize: '0.85rem', marginBottom: '1rem' }}>{createSuccessMsg}</div>}
              {attendanceOptions.length === 0 && (
                <div className="workspace-state" role="status">
                  No active class/subject assignments are available for this account. Ask an administrator to configure the teacher assignment or timetable.
                </div>
              )}

              <form onSubmit={handleCreateSession} style={{ display: 'flex', flexDirection: 'column', gap: '1.2rem' }}>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
                  <div>
                    <label style={{ display: 'block', fontSize: '0.82rem', color: 'var(--text-secondary)', marginBottom: '0.35rem' }}>Academic Year</label>
                    <select
                      className="glass-input"
                      value={form.academic_year_id}
                      disabled={availableYears.length === 0}
                      onChange={(e) => {
                        const academicYearId = e.target.value;
                        const firstSemester = semesters.find((semester) => (
                          semester.academic_year_id === Number(academicYearId)
                          && attendanceOptions.some((option) => (
                            option.academic_year_id === semester.academic_year_id
                            && option.semester_id === semester.id
                          ))
                        ));
                        setForm((previous) => ({
                          ...previous,
                          academic_year_id: academicYearId,
                          semester_id: firstSemester ? String(firstSemester.id) : '',
                          division_id: '',
                          batch_id: '',
                          subject_id: '',
                        }));
                      }}
                    >
                      <option value="">Select Academic Year</option>
                      {availableYears.map((y) => (
                        <option key={y.id} value={y.id} style={{ background: '#111827' }}>{y.name}</option>
                      ))}
                    </select>
                  </div>

                  <div>
                    <label style={{ display: 'block', fontSize: '0.82rem', color: 'var(--text-secondary)', marginBottom: '0.35rem' }}>Semester</label>
                    <select
                      className="glass-input"
                      value={form.semester_id}
                      disabled={availableSemesters.length === 0}
                      onChange={(e) => setForm((previous) => ({
                        ...previous,
                        semester_id: e.target.value,
                        division_id: '',
                        batch_id: '',
                        subject_id: '',
                      }))}
                    >
                      <option value="">Select Semester</option>
                      {availableSemesters.map((s) => (
                        <option key={s.id} value={s.id} style={{ background: '#111827' }}>{s.name}</option>
                      ))}
                    </select>
                  </div>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
                  <div>
                    <label style={{ display: 'block', fontSize: '0.82rem', color: 'var(--text-secondary)', marginBottom: '0.35rem' }}>Division</label>
                    <select
                      className="glass-input"
                      value={form.division_id}
                      disabled={availableDivisions.length === 0}
                      onChange={(e) => setForm((previous) => ({
                        ...previous,
                        division_id: e.target.value,
                        batch_id: '',
                        subject_id: '',
                      }))}
                    >
                      <option value="">Select Division</option>
                      {availableDivisions.map((d) => (
                        <option key={d.id} value={d.id} style={{ background: '#111827' }}>{d.name}</option>
                      ))}
                    </select>
                  </div>

                  <div>
                    <label style={{ display: 'block', fontSize: '0.82rem', color: 'var(--text-secondary)', marginBottom: '0.35rem' }}>
                      Batch <span style={{ color: 'var(--text-muted)' }}>(Optional)</span>
                    </label>
                    <select
                      className="glass-input"
                      value={form.batch_id}
                      onChange={(e) => setForm((previous) => ({
                        ...previous,
                        batch_id: e.target.value,
                        subject_id: '',
                      }))}
                    >
                      {scopedAttendanceOptions.some((option) => option.batch_id == null) && (
                        <option value="">All Division (Whole Class)</option>
                      )}
                      {availableBatches.map((b) => (
                        <option key={b.id} value={b.id} style={{ background: '#111827' }}>{b.name}</option>
                      ))}
                    </select>
                  </div>
                </div>

                <div>
                  <label style={{ display: 'block', fontSize: '0.82rem', color: 'var(--text-secondary)', marginBottom: '0.35rem' }}>Subject</label>
                  <select
                    className="glass-input"
                    value={form.subject_id}
                    onChange={(e) => setForm({ ...form, subject_id: e.target.value })}
                    disabled={availableSubjects.length === 0}
                  >
                    <option value="">Select Subject</option>
                  {availableSubjects.map((sub) => (
                      <option key={sub.id} value={sub.id} style={{ background: '#111827' }}>{sub.name} ({sub.code})</option>
                    ))}
                  </select>
                </div>

                <div>
                  <label style={{ display: 'block', fontSize: '0.82rem', color: 'var(--text-secondary)', marginBottom: '0.35rem' }}>Session Duration (Minutes)</label>
                  <input
                    type="number"
                    className="glass-input"
                    value={form.duration_minutes}
                    onChange={(e) => setForm({ ...form, duration_minutes: e.target.value })}
                  />
                </div>

                <button
                  type="submit"
                  className="btn-primary"
                  disabled={!hasValidAttendanceSelection}
                  style={{ marginTop: '0.5rem', height: '46px', opacity: hasValidAttendanceSelection ? 1 : 0.6 }}
                >
                  <Play size={18} /> Launch Session & Display QR
                </button>
              </form>
            </div>

            {/* Active QR Panel */}
            {activeQrSession && (
              <div className="glass-card" style={{ padding: '2rem', textAlign: 'center', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
                <h3 style={{ fontSize: '1.35rem', fontWeight: 800, marginBottom: '0.5rem' }}>Live QR & Session Security</h3>
                <div style={{ marginBottom: '1rem' }}>
                  <CountdownTimer expiresAt={activeQrSession.qr_token_expires_at || activeQrSession.expires_at} expiredLabel="QR TOKEN EXPIRED" />
                </div>

                <div style={{ background: '#ffffff', padding: '1.5rem', borderRadius: '20px', boxShadow: 'var(--shadow-glow)', marginBottom: '1.25rem' }}>
                  <QRCodeSVG value={activeQrSession.session_token} size={220} />
                </div>

                <div style={{ background: 'rgba(255,255,255,0.04)', padding: '0.85rem 1.25rem', borderRadius: '14px', width: '100%', marginBottom: '1.25rem' }}>
                  <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>SESSION TOKEN</div>
                  <div style={{ fontFamily: 'monospace', fontWeight: 800, color: '#818cf8', fontSize: '1.1rem', wordBreak: 'break-all', marginTop: '0.2rem' }}>
                    {activeQrSession.session_token}
                  </div>
                </div>

                <div style={{ display: 'flex', gap: '0.75rem', width: '100%' }}>
                  <button className="btn-secondary" style={{ flex: 1 }} onClick={() => handleViewRecords(activeQrSession)}>
                    <Users size={16} /> Live Monitor
                  </button>
                  <button className="btn-secondary" style={{ flex: 1, color: '#ef4444' }} onClick={() => handleCloseSession(activeQrSession.id)}>
                    Close Session
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Live Monitor / Session Records View */}
      {(activeTab === 'live-monitor' || activeTab === 'records') && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
          <div>
            <h1 style={{ fontSize: '1.85rem', fontWeight: 800 }}>
              {activeTab === 'live-monitor' ? 'Live Session Monitor' : 'Session Attendance Records'}
            </h1>
            <p style={{ color: 'var(--text-secondary)', fontSize: '0.92rem' }}>
              Inspect student check-ins, perform manual attendance overrides, and manage past sessions.
            </p>
          </div>

          <div className="glass-card" style={{ padding: '1.75rem' }}>
            <h3 style={{ fontSize: '1.2rem', fontWeight: 700, marginBottom: '1.25rem' }}>Attendance Sessions List</h3>
            <div className="session-filters">
              <label>
                Subject
                <select
                  className="glass-input"
                  value={sessionSubjectFilter}
                  onChange={(event) => setSessionSubjectFilter(event.target.value)}
                >
                  <option value="">All subjects</option>
                  {subjects.map((subject) => (
                    <option key={subject.id} value={subject.id}>{subject.name}</option>
                  ))}
                </select>
              </label>
              <label>
                Session date
                <input
                  className="glass-input"
                  type="date"
                  value={sessionDateFilter}
                  onChange={(event) => setSessionDateFilter(event.target.value)}
                />
              </label>
            </div>

            {loading ? (
              <div style={{ padding: '2rem', textAlign: 'center' }}>Loading sessions...</div>
            ) : sessions.length === 0 ? (
              <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-muted)' }}>No sessions found.</div>
            ) : filteredSessions.length === 0 ? (
              <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-muted)' }}>No sessions match these filters.</div>
            ) : (
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.9rem' }}>
                  <thead>
                    <tr style={{ borderBottom: '1px solid var(--border-glass)', color: 'var(--text-secondary)' }}>
                      <th style={{ padding: '0.85rem 1rem' }}>Session ID</th>
                      <th style={{ padding: '0.85rem 1rem' }}>Date</th>
                      <th style={{ padding: '0.85rem 1rem' }}>Subject</th>
                      <th style={{ padding: '0.85rem 1rem' }}>Token</th>
                      <th style={{ padding: '0.85rem 1rem' }}>Status</th>
                      <th style={{ padding: '0.85rem 1rem' }}>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredSessions.map((s) => (
                      <tr key={s.id} style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
                        <td style={{ padding: '0.85rem 1rem', fontWeight: 600 }}>#{s.id}</td>
                        <td style={{ padding: '0.85rem 1rem' }}>{s.session_date}</td>
                        <td style={{ padding: '0.85rem 1rem' }}>{s.subject_name || `Subject #${s.subject_id}`}</td>
                        <td style={{ padding: '0.85rem 1rem', fontFamily: 'monospace', color: '#818cf8' }}>
                          {s.session_token?.slice(0, 12)}...
                        </td>
                        <td style={{ padding: '0.85rem 1rem' }}>
                          <span className={`badge badge-${s.status.toLowerCase()}`}>{s.status}</span>
                        </td>
                        <td style={{ padding: '0.85rem 1rem', display: 'flex', gap: '0.5rem' }}>
                          {s.status === 'ACTIVE' && (
                            <>
                              <button
                                className="btn-secondary"
                                style={{ padding: '0.35rem 0.75rem', fontSize: '0.8rem', background: 'rgba(99, 102, 241, 0.2)' }}
                                onClick={() => handleShowQr(s)}
                              >
                                <QrCode size={14} /> Show QR
                              </button>
                              <button
                                className="btn-secondary"
                                style={{ padding: '0.35rem 0.75rem', fontSize: '0.8rem', color: '#ef4444' }}
                                onClick={() => handleCloseSession(s.id)}
                              >
                                Close
                              </button>
                            </>
                          )}
                          <button
                            className="btn-primary"
                            style={{ padding: '0.35rem 0.75rem', fontSize: '0.8rem' }}
                            onClick={() => handleViewRecords(s)}
                          >
                            <Users size={14} /> View Student Records
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

      {/* Corrections & Audit View */}
      {activeTab === 'corrections' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
          <div>
            <h1 style={{ fontSize: '1.85rem', fontWeight: 800 }}>Attendance Corrections & Audit Logs</h1>
            <p style={{ color: 'var(--text-secondary)', fontSize: '0.92rem' }}>
              Inspect modified student attendance records and track correction compliance reasons.
            </p>
          </div>

          <div className="glass-card" style={{ padding: '1.75rem' }}>
            <h3 style={{ fontSize: '1.2rem', fontWeight: 700, marginBottom: '1.25rem' }}>Recent Corrections Log</h3>

            {auditLogs.length === 0 ? (
              <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-muted)' }}>
                No attendance corrections logged yet.
              </div>
            ) : (
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.9rem' }}>
                  <thead>
                    <tr style={{ borderBottom: '1px solid var(--border-glass)', color: 'var(--text-secondary)' }}>
                      <th style={{ padding: '0.85rem 1rem' }}>Log ID</th>
                      <th style={{ padding: '0.85rem 1rem' }}>Student</th>
                      <th style={{ padding: '0.85rem 1rem' }}>Transition</th>
                      <th style={{ padding: '0.85rem 1rem' }}>Corrected By</th>
                      <th style={{ padding: '0.85rem 1rem' }}>Reason</th>
                    </tr>
                  </thead>
                  <tbody>
                    {auditLogs.map((log) => (
                      <tr key={log.id} style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
                        <td style={{ padding: '0.85rem 1rem', fontWeight: 600 }}>#{log.id}</td>
                        <td style={{ padding: '0.85rem 1rem' }}>
                          <div style={{ fontWeight: 700 }}>{log.student_full_name}</div>
                          <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>{log.student_roll_number}</div>
                        </td>
                        <td style={{ padding: '0.85rem 1rem' }}>
                          <span style={{ color: '#f87171' }}>{log.old_status}</span> ➔ <span style={{ color: '#34d399', fontWeight: 700 }}>{log.new_status}</span>
                        </td>
                        <td style={{ padding: '0.85rem 1rem', fontWeight: 600, color: '#818cf8' }}>@{log.corrected_by_name}</td>
                        <td style={{ padding: '0.85rem 1rem', color: 'var(--text-secondary)', fontStyle: 'italic' }}>"{log.reason}"</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      )}

      {/* My Assigned Classes View */}
      {activeTab === 'my-classes' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem' }}>
            <div>
              <h1 style={{ fontSize: '1.85rem', fontWeight: 800 }}>My Assigned Classes</h1>
              <p style={{ color: 'var(--text-secondary)', fontSize: '0.92rem' }}>
                Overview of your academic divisions, subject workloads, and quick attendance launchers.
              </p>
            </div>
            <button className="btn-primary" onClick={() => onNavigate('start-session')}>
              <QrCode size={18} /> Start Attendance Session
            </button>
          </div>

          {loading ? (
            <div className="glass-card" style={{ padding: '3rem', textAlign: 'center', color: 'var(--text-muted)' }}>
              Loading assigned classes...
            </div>
          ) : classAssignmentItems.length === 0 ? (
            <div className="glass-card" style={{ padding: '3.5rem 2rem', textAlign: 'center', borderRadius: '20px' }}>
              <div style={{
                width: '64px', height: '64px', borderRadius: '50%',
                background: 'rgba(99, 102, 241, 0.12)', border: '1px solid rgba(99, 102, 241, 0.25)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                margin: '0 auto 1.25rem auto', color: '#818cf8'
              }}>
                <Layers size={30} />
              </div>
              <h3 style={{ fontSize: '1.3rem', fontWeight: 800, marginBottom: '0.5rem' }}>No Class Assignments Found</h3>
              <p style={{ color: 'var(--text-secondary)', fontSize: '0.92rem', maxWidth: '480px', margin: '0 auto 1.5rem auto' }}>
                Your teaching assignments and division mapping will appear here once configured by the department admin.
              </p>
            </div>
          ) : (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '1.25rem' }}>
              {classAssignmentItems.map((item) => {
                const subName = item.subject_name || item.name || `Subject #${item.subject_id}`;
                const divName = item.division_name || (item.division_id ? `Division #${item.division_id}` : 'Division not specified');
                const subCode = item.subject_code || `SUB-${item.subject_id}`;
                const dayName = item.day_of_week || 'Timetable not configured';

                return (
                  <div key={item.id || idx} className="glass-card" style={{
                    padding: '1.5rem',
                    display: 'flex',
                    flexDirection: 'column',
                    justify: 'space-between',
                    gap: '1.25rem',
                    borderRadius: '18px',
                    border: '1px solid var(--border-glass)'
                  }}>
                    <div>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '0.75rem' }}>
                        <div>
                          <div style={{ fontSize: '0.78rem', color: '#818cf8', fontWeight: 700, textTransform: 'uppercase', tracking: '0.05em' }}>
                            {divName}
                          </div>
                          <div style={{ fontSize: '1.2rem', fontWeight: 800, color: 'var(--text-primary)', marginTop: '0.2rem' }}>
                            {subName}
                          </div>
                        </div>
                        <span className="badge badge-present" style={{ fontSize: '0.75rem' }}>
                          {subCode}
                        </span>
                      </div>

                      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem', fontSize: '0.85rem', color: 'var(--text-secondary)', marginTop: '0.75rem' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                          <Clock size={15} color="var(--text-muted)" />
                          <span>
                            {item.start_time
                              ? <>Schedule: <strong>{dayName}</strong> ({item.start_time} - {item.end_time})</>
                              : 'Teacher assignment'}
                          </span>
                        </div>
                        {item.room_number && (
                          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                            <BookOpen size={15} color="var(--text-muted)" />
                            <span>Classroom / Lab: <strong>{item.room_number}</strong></span>
                          </div>
                        )}
                      </div>
                    </div>

                    <button
                      className="btn-primary"
                      onClick={() => {
                        setForm((prev) => ({
                          ...prev,
                          academic_year_id: String(item.academic_year_id),
                          semester_id: String(item.semester_id),
                          division_id: String(item.division_id),
                          batch_id: item.batch_id ? String(item.batch_id) : '',
                          subject_id: String(item.subject_id),
                        }));
                        onNavigate('start-session');
                      }}
                      style={{ padding: '0.65rem 1rem', fontSize: '0.85rem', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.5rem', borderRadius: '10px' }}
                    >
                      <QrCode size={16} /> Launch Attendance Session
                    </button>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* My Timetable Schedule View */}
      {activeTab === 'timetable' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem' }}>
            <div>
              <h1 style={{ fontSize: '1.85rem', fontWeight: 800 }}>My Weekly Teaching Timetable</h1>
              <p style={{ color: 'var(--text-secondary)', fontSize: '0.92rem' }}>
                View your weekly assigned lecture slots, practical batches, and classroom allocations.
              </p>
            </div>
            <button className="btn-primary" onClick={() => onNavigate('start-session')}>
              <QrCode size={18} /> Start Attendance Session
            </button>
          </div>

          <div className="glass-card" style={{ padding: '1.75rem' }}>
            {loading ? (
              <div style={{ padding: '3rem', textAlign: 'center', color: 'var(--text-muted)' }}>
                Loading weekly timetable...
              </div>
            ) : timetables.length === 0 ? (
              <div style={{ padding: '3rem 1.5rem', textAlign: 'center' }}>
                <div style={{
                  width: '64px', height: '64px', borderRadius: '50%',
                  background: 'rgba(99, 102, 241, 0.12)', border: '1px solid rgba(99, 102, 241, 0.25)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  margin: '0 auto 1.25rem auto', color: '#818cf8'
                }}>
                  <Calendar size={30} />
                </div>
                <h3 style={{ fontSize: '1.25rem', fontWeight: 800, marginBottom: '0.5rem' }}>No Timetable Slots Configured</h3>
                <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', maxWidth: '480px', margin: '0 auto 1.5rem auto' }}>
                  No weekly lecture slots are assigned to your profile yet. Department administrators can add timetable entries in the Admin Panel.
                </p>
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
                {['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'].map((day) => {
                  const daySlots = timetables.filter((t) => t.day_of_week?.toLowerCase() === day.toLowerCase());
                  if (daySlots.length === 0) return null;

                  return (
                    <div key={day} style={{ display: 'flex', flexDirection: 'column', gap: '0.85rem' }}>
                      <h4 style={{ fontSize: '1.05rem', fontWeight: 800, color: '#818cf8', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                        <Calendar size={18} /> {day}
                      </h4>
                      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '1rem' }}>
                        {daySlots.map((slot) => (
                          <div key={slot.id} style={{
                            padding: '1.15rem',
                            background: 'rgba(255,255,255,0.03)',
                            border: '1px solid var(--border-glass)',
                            borderRadius: '14px',
                            display: 'flex',
                            flexDirection: 'column',
                            justify: 'space-between',
                            gap: '0.75rem'
                          }}>
                            <div>
                              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.4rem' }}>
                                <span style={{ fontFamily: 'monospace', fontWeight: 700, color: '#34d399', fontSize: '0.85rem' }}>
                                  {slot.start_time} - {slot.end_time}
                                </span>
                                <span className="badge badge-present" style={{ fontSize: '0.72rem' }}>
                                  {slot.subject_code || `SUB-${slot.subject_id}`}
                                </span>
                              </div>
                              <div style={{ fontWeight: 800, fontSize: '1.05rem', color: 'var(--text-primary)' }}>
                                {slot.subject_name || `Subject #${slot.subject_id}`}
                              </div>
                              <div style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', marginTop: '0.25rem' }}>
                                Division: <strong>{slot.division_name || `#${slot.division_id}`}</strong> {slot.batch_name ? `• Batch ${slot.batch_name}` : ''}
                              </div>
                            </div>

                            <button
                              className="btn-secondary"
                              onClick={() => {
                                setForm((prev) => ({
                                  ...prev,
                                  academic_year_id: String(slot.academic_year_id),
                                  semester_id: String(slot.semester_id),
                                  division_id: String(slot.division_id),
                                  batch_id: slot.batch_id ? String(slot.batch_id) : '',
                                  subject_id: String(slot.subject_id),
                                }));
                                onNavigate('start-session');
                              }}
                              style={{ padding: '0.45rem 0.85rem', fontSize: '0.8rem', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.4rem', marginTop: '0.25rem' }}
                            >
                              <Play size={14} /> Start Session For This Slot
                            </button>
                          </div>
                        ))}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Class Defaulter Reports View */}
      {activeTab === 'reports' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
          <div>
            <h1 style={{ fontSize: '1.85rem', fontWeight: 800 }}>Class Defaulter Reports</h1>
            <p style={{ color: 'var(--text-secondary)', fontSize: '0.92rem' }}>
              Identify students failing to meet mandatory attendance percentages in your classes.
            </p>
          </div>

          <div className="glass-card" style={{ padding: '1.75rem' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem', flexWrap: 'wrap', gap: '1rem' }}>
              <h3 style={{ fontSize: '1.2rem', fontWeight: 700 }}>Defaulters List</h3>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                <label style={{ fontSize: '0.88rem', color: 'var(--text-secondary)' }}>Threshold (%):</label>
                <input
                  type="number"
                  className="glass-input"
                  style={{ width: '80px', padding: '0.4rem 0.6rem' }}
                  value={threshold ?? ''}
                  onChange={(e) => setThreshold(e.target.value)}
                />
                <button className="btn-primary" style={{ padding: '0.4rem 0.85rem' }} onClick={fetchTeacherData}>
                  Apply Filter
                </button>
              </div>
            </div>

            {defaulters.length === 0 ? (
              <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-muted)' }}>
                🎉 Great news! No student attendance is currently below {threshold}%.
              </div>
            ) : (
              <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.9rem' }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid var(--border-glass)', color: 'var(--text-secondary)' }}>
                    <th style={{ padding: '0.85rem 1rem' }}>Roll No</th>
                    <th style={{ padding: '0.85rem 1rem' }}>Student Name</th>
                    <th style={{ padding: '0.85rem 1rem' }}>Email</th>
                    <th style={{ padding: '0.85rem 1rem' }}>Attended / Total</th>
                    <th style={{ padding: '0.85rem 1rem' }}>Percentage</th>
                    <th style={{ padding: '0.85rem 1rem' }}>Risk Status</th>
                  </tr>
                </thead>
                <tbody>
                  {defaulters.map((st) => (
                    <tr key={st.student_id} style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
                      <td style={{ padding: '0.85rem 1rem', fontWeight: 600 }}>{st.roll_number}</td>
                      <td style={{ padding: '0.85rem 1rem', fontWeight: 700 }}>{st.full_name}</td>
                      <td style={{ padding: '0.85rem 1rem', color: 'var(--text-secondary)' }}>{st.email}</td>
                      <td style={{ padding: '0.85rem 1rem' }}>{st.attended_sessions} / {st.total_sessions}</td>
                      <td style={{ padding: '0.85rem 1rem', fontWeight: 800, color: st.attendance_percentage < threshold * 0.8 ? '#f87171' : '#fbbf24' }}>
                        {st.attendance_percentage}%
                      </td>
                      <td style={{ padding: '0.85rem 1rem' }}>
                        <RiskBadge percentage={st.attendance_percentage} requiredPercentage={threshold} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
      )}

      {/* Modal: View Records & Manual Marking */}
      {selectedSessionRecords && (
        <div className="modal-overlay">
          <div className="glass-card" style={{ maxWidth: '720px', width: '100%', padding: '2rem', maxHeight: '85vh', overflowY: 'auto' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem' }}>
              <div>
                <h3 style={{ fontSize: '1.3rem', fontWeight: 800 }}>
                  Attendance Records — Session #{selectedSessionRecords.id}
                </h3>
                <p style={{ fontSize: '0.82rem', color: 'var(--text-secondary)' }}>
                  Date: {selectedSessionRecords.session_date} • Status: {selectedSessionRecords.status}
                </p>
              </div>
              <button className="btn-secondary" style={{ padding: '0.3rem 0.6rem' }} onClick={() => setSelectedSessionRecords(null)}>
                <XCircle size={18} />
              </button>
            </div>

            {recordLoading ? (
              <div style={{ textAlign: 'center', padding: '2rem' }}>Loading student records...</div>
            ) : (
              <>
                {monitorData && (
                  <div className="qr-monitor-summary">
                    <div><strong>{monitorData.total_enrolled}</strong><span>Enrolled</span></div>
                    <div><strong>{monitorData.present_count}</strong><span>Present</span></div>
                    <div><strong>{monitorData.absent_count}</strong><span>Absent</span></div>
                    <div><strong>{monitorData.not_marked_count}</strong><span>Not marked</span></div>
                    <div><strong>{monitorData.attendance_percentage}%</strong><span>Attendance</span></div>
                  </div>
                )}
                <label className="qr-monitor-search">
                  <Search size={16} />
                  <input
                    className="glass-input"
                    value={studentSearch}
                    onChange={(event) => setStudentSearch(event.target.value)}
                    placeholder="Search roster by name or roll number"
                  />
                </label>
                {!monitorData?.students?.length ? (
              <div style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-muted)' }}>
                No enrolled students were found for this session.
              </div>
                ) : (
              <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.88rem' }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid var(--border-glass)', color: 'var(--text-secondary)' }}>
                    <th style={{ padding: '0.75rem' }}>Roll No</th>
                    <th style={{ padding: '0.75rem' }}>Student Name</th>
                    <th style={{ padding: '0.75rem' }}>Status</th>
                    <th style={{ padding: '0.75rem' }}>Source</th>
                    <th style={{ padding: '0.75rem' }}>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {monitorData.students
                    .filter((student) => `${student.full_name} ${student.roll_number}`.toLowerCase().includes(studentSearch.toLowerCase()))
                    .map((student) => {
                      const r = records.find((record) => record.student_id === student.student_id);
                      return (
                    <tr key={student.student_id} style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
                      <td style={{ padding: '0.75rem', fontWeight: 600 }}>{student.roll_number}</td>
                      <td style={{ padding: '0.75rem', fontWeight: 700 }}>{student.full_name}</td>
                      <td style={{ padding: '0.75rem' }}>
                        <span className={`badge badge-${student.status.toLowerCase()}`}>{student.status.replace('_', ' ')}</span>
                      </td>
                      <td style={{ padding: '0.75rem', color: 'var(--text-muted)' }}>{r?.source || '—'}</td>
                      <td style={{ padding: '0.75rem' }}>
                        {r && <button
                          className="btn-secondary"
                          style={{ padding: '0.25rem 0.65rem', fontSize: '0.75rem' }}
                          onClick={() => {
                            setCorrectingRecord(r);
                            setNewStatus(r.status === 'PRESENT' ? 'ABSENT' : 'PRESENT');
                          }}
                        >
                          <Edit3 size={12} /> Audit Override
                        </button>}
                      </td>
                    </tr>
                    );
                  })}
                </tbody>
              </table>
                )}
              </>
            )}
          </div>
        </div>
      )}

      {/* Modal: Attendance Correction */}
      {correctingRecord && (
        <div className="modal-overlay">
          <div className="glass-card" style={{ maxWidth: '440px', width: '100%', padding: '2rem' }}>
            <h3 style={{ fontSize: '1.25rem', fontWeight: 800, marginBottom: '0.5rem' }}>Audit Attendance Correction</h3>
            <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '1.25rem' }}>
              Modifying status for student roll #{correctingRecord.student_roll_number} ({correctingRecord.student_full_name})
            </p>

            {corrError && <div style={{ color: '#ef4444', fontSize: '0.85rem', marginBottom: '1rem' }}>{corrError}</div>}

            <form onSubmit={handleApplyCorrection} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              <div>
                <label style={{ display: 'block', fontSize: '0.82rem', color: 'var(--text-secondary)', marginBottom: '0.35rem' }}>New Status Target</label>
                <select className="glass-input" value={newStatus} onChange={(e) => setNewStatus(e.target.value)}>
                  <option value="PRESENT" style={{ background: '#111827' }}>PRESENT</option>
                  <option value="ABSENT" style={{ background: '#111827' }}>ABSENT</option>
                </select>
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '0.82rem', color: 'var(--text-secondary)', marginBottom: '0.35rem' }}>Reason for Mandatory Audit Trail</label>
                <textarea
                  className="glass-input"
                  rows={3}
                  placeholder="e.g. Approved medical leave certificate submitted / Manual verification"
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                />
              </div>

              <div style={{ display: 'flex', gap: '0.75rem', marginTop: '0.5rem' }}>
                <button type="submit" className="btn-primary" style={{ flex: 1 }}>Save Audit Correction</button>
                <button type="button" className="btn-secondary" style={{ flex: 1 }} onClick={() => setCorrectingRecord(null)}>Cancel</button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal: Live QR Popup */}
      {activeQrSession && activeTab !== 'start-session' && (
        <div className="modal-overlay">
          <div className="glass-card" style={{ maxWidth: '420px', width: '100%', padding: '2rem', textAlign: 'center' }}>
            <h3 style={{ fontSize: '1.4rem', fontWeight: 800, marginBottom: '0.5rem' }}>Live QR Session</h3>
            <div style={{ marginBottom: '1rem' }}>
              <CountdownTimer expiresAt={activeQrSession.qr_token_expires_at || activeQrSession.expires_at} expiredLabel="QR TOKEN EXPIRED" />
            </div>

            <div style={{ background: '#ffffff', padding: '1.5rem', borderRadius: '16px', display: 'inline-block', marginBottom: '1.25rem' }}>
              <QRCodeSVG value={activeQrSession.session_token} size={220} />
            </div>

            <div style={{ background: 'rgba(255,255,255,0.05)', padding: '0.75rem', borderRadius: '12px', marginBottom: '1.5rem' }}>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>SESSION TOKEN</div>
              <div style={{ fontFamily: 'monospace', fontWeight: 700, color: '#818cf8', fontSize: '1rem', wordBreak: 'break-all' }}>
                {activeQrSession.session_token}
              </div>
            </div>

            <div style={{ display: 'flex', gap: '0.75rem' }}>
              <button className="btn-secondary" style={{ flex: 1, color: '#ef4444' }} onClick={() => handleCloseSession(activeQrSession.id)}>
                Close Session
              </button>
              <button className="btn-secondary" style={{ flex: 1 }} onClick={() => setActiveQrSession(null)}>
                Hide Popup
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
