import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  AlertTriangle,
  BookOpen,
  Check,
  FileText,
  LoaderCircle,
  Plus,
  Send,
  Sparkles,
  Trash2,
  Upload,
} from 'lucide-react';
import { api } from '../../api';

const pageTitles = {
  curriculum: 'Curriculum progress',
  assignments: 'Assignments',
  submissions: 'Student submissions',
  assessments: 'Assessments',
  risks: 'Academic risk',
  activities: 'Student activities',
  progress: 'Academic progress',
  assistant: 'AI academic assistant',
  documents: 'Academic documents',
  notifications: 'Notifications',
  profile: 'My profile',
};

const dateInputValue = (date) => {
  const local = new Date(date.getTime() - date.getTimezoneOffset() * 60000);
  return local.toISOString().slice(0, 16);
};

function PageHeader({ title, description }) {
  return (
    <header className="workspace-heading">
      <div>
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
    </header>
  );
}

function StatePanel({ loading, error, empty, children }) {
  if (loading) {
    return <div className="workspace-state"><LoaderCircle className="loading-icon" size={22} /> Loading data…</div>;
  }
  if (error) return <div className="workspace-state error-state" role="alert">{error}</div>;
  if (empty) return <div className="workspace-state">{empty}</div>;
  return children;
}

function ProgressBar({ value }) {
  const percentage = Math.max(0, Math.min(Number(value) || 0, 100));
  return (
    <div className="progress-track" role="progressbar" aria-valuenow={percentage} aria-valuemin="0" aria-valuemax="100">
      <span style={{ width: `${percentage}%` }} />
    </div>
  );
}

