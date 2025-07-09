"""Constants used in the FLM scraper."""

# Text fields for parsing
TEXT_FIELDS = [
    'material(s)', 
    'lo(s)', 
    "sessions (45'/session)", 
    'assessment(s)', 
    'constructive question(s)'
]

# Columns to remove during cleanup
COLUMNS_TO_REMOVE = [
    'Syllabus Name:', 
    'Syllabus English:',
    'Subject Code:',
    'NoCredit:', 
    'Pre-Requisite:'
]

# Assessment category mapping
ASSESSMENT_CATEGORIES = {
    'Final exam': 'Final exam',
    'Thi cuối kỳFinal exam': 'Final exam',
    'Thi cuối kỳ': 'Final exam',
    'Final Exam': 'Final exam',
    'Mid-term': 'Mid-term',
    'Kiểm tra giữa kì': 'Mid-term',
    'Kiểm tra giữa kỳ': 'Mid-term',
    'Bài tập (Assignment)': 'Assignment',
    'Bài \x1dtập (Assignment)': 'Assignment',
    'Assignment': 'Assignment',
    'Assignments': 'Assignment',
    'Assignments/Exercises': 'Assignment',
    'Group Assignm ent 1 (Checkp oint 1)': 'Group Assignment 1 (Checkpoint 1)',
    'Group Assignm ent 2 (Checkp oint 2)': 'Group Assignment 2 (Checkpoint 2)',
    'Group Assignm ent 3 (Checkp oint 3)': 'Group Assignment 3 (Checkpoint 3)',
    'Progress Test': 'Progress test',
    'Progress test': 'Progress test',
    'Progress Tests': 'Progress test',
    'Tham gia trên lớpParticipation': 'Participation',
    'Participation': 'Participation',
    'Tham gia giờ học tại giảng đường': 'Participation',
    'Quiz': 'Quiz',
    'Group presentation': 'Group presentation',
    'Group Project': 'Group project',
    'Practical Exam': 'Practical Exam',
    'PE': 'PE',
    'TE': 'TE',
    'Activity': 'Activity',
    'Project': 'Project'
}

# Text columns to drop after processing
TEXT_COLUMNS_TO_DROP = [
    'material(s)_text',
    'lo(s)_text',
    "sessions (45'/session)_text",
    'assessment(s)_text',
    'constructive question(s)_text',
    'assessment(s)_text_processed',
    'material(s)_text_processed',
    'lo(s)_text_processed',
    "sessions (45'/session)_text_processed",
    'constructive question(s)_text_processed'
] 