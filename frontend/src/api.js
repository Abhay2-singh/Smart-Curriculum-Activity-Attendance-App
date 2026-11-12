const rawBaseUrl = import.meta.env?.VITE_API_BASE_URL;
const API_BASE_URL = rawBaseUrl
  ? (rawBaseUrl.endsWith('/') ? rawBaseUrl.slice(0, -1) : rawBaseUrl)
  : '/api';

export const getAuthToken = () => localStorage.getItem('token');
export const setAuthToken = (token) => localStorage.setItem('token', token);
export const removeAuthToken = () => {
  localStorage.removeItem('token');
  localStorage.removeItem('user');
};

export const getStoredUser = () => {
  const user = localStorage.getItem('user');
  return user ? JSON.parse(user) : null;
};

export const setStoredUser = (user) => localStorage.setItem('user', JSON.stringify(user));

export async function apiRequest(endpoint, options = {}) {
  const token = getAuthToken();
  const isFormData = options.body instanceof FormData;
  const headers = {
    ...(!isFormData ? { 'Content-Type': 'application/json' } : {}),
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...(options.headers || {}),
  };

  const config = {
    ...options,
    headers,
  };

  let response;
  try {
    response = await fetch(`${API_BASE_URL}${endpoint}`, config);
  } catch {
    // If proxied fetch failed or network error occurred, attempt fallback direct URL fetch
    if (API_BASE_URL.startsWith('/')) {
      try {
        response = await fetch(`http://127.0.0.1:8000/api${endpoint}`, config);
      } catch {
        throw new Error(`Unable to connect to FastAPI backend server (${API_BASE_URL}). Please ensure backend server is running.`);
      }
    } else {
      throw new Error(`Unable to connect to FastAPI backend server (${API_BASE_URL}). Please ensure backend server is running.`);
    }
  }

  if (response.status === 401) {
    removeAuthToken();
    window.dispatchEvent(new Event('unauthorized'));
  }

  const data = await response.json().catch(() => ({}));

  if (!response.ok) {
    let errorMsg = 'An API error occurred';
    if (typeof data.detail === 'string') {
      errorMsg = data.detail;
    } else if (Array.isArray(data.detail)) {
      errorMsg = data.detail.map(e => e.msg || e.detail || JSON.stringify(e)).join(', ');
    } else if (typeof data.detail === 'object' && data.detail !== null) {
      errorMsg = data.detail.message || data.detail.msg || JSON.stringify(data.detail);
    } else if (data.message) {
      errorMsg = typeof data.message === 'string' ? data.message : JSON.stringify(data.message);
    }
    throw new Error(errorMsg);
  }

  return data;
}