export default function LearningWorkspace({ role, user, activeTab }) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [subjects, setSubjects] = useState([]);
  const [teacherOptions, setTeacherOptions] = useState([]);
  const [selectedSubject, setSelectedSubject] = useState('');
  const [data, setData] = useState([]);
  const [related, setRelated] = useState([]);
  const [input, setInput] = useState({});
  const [insights, setInsights] = useState(null);
  const [busy, setBusy] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);
  const [statusAssignment, setStatusAssignment] = useState(null);
  const subjectCache = useRef({ role: null, loaded: false, items: [] });

  const isStaff = role === 'ADMIN' || role === 'TEACHER';
  const studentId = user?.student_profile?.id;
  const teacherId = user?.teacher_profile?.id;

  const loadSubjects = useCallback(async () => {
    if (subjectCache.current.role === role && subjectCache.current.loaded && subjectCache.current.items?.length > 0) {
      return subjectCache.current.items;
    }
    if (role === 'STUDENT') {
      let ownSubjects = [];
      try {
        const summary = await api.getMySummary();
        ownSubjects = (summary.subject_breakdown || []).map((item) => ({
          id: item.subject_id || item.id,
          name: item.subject_name || item.name,
          code: item.subject_code || item.code,
        }));
      } catch {
        // Fallback to all subjects
      }
      if (ownSubjects.length === 0) {
        try {
          ownSubjects = await api.getSubjects();
        } catch {
          // Ignored
        }
      }
      setSubjects(ownSubjects);
      subjectCache.current = { role, loaded: true, items: ownSubjects };
      return ownSubjects;
    }
    const allSubjects = await api.getSubjects().catch(() => []);
    if (role !== 'TEACHER') {
      setSubjects(allSubjects);
      subjectCache.current = { role, loaded: true, items: allSubjects };
      return allSubjects;
    }
    let ownSubjects = [];
    if (teacherId) {
      try {
        const assignments = await api.getSubjectAssignments(teacherId);
        const assignedIds = new Set(assignments.map((item) => item.subject_id));
        ownSubjects = allSubjects.filter((item) => assignedIds.has(item.id));
      } catch {
        // Fallback
      }
    }
    if (ownSubjects.length === 0) {
      ownSubjects = allSubjects;
    }
    setSubjects(ownSubjects);
    subjectCache.current = { role, loaded: true, items: ownSubjects };
    return ownSubjects;
  }, [role, teacherId]);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError('');
    setData([]);
    setRelated([]);
    setInsights(null);
    const load = async () => {
      const needsSubjects = ['curriculum', 'assignments', 'submissions', 'assessments', 'documents'].includes(activeTab)
        || (role !== 'ADMIN' && ['assistant', 'risks', 'progress'].includes(activeTab));
      const loadedSubjects = needsSubjects ? await loadSubjects() : [];
      if (role === 'ADMIN' && ['assignments', 'assessments'].includes(activeTab)) {
        const teachers = await api.getUsers({ role: 'TEACHER', limit: 100 });
        if (active) setTeacherOptions(teachers.items.filter((item) => item.teacher_profile));
      }
      const subjectId = selectedSubject || loadedSubjects[0]?.id || loadedSubjects[0]?.subject_id || '';
      if (active && subjectId && !selectedSubject) setSelectedSubject(String(subjectId));

      let result = [];
      let secondary = [];
      let staffInsights = null;
      switch (activeTab) {
        case 'curriculum':
          if (subjectId) {
            [result, secondary] = await Promise.all([
              api.getCurriculumUnits(subjectId),
              api.getSyllabusProgress(subjectId, studentId),
            ]);
          }
          break;
        case 'assignments':
          result = await api.getAssignments();
            if (active) setStatusAssignment(null);
            break;
        case 'submissions': {
          result = await api.getAssignments({ state: 'all', subject_id: subjectId || undefined });
          break;
        }
        case 'assessments':
          [result, secondary] = await Promise.all([
            api.getAssessments(subjectId || undefined),
            isStaff
              ? api.getAssessmentAverages(subjectId || undefined)
              : api.getAssessmentPerformance(studentId, subjectId || undefined),
          ]);
          break;
        case 'risks':
        case 'progress':
          if (role === 'STUDENT') {
            result = await api.getAcademicGaps(undefined, subjectId || undefined);
            secondary = await api.getNextBestActions();
          } else {
            [result, secondary, staffInsights] = await Promise.all([
              api.getAcademicRisks(role === 'TEACHER' && subjectId ? { subject_id: subjectId } : {}),
              api.getAcademicAlerts(),
              api.getAcademicInsights({
                subject_id: role === 'TEACHER' ? (subjectId || undefined) : undefined,
                limit: 50,
              }),
            ]);
          }
          break;
        case 'activities':
          [result, secondary] = await Promise.all([
            api.getActivities(),
            role === 'STUDENT' ? api.getActivityHistory() : api.getActivityStatistics(),
          ]);
          break;
        case 'documents':
          result = await api.getDocuments(subjectId || undefined);
          break;
        case 'assistant':
          result = await api.getAssistantHistory();
          break;
        case 'notifications':
          result = await api.getNotifications();
          break;
        default:
          break;
      }
      if (active) {
        setData(Array.isArray(result) ? result : result ? [result] : []);
        setRelated(Array.isArray(secondary) ? secondary : secondary ? [secondary] : []);
        setInsights(staffInsights);
      }
    };
    load()
      .catch((err) => {
        if (active) setError(err.message || 'Unable to load this section.');
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => { active = false; };
  }, [activeTab, isStaff, loadSubjects, role, selectedSubject, studentId, teacherId, refreshKey]);

  const runAction = async (action, successMessage, refresh = true) => {
    setBusy(true);
    setError('');
    setNotice('');
    try {
      await action();
      setNotice(successMessage);
      if (refresh) {
        setRefreshKey((current) => current + 1);
        setInput({});
      }
    } catch (err) {
      setError(err.message || 'The requested action failed.');
    } finally {
      setBusy(false);
    }
  };

  const subjectSelector = subjects.length > 0 && (
    <label className="workspace-filter">
      <span>Subject</span>
      <select className="glass-input" value={selectedSubject} onChange={(event) => setSelectedSubject(event.target.value)}>
        {subjects.map((subject) => {
          const id = subject.id || subject.subject_id;
          return <option key={id} value={id}>{subject.name || subject.subject_name || `Subject ${id}`}</option>;
        })}
      </select>
    </label>
  );
  const teacherSelector = role === 'ADMIN' && (
    <label>Assigned teacher
      <select className="glass-input" required value={input.teacherId || ''} onChange={(event) => setInput({ ...input, teacherId: event.target.value })}>
        <option value="">Select teacher</option>
        {teacherOptions.map((teacher) => <option key={teacher.teacher_profile.id} value={teacher.teacher_profile.id}>{teacher.teacher_profile.full_name} · {teacher.teacher_profile.employee_id}</option>)}
      </select>
    </label>
  );

  const pageDescription = {
    curriculum: 'Compare backend-reported expected syllabus completion with actual progress.',
    assignments: role === 'STUDENT' ? 'Review deadlines, submit written work, and track evaluations.' : 'Create and manage assignments for your assigned classes.',
    submissions: 'Review student work and record evaluations.',
    assessments: 'Review assessment schedules and backend-reported performance.',
    risks: 'Review backend risk classifications and the indicators behind them.',
    progress: 'Your academic gaps and personalized recommendations from the backend.',
    activities: 'Review academic and extracurricular activity records.',
    assistant: 'Ask questions grounded in your available course documents.',
    documents: 'View course document metadata and upload source PDFs.',
    notifications: 'View and mark your notifications as read.',
    profile: 'Account details returned by your authenticated profile.',
  }[activeTab];

  const submitAssignment = (event, assignmentId) => {
    event.preventDefault();
    runAction(
      () => api.submitAssignment(assignmentId, input[`submission-${assignmentId}`] || ''),
      'Assignment submitted.',
    );
  };

  const renderAssignmentCards = (teacherReview = false) => (
    <div className="workspace-grid">
      {data.map((assignment) => (
        <article className="workspace-card" key={assignment.id}>
          <div className="card-title-row">
            <h3>{assignment.title}</h3>
            <span className={`workspace-badge ${new Date(assignment.due_at) < new Date() ? 'risk-high' : ''}`}>
              {new Date(assignment.due_at).toLocaleDateString()}
              {new Date(assignment.due_at) < new Date() ? ' · Overdue' : ''}
            </span>
          </div>
          <p>{assignment.description || 'No assignment instructions were provided.'}</p>
          <div className="workspace-meta">Maximum marks: {assignment.max_marks} · Subject #{assignment.subject_id}</div>
          {!teacherReview && role === 'STUDENT' && (
            <>
              <button className="btn-secondary" onClick={() => loadStudentSubmissionStatus(assignment.id)}>Check submission status</button>
              <form onSubmit={(event) => submitAssignment(event, assignment.id)} className="workspace-form">
                <label>Written submission
                  <textarea className="glass-input" rows="4" minLength="1" required
                    value={input[`submission-${assignment.id}`] || ''}
                    onChange={(event) => setInput({ ...input, [`submission-${assignment.id}`]: event.target.value })} />
                </label>
                <button className="btn-primary" disabled={busy}><Send size={16} /> Submit work</button>
              </form>
            </>
          )}
          {teacherReview && (
            <button className="btn-secondary" onClick={() => loadSubmissions(assignment.id)}>View submissions</button>
          )}
        </article>
      ))}
    </div>
  );

  const loadSubmissions = async (assignmentId) => {
    setBusy(true);
    setError('');
    try {
      setRelated(await api.getSubmissions(assignmentId));
    } catch (err) {
      setError(err.message || 'Unable to load submissions.');
    } finally {
      setBusy(false);
    }
  };

  const loadAssessmentResults = async (assessmentId) => {
    setBusy(true);
    setError('');
    try {
      setRelated(await api.getAssessmentResults(assessmentId));
    } catch (err) {
      setError(err.message || 'Unable to load assessment results.');
    } finally {
      setBusy(false);
    }
  };

  const loadStudentSubmissionStatus = async (assignmentId) => {
    setBusy(true);
    setError('');
    try {
      setRelated(await api.getSubmissions(assignmentId));
      setStatusAssignment(assignmentId);
    } catch (err) {
      setError(err.message || 'Unable to load submission status.');
    } finally {
      setBusy(false);
    }
  };

  const renderPage = () => {
    if (activeTab === 'profile') {
      const profile = user.student_profile || user.teacher_profile || {};
      return (
        <div className="workspace-card profile-card">
          <dl>
            <div><dt>Name</dt><dd>{profile.full_name || user.full_name || user.username}</dd></div>
            <div><dt>Username</dt><dd>{user.username}</dd></div>
            <div><dt>Email</dt><dd>{profile.email || user.email || 'Not provided'}</dd></div>
            <div><dt>Role</dt><dd>{user.role}</dd></div>
            <div><dt>Profile ID</dt><dd>{profile.id || 'Not linked'}</dd></div>
          </dl>
          <p className="workspace-meta">Profile editing is not available in the current backend API.</p>
        </div>
      );
    }

    if (activeTab === 'assistant') {
      return (
        <div className="workspace-card assistant-panel">
          <div className="card-title-row">
            <div>
              <h2>Academic assistant</h2>
              <p>Answers use your academic records and authorized source documents.</p>
            </div>
            <button
              type="button"
              className="btn-secondary"
              disabled={busy || data.length === 0}
              onClick={() => runAction(async () => {
                await api.clearAssistantHistory();
                setData([]);
              }, 'Conversation cleared.', false)}
            >
              <Trash2 size={15} /> Clear chat
            </button>
          </div>
          {subjectSelector}
          <div className="assistant-history">
            {data.length > 0 ? data.map((message, index) => (
              <article
                className={`chat-message ${message.role === 'user' ? 'chat-message-user' : 'chat-message-assistant'}`}
                key={message.id || `${message.role}-${index}`}
              >
                <span className="chat-message-label">{message.role === 'user' ? 'You' : 'Academic assistant'}</span>
                <div className={message.role === 'user' ? 'chat-question' : 'chat-answer'}>{message.content}</div>
                {message.role === 'assistant' && message.citations?.length > 0 && (
                  <section className="citation-list">
                    <h3>Sources</h3>
                    {message.citations.map((citation) => (
                      <blockquote key={`${message.id || index}-${citation.document_id}-${citation.chunk_id}`}>
                        <strong>{citation.filename}</strong>
                        <p>{citation.text}</p>
                      </blockquote>
                    ))}
                  </section>
                )}
              </article>
            )) : <div className="workspace-state">Ask about your attendance, coursework, syllabus, assessments, or academic policies.</div>}
            {busy && <div className="workspace-state" role="status"><LoaderCircle className="loading-icon" size={18} /> Checking your academic records and sources…</div>}
          </div>
          <div className="assistant-suggestions" aria-label="Suggested questions">
            {[
              'What should I focus on next?',
              'What is my attendance in this subject?',
              'Which assignments are pending?',
              'Explain the syllabus topics from my documents.',
              'What does the attendance policy say?',
            ].map((suggestion) => (
              <button
                type="button"
                className="btn-secondary"
                key={suggestion}
                onClick={() => setInput((current) => ({ ...current, question: suggestion }))}
              >
                {suggestion}
              </button>
            ))}
          </div>
          <form className="workspace-form" onSubmit={(event) => {
            event.preventDefault();
            const question = input.question || '';
            if (question.trim().length < 3) {
              setError('Enter a question with at least three characters.');
              return;
            }
            let targetSubject = selectedSubject;
            if (!targetSubject && role !== 'ADMIN') {
              if (subjects.length > 0) {
                targetSubject = String(subjects[0].id || subjects[0].subject_id);
                setSelectedSubject(targetSubject);
              } else {
                setError('Choose a subject before asking the assistant.');
                return;
              }
            }
            runAction(async () => {
              const answer = await api.askAcademicAssistant(question, targetSubject || undefined);
              const timestamp = new Date().toISOString();
              setData((messages) => [
                ...messages,
                { role: 'user', content: question, created_at: timestamp },
                {
                  role: 'assistant',
                  content: answer.answer,
                  citations: answer.citations || [],
                  created_at: timestamp,
                },
              ]);
              setInput((current) => ({ ...current, question: '' }));
            }, 'Answer received.', false);
          }}>
            <label>Your question
              <textarea className="glass-input" rows="3" maxLength="4000" required
                value={input.question || ''}
                onChange={(event) => setInput({ ...input, question: event.target.value })} />
            </label>
            <button className="btn-primary" disabled={busy || !input.question?.trim()}><Send size={16} /> Ask assistant</button>
          </form>
        </div>
      );
    }

    if (activeTab === 'curriculum') {
      const progress = related[0];
      return (
        <>
          {subjectSelector}
          <StatePanel loading={loading} error={error} empty={!progress && !data.length ? 'No syllabus progress is available for this subject yet.' : null}>
            {progress && (
              <div className="workspace-card progress-card">
                <div className="card-title-row">
                  <div><h2>{progress.subject_name}</h2><p>{progress.completed_topics} of {progress.total_topics} topics completed</p></div>
                  <strong>{Number(progress.actual_progress_percentage).toFixed(1)}%</strong>
                </div>
                <ProgressBar value={progress.actual_progress_percentage} />
                <div className="progress-comparison">
                  <span>Actual {Number(progress.actual_progress_percentage).toFixed(1)}%</span>
                  <span>Expected {Number(progress.expected_progress_percentage).toFixed(1)}%</span>
                  <span className={Number(progress.curriculum_gap_percentage) > 0 ? 'negative-gap' : 'positive-gap'}>
                    Gap {Number(progress.curriculum_gap_percentage).toFixed(1)}%
                  </span>
                </div>
              </div>
            )}
            {data.length > 0 && (
              <div className="workspace-grid">
                {data.map((unit) => <article className="workspace-card" key={unit.id}>
                  <div className="card-title-row"><h3>{unit.order_index}. {unit.title}</h3><BookOpen size={18} /></div>
                  <p>{unit.description || 'No unit description.'}</p>
                  <div className="workspace-meta">Unit #{unit.id}{unit.expected_completion_date ? ` · Expected ${new Date(unit.expected_completion_date).toLocaleDateString()}` : ''}</div>
                  <div className="workspace-meta">Topic lists and topic-level progress are not exposed by the current API.</div>
                </article>)}
              </div>
            )}
          </StatePanel>
          {isStaff && (
            <form className="workspace-card workspace-form" onSubmit={(event) => {
              event.preventDefault();
              runAction(() => api.createCurriculumUnit({
                subject_id: Number(selectedSubject),
                title: input.unitTitle,
                description: input.unitDescription || null,
                order_index: Number(input.unitOrder),
              }), 'Curriculum unit created.');
            }}>
              <h3><Plus size={18} /> Add curriculum unit</h3>
              {subjectSelector}
              <label>Unit title<input className="glass-input" required value={input.unitTitle || ''} onChange={(event) => setInput({ ...input, unitTitle: event.target.value })} /></label>
              <label>Order<input className="glass-input" type="number" min="1" required value={input.unitOrder || ''} onChange={(event) => setInput({ ...input, unitOrder: event.target.value })} /></label>
              <label>Description<textarea className="glass-input" rows="2" value={input.unitDescription || ''} onChange={(event) => setInput({ ...input, unitDescription: event.target.value })} /></label>
              <button className="btn-primary" disabled={busy}>Create unit</button>
            </form>
          )}
          {isStaff && data.length > 0 && (
            <form className="workspace-card workspace-form" onSubmit={(event) => {
              event.preventDefault();
              runAction(() => api.createCurriculumTopic(Number(input.unitId), {
                title: input.topicTitle,
                description: input.topicDescription || null,
                order_index: Number(input.topicOrder),
              }), 'Curriculum topic created.');
            }}>
              <h3><Plus size={18} /> Add topic to a unit</h3>
              <label>Unit<select className="glass-input" required value={input.unitId || ''} onChange={(event) => setInput({ ...input, unitId: event.target.value })}>
                <option value="">Select unit</option>
                {data.map((unit) => <option key={unit.id} value={unit.id}>{unit.order_index}. {unit.title}</option>)}
              </select></label>
              <label>Topic title<input className="glass-input" required value={input.topicTitle || ''} onChange={(event) => setInput({ ...input, topicTitle: event.target.value })} /></label>
              <label>Order<input className="glass-input" type="number" min="1" required value={input.topicOrder || ''} onChange={(event) => setInput({ ...input, topicOrder: event.target.value })} /></label>
              <label>Description<textarea className="glass-input" rows="2" value={input.topicDescription || ''} onChange={(event) => setInput({ ...input, topicDescription: event.target.value })} /></label>
              <button className="btn-primary" disabled={busy}>Create topic</button>
            </form>
          )}
        </>
      );
    }

    if (activeTab === 'assignments') {
      return (
        <>
          {subjectSelector}
          <StatePanel loading={loading} error={error} empty={data.length ? null : 'No assignments are available.'}>
            {renderAssignmentCards(false)}
          </StatePanel>
          {role === 'STUDENT' && statusAssignment && (
            <section className="workspace-card">
              <h3>Submission status · Assignment #{statusAssignment}</h3>
              {related.length === 0 ? <p>No submission has been received for this assignment.</p> : related.map((submission) => (
                <div key={submission.id}>
                  <p>Submitted {new Date(submission.submitted_at).toLocaleString()}</p>
                  <p>Evaluation: {submission.score == null ? 'Awaiting evaluation' : `${submission.score} marks`}</p>
                  {submission.feedback && <p>Feedback: {submission.feedback}</p>}
                </div>
              ))}
            </section>
          )}
          {isStaff && (
            <form className="workspace-card workspace-form" onSubmit={(event) => {
              event.preventDefault();
              runAction(() => api.createAssignment({
                subject_id: Number(selectedSubject),
                ...(role === 'ADMIN' ? { teacher_id: Number(input.teacherId) } : {}),
                title: input.title,
                description: input.description || null,
                due_at: new Date(input.dueAt).toISOString(),
                max_marks: Number(input.maxMarks),
              }), 'Assignment created.');
            }}>
              <h3><Plus size={18} /> Create assignment</h3>
              {subjectSelector}
              {teacherSelector}
              <label>Title<input className="glass-input" required value={input.title || ''} onChange={(event) => setInput({ ...input, title: event.target.value })} /></label>
              <label>Instructions<textarea className="glass-input" rows="3" value={input.description || ''} onChange={(event) => setInput({ ...input, description: event.target.value })} /></label>
              <label>Due date<input className="glass-input" type="datetime-local" required min={dateInputValue(new Date())} value={input.dueAt || ''} onChange={(event) => setInput({ ...input, dueAt: event.target.value })} /></label>
              <label>Maximum marks<input className="glass-input" type="number" min="0.01" step="0.01" required value={input.maxMarks || ''} onChange={(event) => setInput({ ...input, maxMarks: event.target.value })} /></label>
              <button className="btn-primary" disabled={busy || !selectedSubject || (role === 'ADMIN' && !input.teacherId)}>Create assignment</button>
            </form>
          )}
          {role === 'STUDENT' && <p className="workspace-meta">File upload is not supported by the current submission API; written text is submitted directly.</p>}
        </>
      );
    }

    if (activeTab === 'submissions') {
      return (
        <>
          {subjectSelector}
          <StatePanel loading={loading} error={error} empty={data.length ? null : 'No assignments are available to review.'}>
            {renderAssignmentCards(true)}
          </StatePanel>
          {related.length > 0 && <div className="workspace-grid">
            {related.map((submission) => (
              <form className="workspace-card workspace-form" key={submission.id} onSubmit={(event) => {
                event.preventDefault();
                runAction(() => api.evaluateSubmission(submission.id, Number(input[`score-${submission.id}`]), input[`feedback-${submission.id}`] || null), 'Submission evaluation saved.', false);
              }}>
                <div className="card-title-row"><h3>Submission #{submission.id}</h3><span className="workspace-badge">{submission.score ?? 'Not graded'}</span></div>
                <p className="submission-content">{submission.content}</p>
                <label>Score<input className="glass-input" type="number" min="0" step="0.01" required value={input[`score-${submission.id}`] ?? submission.score ?? ''} onChange={(event) => setInput({ ...input, [`score-${submission.id}`]: event.target.value })} /></label>
                <label>Feedback<textarea className="glass-input" rows="2" value={input[`feedback-${submission.id}`] ?? submission.feedback ?? ''} onChange={(event) => setInput({ ...input, [`feedback-${submission.id}`]: event.target.value })} /></label>
                <button className="btn-primary" disabled={busy}>Save evaluation</button>
              </form>
            ))}
          </div>}
        </>
      );
    }

    if (activeTab === 'assessments') {
      return (
        <>
          {subjectSelector}
          <StatePanel loading={loading} error={error} empty={data.length ? null : 'No assessments are available.'}>
            <div className="workspace-grid">
              {data.map((assessment) => <article className="workspace-card" key={assessment.id}>
                <h3>{assessment.title}</h3>
                <p>{assessment.assessment_type} · {new Date(assessment.scheduled_at).toLocaleString()}</p>
                <div className="workspace-meta">Maximum marks: {assessment.max_marks} · Subject #{assessment.subject_id}</div>
                {isStaff && <button className="btn-secondary" onClick={() => loadAssessmentResults(assessment.id)}>View recorded results</button>}
              </article>)}
            </div>
          </StatePanel>
          {related.length > 0 && <section className="workspace-card">
            <h3>{isStaff ? 'Subject performance averages' : 'Your assessment performance'}</h3>
            <div className="workspace-grid">
              {related.map((item, index) => <article className="workspace-stat" key={item.id || item.assessment_id || index}>
                {Object.entries(item).filter(([, value]) => value === null || ['string', 'number'].includes(typeof value)).map(([key, value]) => (
                  <div key={key}><span>{key.replaceAll('_', ' ')}</span><strong>{value ?? '—'}</strong></div>
                ))}
              </article>)}
            </div>
          </section>}
          {isStaff && (
            <form className="workspace-card workspace-form" onSubmit={(event) => {
              event.preventDefault();
              runAction(() => api.createAssessment({
                subject_id: Number(selectedSubject),
                ...(role === 'ADMIN' ? { teacher_id: Number(input.teacherId) } : {}),
                title: input.assessmentTitle,
                assessment_type: input.assessmentType,
                scheduled_at: new Date(input.scheduledAt).toISOString(),
                max_marks: Number(input.assessmentMaxMarks),
              }), 'Assessment created.');
            }}>
              <h3><Plus size={18} /> Schedule assessment</h3>
              {subjectSelector}
              {teacherSelector}
              <label>Title<input className="glass-input" required value={input.assessmentTitle || ''} onChange={(event) => setInput({ ...input, assessmentTitle: event.target.value })} /></label>
              <label>Type<input className="glass-input" required value={input.assessmentType || ''} onChange={(event) => setInput({ ...input, assessmentType: event.target.value })} /></label>
              <label>Scheduled at<input className="glass-input" type="datetime-local" required value={input.scheduledAt || ''} onChange={(event) => setInput({ ...input, scheduledAt: event.target.value })} /></label>
              <label>Maximum marks<input className="glass-input" type="number" min="0.01" step="0.01" required value={input.assessmentMaxMarks || ''} onChange={(event) => setInput({ ...input, assessmentMaxMarks: event.target.value })} /></label>
              <button className="btn-primary" disabled={busy || !selectedSubject || (role === 'ADMIN' && !input.teacherId)}>Schedule assessment</button>
            </form>
          )}
          {isStaff && related.length === 0 && <p className="workspace-meta">Use backend assessment result APIs to record marks; student record IDs are required and no class roster result workflow is available in this API.</p>}
          {isStaff && related.length > 0 && <section className="workspace-card">
            <h3>Recorded assessment results</h3>
            <div className="workspace-grid">{related.map((result) => <div className="workspace-stat" key={result.id}>
              <span>Student #{result.student_id}</span><strong>{result.marks}</strong>
              {result.feedback && <p>{result.feedback}</p>}
            </div>)}</div>
          </section>}
          {isStaff && data.length > 0 && <form className="workspace-card workspace-form" onSubmit={(event) => {
            event.preventDefault();
            runAction(() => api.recordAssessmentResult(Number(input.resultAssessmentId), {
              student_id: Number(input.resultStudentId),
              marks: Number(input.resultMarks),
              feedback: input.resultFeedback || null,
            }), 'Assessment result saved.', false);
          }}>
            <h3>Record assessment marks</h3>
            <label>Assessment<select className="glass-input" required value={input.resultAssessmentId || ''} onChange={(event) => setInput({ ...input, resultAssessmentId: event.target.value })}>
              <option value="">Choose an assessment</option>
              {data.map((assessment) => <option key={assessment.id} value={assessment.id}>{assessment.title}</option>)}
            </select></label>
            <label>Student profile ID<input className="glass-input" type="number" min="1" required value={input.resultStudentId || ''} onChange={(event) => setInput({ ...input, resultStudentId: event.target.value })} /></label>
            <label>Marks<input className="glass-input" type="number" min="0" step="0.01" required value={input.resultMarks || ''} onChange={(event) => setInput({ ...input, resultMarks: event.target.value })} /></label>
            <label>Feedback<textarea className="glass-input" rows="2" value={input.resultFeedback || ''} onChange={(event) => setInput({ ...input, resultFeedback: event.target.value })} /></label>
            <button className="btn-primary" disabled={busy}>Save marks</button>
          </form>}
        </>
      );
    }

    if (activeTab === 'risks' || activeTab === 'progress') {
      const risk = data[0];
      if (role === 'STUDENT') {
        const gap = risk || {};
        return (
          <>
            <StatePanel loading={loading} error={error} empty={!risk ? 'Academic gap metrics will appear when the backend has enough student records.' : null}>
              <div className="workspace-grid">
                {[
                  ['Attendance gap', gap.attendance_gap, '%'],
                  ['Curriculum gap', gap.curriculum_gap, '%'],
                  ['Pending assignments', gap.pending_assignments, ''],
                  ['Performance gap', gap.performance_gap, '%'],
                ].map(([label, value, suffix]) => <div className="workspace-card workspace-metric" key={label}>
                  <span>{label}</span><strong>{value == null ? '—' : `${Number(value).toFixed(1)}${suffix}`}</strong>
                </div>)}
                <div className="workspace-card workspace-metric"><span>Risk level</span><strong className={`risk-${String(gap.risk_level || 'low').toLowerCase()}`}>{gap.risk_level || '—'}</strong></div>
              </div>
              {gap.risk_reasons?.length > 0 && <div className="workspace-card">
                <h3><AlertTriangle size={18} /> Risk reasons</h3>
                <ul className="workspace-list">{gap.risk_reasons.map((reason) => <li key={reason}>{reason}</li>)}</ul>
              </div>}
            </StatePanel>
            <section className="workspace-card">
              <h3><Sparkles size={18} /> Your next best actions</h3>
              {related.length ? (
                <div className="workspace-grid">
                  {related.map((item, index) => <article className="workspace-card" key={`${item.subject_id || 'general'}-${item.indicator || index}`}>
                    <div className="card-title-row">
                      <h4>{item.action || item.recommendation || item.title}</h4>
                      <span className={`workspace-badge risk-${String(item.priority || 'LOW').toLowerCase()}`}>{item.priority || 'Suggested'}</span>
                    </div>
                    <p>{item.rationale || item.message || 'Based on your latest academic records.'}</p>
                  </article>)}
                </div>
              ) : <p>No current next steps were identified from your recorded academic data.</p>}
            </section>
          </>
        );
      }
      return (
        <>
          {insights && <section className="workspace-card">
            <div className="card-title-row">
              <h2>Live academic insights</h2>
              {insights.truncated && <span className="workspace-badge">Showing a limited student sample</span>}
            </div>
            <p>{insights.students_analyzed} students analyzed across {insights.subject_student_analyses} student-subject records.</p>
            <div className="workspace-grid">
              {Object.entries(insights.risk_distribution || {}).map(([level, count]) => (
                <div className="workspace-stat" key={level}><span>{level} risk</span><strong>{count}</strong></div>
              ))}
            </div>
            {role === 'ADMIN' && insights.departments?.length > 0 && <div className="workspace-grid">
              {insights.departments.map((department) => <article className="workspace-card" key={department.department_id}>
                <h3>{department.department_name}</h3>
                <p>{department.student_subject_analyses} student-subject records · {department.risk_distribution.HIGH} high risk · {department.risk_distribution.MEDIUM} medium risk</p>
                <p>Average attendance gap {department.average_attendance_gap} points · syllabus gap {department.average_curriculum_gap} points</p>
              </article>)}
            </div>}
            {insights.subjects?.length > 0 && <div className="workspace-grid">
              {insights.subjects.map((subject) => <article className="workspace-card" key={subject.subject_id}>
                <h3>{subject.subject_name}</h3>
                <p>{subject.students_analyzed} students · {subject.risk_distribution.HIGH} high risk · {subject.risk_distribution.MEDIUM} medium risk</p>
                <p>Average attendance gap {subject.average_attendance_gap} points · syllabus gap {subject.average_curriculum_gap} points</p>
              </article>)}
            </div>}
            {insights.students_requiring_attention?.length > 0 && <div className="workspace-grid">
              {insights.students_requiring_attention.slice(0, 20).map((student, index) => <article className="workspace-card" key={`${student.student_id}-${student.subject_id}-${index}`}>
                <div className="card-title-row"><h3>{student.student_name}</h3><span className={`workspace-badge risk-${student.risk_level.toLowerCase()}`}>{student.risk_level}</span></div>
                <p>{student.subject_name} · attendance {student.attendance_percentage == null ? 'no classes recorded' : `${student.attendance_percentage}% (target ${student.required_attendance_percentage}%)`}</p>
                {student.risk_reasons?.length > 0 && <p>{student.risk_reasons.join(' · ')}</p>}
              </article>)}
            </div>}
          </section>}
          <label className="workspace-filter">Risk level
            <select className="glass-input" value={input.riskLevel || ''} onChange={(event) => {
              const value = event.target.value;
              setInput({ ...input, riskLevel: value });
              api.getAcademicRisks({ risk_level: value || undefined }).then(setData).catch((err) => setError(err.message));
            }}>
              <option value="">All levels</option><option value="HIGH">High</option><option value="MEDIUM">Medium</option><option value="LOW">Low</option>
            </select>
          </label>
          <StatePanel loading={loading} error={error} empty={data.length ? null : 'No stored academic risk records match this filter.'}>
            <div className="workspace-grid">
              {data.map((item, index) => <article className="workspace-card" key={`${item.student_id}-${item.subject_id}-${index}`}>
                <div className="card-title-row"><h3>Student #{item.student_id}</h3><span className={`workspace-badge risk-${item.risk_level.toLowerCase()}`}>{item.risk_level}</span></div>
                <p>{item.subject_id ? `Subject #${item.subject_id}` : 'Overall risk'}</p>
                <ul className="workspace-list">{(item.risk_reasons || []).map((reason) => <li key={reason}>{reason}</li>)}</ul>
              </article>)}
            </div>
          </StatePanel>
          {related.length > 0 && <section className="workspace-card"><h3>Academic alerts</h3>{related.map((alert) => <p key={alert.id}>{alert.title} · {alert.severity}</p>)}</section>}
        </>
      );
    }

    if (activeTab === 'activities') {
      return (
        <>
          <StatePanel loading={loading} error={error} empty={data.length ? null : 'No activities are available.'}>
            <div className="workspace-grid">{data.map((activity) => <article className="workspace-card" key={activity.id}>
              <div className="card-title-row"><h3>{activity.title}</h3><span className="workspace-badge">{activity.activity_type}</span></div>
              <p>{activity.description || 'No description provided.'}</p>
              <div className="workspace-meta">{new Date(activity.activity_date).toLocaleDateString()}</div>
              {isStaff && <form className="workspace-form" onSubmit={(event) => {
                event.preventDefault();
                runAction(() => api.recordActivityParticipation(activity.id, {
                  student_id: Number(input[`activityStudent-${activity.id}`]),
                  participated: true,
                  achievement: input[`activityAchievement-${activity.id}`] || null,
                  points: Number(input[`activityPoints-${activity.id}`] || 0),
                }), 'Student participation recorded.', false);
              }}>
                <label>Student profile ID<input className="glass-input" type="number" min="1" required value={input[`activityStudent-${activity.id}`] || ''} onChange={(event) => setInput({ ...input, [`activityStudent-${activity.id}`]: event.target.value })} /></label>
                <label>Achievement<input className="glass-input" value={input[`activityAchievement-${activity.id}`] || ''} onChange={(event) => setInput({ ...input, [`activityAchievement-${activity.id}`]: event.target.value })} /></label>
                <label>Points<input className="glass-input" type="number" min="0" value={input[`activityPoints-${activity.id}`] || '0'} onChange={(event) => setInput({ ...input, [`activityPoints-${activity.id}`]: event.target.value })} /></label>
                <button className="btn-secondary" disabled={busy}>Record participation</button>
              </form>}
            </article>)}</div>
          </StatePanel>
          {isStaff && <form className="workspace-card workspace-form" onSubmit={(event) => {
            event.preventDefault();
            runAction(() => api.createActivity({
              title: input.activityTitle,
              description: input.activityDescription || null,
              activity_type: input.activityType,
              activity_date: new Date(input.activityDate).toISOString(),
              subject_id: selectedSubject ? Number(selectedSubject) : null,
            }), 'Activity created.');
          }}>
            <h3><Plus size={18} /> Create activity</h3>
            <label>Title<input className="glass-input" required value={input.activityTitle || ''} onChange={(event) => setInput({ ...input, activityTitle: event.target.value })} /></label>
            <label>Type<select className="glass-input" value={input.activityType || 'ACADEMIC'} onChange={(event) => setInput({ ...input, activityType: event.target.value })}><option>ACADEMIC</option><option>EXTRACURRICULAR</option></select></label>
            <label>Date<input className="glass-input" type="datetime-local" required value={input.activityDate || ''} onChange={(event) => setInput({ ...input, activityDate: event.target.value })} /></label>
            <label>Description<textarea className="glass-input" rows="2" value={input.activityDescription || ''} onChange={(event) => setInput({ ...input, activityDescription: event.target.value })} /></label>
            <button className="btn-primary" disabled={busy}>Create activity</button>
          </form>}
          {related.length > 0 && <div className="workspace-card"><h3>{role === 'STUDENT' ? 'Participation history' : 'Activity statistics'}</h3><pre className="workspace-json">{JSON.stringify(related, null, 2)}</pre></div>}
        </>
      );
    }

    if (activeTab === 'documents') {
      return (
        <>
          {subjectSelector}
          <StatePanel loading={loading} error={error} empty={data.length ? null : 'No academic documents have been added for this subject.'}>
            <div className="workspace-grid">{data.map((document) => <article className="workspace-card" key={document.id}>
              <h3><FileText size={18} /> {document.filename}</h3>
              <p>{document.content_type}</p>
              <span className="workspace-badge">Processing {document.processing_status || 'READY'}</span>
              <p>Department {document.department_id ?? 'all'} · class {document.academic_class_id ?? 'all'} · academic year {document.academic_year_id ?? 'all'} · semester {document.semester_id ?? 'all'}</p>
              <div className="workspace-meta">Uploaded {new Date(document.created_at).toLocaleString()}</div>
              {isStaff && <button
                type="button"
                className="btn-secondary"
                disabled={busy}
                onClick={() => {
                  if (window.confirm(`Delete "${document.filename}" and its indexed chunks?`)) {
                    runAction(() => api.deleteDocument(document.id), 'Document and indexed chunks deleted.');
                  }
                }}
              >
                <Trash2 size={15} /> Delete
              </button>}
              {isStaff && <form className="workspace-form" onSubmit={(event) => {
                event.preventDefault();
                const file = input[`replaceFile-${document.id}`];
                if (!file || file.type !== 'application/pdf') {
                  setError('Select a replacement PDF document.');
                  return;
                }
                runAction(
                  () => api.replaceDocument(document.id, file),
                  'Document replaced and re-indexed.',
                );
              }}>
                <label>Replace with a new PDF<input
                  className="glass-input"
                  type="file"
                  accept="application/pdf,.pdf"
                  required
                  onChange={(event) => setInput((current) => ({
                    ...current,
                    [`replaceFile-${document.id}`]: event.target.files?.[0],
                  }))}
                /></label>
                <button className="btn-secondary" disabled={busy}>Replace and re-index</button>
              </form>}
            </article>)}</div>
          </StatePanel>
          {isStaff && <form className="workspace-card workspace-form" onSubmit={(event) => {
            event.preventDefault();
            const file = input.document;
            if (!file || file.type !== 'application/pdf') {
              setError('Select a PDF document.');
              return;
            }
            if (role === 'TEACHER' && !selectedSubject) {
              setError('Choose an assigned subject before uploading.');
              return;
            }
            const metadata = input.documentGlobal ? {
              department_id: input.documentDepartment,
              academic_class_id: input.documentClass,
              academic_year_id: input.documentYear,
              semester_id: input.documentSemester,
            } : { academic_class_id: input.documentClass };
            const documentSubject = role === 'ADMIN' && input.documentGlobal
              ? undefined
              : selectedSubject || undefined;
            runAction(
              () => api.uploadDocument(file, documentSubject, metadata),
              'Document processed and indexed.',
            );
          }}>
            <h3><Upload size={18} /> Upload and index an academic PDF</h3>
            {role === 'ADMIN' && <label className="workspace-checkbox">
              <input
                type="checkbox"
                checked={Boolean(input.documentGlobal)}
                onChange={(event) => setInput({ ...input, documentGlobal: event.target.checked })}
              />
              Institution-wide document (no subject)
            </label>}
            {!input.documentGlobal && subjectSelector}
            <p className="workspace-meta">When a subject is selected, department, semester, and academic year are derived and validated by the backend.</p>
            {!input.documentGlobal && <label>Course/class ID (optional)<input className="glass-input" type="number" min="1" value={input.documentClass || ''} onChange={(event) => setInput({ ...input, documentClass: event.target.value })} /></label>}
            {input.documentGlobal && role === 'ADMIN' && <>
              <label>Department ID (optional)<input className="glass-input" type="number" min="1" value={input.documentDepartment || ''} onChange={(event) => setInput({ ...input, documentDepartment: event.target.value })} /></label>
              <label>Course/class ID (optional)<input className="glass-input" type="number" min="1" value={input.documentClass || ''} onChange={(event) => setInput({ ...input, documentClass: event.target.value })} /></label>
              <label>Academic year ID (optional)<input className="glass-input" type="number" min="1" value={input.documentYear || ''} onChange={(event) => setInput({ ...input, documentYear: event.target.value })} /></label>
              <label>Semester ID (optional)<input className="glass-input" type="number" min="1" value={input.documentSemester || ''} onChange={(event) => setInput({ ...input, documentSemester: event.target.value })} /></label>
            </>}
            <label>PDF file<input className="glass-input" type="file" accept="application/pdf,.pdf" required onChange={(event) => setInput({ ...input, document: event.target.files?.[0] })} /></label>
            <button className="btn-primary" disabled={busy || (role === 'TEACHER' && !selectedSubject)}>Upload document</button>
          </form>}
        </>
      );
    }

    if (activeTab === 'notifications') {
      return (
        <StatePanel loading={loading} error={error} empty={data.length ? null : 'No notifications yet.'}>
          <div className="workspace-grid">{data.map((notification) => <article className="workspace-card" key={notification.id}>
            <div className="card-title-row"><h3>{notification.title}</h3>{!notification.read_at && <span className="workspace-badge">Unread</span>}</div>
            <p>{notification.message}</p>
            <div className="workspace-meta">{new Date(notification.created_at).toLocaleString()} · {notification.category}</div>
            {!notification.read_at && <button className="btn-secondary" onClick={() => runAction(() => api.markNotificationRead(notification.id), 'Notification marked as read.')}>
              <Check size={16} /> Mark read
            </button>}
          </article>)}</div>
        </StatePanel>
      );
    }
    return null;
  };

  if (!pageTitles[activeTab]) return null;
  return (
    <section className="learning-workspace">
      <PageHeader title={pageTitles[activeTab]} description={pageDescription} />
      {notice && <div className="workspace-notice" role="status">{notice}</div>}
      {error && !loading && <div className="workspace-error" role="alert">{error}</div>}
      {renderPage()}
    </section>
  );
}
