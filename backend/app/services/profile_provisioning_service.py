import secrets
from datetime import date, datetime, timedelta, timezone
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import select, func

from app.models.user import User
from app.models.enums import UserRole
from app.models.academic import Department, AcademicYear, Semester, AcademicClass, Division, Batch
from app.models.subject import Subject
from app.models.assignments import ClassSubjectAssignment, TeacherAssignment
from app.models.profiles import Student, Teacher


def init_default_academic_structure(db: Session) -> None:
    """
    Idempotently ensures default Department, AcademicYear, Semester,
    AcademicClass, Division, Batch, Subjects, and ClassSubjectAssignments exist.
    """
    try:
        # 1. Department
        dept = db.query(Department).filter(Department.code == "COMP").first()
        if not dept:
            dept = db.query(Department).first()
        if not dept:
            dept = Department(name="Computer Engineering", code="COMP", is_active=True)
            db.add(dept)
            db.flush()

        # 2. Academic Year
        ay = db.query(AcademicYear).filter(AcademicYear.name == "2025-2026").first()
        if not ay:
            ay = db.query(AcademicYear).first()
        if not ay:
            ay = AcademicYear(
                name="2025-2026",
                start_date=date(2025, 7, 1),
                end_date=date(2026, 6, 30),
                is_active=True,
            )
            db.add(ay)
            db.flush()

        # 3. Semester
        sem = db.query(Semester).filter(Semester.academic_year_id == ay.id, Semester.semester_number == 5).first()
        if not sem:
            sem = db.query(Semester).filter(Semester.academic_year_id == ay.id).first()
        if not sem:
            sem = Semester(
                academic_year_id=ay.id,
                semester_number=5,
                name="Semester V",
                start_date=date(2025, 7, 1),
                end_date=date(2025, 12, 31),
                is_active=True,
            )
            db.add(sem)
            db.flush()

        # 4. Academic Class
        ac_class = db.query(AcademicClass).filter(AcademicClass.department_id == dept.id, AcademicClass.code == "TY").first()
        if not ac_class:
            ac_class = db.query(AcademicClass).filter(AcademicClass.department_id == dept.id).first()
        if not ac_class:
            ac_class = AcademicClass(
                department_id=dept.id,
                name="Third Year",
                code="TY",
                is_active=True,
            )
            db.add(ac_class)
            db.flush()

        # 5. Division
        div = db.query(Division).filter(
            Division.academic_class_id == ac_class.id,
            Division.academic_year_id == ay.id,
            Division.semester_id == sem.id,
            Division.name == "Division A"
        ).first()
        if not div:
            div = db.query(Division).filter(
                Division.academic_class_id == ac_class.id,
                Division.academic_year_id == ay.id,
                Division.semester_id == sem.id,
            ).first()
        if not div:
            div = Division(
                academic_class_id=ac_class.id,
                academic_year_id=ay.id,
                semester_id=sem.id,
                name="Division A",
                is_active=True,
            )
            db.add(div)
            db.flush()

        # 6. Batches
        batch_a1 = db.query(Batch).filter(Batch.division_id == div.id, Batch.name == "Batch A1").first()
        if not batch_a1:
            batch_a1 = Batch(division_id=div.id, name="Batch A1", is_active=True)
            db.add(batch_a1)
            db.flush()

        batch_a2 = db.query(Batch).filter(Batch.division_id == div.id, Batch.name == "Batch A2").first()
        if not batch_a2:
            batch_a2 = Batch(division_id=div.id, name="Batch A2", is_active=True)
            db.add(batch_a2)
            db.flush()

        # 7. Subjects
        subjects_data = [
            ("Operating Systems", "CS501"),
            ("Software Engineering", "CS502"),
            ("Database Management Systems", "CS503"),
            ("Computer Networks", "CS504"),
            ("Web Development", "CS505"),
            ("Artificial Intelligence", "CS506"),
        ]

        for sub_name, sub_code in subjects_data:
            sub = db.query(Subject).filter(Subject.code == sub_code).first()
            if not sub:
                sub = Subject(
                    name=sub_name,
                    code=sub_code,
                    department_id=dept.id,
                    semester_id=sem.id,
                    is_active=True,
                )
                db.add(sub)
                db.flush()

            # ClassSubjectAssignment
            csa = db.query(ClassSubjectAssignment).filter(
                ClassSubjectAssignment.academic_class_id == ac_class.id,
                ClassSubjectAssignment.subject_id == sub.id,
                ClassSubjectAssignment.academic_year_id == ay.id,
                ClassSubjectAssignment.semester_id == sem.id,
            ).first()
            if not csa:
                csa = ClassSubjectAssignment(
                    academic_class_id=ac_class.id,
                    subject_id=sub.id,
                    academic_year_id=ay.id,
                    semester_id=sem.id,
                    division_id=div.id,
                    is_active=True,
                )
                db.add(csa)
                db.flush()

        db.commit()
    except Exception as e:
        db.rollback()
        print(f"[Academic Structure Setup Warning] {e}")