export const api = {
  login: (username, password) =>
    apiRequest('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    }),

  getMe: () => apiRequest('/auth/me'),

  // User Management
  getUsers: (params = {}) => {
    const searchParams = new URLSearchParams();
    if (params.skip !== undefined) searchParams.append('skip', params.skip);
    if (params.limit !== undefined) searchParams.append('limit', params.limit);
    if (params.role) searchParams.append('role', params.role);
    if (params.is_active !== undefined && params.is_active !== null) searchParams.append('is_active', params.is_active);
    if (params.search) searchParams.append('search', params.search);
    return apiRequest(`/users?${searchParams.toString()}`);
  },
  createUser: (userData) =>
    apiRequest('/users', {
      method: 'POST',
      body: JSON.stringify(userData),
    }),
  getUser: (id) => apiRequest(`/users/${id}`),
  updateUser: (id, userData) =>
    apiRequest(`/users/${id}`, {
      method: 'PUT',
      body: JSON.stringify(userData),
    }),
  updateUserStatus: (id, is_active) =>
    apiRequest(`/users/${id}/status`, {
      method: 'PATCH',
      body: JSON.stringify({ is_active }),
    }),

  // Academic Structure
  getDepartments: () => apiRequest('/departments'),
  getAcademicYears: () => apiRequest('/academic-years'),
  getSemesters: (academicYearId) =>
    apiRequest(`/semesters${academicYearId ? `?academic_year_id=${academicYearId}` : ''}`),
  getAcademicClasses: (departmentId) =>
    apiRequest(`/academic-classes${departmentId ? `?department_id=${departmentId}` : ''}`),
  getDivisions: (classId) =>
    apiRequest(`/divisions${classId ? `?academic_class_id=${classId}` : ''}`),
  getBatches: (divisionId) =>
    apiRequest(`/batches${divisionId ? `?division_id=${divisionId}` : ''}`),
  getSubjects: (departmentId, semesterId) => {
    const params = new URLSearchParams();
    if (departmentId) params.append('department_id', departmentId);
    if (semesterId) params.append('semester_id', semesterId);
    return apiRequest(`/subjects?${params.toString()}`);
  },
  getTeachers: async (departmentId) => {
    const res = await api.getUsers({ role: 'TEACHER', limit: 100 });
    let items = res.items || [];
    if (departmentId) {
      items = items.filter((user) => user.teacher_profile?.department_id === Number(departmentId));
    }
    return items.map((user) => ({
      id: user.teacher_profile?.id,
      employee_id: user.teacher_profile?.employee_id,
      full_name: user.teacher_profile?.full_name || user.username,
      email: user.teacher_profile?.email || user.email,
      department_id: user.teacher_profile?.department_id,
    }));
  },
  getStudents: async (params = {}) => {
    const res = await api.getUsers({ role: 'STUDENT', limit: 100 });
    let items = res.items || [];
    if (params.division_id) {
      items = items.filter((user) => user.student_profile?.division_id === Number(params.division_id));
    }
    return items.map((user) => ({
      id: user.student_profile?.id,
      student_id: user.student_profile?.student_id,
      roll_number: user.student_profile?.roll_number,
      full_name: user.student_profile?.full_name || user.username,
      email: user.student_profile?.email || user.email,
      division_id: user.student_profile?.division_id,
    }));
  },
  getEnrollments: (divisionId) =>
    apiRequest(`/class-subject-assignments${divisionId ? `?division_id=${divisionId}` : ''}`),
  getSubjectAssignments: (teacherId) =>
    apiRequest(`/teacher-assignments${teacherId ? `?teacher_id=${teacherId}` : ''}`),
  getClassSubjectAssignments: (filters = {}) => {
    const params = new URLSearchParams();
    Object.entries(filters).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== '') params.set(key, value);
    });
    return apiRequest(`/class-subject-assignments${params.size ? `?${params}` : ''}`);
  },
  getTeacherAssignments: (filters = {}) => {
    const params = new URLSearchParams();
    Object.entries(filters).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== '') params.set(key, value);
    });
    return apiRequest(`/teacher-assignments${params.size ? `?${params}` : ''}`);
  },
  createAcademicYear: (data) =>
    apiRequest('/academic-years', { method: 'POST', body: JSON.stringify(data) }),
  updateAcademicYear: (id, data) =>
    apiRequest(`/academic-years/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  updateAcademicYearStatus: (id, is_active) =>
    apiRequest(`/academic-years/${id}/status`, { method: 'PATCH', body: JSON.stringify({ is_active }) }),
  createSemester: (data) =>
    apiRequest('/semesters', { method: 'POST', body: JSON.stringify(data) }),
  updateSemester: (id, data) =>
    apiRequest(`/semesters/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  updateSemesterStatus: (id, is_active) =>
    apiRequest(`/semesters/${id}/status`, { method: 'PATCH', body: JSON.stringify({ is_active }) }),
  createDepartment: (data) =>
    apiRequest('/departments', { method: 'POST', body: JSON.stringify(data) }),
  updateDepartment: (id, data) =>
    apiRequest(`/departments/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  updateDepartmentStatus: (id, is_active) =>
    apiRequest(`/departments/${id}/status`, { method: 'PATCH', body: JSON.stringify({ is_active }) }),
  createAcademicClass: (data) =>
    apiRequest('/academic-classes', { method: 'POST', body: JSON.stringify(data) }),
  updateAcademicClass: (id, data) =>
    apiRequest(`/academic-classes/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  updateAcademicClassStatus: (id, is_active) =>
    apiRequest(`/academic-classes/${id}/status`, { method: 'PATCH', body: JSON.stringify({ is_active }) }),
  createDivision: (data) =>
    apiRequest('/divisions', { method: 'POST', body: JSON.stringify(data) }),
  updateDivision: (id, data) =>
    apiRequest(`/divisions/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  updateDivisionStatus: (id, is_active) =>
    apiRequest(`/divisions/${id}/status`, { method: 'PATCH', body: JSON.stringify({ is_active }) }),
  createBatch: (data) =>
    apiRequest('/batches', { method: 'POST', body: JSON.stringify(data) }),
  updateBatch: (id, data) =>
    apiRequest(`/batches/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  updateBatchStatus: (id, is_active) =>
    apiRequest(`/batches/${id}/status`, { method: 'PATCH', body: JSON.stringify({ is_active }) }),
  createSubject: (data) =>
    apiRequest('/subjects', { method: 'POST', body: JSON.stringify(data) }),
  updateSubject: (id, data) =>
    apiRequest(`/subjects/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  updateSubjectStatus: (id, is_active) =>
    apiRequest(`/subjects/${id}/status`, { method: 'PATCH', body: JSON.stringify({ is_active }) }),
  createClassSubjectAssignment: (data) =>
    apiRequest('/class-subject-assignments', { method: 'POST', body: JSON.stringify(data) }),
  updateClassSubjectAssignment: (id, data) =>
    apiRequest(`/class-subject-assignments/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  createTeacherAssignment: (data) =>
    apiRequest('/teacher-assignments', { method: 'POST', body: JSON.stringify(data) }),
  updateTeacherAssignment: (id, data) =>
    apiRequest(`/teacher-assignments/${id}`, { method: 'PUT', body: JSON.stringify(data) }),

  // Curriculum, assignments, assessment, and academic support
  createCurriculumUnit: (data) =>
    apiRequest('/curriculum/units', { method: 'POST', body: JSON.stringify(data) }),
  getCurriculumUnits: (subjectId) =>
    apiRequest(`/curriculum/subjects/${subjectId}`),
  createCurriculumTopic: (unitId, data) =>
    apiRequest(`/curriculum/units/${unitId}/topics`, { method: 'POST', body: JSON.stringify(data) }),
  updateTopicProgress: (topicId, status, studentId) => {
    const params = new URLSearchParams();
    if (studentId) params.set('student_id', studentId);
    return apiRequest(`/curriculum/topics/${topicId}/progress${params.size ? `?${params}` : ''}`, {
      method: 'PUT',
      body: JSON.stringify({ status }),
    });
  },
  getSyllabusProgress: (subjectId, studentId) => {
    const params = new URLSearchParams();
    if (studentId) params.set('student_id', studentId);
    return apiRequest(`/curriculum/subjects/${subjectId}/progress${params.size ? `?${params}` : ''}`);
  },
  createAssignment: (data) =>
    apiRequest('/assignments', { method: 'POST', body: JSON.stringify(data) }),
  getAssignments: (filters = {}) => {
    const params = new URLSearchParams();
    Object.entries(filters).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== '') params.set(key, value);
    });
    return apiRequest(`/assignments${params.size ? `?${params}` : ''}`);
  },
  updateAssignment: (id, data) =>
    apiRequest(`/assignments/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  deleteAssignment: (id) => apiRequest(`/assignments/${id}`, { method: 'DELETE' }),
  submitAssignment: (id, content) =>
    apiRequest(`/assignments/${id}/submissions`, { method: 'POST', body: JSON.stringify({ content }) }),
  getSubmissions: (assignmentId) => apiRequest(`/assignments/${assignmentId}/submissions`),
  evaluateSubmission: (submissionId, score, feedback) =>
    apiRequest(`/submissions/${submissionId}/evaluate`, {
      method: 'PATCH',
      body: JSON.stringify({ score, feedback }),
    }),
  createAssessment: (data) =>
    apiRequest('/assessments', { method: 'POST', body: JSON.stringify(data) }),
  getAssessments: (subjectId) =>
    apiRequest(`/assessments${subjectId ? `?subject_id=${subjectId}` : ''}`),
  getAssessmentPerformance: (studentId, subjectId) => {
    const params = new URLSearchParams();
    if (studentId) params.set('student_id', studentId);
    if (subjectId) params.set('subject_id', subjectId);
    return apiRequest(`/assessments/performance${params.size ? `?${params}` : ''}`);
  },
  getAssessmentAverages: (subjectId, divisionId) => {
    const params = new URLSearchParams();
    if (subjectId) params.set('subject_id', subjectId);
    if (divisionId) params.set('division_id', divisionId);
    return apiRequest(`/assessments/subject-averages${params.size ? `?${params}` : ''}`);
  },
  getAssessmentResults: (assessmentId) => apiRequest(`/assessments/${assessmentId}/results`),
  recordAssessmentResult: (assessmentId, data) =>
    apiRequest(`/assessments/${assessmentId}/results`, { method: 'POST', body: JSON.stringify(data) }),
  updateAssessmentResult: (assessmentId, studentId, data) =>
    apiRequest(`/assessments/${assessmentId}/results/${studentId}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    }),
  getAcademicGaps: (studentId, subjectId) => {
    const params = new URLSearchParams();
    if (studentId) params.set('student_id', studentId);
    if (subjectId) params.set('subject_id', subjectId);
    return apiRequest(`/analytics/gaps${params.size ? `?${params}` : ''}`);
  },
  analyzeAcademicRisk: (studentId, subjectId) => {
    const params = new URLSearchParams();
    if (studentId) params.set('student_id', studentId);
    if (subjectId) params.set('subject_id', subjectId);
    return apiRequest(`/analytics/analyze${params.size ? `?${params}` : ''}`, { method: 'POST' });
  },
  getAcademicRisks: (filters = {}) => {
    const params = new URLSearchParams();
    Object.entries(filters).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== '') params.set(key, value);
    });
    return apiRequest(`/analytics/risks${params.size ? `?${params}` : ''}`);
  },
  getAcademicAlerts: (studentId) =>
    apiRequest(`/alerts${studentId ? `?student_id=${studentId}` : ''}`),
  getRecommendations: (studentId) =>
    apiRequest(`/recommendations${studentId ? `?student_id=${studentId}` : ''}`),
  getNextBestActions: (studentId, subjectId) => {
    const params = new URLSearchParams();
    if (studentId) params.set('student_id', studentId);
    if (subjectId) params.set('subject_id', subjectId);
    return apiRequest(`/recommendations/next-best-action${params.size ? `?${params}` : ''}`);
  },
  getAcademicInsights: (filters = {}) => {
    const params = new URLSearchParams();
    Object.entries(filters).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== '') params.set(key, value);
    });
    return apiRequest(`/analytics/insights${params.size ? `?${params}` : ''}`);
  },
  getNotifications: () => apiRequest('/notifications'),
  markNotificationRead: (id) =>
    apiRequest(`/notifications/${id}/read`, { method: 'PATCH' }),
  getActivities: () => apiRequest('/activities'),
  getActivityHistory: (studentId) =>
    apiRequest(`/activities/history${studentId ? `?student_id=${studentId}` : ''}`),
  getActivityStatistics: (studentId) =>
    apiRequest(`/activities/statistics${studentId ? `?student_id=${studentId}` : ''}`),
  createActivity: (data) =>
    apiRequest('/activities', { method: 'POST', body: JSON.stringify(data) }),
  recordActivityParticipation: (activityId, data) =>
    apiRequest(`/activities/${activityId}/participation`, { method: 'POST', body: JSON.stringify(data) }),
  uploadDocument: (file, subjectId, metadata = {}) => {
    const formData = new FormData();
    formData.append('file', file);
    if (subjectId) formData.append('subject_id', subjectId);
    Object.entries(metadata).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== '') formData.append(key, value);
    });
    return apiRequest('/documents', { method: 'POST', body: formData });
  },
  getDocuments: (subjectId) =>
    apiRequest(`/documents${subjectId ? `?subject_id=${subjectId}` : ''}`),
  deleteDocument: (documentId) =>
    apiRequest(`/documents/${documentId}`, { method: 'DELETE' }),
  replaceDocument: (documentId, file) => {
    const formData = new FormData();
    formData.append('file', file);
    return apiRequest(`/documents/${documentId}/replace`, {
      method: 'POST',
      body: formData,
    });
  },
  askAcademicAssistant: (question, subjectId) =>
    apiRequest('/assistant/query', {
      method: 'POST',
      body: JSON.stringify({ question, subject_id: subjectId || null }),
    }),
  getAssistantHistory: () => apiRequest('/assistant/history'),
  clearAssistantHistory: () => apiRequest('/assistant/history', { method: 'DELETE' }),

  // Timetable Management
  getTimetables: (filters = {}) => {
    const params = new URLSearchParams();
    Object.entries(filters).forEach(([key, val]) => {
      if (val !== undefined && val !== null && val !== '') {
        params.append(key, val);
      }
    });
    return apiRequest(`/timetable?${params.toString()}`);
  },
  createTimetable: (data) =>
    apiRequest('/timetable', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  updateTimetableStatus: (id, is_active) =>
    apiRequest(`/timetable/${id}/status`, {
      method: 'PATCH',
      body: JSON.stringify({ is_active }),
    }),

  // Attendance Sessions
  createSession: (payload) =>
    apiRequest('/attendance-sessions', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  getSessions: (filters = {}) => {
    const params = new URLSearchParams();
    Object.entries(filters).forEach(([key, val]) => {
      if (val !== undefined && val !== null && val !== '') {
        params.append(key, val);
      }
    });
    return apiRequest(`/attendance-sessions?${params.toString()}`);
  },

  getSessionByToken: (token) => apiRequest(`/attendance-sessions/token/${encodeURIComponent(token)}`),
  getAttendanceSession: (id) => apiRequest(`/attendance-sessions/${id}`),
  refreshSessionToken: (id) =>
    apiRequest(`/attendance-sessions/${id}/refresh-token`, { method: 'POST' }),
  getSessionMonitor: (id) => apiRequest(`/attendance-sessions/${id}/monitor`),
  closeSession: (id) => apiRequest(`/attendance-sessions/${id}/close`, { method: 'PATCH' }),
  cancelSession: (id) => apiRequest(`/attendance-sessions/${id}/cancel`, { method: 'PATCH' }),

  // Attendance Marking & Records
  studentMarkAttendance: (session_token) =>
    apiRequest('/attendance/mark', {
      method: 'POST',
      body: JSON.stringify({ session_token }),
    }),

  manualMarkAttendance: (sessionId, records) =>
    apiRequest(`/attendance/sessions/${sessionId}/manual-mark`, {
      method: 'POST',
      body: JSON.stringify({ records }),
    }),

  getSessionRecords: (sessionId) => apiRequest(`/attendance/sessions/${sessionId}/records`),

  correctAttendance: (recordId, new_status, reason) =>
    apiRequest(`/attendance/records/${recordId}/correct`, {
      method: 'PATCH',
      body: JSON.stringify({ new_status, reason }),
    }),

  getAuditLogs: () => apiRequest('/attendance/audit-logs'),
  getMyHistory: () => apiRequest('/attendance/my-history'),

  // Reports
  getMySummary: () => apiRequest('/attendance/my-summary'),
  getStudentSummary: (studentId) => apiRequest(`/attendance/students/${studentId}/summary`),
  getDefaulters: (divisionId, threshold = null, academicYearId = null) => {
    const params = new URLSearchParams();
    if (threshold !== null && threshold !== '') params.append('threshold_percentage', threshold);
    if (divisionId) params.append('division_id', divisionId);
    if (academicYearId) params.append('academic_year_id', academicYearId);
    return apiRequest(`/reports/defaulters?${params.toString()}`);
  },
};
