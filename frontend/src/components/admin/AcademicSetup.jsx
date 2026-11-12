import React, { useCallback, useEffect, useState } from 'react';
import { api } from '../../api';

const setupTypes = [
  { id: 'academicYear', label: 'Academic year' },
  { id: 'semester', label: 'Semester' },
  { id: 'department', label: 'Department' },
  { id: 'academicClass', label: 'Class' },
  { id: 'division', label: 'Division' },
  { id: 'batch', label: 'Batch' },
  { id: 'subject', label: 'Subject' },
  { id: 'classSubjectAssignment', label: 'Class-subject mapping' },
  { id: 'teacherAssignment', label: 'Teacher assignment' },
  { id: 'timetable', label: 'Timetable entry' },
];

const dayOptions = ['MONDAY', 'TUESDAY', 'WEDNESDAY', 'THURSDAY', 'FRIDAY', 'SATURDAY', 'SUNDAY']
  .map((day) => ({ id: day, name: day }));

export default function AcademicSetup({ onDataChanged }) {
  const [setupType, setSetupType] = useState('academicYear');
  const [form, setForm] = useState({});
  const [data, setData] = useState({
    years: [],
    semesters: [],
    departments: [],
    classes: [],
    divisions: [],
    batches: [],
    subjects: [],
    teachers: [],
  });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  const selectedDivision = data.divisions.find((item) => item.id === Number(form.division_id));
  const selectedClass = data.classes.find((item) => (
    item.id === Number(form.academic_class_id || selectedDivision?.academic_class_id)
  ));
  const subjectDepartmentId = form.department_id || selectedClass?.department_id;

  const loadData = useCallback(async () => {
    setError('');
    try {
      const [years, semesters, departments, classes, divisions, batches, subjects, teachers] = await Promise.all([
        api.getAcademicYears(),
        api.getSemesters(),
        api.getDepartments(),
        api.getAcademicClasses(),
        api.getDivisions(),
        api.getBatches(),
        api.getSubjects(),
        api.getTeachers(),
      ]);
      setData({ years, semesters, departments, classes, divisions, batches, subjects, teachers });
    } catch (loadError) {
      setError(loadError.message || 'Unable to load setup data.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const selectOptions = {
    academic_year_id: data.years,
    semester_id: data.semesters.filter((item) => (
      !form.academic_year_id || item.academic_year_id === Number(form.academic_year_id)
    )),
    department_id: data.departments,
    academic_class_id: data.classes.filter((item) => (
      !form.department_id || item.department_id === Number(form.department_id)
    )),
    division_id: data.divisions.filter((item) => (
      (!form.academic_class_id || item.academic_class_id === Number(form.academic_class_id))
      && (!form.academic_year_id || item.academic_year_id === Number(form.academic_year_id))
      && (!form.semester_id || item.semester_id === Number(form.semester_id))
    )),
    batch_id: data.batches.filter((item) => (
      form.division_id && item.division_id === Number(form.division_id)
    )),
    subject_id: data.subjects.filter((item) => (
      (!subjectDepartmentId || item.department_id === Number(subjectDepartmentId))
      && (!form.semester_id || item.semester_id === Number(form.semester_id))
    )),
    teacher_id: data.teachers,
    day_of_week: dayOptions,
  };

  const fields = {
    academicYear: [
      { name: 'name', label: 'Academic year name', placeholder: '2026-2027' },
      { name: 'start_date', label: 'Start date', type: 'date' },
      { name: 'end_date', label: 'End date', type: 'date' },
    ],
    semester: [
      { name: 'academic_year_id', label: 'Academic year', type: 'select', required: true },
      { name: 'semester_number', label: 'Semester number', type: 'number', required: true, min: 1 },
      { name: 'name', label: 'Semester name', placeholder: 'Semester 1' },
      { name: 'start_date', label: 'Start date', type: 'date', optional: true },
      { name: 'end_date', label: 'End date', type: 'date', optional: true },
    ],
    department: [
      { name: 'name', label: 'Department name' },
      { name: 'code', label: 'Department code', placeholder: 'CSE' },
    ],
    academicClass: [
      { name: 'department_id', label: 'Department', type: 'select', required: true },
      { name: 'name', label: 'Class name', placeholder: 'First Year' },
      { name: 'code', label: 'Class code', placeholder: 'FY' },
    ],
    division: [
      { name: 'academic_year_id', label: 'Academic year', type: 'select', required: true },
      { name: 'semester_id', label: 'Semester', type: 'select', required: true },
      { name: 'academic_class_id', label: 'Class', type: 'select', required: true },
      { name: 'name', label: 'Division name', placeholder: 'A' },
    ],
    batch: [
      { name: 'division_id', label: 'Division', type: 'select', required: true },
      { name: 'name', label: 'Batch name', placeholder: 'Batch 1' },
    ],
    subject: [
      { name: 'department_id', label: 'Department', type: 'select', required: true },
      { name: 'semester_id', label: 'Semester', type: 'select', required: true },
      { name: 'name', label: 'Subject name' },
      { name: 'code', label: 'Subject code', placeholder: 'CS101' },
    ],
    classSubjectAssignment: [
      { name: 'academic_year_id', label: 'Academic year', type: 'select', required: true },
      { name: 'semester_id', label: 'Semester', type: 'select', required: true },
      { name: 'academic_class_id', label: 'Class', type: 'select', required: true },
      { name: 'division_id', label: 'Division (optional)', type: 'select', optional: true },
      { name: 'subject_id', label: 'Subject', type: 'select', required: true },
    ],
    teacherAssignment: [
      { name: 'teacher_id', label: 'Teacher account', type: 'select', required: true },
      { name: 'academic_year_id', label: 'Academic year', type: 'select', required: true },
      { name: 'semester_id', label: 'Semester', type: 'select', required: true },
      { name: 'academic_class_id', label: 'Class', type: 'select', required: true },
      { name: 'division_id', label: 'Division (optional)', type: 'select', optional: true },
      { name: 'batch_id', label: 'Batch (optional)', type: 'select', optional: true },
      { name: 'subject_id', label: 'Subject', type: 'select', required: true },
    ],
    timetable: [
      { name: 'academic_year_id', label: 'Academic year', type: 'select', required: true },
      { name: 'semester_id', label: 'Semester', type: 'select', required: true },
      { name: 'division_id', label: 'Division', type: 'select', required: true },
      { name: 'batch_id', label: 'Batch (optional)', type: 'select', optional: true },
      { name: 'subject_id', label: 'Subject', type: 'select', required: true },
      { name: 'teacher_id', label: 'Teacher account', type: 'select', required: true },
      { name: 'day_of_week', label: 'Day', type: 'select', required: true },
      { name: 'start_time', label: 'Start time', type: 'time' },
      { name: 'end_time', label: 'End time', type: 'time' },
      { name: 'room', label: 'Room (optional)', optional: true },
    ],
  }[setupType];

  const createMethods = {
    academicYear: api.createAcademicYear,
    semester: api.createSemester,
    department: api.createDepartment,
    academicClass: api.createAcademicClass,
    division: api.createDivision,
    batch: api.createBatch,
    subject: api.createSubject,
    classSubjectAssignment: api.createClassSubjectAssignment,
    teacherAssignment: api.createTeacherAssignment,
    timetable: api.createTimetable,
  };

  const handleTypeChange = (nextType) => {
    setSetupType(nextType);
    setForm({});
    setError('');
    setSuccess('');
  };

  const handleFieldChange = (name, value) => {
    setForm((current) => {
      const next = { ...current, [name]: value };
      if (name === 'academic_year_id') {
        next.semester_id = '';
        next.division_id = '';
        next.batch_id = '';
        next.subject_id = '';
      } else if (name === 'semester_id') {
        next.division_id = '';
        next.batch_id = '';
        next.subject_id = '';
      } else if (name === 'academic_class_id') {
        next.division_id = '';
        next.batch_id = '';
      } else if (name === 'department_id') {
        next.academic_class_id = '';
        next.subject_id = '';
      } else if (name === 'division_id') {
        next.batch_id = '';
      }
      return next;
    });
    setError('');
    setSuccess('');
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    if (setupType === 'teacherAssignment' && form.batch_id && !form.division_id) {
      setError('Select the division before assigning a specific batch.');
      return;
    }
    setSaving(true);
    setError('');
    setSuccess('');
    const payload = {};
    fields.forEach((field) => {
      const value = form[field.name];
      if (value === undefined || value === '') return;
      if (field.type === 'number' || field.type === 'select') {
        payload[field.name] = field.type === 'number' ? Number(value) : (
          ['academic_year_id', 'semester_id', 'department_id', 'academic_class_id', 'division_id', 'batch_id', 'subject_id', 'teacher_id']
            .includes(field.name) ? Number(value) : value
        );
      } else if (field.type === 'time') {
        payload[field.name] = value.length === 5 ? `${value}:00` : value;
      } else {
        payload[field.name] = value;
      }
    });

    try {
      await createMethods[setupType](payload);
      setSuccess(`${setupTypes.find((item) => item.id === setupType)?.label} added successfully.`);
      setForm({});
      await loadData();
      onDataChanged();
    } catch (saveError) {
      setError(saveError.message || 'Unable to save this record.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <section className="glass-card" style={{ padding: '1.5rem' }}>
      <div style={{ marginBottom: '1rem' }}>
        <h2 style={{ fontSize: '1.15rem', fontWeight: 800, marginBottom: '0.35rem' }}>Add your academic data</h2>
        <p style={{ color: 'var(--text-secondary)', fontSize: '0.86rem', margin: 0 }}>
          Set up in order: academic year and semester, department and class, division and batch, subjects, then teacher assignments or timetable.
          Create teacher/student accounts under User Management.
        </p>
      </div>

      {error && <div className="workspace-error" role="alert">{error}</div>}
      {success && <div className="workspace-state" role="status">{success}</div>}

      <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1rem', marginTop: '1rem' }}>
        <label style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem', color: 'var(--text-secondary)', fontSize: '0.85rem' }}>
          What do you want to add?
          <select className="glass-input" value={setupType} onChange={(event) => handleTypeChange(event.target.value)}>
            {setupTypes.map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}
          </select>
        </label>

        {loading ? (
          <div className="workspace-state" role="status">Loading academic setup options…</div>
        ) : (
          <>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(210px, 1fr))', gap: '0.85rem' }}>
              {fields.map((field) => {
                const options = selectOptions[field.name] || [];
                const isSelect = field.type === 'select';
                return (
                  <label key={field.name} style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem', color: 'var(--text-secondary)', fontSize: '0.85rem' }}>
                    {field.label}
                    {isSelect ? (
                      <select
                        className="glass-input"
                        required={!field.optional}
                        value={form[field.name] || ''}
                        onChange={(event) => handleFieldChange(field.name, event.target.value)}
                      >
                        <option value="">{field.optional ? 'None' : `Select ${field.label.toLowerCase()}`}</option>
                        {options.map((option) => (
                          <option key={option.id} value={option.id}>
                            {option.name || option.full_name || option.code || option.employee_id}
                            {option.code && option.name ? ` (${option.code})` : ''}
                          </option>
                        ))}
                      </select>
                    ) : (
                      <input
                        className="glass-input"
                        type={field.type || 'text'}
                        required={!field.optional}
                        min={field.min}
                        placeholder={field.placeholder}
                        value={form[field.name] || ''}
                        onChange={(event) => handleFieldChange(field.name, event.target.value)}
                      />
                    )}
                  </label>
                );
              })}
            </div>
            <div>
              <button type="submit" className="btn-primary" disabled={saving || loading}>
                {saving ? 'Saving…' : `Add ${setupTypes.find((item) => item.id === setupType)?.label}`}
              </button>
            </div>
          </>
        )}
      </form>
    </section>
  );
}