def ensure_user_profile(db: Session, user: User) -> User:
    """
    Ensures that Student or Teacher users have their respective profile
    fully created and linked to the active academic structure and subjects.
    Safe and idempotent.
    """
    if not user or user.role == UserRole.ADMIN:
        return user

    try:
        # Guarantee baseline academic entities exist
        dept = db.query(Department).filter(Department.is_active == True).first()
        ay = db.query(AcademicYear).filter(AcademicYear.is_active == True).first()
        sem = db.query(Semester).filter(Semester.academic_year_id == ay.id, Semester.is_active == True).first() if ay else None
        ac_class = db.query(AcademicClass).filter(AcademicClass.department_id == dept.id, AcademicClass.is_active == True).first() if dept else None
        div = db.query(Division).filter(Division.academic_class_id == ac_class.id, Division.is_active == True).first() if ac_class else None
        batch = db.query(Batch).filter(Batch.division_id == div.id, Batch.is_active == True).first() if div else None

        if not (dept and ay and sem and ac_class and div and batch):
            init_default_academic_structure(db)
            dept = db.query(Department).filter(Department.is_active == True).first()
            ay = db.query(AcademicYear).filter(AcademicYear.is_active == True).first()
            sem = db.query(Semester).filter(Semester.academic_year_id == ay.id, Semester.is_active == True).first() if ay else None
            ac_class = db.query(AcademicClass).filter(AcademicClass.department_id == dept.id, AcademicClass.is_active == True).first() if dept else None
            div = db.query(Division).filter(Division.academic_class_id == ac_class.id, Division.is_active == True).first() if ac_class else None
            batch = db.query(Batch).filter(Batch.division_id == div.id, Batch.is_active == True).first() if div else None

        # --- STUDENT PROVISIONING ---
        if user.role == UserRole.STUDENT:
            student = user.student_profile
            if student is None:
                # 1. Try to link an existing unlinked student record with same email or enrollment
                existing_st = None
                if user.email:
                    existing_st = db.query(Student).filter(Student.email == user.email, Student.user_id.is_(None)).first()
                if not existing_st and user.enrollment_number:
                    existing_st = db.query(Student).filter(Student.enrollment_number == user.enrollment_number, Student.user_id.is_(None)).first()

                if existing_st:
                    existing_st.user_id = user.id
                    if user.full_name and not existing_st.full_name:
                        existing_st.full_name = user.full_name
                    db.commit()
                    db.refresh(user)
                    return user

                # 2. Auto-generate profile
                enrollment_no = user.enrollment_number or f"SVVV{user.id:04d}"
                # Check uniqueness of enrollment_number
                dup_en = db.query(Student.id).filter(Student.enrollment_number == enrollment_no).first()
                if dup_en:
                    enrollment_no = f"SVVV{user.id:04d}{int(datetime.now().timestamp()) % 1000}"

                student_code = f"STU-{user.id:04d}"
                dup_code = db.query(Student.id).filter(Student.student_id == student_code).first()
                if dup_code:
                    student_code = f"STU-{user.id:04d}-{int(datetime.now().timestamp()) % 1000}"

                roll_no = f"RN-{user.id:03d}"
                dup_roll = db.query(Student.id).filter(
                    Student.division_id == div.id,
                    Student.academic_year_id == ay.id,
                    Student.semester_id == sem.id,
                    Student.roll_number == roll_no,
                ).first()
                if dup_roll:
                    roll_no = f"RN-{user.id:03d}-{int(datetime.now().timestamp()) % 1000}"

                student = Student(
                    user_id=user.id,
                    student_id=student_code,
                    roll_number=roll_no,
                    enrollment_number=enrollment_no,
                    full_name=user.full_name or user.username,
                    email=user.email,
                    department_id=dept.id,
                    academic_class_id=ac_class.id,
                    division_id=div.id,
                    batch_id=batch.id if batch else None,
                    academic_year_id=ay.id,
                    semester_id=sem.id,
                    is_active=True,
                )
                db.add(student)
                if not user.enrollment_number:
                    user.enrollment_number = enrollment_no
                db.commit()
                db.refresh(user)

        # --- TEACHER PROVISIONING ---
        elif user.role == UserRole.TEACHER:
            teacher = user.teacher_profile
            if teacher is None:
                # 1. Try to link an existing unlinked teacher record
                existing_tc = None
                if user.email:
                    existing_tc = db.query(Teacher).filter(Teacher.email == user.email, Teacher.user_id.is_(None)).first()

                if existing_tc:
                    existing_tc.user_id = user.id
                    if user.full_name and not existing_tc.full_name:
                        existing_tc.full_name = user.full_name
                    db.commit()
                    db.refresh(user)
                    teacher = user.teacher_profile
                else:
                    emp_code = f"EMP-{dept.code if dept else 'CSE'}-{user.id:03d}"
                    dup_emp = db.query(Teacher.id).filter(Teacher.employee_id == emp_code).first()
                    if dup_emp:
                        emp_code = f"EMP-{user.id:03d}-{int(datetime.now().timestamp()) % 1000}"

                    teacher = Teacher(
                        user_id=user.id,
                        employee_id=emp_code,
                        full_name=user.full_name or f"Prof. {user.username}",
                        email=user.email,
                        department_id=dept.id,
                        is_active=True,
                    )
                    db.add(teacher)
                    db.commit()
                    db.refresh(user)

            # Ensure this teacher has TeacherAssignment entries for all active subjects
            if user.teacher_profile and ac_class and ay and sem:
                t_prof = user.teacher_profile
                subjects = db.query(Subject).filter(Subject.is_active == True).all()
                for sub in subjects:
                    ta = db.query(TeacherAssignment).filter(
                        TeacherAssignment.teacher_id == t_prof.id,
                        TeacherAssignment.subject_id == sub.id,
                        TeacherAssignment.academic_class_id == ac_class.id,
                        TeacherAssignment.academic_year_id == ay.id,
                        TeacherAssignment.semester_id == sem.id,
                    ).first()
                    if not ta:
                        ta = TeacherAssignment(
                            teacher_id=t_prof.id,
                            subject_id=sub.id,
                            academic_class_id=ac_class.id,
                            academic_year_id=ay.id,
                            semester_id=sem.id,
                            division_id=div.id if div else None,
                            is_active=True,
                        )
                        db.add(ta)
                db.commit()
                db.refresh(user)

    except Exception as e:
        db.rollback()
        print(f"[Profile Auto-Provision Warning for user {user.id} ({user.username})]: {e}")

    return user


def heal_all_existing_users(db: Session) -> None:
    """
    Scans all users in the database and ensures every student and teacher has
    a valid linked profile and assignments.
    """
    try:
        users = db.query(User).all()
        for u in users:
            ensure_user_profile(db, u)
    except Exception as e:
        print(f"[Heal All Existing Users Warning]: {e}")

