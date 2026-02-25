-- ============================================================================
-- Healthcare Practice Demo Seed Data
-- ============================================================================
-- Persona: Dr. Sarah Mitchell, owner of Greenfield Family Practice
-- A family medicine physician using Software of You to manage her practice,
-- patients, staff, referral network, and professional decisions.
-- ============================================================================

-- ============================================================================
-- USER PROFILE
-- ============================================================================
INSERT INTO user_profile (category, key, value, source, updated_at) VALUES
  ('identity', 'name', 'Sarah', 'explicit', datetime('now', '-45 days')),
  ('identity', 'role', 'Solopreneur', 'explicit', datetime('now', '-45 days')),
  ('preferences', 'focus', 'Client relationships, Projects & deliverables, Business communications', 'explicit', datetime('now', '-45 days')),
  ('preferences', 'communication_style', 'Brief and direct', 'explicit', datetime('now', '-45 days'));

INSERT OR REPLACE INTO soy_meta (key, value, updated_at) VALUES
  ('profile_setup_completed', '1', datetime('now', '-45 days'));

-- Prevent auto-sync from attempting Gmail/Calendar API calls in demo mode
INSERT OR REPLACE INTO soy_meta (key, value, updated_at) VALUES
  ('gmail_last_synced', datetime('now'), datetime('now')),
  ('calendar_last_synced', datetime('now'), datetime('now')),
  ('transcripts_last_scanned', datetime('now'), datetime('now'));

-- ============================================================================
-- TAGS
-- ============================================================================
INSERT INTO tags (name, color, category) VALUES
  ('patient', '#10b981', 'type'),
  ('staff', '#6366f1', 'type'),
  ('specialist', '#f59e0b', 'type'),
  ('vendor', '#8b5cf6', 'type'),
  ('insurance', '#ec4899', 'type'),
  ('high-risk', '#ef4444', 'clinical'),
  ('diabetes', '#f97316', 'clinical'),
  ('cardiac', '#dc2626', 'clinical'),
  ('wellness-overdue', '#eab308', 'status'),
  ('follow-up-needed', '#3b82f6', 'status'),
  ('new-patient', '#14b8a6', 'status'),
  ('chronic-care', '#7c3aed', 'clinical');

-- ============================================================================
-- CONTACTS — Patients (20)
-- ============================================================================
INSERT INTO contacts (id, name, email, phone, company, role, type, status, notes, created_at, updated_at) VALUES
  (1, 'Margaret Chen', 'margaret.chen@gmail.com', '555-0101', NULL, 'Retired Teacher', 'individual', 'active', 'Age 67. Hypertension, Type 2 diabetes. On metformin and lisinopril. Very engaged in her care, always asks good questions.', datetime('now', '-90 days'), datetime('now', '-2 days')),
  (2, 'James Rivera', 'jrivera_45@outlook.com', '555-0102', 'Rivera Construction', 'Foreman', 'individual', 'active', 'Age 45. Chronic lower back pain, BMI 31. Referred to PT. Resistant to lifestyle changes but making progress.', datetime('now', '-85 days'), datetime('now', '-5 days')),
  (3, 'David Okafor', 'david.okafor@gmail.com', '555-0103', 'Okafor & Associates CPAs', 'Managing Partner', 'individual', 'active', 'Age 52. Elevated cholesterol, otherwise healthy. Annual wellness done Jan. Very punctual, no-nonsense.', datetime('now', '-80 days'), datetime('now', '-12 days')),
  (4, 'Linda Patel', 'linda.patel@brightideas.co', '555-0104', 'BrightIdeas Marketing', 'Director', 'individual', 'active', 'Age 38. Generalized anxiety, sleep disturbance. Started sertraline 3 months ago — responding well. High stress job.', datetime('now', '-78 days'), datetime('now', '-3 days')),
  (5, 'Michael Torres', 'chef.torres@gmail.com', '555-0105', 'Harvest Kitchen', 'Head Chef', 'individual', 'active', 'Age 33. Rotator cuff strain from kitchen work. Cleared to return to full duty. Interested in nutrition counseling.', datetime('now', '-75 days'), datetime('now', '-18 days')),
  (6, 'Barbara Anderson', 'b.anderson@remax.com', '555-0106', 'RE/MAX', 'Realtor', 'individual', 'active', 'Age 62. Osteoporosis (T-score -2.7), knee OA. On alendronate. Active lifestyle despite joint issues. DEXA due in 6 months.', datetime('now', '-72 days'), datetime('now', '-7 days')),
  (7, 'Thomas Nguyen', 'tng.dev@gmail.com', '555-0107', 'Cascade Software', 'Senior Developer', 'individual', 'active', 'Age 44. Chronic migraines (8-10/month). Tried sumatriptan — partial relief. Considering preventive. Ergonomic setup discussed.', datetime('now', '-70 days'), datetime('now', '-1 days')),
  (8, 'Patricia Murphy', 'pat.murphy.rn@gmail.com', '555-0108', NULL, 'Retired RN', 'individual', 'active', 'Age 58. Former ER nurse, retired early. Very health-literate. Due for colonoscopy screening. Strong advocate for preventive care.', datetime('now', '-68 days'), datetime('now', '-20 days')),
  (9, 'Carlos Gutierrez', 'carlos.g@fitlife.com', '555-0109', 'FitLife Training', 'Personal Trainer', 'individual', 'active', 'Age 29. ACL reconstruction 4 months ago. PT going well, ahead of schedule. Eager to return to training clients.', datetime('now', '-65 days'), datetime('now', '-10 days')),
  (10, 'Helen Brooks', 'helen.brooks@yahoo.com', '555-0110', NULL, 'Retired Librarian', 'individual', 'active', 'Age 73. Mild cognitive concerns — MMSE 26/30. Daughter involved in care. Started brain health protocol. Follow-up in 3 months.', datetime('now', '-62 days'), datetime('now', '-4 days')),
  (11, 'Jason Williams', 'jwilliams@lincolnsd.edu', '555-0111', 'Lincoln School District', 'History Teacher', 'individual', 'active', 'Age 41. Seasonal allergies, mild persistent asthma. On fluticasone/salmeterol. Well controlled. Annual spirometry due.', datetime('now', '-60 days'), datetime('now', '-15 days')),
  (12, 'Maria Santos', 'maria.santos.home@gmail.com', '555-0112', NULL, 'Stay-at-Home Parent', 'individual', 'active', 'Age 36. 6-month postpartum. Screening negative for PPD. Cleared for exercise. Wants to discuss family planning next visit.', datetime('now', '-55 days'), datetime('now', '-8 days')),
  (13, 'Frank DeLuca', 'frank@delucabuilders.com', '555-0113', 'DeLuca Builders', 'Owner', 'individual', 'active', 'Age 65. Pre-diabetic (A1c 6.2). Started lifestyle modification program. Down 8 lbs in 2 months. Very motivated since his brother''s diagnosis.', datetime('now', '-50 days'), datetime('now', '-3 days')),
  (14, 'Dorothy Hawkins', NULL, '555-0114', NULL, 'Retired', 'individual', 'active', 'Age 80. Polypharmacy — 9 medications. Fall risk assessment done. Home safety checklist reviewed with daughter. Medication reconciliation needed.', datetime('now', '-48 days'), datetime('now', '-2 days')),
  (15, 'Ryan O''Brien', 'ryan.obrien@university.edu', '555-0115', 'State University', 'Graduate Student', 'individual', 'active', 'Age 27. ADHD — on methylphenidate 20mg. Good response, GPA improved. Anxiety during exam periods. Wants to discuss non-stimulant options.', datetime('now', '-45 days'), datetime('now', '-6 days')),
  (16, 'Stephanie Lee', 's.lee@hartfordlaw.com', '555-0116', 'Hartford & Lee LLP', 'Senior Partner', 'individual', 'active', 'Age 49. Stage 1 hypertension. Started amlodipine after lifestyle measures insufficient. Very busy — missed last two follow-ups.', datetime('now', '-42 days'), datetime('now', '-14 days')),
  (17, 'Ahmed Hassan', 'ahmed@spiceroute.com', '555-0117', 'The Spice Route', 'Owner', 'individual', 'active', 'Age 56. Type 2 diabetes, diabetic neuropathy in feet. A1c trending down (7.8 → 7.1). Podiatry referral active. Restaurant hours make scheduling hard.', datetime('now', '-40 days'), datetime('now', '-1 days')),
  (18, 'Nancy Palmer', 'nancy.palmer@outlook.com', '555-0118', NULL, 'Retired HR Director', 'individual', 'active', 'Age 61. Perimenopause management. Hot flashes, sleep disruption. Discussing HRT options. Bone density scan scheduled.', datetime('now', '-38 days'), datetime('now', '-9 days')),
  (19, 'Robert Kim', 'rkim.retired@gmail.com', '555-0119', NULL, 'Retired Engineer', 'individual', 'active', 'Age 71. COPD (moderate, GOLD stage 2). On tiotropium + albuterol PRN. Pulmonary rehab completed. Former smoker, quit 5 years ago.', datetime('now', '-35 days'), datetime('now', '-5 days')),
  (20, 'Susan Washington', 'swashington@lincolnsd.edu', '555-0120', 'Lincoln School District', 'Principal', 'individual', 'active', 'Age 55. Hypothyroidism, well-controlled on levothyroxine. Due for annual wellness and TSH check. Also manages significant work stress.', datetime('now', '-30 days'), datetime('now', '-11 days'));

-- ============================================================================
-- CONTACTS — Staff (3)
-- ============================================================================
INSERT INTO contacts (id, name, email, phone, company, role, type, status, notes, created_at, updated_at) VALUES
  (21, 'Lisa Brennan', 'lisa@greenfieldpractice.com', '555-0201', 'Greenfield Family Practice', 'Office Manager', 'individual', 'active', 'Been with the practice 6 years. Handles scheduling, patient flow, front desk ops. Extremely organized. Working on billing workflow project.', datetime('now', '-90 days'), datetime('now', '-1 days')),
  (22, 'Emily Sato', 'emily@greenfieldpractice.com', '555-0202', 'Greenfield Family Practice', 'Medical Assistant', 'individual', 'active', 'MA certified, 2 years with us. Great with patients, especially elderly. Taking phlebotomy certification course. Reliable and proactive.', datetime('now', '-90 days'), datetime('now', '-3 days')),
  (23, 'Mark Davidson', 'mark@greenfieldpractice.com', '555-0203', 'Greenfield Family Practice', 'Billing Coordinator', 'individual', 'active', 'Handles insurance claims, prior authorizations, and patient billing. Flagged issues with Meridian claim denials that we need to address.', datetime('now', '-90 days'), datetime('now', '-2 days'));

-- ============================================================================
-- CONTACTS — Specialists & External (5)
-- ============================================================================
INSERT INTO contacts (id, name, email, phone, company, role, type, status, notes, created_at, updated_at) VALUES
  (24, 'Dr. Kevin Zhao', 'kzhao@metroheart.com', '555-0301', 'Metro Heart Associates', 'Cardiologist', 'individual', 'active', 'Primary cardiology referral. Very responsive, great communication. Referred Margaret Chen and Robert Kim to him.', datetime('now', '-88 days'), datetime('now', '-7 days')),
  (25, 'Dr. Rachel Torres', 'rtorres@eastsidediabetes.com', '555-0302', 'Eastside Diabetes Center', 'Endocrinologist', 'individual', 'active', 'Endocrine referrals. Co-managing Ahmed Hassan and Margaret Chen. Good about sending notes back promptly.', datetime('now', '-85 days'), datetime('now', '-10 days')),
  (26, 'Tom Bradley', 'tbradley@meridianhealth.com', '555-0401', 'Meridian Health Insurance', 'Provider Relations Rep', 'individual', 'active', 'Our main contact at Meridian. Working through the claim denial issue. Responsive but limited in what he can escalate.', datetime('now', '-60 days'), datetime('now', '-4 days')),
  (27, 'Jennifer Walsh', 'jwalsh@medsupply.com', '555-0402', 'MedSupply Direct', 'Account Manager', 'individual', 'active', 'Handles our medical supply orders. Negotiated a 12% discount on glucose monitors for the diabetic care program.', datetime('now', '-50 days'), datetime('now', '-20 days')),
  (28, 'Alex Cooper', 'acooper@practicepulse.com', '555-0403', 'PracticePulse Software', 'Customer Success Manager', 'individual', 'active', 'Our EHR platform contact. Helping with patient portal rollout. Has been responsive about the portal integration issues.', datetime('now', '-45 days'), datetime('now', '-6 days'));

-- ============================================================================
-- ENTITY TAGS
-- ============================================================================
-- Tag IDs: 1=patient, 2=staff, 3=specialist, 4=vendor, 5=insurance,
--          6=high-risk, 7=diabetes, 8=cardiac, 9=wellness-overdue,
--          10=follow-up-needed, 11=new-patient, 12=chronic-care

-- Patients
INSERT INTO entity_tags (entity_type, entity_id, tag_id) VALUES
  ('contact', 1, 1), ('contact', 2, 1), ('contact', 3, 1), ('contact', 4, 1),
  ('contact', 5, 1), ('contact', 6, 1), ('contact', 7, 1), ('contact', 8, 1),
  ('contact', 9, 1), ('contact', 10, 1), ('contact', 11, 1), ('contact', 12, 1),
  ('contact', 13, 1), ('contact', 14, 1), ('contact', 15, 1), ('contact', 16, 1),
  ('contact', 17, 1), ('contact', 18, 1), ('contact', 19, 1), ('contact', 20, 1);

-- Staff
INSERT INTO entity_tags (entity_type, entity_id, tag_id) VALUES
  ('contact', 21, 2), ('contact', 22, 2), ('contact', 23, 2);

-- Specialists
INSERT INTO entity_tags (entity_type, entity_id, tag_id) VALUES
  ('contact', 24, 3), ('contact', 25, 3);

-- Vendors & Insurance
INSERT INTO entity_tags (entity_type, entity_id, tag_id) VALUES
  ('contact', 26, 5), ('contact', 27, 4), ('contact', 28, 4);

-- Clinical tags
INSERT INTO entity_tags (entity_type, entity_id, tag_id) VALUES
  ('contact', 1, 7), ('contact', 1, 8), ('contact', 1, 12),    -- Margaret: diabetes, cardiac, chronic
  ('contact', 14, 6),                                             -- Dorothy: high-risk
  ('contact', 17, 7), ('contact', 17, 12),                        -- Ahmed: diabetes, chronic
  ('contact', 13, 7),                                             -- Frank: diabetes
  ('contact', 19, 12),                                            -- Robert: chronic (COPD)
  ('contact', 10, 6),                                             -- Helen: high-risk (cognitive)
  ('contact', 7, 12),                                             -- Thomas: chronic (migraines)
  ('contact', 6, 12);                                             -- Barbara: chronic (osteoporosis)

-- Status tags
INSERT INTO entity_tags (entity_type, entity_id, tag_id) VALUES
  ('contact', 16, 9),   -- Stephanie: wellness-overdue (missed follow-ups)
  ('contact', 8, 9),    -- Patricia: wellness-overdue (colonoscopy due)
  ('contact', 7, 10),   -- Thomas: follow-up-needed (migraine preventive discussion)
  ('contact', 14, 10),  -- Dorothy: follow-up-needed (medication reconciliation)
  ('contact', 12, 11);  -- Maria: new-patient

-- ============================================================================
-- CONTACT RELATIONSHIPS
-- ============================================================================
INSERT INTO contact_relationships (contact_id_a, contact_id_b, relationship_type, notes) VALUES
  (1, 24, 'referred_to', 'Margaret referred to Dr. Zhao for cardiac workup'),
  (1, 25, 'referred_to', 'Margaret co-managed with Dr. Torres for diabetes'),
  (11, 20, 'colleague', 'Jason and Susan both work at Lincoln School District'),
  (17, 25, 'referred_to', 'Ahmed referred to Dr. Torres for endocrine management'),
  (19, 24, 'referred_to', 'Robert referred to Dr. Zhao for cardiac clearance'),
  (21, 22, 'colleague', 'Lisa and Emily work together at front desk'),
  (21, 23, 'colleague', 'Lisa and Mark coordinate on billing and scheduling');

-- ============================================================================
-- PROJECTS
-- ============================================================================
INSERT INTO projects (id, name, description, client_id, status, priority, start_date, target_date, completed_date, created_at, updated_at) VALUES
  (1, 'Annual Wellness Outreach', 'Proactive campaign to identify and schedule patients overdue for annual wellness visits. Goal: 85% of active patients seen within 12 months.', NULL, 'active', 'high', datetime('now', '-30 days'), datetime('now', '+60 days'), NULL, datetime('now', '-30 days'), datetime('now', '-1 days')),
  (2, 'Billing Workflow Optimization', 'Streamline insurance claims processing. Address Meridian denial rate (currently 18%, target <5%). Automate prior auth tracking.', NULL, 'active', 'high', datetime('now', '-45 days'), datetime('now', '+30 days'), NULL, datetime('now', '-45 days'), datetime('now', '-2 days')),
  (3, 'Patient Portal Rollout', 'Get 60% of active patients enrolled on PracticePulse portal within 90 days. Enables secure messaging, appointment requests, and lab results viewing.', NULL, 'active', 'medium', datetime('now', '-21 days'), datetime('now', '+69 days'), NULL, datetime('now', '-21 days'), datetime('now', '-6 days')),
  (4, 'Diabetic Care Program', 'Structured care program for diabetic and pre-diabetic patients. Monthly check-ins, A1c tracking, nutrition counseling partnership, and glucose monitor distribution.', NULL, 'planning', 'medium', NULL, datetime('now', '+90 days'), NULL, datetime('now', '-14 days'), datetime('now', '-3 days')),
  (5, 'Second MA Hiring', 'Hire a second medical assistant to handle increased patient volume. Target start date was Feb 1.', NULL, 'completed', 'high', datetime('now', '-60 days'), datetime('now', '-15 days'), datetime('now', '-18 days'), datetime('now', '-60 days'), datetime('now', '-18 days'));

-- ============================================================================
-- TASKS
-- ============================================================================
INSERT INTO tasks (project_id, title, status, priority, assigned_to, due_date, completed_at, sort_order, created_at, updated_at) VALUES
  -- Annual Wellness Outreach
  (1, 'Pull list of patients not seen in 12+ months', 'done', 'high', 21, datetime('now', '-25 days'), datetime('now', '-24 days'), 1, datetime('now', '-30 days'), datetime('now', '-24 days')),
  (1, 'Send outreach letters to overdue patients', 'done', 'high', 21, datetime('now', '-20 days'), datetime('now', '-19 days'), 2, datetime('now', '-28 days'), datetime('now', '-19 days')),
  (1, 'Phone follow-up for non-responders', 'in_progress', 'medium', 22, datetime('now', '+7 days'), NULL, 3, datetime('now', '-15 days'), datetime('now', '-2 days')),
  (1, 'Track scheduling rate and report monthly', 'todo', 'medium', 21, datetime('now', '+30 days'), NULL, 4, datetime('now', '-10 days'), datetime('now', '-10 days')),
  -- Billing Workflow
  (2, 'Audit Meridian claim denials from last quarter', 'done', 'high', 23, datetime('now', '-30 days'), datetime('now', '-28 days'), 1, datetime('now', '-45 days'), datetime('now', '-28 days')),
  (2, 'Meeting with Tom Bradley re: denial patterns', 'done', 'high', NULL, datetime('now', '-20 days'), datetime('now', '-20 days'), 2, datetime('now', '-35 days'), datetime('now', '-20 days')),
  (2, 'Implement prior auth tracking spreadsheet', 'in_progress', 'high', 23, datetime('now', '+5 days'), NULL, 3, datetime('now', '-18 days'), datetime('now', '-3 days')),
  (2, 'Retrain staff on clean claim submission', 'todo', 'medium', 21, datetime('now', '+14 days'), NULL, 4, datetime('now', '-10 days'), datetime('now', '-10 days')),
  -- Patient Portal
  (3, 'Configure portal with PracticePulse', 'done', 'high', 28, datetime('now', '-14 days'), datetime('now', '-13 days'), 1, datetime('now', '-21 days'), datetime('now', '-13 days')),
  (3, 'Create patient enrollment guide (printed handout)', 'done', 'medium', 22, datetime('now', '-10 days'), datetime('now', '-9 days'), 2, datetime('now', '-18 days'), datetime('now', '-9 days')),
  (3, 'Enroll first 20 patients during visits', 'in_progress', 'high', 22, datetime('now', '+14 days'), NULL, 3, datetime('now', '-7 days'), datetime('now', '-2 days')),
  (3, 'Send portal invite emails to remaining patients', 'todo', 'medium', 21, datetime('now', '+30 days'), NULL, 4, datetime('now', '-5 days'), datetime('now', '-5 days')),
  -- Diabetic Care Program
  (4, 'Define program criteria and patient list', 'in_progress', 'high', NULL, datetime('now', '+14 days'), NULL, 1, datetime('now', '-14 days'), datetime('now', '-3 days')),
  (4, 'Source glucose monitors (Jennifer Walsh quote)', 'done', 'medium', 27, datetime('now', '-5 days'), datetime('now', '-6 days'), 2, datetime('now', '-12 days'), datetime('now', '-6 days')),
  (4, 'Design monthly check-in protocol', 'todo', 'high', NULL, datetime('now', '+21 days'), NULL, 3, datetime('now', '-10 days'), datetime('now', '-10 days')),
  (4, 'Partner with nutritionist for counseling referrals', 'todo', 'medium', NULL, datetime('now', '+30 days'), NULL, 4, datetime('now', '-7 days'), datetime('now', '-7 days')),
  -- Second MA Hiring (completed)
  (5, 'Post job listing', 'done', 'high', 21, datetime('now', '-55 days'), datetime('now', '-54 days'), 1, datetime('now', '-60 days'), datetime('now', '-54 days')),
  (5, 'Screen and interview candidates', 'done', 'high', NULL, datetime('now', '-35 days'), datetime('now', '-32 days'), 2, datetime('now', '-50 days'), datetime('now', '-32 days')),
  (5, 'Extend offer to Emily Sato', 'done', 'high', NULL, datetime('now', '-25 days'), datetime('now', '-25 days'), 3, datetime('now', '-33 days'), datetime('now', '-25 days')),
  (5, 'Onboarding and training', 'done', 'medium', 21, datetime('now', '-15 days'), datetime('now', '-18 days'), 4, datetime('now', '-24 days'), datetime('now', '-18 days'));

-- ============================================================================
-- MILESTONES
-- ============================================================================
INSERT INTO milestones (project_id, name, target_date, completed_date, status, created_at) VALUES
  (1, 'Outreach letters sent', datetime('now', '-18 days'), datetime('now', '-19 days'), 'completed', datetime('now', '-30 days')),
  (1, '50% of overdue patients scheduled', datetime('now', '+30 days'), NULL, 'pending', datetime('now', '-30 days')),
  (2, 'Denial root cause identified', datetime('now', '-25 days'), datetime('now', '-28 days'), 'completed', datetime('now', '-45 days')),
  (2, 'Meridian denial rate below 10%', datetime('now', '+30 days'), NULL, 'pending', datetime('now', '-35 days')),
  (3, 'Portal live and tested', datetime('now', '-12 days'), datetime('now', '-13 days'), 'completed', datetime('now', '-21 days')),
  (3, '60% patient enrollment', datetime('now', '+69 days'), NULL, 'pending', datetime('now', '-21 days')),
  (4, 'Program design finalized', datetime('now', '+21 days'), NULL, 'pending', datetime('now', '-14 days')),
  (5, 'New MA starts', datetime('now', '-18 days'), datetime('now', '-18 days'), 'completed', datetime('now', '-60 days'));

-- ============================================================================
-- CONTACT INTERACTIONS (~55)
-- ============================================================================
INSERT INTO contact_interactions (contact_id, type, direction, subject, summary, occurred_at, created_at) VALUES
  -- Margaret Chen (active, complex patient)
  (1, 'meeting', 'outbound', 'Quarterly diabetes review', 'A1c stable at 7.0. BP 138/82, slightly above target. Discussed adding low-dose HCTZ. Patient wants to try dietary changes first — agreed to 6-week trial.', datetime('now', '-2 days'), datetime('now', '-2 days')),
  (1, 'call', 'inbound', 'Question about metformin timing', 'Margaret called asking about taking metformin with meals vs before. Advised with meals to reduce GI side effects. No issues otherwise.', datetime('now', '-18 days'), datetime('now', '-18 days')),
  (1, 'email', 'outbound', 'Lab results follow-up', 'Sent lab results with annotations. Lipid panel improved — LDL down from 142 to 118. Encouraged to keep up dietary changes.', datetime('now', '-30 days'), datetime('now', '-30 days')),
  -- James Rivera
  (2, 'meeting', 'outbound', 'Back pain follow-up', 'MRI shows L4-L5 disc bulge, no surgical indication. PT helping — pain 5/10 down from 8/10. Discussed ergonomics at work site. Renewed meloxicam.', datetime('now', '-5 days'), datetime('now', '-5 days')),
  (2, 'call', 'outbound', 'PT progress check', 'Quick check-in. James reports good progress with PT. Able to work full days now. Continuing exercises at home.', datetime('now', '-25 days'), datetime('now', '-25 days')),
  -- David Okafor
  (3, 'meeting', 'outbound', 'Annual wellness visit', 'Complete physical. All labs normal except LDL 168. Discussed statin — patient prefers 3-month lifestyle trial first. Recheck in April.', datetime('now', '-12 days'), datetime('now', '-12 days')),
  -- Linda Patel
  (4, 'meeting', 'outbound', 'Anxiety follow-up — 3 month check', 'Sertraline 50mg working well. Sleep improved from 4-5 hrs to 6-7 hrs. PHQ-9 down from 14 to 6. Discussed mindfulness app. Continue current regimen.', datetime('now', '-3 days'), datetime('now', '-3 days')),
  (4, 'call', 'inbound', 'Medication side effects question', 'Linda experiencing mild nausea in AM. Suggested taking sertraline with dinner instead. Will monitor.', datetime('now', '-35 days'), datetime('now', '-35 days')),
  -- Michael Torres
  (5, 'meeting', 'outbound', 'Rotator cuff clearance', 'Full ROM restored. Strength 5/5. Cleared for full kitchen duties. Discussed injury prevention stretches. Interested in sports nutrition consult.', datetime('now', '-18 days'), datetime('now', '-18 days')),
  -- Barbara Anderson
  (6, 'meeting', 'outbound', 'Osteoporosis management visit', 'On alendronate 12 months. Tolerating well. Knee pain managed with acetaminophen and bracing. DEXA scheduled for July. Discussed calcium + vitamin D.', datetime('now', '-7 days'), datetime('now', '-7 days')),
  (6, 'call', 'inbound', 'Knee pain flare', 'Acute knee pain after showing houses all weekend. No swelling, no locking. Advised RICE, OTC topical diclofenac. Come in if not better in 5 days.', datetime('now', '-22 days'), datetime('now', '-22 days')),
  -- Thomas Nguyen
  (7, 'meeting', 'outbound', 'Migraine management discussion', 'Frequency increased to 10/month. Sumatriptan provides only 50% relief. Starting topiramate 25mg for prevention. Discussed migraine diary tracking. Follow-up in 6 weeks.', datetime('now', '-1 days'), datetime('now', '-1 days')),
  (7, 'email', 'outbound', 'Migraine diary template', 'Sent migraine tracking template and trigger identification guide. Asked Thomas to log for 4 weeks before next visit.', datetime('now', '-1 days'), datetime('now', '-1 days')),
  -- Helen Brooks
  (10, 'meeting', 'outbound', 'Cognitive follow-up with family', 'MMSE 26/30, stable from 3 months ago. Daughter Karen present. Brain health protocol continuing — exercise, social engagement, puzzles. Discussed advance directive planning.', datetime('now', '-4 days'), datetime('now', '-4 days')),
  (10, 'call', 'inbound', 'Daughter Karen — medication question', 'Karen called about Helen confusing morning and evening medications. Suggested pill organizer and simplified regimen. Will review at next visit.', datetime('now', '-28 days'), datetime('now', '-28 days')),
  -- Carlos Gutierrez
  (9, 'meeting', 'outbound', 'ACL rehab — 4 month check', 'Excellent progress. Lachman test negative. Quad strength 85% of contralateral. PT says 2 more months. Can start light demo training with clients.', datetime('now', '-10 days'), datetime('now', '-10 days')),
  -- Frank DeLuca
  (13, 'meeting', 'outbound', 'Pre-diabetes check-in', 'Down 8 lbs (from 221 to 213). Fasting glucose 108, was 118. Walking 30 min daily. Very motivated — brother was diagnosed with T2D last year. A1c recheck in 4 weeks.', datetime('now', '-3 days'), datetime('now', '-3 days')),
  (13, 'call', 'outbound', 'Nutrition program follow-up', 'Checked in on meal planning. Frank doing well — reduced refined carbs, more vegetables. Wife cooking healthier. Encouraged continuation.', datetime('now', '-20 days'), datetime('now', '-20 days')),
  -- Dorothy Hawkins
  (14, 'meeting', 'outbound', 'Medication reconciliation visit', 'Reviewed all 9 medications with daughter present. Deprescribed omeprazole (no current indication), reduced to 8. Discussed fall prevention — grab bars installed.', datetime('now', '-2 days'), datetime('now', '-2 days')),
  (14, 'call', 'inbound', 'Daughter — fall concern', 'Dorothy had a near-fall at home. No injury. Daughter concerned. Moved up appointment for home safety review. PT referral for balance training.', datetime('now', '-16 days'), datetime('now', '-16 days')),
  -- Ryan O'Brien
  (15, 'meeting', 'outbound', 'ADHD medication check', 'Methylphenidate working well — focus improved, GPA up to 3.4 from 2.8. Some appetite suppression at lunch. Discussed taking med after breakfast. Exam anxiety — will revisit.', datetime('now', '-6 days'), datetime('now', '-6 days')),
  -- Stephanie Lee
  (16, 'email', 'outbound', 'Missed appointment — rescheduling', 'Third missed follow-up for hypertension. Emailed to reschedule. BP needs monitoring — last reading was 148/92. Emphasized importance of follow-through.', datetime('now', '-14 days'), datetime('now', '-14 days')),
  -- Ahmed Hassan
  (17, 'meeting', 'outbound', 'Diabetes management — quarterly', 'A1c down to 7.1 from 7.8. Great progress. Neuropathy stable — tingling but no pain. Podiatry visit confirmed. Discussed foot care routine. Evening appointment to accommodate restaurant hours.', datetime('now', '-1 days'), datetime('now', '-1 days')),
  (17, 'call', 'inbound', 'Scheduling difficulty', 'Ahmed having trouble making appointments due to restaurant lunch prep. Offered early morning or late afternoon slots. Booked 7:30 AM going forward.', datetime('now', '-22 days'), datetime('now', '-22 days')),
  -- Nancy Palmer
  (18, 'meeting', 'outbound', 'Menopause management visit', 'Hot flashes 6-8/day, disrupting sleep. Discussed HRT risks/benefits thoroughly. Patient wants to try low-dose estradiol patch. Ordered bone density scan.', datetime('now', '-9 days'), datetime('now', '-9 days')),
  -- Robert Kim
  (19, 'meeting', 'outbound', 'COPD quarterly visit', 'Spirometry: FEV1 58% predicted, stable. No exacerbations since last visit. Flu and pneumonia vaccines up to date. Discussed pulmonary rehab maintenance.', datetime('now', '-5 days'), datetime('now', '-5 days')),
  (19, 'call', 'inbound', 'Shortness of breath episode', 'Mild SOB after yard work. Resolved with rest and albuterol. No fever, no cough change. Advised to limit outdoor exertion on high pollen days.', datetime('now', '-20 days'), datetime('now', '-20 days')),
  -- Susan Washington
  (20, 'meeting', 'outbound', 'Annual wellness + thyroid check', 'TSH 2.8, in range. Levothyroxine dose unchanged. Discussed stress management — principal job is demanding. Recommended structured breaks and considering counseling referral.', datetime('now', '-11 days'), datetime('now', '-11 days')),
  -- Staff interactions
  (21, 'meeting', 'outbound', 'Weekly huddle', 'Discussed patient portal enrollment numbers, upcoming wellness outreach calls, and Meridian billing issues. Lisa taking lead on retraining front desk.', datetime('now', '-1 days'), datetime('now', '-1 days')),
  (21, 'meeting', 'outbound', 'Billing workflow review', 'Reviewed denial patterns with Lisa and Mark. Most denials are missing modifier codes. Creating checklist for clean submissions.', datetime('now', '-8 days'), datetime('now', '-8 days')),
  (22, 'meeting', 'outbound', 'Portal enrollment check-in', 'Emily has enrolled 8 patients this week. Some older patients need more hand-holding — she printed step-by-step guides. Good initiative.', datetime('now', '-3 days'), datetime('now', '-3 days')),
  (23, 'meeting', 'outbound', 'Prior auth tracking setup', 'Mark set up the tracking spreadsheet. Already identified 3 pending auths that were about to expire. Caught them in time.', datetime('now', '-5 days'), datetime('now', '-5 days')),
  -- External interactions
  (24, 'email', 'inbound', 'Margaret Chen cardiac workup results', 'Dr. Zhao sent echo results: EF 55%, no structural abnormalities. Mild diastolic dysfunction consistent with age and hypertension. No intervention needed.', datetime('now', '-15 days'), datetime('now', '-15 days')),
  (25, 'email', 'inbound', 'Ahmed Hassan endo visit note', 'Dr. Torres adjusted Ahmed insulin regimen. Switched to once-daily basal. A1c target 6.5-7.0. Follow-up in 3 months.', datetime('now', '-10 days'), datetime('now', '-10 days')),
  (26, 'meeting', 'outbound', 'Meridian denial discussion', 'Met with Tom re: 18% denial rate. Root cause: modifier code 25 missing on E/M + procedure same-day claims. Tom confirmed this is a known Meridian requirement. Sending updated billing guide.', datetime('now', '-20 days'), datetime('now', '-20 days')),
  (26, 'email', 'inbound', 'Meridian billing guide update', 'Tom sent updated Meridian billing requirements document. Key change: modifier 25 now required on all same-day E/M claims. Forwarded to Mark.', datetime('now', '-18 days'), datetime('now', '-18 days')),
  (27, 'call', 'outbound', 'Glucose monitor pricing', 'Jennifer quoted $18/unit for Accu-Chek Guide monitors (bulk 50+). Standard is $24. 25% savings for the diabetic care program. Will send formal quote.', datetime('now', '-8 days'), datetime('now', '-8 days')),
  (28, 'meeting', 'outbound', 'Portal configuration review', 'Alex walked us through secure messaging setup and lab results display. Integration with our lab vendor is seamless. One issue: appointment request routing needs configuration.', datetime('now', '-13 days'), datetime('now', '-13 days')),
  (28, 'email', 'inbound', 'Portal appointment routing fix', 'Alex confirmed the appointment routing config is fixed. New requests will go directly to Lisa for scheduling. Live now.', datetime('now', '-6 days'), datetime('now', '-6 days')),
  -- Additional patient interactions for volume
  (8, 'call', 'outbound', 'Colonoscopy reminder', 'Called Patricia about overdue colonoscopy screening. She acknowledged — scheduling with GI this month. Former nurse, understands importance.', datetime('now', '-20 days'), datetime('now', '-20 days')),
  (11, 'meeting', 'outbound', 'Asthma annual review', 'Well controlled. No ER visits. Spirometry stable. Renewed fluticasone/salmeterol. Discussed allergy season prep — starting nasal steroids March 1.', datetime('now', '-15 days'), datetime('now', '-15 days')),
  (12, 'meeting', 'outbound', 'Postpartum 6-month visit', 'Screening negative for PPD (Edinburgh 4/30). Weight returning to pre-pregnancy. Cleared for all exercise. Discussed contraception options — chose IUD.', datetime('now', '-8 days'), datetime('now', '-8 days'));

-- ============================================================================
-- FOLLOW-UPS
-- ============================================================================
INSERT INTO follow_ups (contact_id, due_date, reason, status, completed_at, created_at) VALUES
  (1, datetime('now', '+42 days'), 'Recheck BP after 6-week dietary trial', 'pending', NULL, datetime('now', '-2 days')),
  (7, datetime('now', '+42 days'), 'Topiramate 6-week follow-up for migraines', 'pending', NULL, datetime('now', '-1 days')),
  (10, datetime('now', '+84 days'), '3-month cognitive recheck — MMSE', 'pending', NULL, datetime('now', '-4 days')),
  (13, datetime('now', '+28 days'), 'A1c recheck — pre-diabetes monitoring', 'pending', NULL, datetime('now', '-3 days')),
  (14, datetime('now', '+14 days'), 'Post-deprescribing check — off omeprazole', 'pending', NULL, datetime('now', '-2 days')),
  (16, datetime('now', '+7 days'), 'Hypertension follow-up — URGENT, 2 missed visits', 'pending', NULL, datetime('now', '-14 days')),
  (17, datetime('now', '+84 days'), 'Diabetes quarterly — A1c and foot check', 'pending', NULL, datetime('now', '-1 days')),
  (18, datetime('now', '+28 days'), 'HRT check — estradiol patch tolerance', 'pending', NULL, datetime('now', '-9 days')),
  (3, datetime('now', '+75 days'), 'Cholesterol recheck after lifestyle trial', 'pending', NULL, datetime('now', '-12 days')),
  (9, datetime('now', '+56 days'), 'ACL rehab 6-month milestone assessment', 'pending', NULL, datetime('now', '-10 days')),
  -- Completed follow-ups
  (2, datetime('now', '-5 days'), 'Back pain follow-up after PT', 'completed', datetime('now', '-5 days'), datetime('now', '-25 days')),
  (5, datetime('now', '-18 days'), 'Rotator cuff clearance assessment', 'completed', datetime('now', '-18 days'), datetime('now', '-40 days')),
  (13, datetime('now', '-3 days'), 'Pre-diabetes weight and glucose recheck', 'completed', datetime('now', '-3 days'), datetime('now', '-20 days')),
  (6, datetime('now', '-7 days'), 'Osteoporosis 12-month alendronate review', 'completed', datetime('now', '-7 days'), datetime('now', '-30 days'));

-- ============================================================================
-- EMAILS
-- ============================================================================
INSERT INTO emails (gmail_id, thread_id, contact_id, direction, from_address, from_name, to_addresses, subject, snippet, body_preview, labels, is_read, is_starred, received_at, synced_at) VALUES
  ('demo_e01', 'demo_t01', 1, 'inbound', 'margaret.chen@gmail.com', 'Margaret Chen', 'dr.mitchell@greenfieldpractice.com', 'Question about my A1c results', 'Hi Dr. Mitchell, I got my lab results in the mail and wanted to ask about...', 'Hi Dr. Mitchell, I got my lab results in the mail and wanted to ask about my A1c number. It says 7.0 — is that good? I have been really trying with the diet changes you suggested. Also, should I be worried about the cholesterol numbers? Thank you, Margaret', '["INBOX"]', 1, 0, datetime('now', '-8 days'), datetime('now', '-8 days')),
  ('demo_e02', 'demo_t01', 1, 'outbound', 'dr.mitchell@greenfieldpractice.com', 'Dr. Sarah Mitchell', 'margaret.chen@gmail.com', 'Re: Question about my A1c results', 'Great news, Margaret! An A1c of 7.0 is right at our target...', 'Great news, Margaret! An A1c of 7.0 is right at our target and stable from your last check. Your dietary changes are clearly working. Your LDL cholesterol also improved — down from 142 to 118. Keep up what you are doing. We will recheck everything at your next quarterly visit. Best, Dr. Mitchell', '["SENT"]', 1, 0, datetime('now', '-8 days'), datetime('now', '-8 days')),
  ('demo_e03', 'demo_t02', 16, 'outbound', 'dr.mitchell@greenfieldpractice.com', 'Dr. Sarah Mitchell', 's.lee@hartfordlaw.com', 'Important: Please reschedule your blood pressure follow-up', 'Hi Stephanie, I noticed you have missed your last two scheduled follow-ups...', 'Hi Stephanie, I noticed you have missed your last two scheduled follow-ups for your blood pressure management. Your last reading was 148/92, which is above our target of 130/80. I understand your schedule is demanding, but monitoring is important at this stage. Could you call the office to reschedule? We have early morning and evening slots available. Best, Dr. Mitchell', '["SENT"]', 1, 1, datetime('now', '-14 days'), datetime('now', '-14 days')),
  ('demo_e04', 'demo_t03', 24, 'inbound', 'kzhao@metroheart.com', 'Dr. Kevin Zhao', 'dr.mitchell@greenfieldpractice.com', 'Margaret Chen — Echo Results', 'Sarah, echo results for your patient Margaret Chen are attached...', 'Sarah, echo results for your patient Margaret Chen are attached. Summary: EF 55%, no structural abnormalities. Mild diastolic dysfunction grade 1, consistent with age and hypertension history. No intervention warranted at this time. Recommend continued BP management per your plan. Happy to discuss if you have questions. Kevin', '["INBOX"]', 1, 0, datetime('now', '-15 days'), datetime('now', '-15 days')),
  ('demo_e05', 'demo_t04', 25, 'inbound', 'rtorres@eastsidediabetes.com', 'Dr. Rachel Torres', 'dr.mitchell@greenfieldpractice.com', 'Ahmed Hassan — Visit Summary', 'Hi Sarah, saw Ahmed today. Adjusted his insulin regimen...', 'Hi Sarah, saw Ahmed today. Adjusted his insulin regimen to once-daily basal (Lantus 18 units at bedtime). His A1c of 7.1 is a big improvement. Neuropathy symptoms stable. Continue current foot care plan. Target A1c 6.5-7.0. I will see him again in 3 months. Best, Rachel', '["INBOX"]', 1, 0, datetime('now', '-10 days'), datetime('now', '-10 days')),
  ('demo_e06', 'demo_t05', 26, 'inbound', 'tbradley@meridianhealth.com', 'Tom Bradley', 'dr.mitchell@greenfieldpractice.com', 'Updated Meridian Billing Requirements', 'Dr. Mitchell, as discussed, here is the updated billing guide...', 'Dr. Mitchell, as discussed in our meeting, here is the updated Meridian billing requirements document. The key change is that modifier 25 is now required on all same-day E/M claims when a procedure is also performed. I have also included the appeal form for your existing denials. Let me know if you have questions. Tom', '["INBOX"]', 1, 1, datetime('now', '-18 days'), datetime('now', '-18 days')),
  ('demo_e07', 'demo_t06', 28, 'inbound', 'acooper@practicepulse.com', 'Alex Cooper', 'dr.mitchell@greenfieldpractice.com', 'Portal appointment routing — fixed', 'Hi Dr. Mitchell, good news! The appointment request routing has been...', 'Hi Dr. Mitchell, good news! The appointment request routing has been configured. New patient appointment requests through the portal will now route directly to Lisa for scheduling. No more lost requests. Let me know if you notice any issues. Alex', '["INBOX"]', 1, 0, datetime('now', '-6 days'), datetime('now', '-6 days')),
  ('demo_e08', 'demo_t07', 7, 'outbound', 'dr.mitchell@greenfieldpractice.com', 'Dr. Sarah Mitchell', 'tng.dev@gmail.com', 'Migraine diary template', 'Hi Thomas, as discussed today, here is the migraine tracking template...', 'Hi Thomas, as discussed today, here is the migraine tracking template. Please log each migraine for the next 4 weeks, noting: time of onset, duration, severity (1-10), any identifiable triggers (food, sleep, screen time, weather), and which medication you took. This will help us evaluate how the topiramate is working at your 6-week follow-up. Best, Dr. Mitchell', '["SENT"]', 1, 0, datetime('now', '-1 days'), datetime('now', '-1 days')),
  ('demo_e09', 'demo_t08', 27, 'inbound', 'jwalsh@medsupply.com', 'Jennifer Walsh', 'dr.mitchell@greenfieldpractice.com', 'Glucose monitor quote — bulk pricing', 'Dr. Mitchell, here is the formal quote for Accu-Chek Guide monitors...', 'Dr. Mitchell, here is the formal quote for the Accu-Chek Guide monitors. At 50+ units: $18.00/unit (list price $24.00, 25% savings). Includes test strips starter pack with each unit. Delivery within 5 business days of order. Quote valid for 60 days. Let me know when you are ready to move forward. Jennifer', '["INBOX"]', 1, 1, datetime('now', '-7 days'), datetime('now', '-7 days')),
  ('demo_e10', 'demo_t09', 13, 'inbound', 'frank@delucabuilders.com', 'Frank DeLuca', 'dr.mitchell@greenfieldpractice.com', 'Quick update — down another 2 pounds!', 'Doc, just wanted to let you know I weighed in at 211 this morning...', 'Doc, just wanted to let you know I weighed in at 211 this morning. That is 10 lbs down total. My wife has been cooking more vegetables and less pasta (do not tell my mother). The walking is getting easier too — I am up to 35 minutes most days. See you at the A1c recheck next month. Frank', '["INBOX"]', 1, 1, datetime('now', '-4 days'), datetime('now', '-4 days')),
  ('demo_e11', 'demo_t10', 17, 'inbound', 'ahmed@spiceroute.com', 'Ahmed Hassan', 'dr.mitchell@greenfieldpractice.com', 'Thank you for the early appointment slots', 'Dr. Mitchell, thank you for offering the 7:30 AM appointments...', 'Dr. Mitchell, thank you for offering the 7:30 AM appointments. That makes it so much easier for me with the restaurant schedule. I saw Dr. Torres last week and she was happy with the progress. The new insulin schedule is simpler too. See you in 3 months. Ahmed', '["INBOX"]', 1, 0, datetime('now', '-3 days'), datetime('now', '-3 days'));

-- ============================================================================
-- CALENDAR EVENTS
-- ============================================================================
INSERT INTO calendar_events (google_event_id, title, description, location, start_time, end_time, all_day, status, attendees, contact_ids, project_id, synced_at) VALUES
  -- Past events
  ('demo_cal01', 'Staff Huddle', 'Weekly team meeting', 'Conference Room', datetime('now', '-1 days', 'start of day', '+8 hours'), datetime('now', '-1 days', 'start of day', '+8 hours', '+30 minutes'), 0, 'confirmed', '["Lisa Brennan", "Emily Sato", "Mark Davidson"]', '[21, 22, 23]', NULL, datetime('now', '-1 days')),
  ('demo_cal02', 'Margaret Chen — Diabetes Review', 'Quarterly A1c and BP check', 'Exam Room 1', datetime('now', '-2 days', 'start of day', '+9 hours'), datetime('now', '-2 days', 'start of day', '+9 hours', '+30 minutes'), 0, 'confirmed', '["Margaret Chen"]', '[1]', NULL, datetime('now', '-2 days')),
  ('demo_cal03', 'Tom Bradley — Meridian Claims Meeting', 'Discuss denial rate and billing requirements', 'Office', datetime('now', '-20 days', 'start of day', '+14 hours'), datetime('now', '-20 days', 'start of day', '+14 hours', '+45 minutes'), 0, 'confirmed', '["Tom Bradley"]', '[26]', 2, datetime('now', '-20 days')),
  ('demo_cal04', 'Alex Cooper — Portal Setup', 'Configure patient portal with PracticePulse', 'Conference Room', datetime('now', '-13 days', 'start of day', '+10 hours'), datetime('now', '-13 days', 'start of day', '+10 hours', '+60 minutes'), 0, 'confirmed', '["Alex Cooper"]', '[28]', 3, datetime('now', '-13 days')),
  -- Upcoming events
  ('demo_cal05', 'Staff Huddle', 'Weekly team meeting', 'Conference Room', datetime('now', '+6 days', 'start of day', '+8 hours'), datetime('now', '+6 days', 'start of day', '+8 hours', '+30 minutes'), 0, 'confirmed', '["Lisa Brennan", "Emily Sato", "Mark Davidson"]', '[21, 22, 23]', NULL, datetime('now')),
  ('demo_cal06', 'Thomas Nguyen — Migraine Follow-up', '6-week topiramate check', 'Exam Room 2', datetime('now', '+42 days', 'start of day', '+10 hours'), datetime('now', '+42 days', 'start of day', '+10 hours', '+30 minutes'), 0, 'confirmed', '["Thomas Nguyen"]', '[7]', NULL, datetime('now')),
  ('demo_cal07', 'Dorothy Hawkins — Post-Deprescribing Check', 'Check after stopping omeprazole', 'Exam Room 1', datetime('now', '+14 days', 'start of day', '+11 hours'), datetime('now', '+14 days', 'start of day', '+11 hours', '+20 minutes'), 0, 'confirmed', '["Dorothy Hawkins"]', '[14]', NULL, datetime('now')),
  ('demo_cal08', 'Frank DeLuca — A1c Recheck', 'Pre-diabetes monitoring', 'Lab + Exam Room 1', datetime('now', '+28 days', 'start of day', '+9 hours'), datetime('now', '+28 days', 'start of day', '+9 hours', '+30 minutes'), 0, 'confirmed', '["Frank DeLuca"]', '[13]', NULL, datetime('now')),
  ('demo_cal09', 'Nancy Palmer — HRT Follow-up', 'Estradiol patch tolerance check', 'Exam Room 2', datetime('now', '+28 days', 'start of day', '+14 hours'), datetime('now', '+28 days', 'start of day', '+14 hours', '+30 minutes'), 0, 'confirmed', '["Nancy Palmer"]', '[18]', NULL, datetime('now')),
  ('demo_cal10', 'Stephanie Lee — BP Follow-up (RESCHEDULED)', 'Hypertension monitoring — must attend', 'Exam Room 1', datetime('now', '+7 days', 'start of day', '+7 hours', '+30 minutes'), datetime('now', '+7 days', 'start of day', '+8 hours'), 0, 'confirmed', '["Stephanie Lee"]', '[16]', NULL, datetime('now')),
  ('demo_cal11', 'Diabetic Care Program Planning', 'Design program protocol with team', 'Conference Room', datetime('now', '+10 days', 'start of day', '+12 hours'), datetime('now', '+10 days', 'start of day', '+13 hours'), 0, 'confirmed', '["Lisa Brennan", "Emily Sato"]', '[21, 22]', 4, datetime('now')),
  ('demo_cal12', 'County Medical Society — Quarterly Dinner', 'Networking event, Dr. Zhao will be there', 'Greenfield Country Club', datetime('now', '+18 days', 'start of day', '+18 hours'), datetime('now', '+18 days', 'start of day', '+21 hours'), 0, 'confirmed', NULL, NULL, NULL, datetime('now'));

-- ============================================================================
-- TRANSCRIPTS (3 realistic conversations)
-- ============================================================================
INSERT INTO transcripts (id, title, source, raw_text, summary, duration_minutes, occurred_at, processed_at, created_at, updated_at, call_intelligence) VALUES
  (1, 'Weekly Staff Huddle — Feb 17', 'paste',
'Dr. Mitchell: Good morning everyone. Let us run through the week. Lisa, how are the wellness outreach calls going?

Lisa Brennan: We sent 42 letters last month and I have been following up by phone. So far 18 patients have scheduled. That is about 43%. The ones who have not responded tend to be younger patients who probably think they do not need a checkup.

Dr. Mitchell: 43% is solid for the first round. Emily, how is the portal enrollment going?

Emily Sato: Really well actually. I have gotten 8 patients signed up this week. The printed guide is helping a lot, especially with older patients. Margaret Chen was thrilled she could see her lab results online. Some patients need me to walk them through it step by step but they get it eventually.

Dr. Mitchell: That is great. Margaret is a perfect example — she is really engaged in her care. Mark, where are we on the Meridian billing issue?

Mark Davidson: Good news. I found the root cause. 73% of our denials are because we were missing modifier 25 on same-day E/M and procedure claims. Tom Bradley sent over the updated requirements. I have already resubmitted 8 of the denied claims with the correct modifier and 5 have been approved.

Dr. Mitchell: Excellent detective work. What is our denial rate trending toward?

Mark Davidson: If the resubmissions all go through, we should be down to about 8% by end of month. I am also building a checklist for the front desk to catch these before submission.

Dr. Mitchell: Perfect. Any patient concerns this week?

Emily Sato: Dorothy Hawkins'' daughter called worried about a near-fall. I moved up her appointment. Also, Stephanie Lee still has not rescheduled her blood pressure follow-up. That is the third missed visit.

Dr. Mitchell: Stephanie worries me. Her last BP was 148 over 92. Lisa, can you try her office number? Sometimes that works better for professionals who screen personal calls.

Lisa Brennan: Will do. I will try today.

Dr. Mitchell: Great huddle everyone. Let us keep the momentum going on the portal and billing projects.',
  'Weekly staff meeting covering wellness outreach (43% scheduling rate from letters), portal enrollment (8 new this week), Meridian billing resolution (modifier 25 identified as root cause, denial rate trending to 8%), and patient concerns (Dorothy Hawkins fall risk, Stephanie Lee missed follow-ups).',
  25, datetime('now', '-1 days'), datetime('now', '-1 days'), datetime('now', '-1 days'), datetime('now', '-1 days'), NULL),

  (2, 'Meridian Insurance — Claims Discussion', 'paste',
'Dr. Mitchell: Tom, thanks for meeting with us. We have been seeing an 18% denial rate on Meridian claims and I want to understand why.

Tom Bradley: Of course, Dr. Mitchell. I pulled your account data and I can see the pattern. The vast majority of your denials are on same-day evaluation and management claims when a procedure is also billed.

Dr. Mitchell: So it is a coding issue, not a clinical documentation issue?

Tom Bradley: Exactly. You need modifier 25 appended to the E/M code when a separately identifiable service is performed on the same day. It is a Meridian-specific requirement that we tightened up last quarter.

Dr. Mitchell: That is frustrating that we were not notified about the change. How many of our existing denials can be appealed?

Tom Bradley: All of them within 90 days of the original denial date. I would recommend batch-resubmitting them with the modifier added. I can send you the appeal form and an updated billing guide.

Dr. Mitchell: Mark, are you getting this? Can you handle the resubmissions?

Mark Davidson: Already on it. I will pull all denied claims from the last quarter and start resubmitting this week.

Tom Bradley: One more thing — I would suggest building a pre-submission checklist. Our analytics show that practices who use a modifier checklist see denial rates under 3%.

Dr. Mitchell: That is a great idea. We will implement that. Tom, what is the timeline on processing the appeals?

Tom Bradley: Typically 14 to 21 business days. I will flag your account for expedited review given the volume.

Dr. Mitchell: Appreciate that. Let us check in again in 30 days to see where the numbers land.',
  'Meeting with Meridian insurance rep about 18% claim denial rate. Root cause: missing modifier 25 on same-day E/M claims. All denials within 90-day appeal window. Tom providing updated billing guide and appeal forms. Mark to batch-resubmit denied claims. Pre-submission checklist recommended.',
  20, datetime('now', '-20 days'), datetime('now', '-20 days'), datetime('now', '-20 days'), datetime('now', '-20 days'), NULL),

  (3, 'PracticePulse Portal Setup — Alex Cooper', 'paste',
'Alex Cooper: Dr. Mitchell, let me walk you through what we have configured for your patient portal.

Dr. Mitchell: Great. My main priorities are secure messaging, lab results, and appointment requests.

Alex Cooper: All three are set up. For secure messaging, patients can send messages that route directly to your inbox in PracticePulse. You can reply from there or the mobile app.

Dr. Mitchell: What about response time expectations? I do not want patients expecting instant replies.

Alex Cooper: Good question. We have set the default message to say responses within 2 business days. You can customize that. Most practices find that sets the right expectation.

Dr. Mitchell: That works. What about lab results?

Alex Cooper: Lab results are pulled automatically from your Quest and LabCorp integrations. They will appear in the patient portal 24 hours after they are finalized. You can hold specific results if you want to discuss them with the patient first.

Dr. Mitchell: I like the hold option. For things like cancer screenings, I want to deliver those personally.

Alex Cooper: Absolutely. You can set hold rules by test type. Now for appointment requests — this is where we had the routing issue. New requests were going to a general queue. I have reconfigured them to route directly to Lisa Brennan for scheduling.

Dr. Mitchell: Perfect. Lisa is the right person for that. What about enrollment? How do we get patients signed up?

Alex Cooper: Each patient gets a unique activation code. We can generate these in batch from your patient list. Your staff can hand them out during visits or you can email them. The enrollment process takes about 3 minutes.

Dr. Mitchell: Emily has been enrolling patients at checkout. That seems to be working well. What is our target?

Alex Cooper: Industry average is about 40% enrollment within the first year. Given your practice size, I would aim for 60% in 90 days since you have an engaged patient population.

Dr. Mitchell: 60% sounds right. What analytics do you have for tracking adoption?

Alex Cooper: I will set up a monthly report showing enrollment rate, message volume, appointment requests, and lab result views. That way you can see exactly what patients are using.',
  'Portal setup meeting with PracticePulse. Configured: secure messaging (2-day response SLA), lab results (auto-pull with hold option for sensitive results), appointment requests (routing fixed to Lisa). Enrollment target: 60% in 90 days. Monthly adoption analytics to be set up.',
  30, datetime('now', '-13 days'), datetime('now', '-13 days'), datetime('now', '-13 days'), datetime('now', '-13 days'), NULL);

-- ============================================================================
-- TRANSCRIPT PARTICIPANTS
-- ============================================================================
INSERT INTO transcript_participants (transcript_id, contact_id, speaker_label, is_user, created_at) VALUES
  (1, NULL, 'Dr. Mitchell', 1, datetime('now', '-1 days')),
  (1, 21, 'Lisa Brennan', 0, datetime('now', '-1 days')),
  (1, 22, 'Emily Sato', 0, datetime('now', '-1 days')),
  (1, 23, 'Mark Davidson', 0, datetime('now', '-1 days')),
  (2, NULL, 'Dr. Mitchell', 1, datetime('now', '-20 days')),
  (2, 26, 'Tom Bradley', 0, datetime('now', '-20 days')),
  (2, 23, 'Mark Davidson', 0, datetime('now', '-20 days')),
  (3, NULL, 'Dr. Mitchell', 1, datetime('now', '-13 days')),
  (3, 28, 'Alex Cooper', 0, datetime('now', '-13 days'));

-- ============================================================================
-- COMMITMENTS
-- ============================================================================
INSERT INTO commitments (transcript_id, owner_contact_id, is_user_commitment, description, deadline_mentioned, deadline_date, status, linked_project_id, created_at, updated_at) VALUES
  -- From Staff Huddle
  (1, 21, 0, 'Lisa to call Stephanie Lee at her office number to reschedule BP follow-up', 'today', datetime('now'), 'completed', NULL, datetime('now', '-1 days'), datetime('now', '-1 days')),
  (1, 23, 0, 'Mark to build pre-submission checklist for clean claims', NULL, datetime('now', '+14 days'), 'open', 2, datetime('now', '-1 days'), datetime('now', '-1 days')),
  (1, 22, 0, 'Emily to continue portal enrollment — target 20 patients this month', 'this month', datetime('now', '+28 days'), 'open', 3, datetime('now', '-1 days'), datetime('now', '-1 days')),
  -- From Meridian meeting
  (2, 23, 0, 'Mark to batch-resubmit all denied claims with modifier 25', 'this week', datetime('now', '-13 days'), 'completed', 2, datetime('now', '-20 days'), datetime('now', '-13 days')),
  (2, 26, 0, 'Tom to send updated Meridian billing guide and appeal forms', NULL, datetime('now', '-18 days'), 'completed', 2, datetime('now', '-20 days'), datetime('now', '-18 days')),
  (2, 26, 0, 'Tom to flag account for expedited appeal review', NULL, NULL, 'completed', 2, datetime('now', '-20 days'), datetime('now', '-19 days')),
  (2, NULL, 1, 'Check in with Tom in 30 days on denial rate numbers', '30 days', datetime('now', '+10 days'), 'open', 2, datetime('now', '-20 days'), datetime('now', '-20 days')),
  -- From Portal meeting
  (3, 28, 0, 'Alex to set up monthly adoption analytics report', NULL, datetime('now', '-6 days'), 'completed', 3, datetime('now', '-13 days'), datetime('now', '-6 days')),
  (3, 28, 0, 'Alex to fix appointment request routing to Lisa', NULL, datetime('now', '-10 days'), 'completed', 3, datetime('now', '-13 days'), datetime('now', '-6 days')),
  (3, NULL, 1, 'Set hold rules for cancer screening lab results in portal', NULL, datetime('now', '+7 days'), 'open', 3, datetime('now', '-13 days'), datetime('now', '-13 days')),
  (3, NULL, 1, 'Review portal enrollment numbers at 30-day mark', '30 days', datetime('now', '+17 days'), 'open', 3, datetime('now', '-13 days'), datetime('now', '-13 days'));

-- ============================================================================
-- CONVERSATION METRICS
-- ============================================================================
INSERT INTO conversation_metrics (transcript_id, contact_id, talk_ratio, word_count, question_count, interruption_count, longest_monologue_seconds, created_at) VALUES
  (1, NULL, 0.35, 287, 6, 0, 45, datetime('now', '-1 days')),
  (2, NULL, 0.45, 198, 5, 0, 60, datetime('now', '-20 days')),
  (3, NULL, 0.30, 156, 6, 0, 40, datetime('now', '-13 days'));

-- ============================================================================
-- COMMUNICATION INSIGHTS
-- ============================================================================
INSERT INTO communication_insights (transcript_id, contact_id, insight_type, content, sentiment, created_at) VALUES
  (1, NULL, 'coach_note', 'Good delegation pattern: assigned specific follow-ups to each team member with clear ownership. Consider setting explicit deadlines for each action item.', 'positive', datetime('now', '-1 days')),
  (1, 21, 'relationship_pulse', 'Lisa is a strong operational partner. She proactively reports metrics (43% scheduling rate) and takes initiative on outreach. High trust, collaborative dynamic.', 'positive', datetime('now', '-1 days')),
  (1, 23, 'relationship_pulse', 'Mark is proving to be an excellent problem-solver. Identified the root cause of billing denials independently and already started resolving them. Emerging as a key team asset.', 'positive', datetime('now', '-1 days')),
  (2, 26, 'relationship_pulse', 'Tom Bradley is cooperative and transparent. He shared data and offered expedited processing. However, communication about policy changes (modifier 25 requirement) was inadequate — this should have been proactively communicated to providers.', 'neutral', datetime('now', '-20 days')),
  (2, NULL, 'coach_note', 'Effective meeting: identified root cause, agreed on corrective actions, and set a 30-day follow-up. Consider documenting the billing checklist as a formal SOP to prevent recurrence.', 'positive', datetime('now', '-20 days')),
  (3, 28, 'relationship_pulse', 'Alex Cooper is responsive and solutions-oriented. Fixed the routing issue quickly and proactively suggested enrollment targets and analytics. Strong vendor relationship.', 'positive', datetime('now', '-13 days'));

-- ============================================================================
-- RELATIONSHIP SCORES
-- ============================================================================
INSERT INTO relationship_scores (contact_id, score_date, meeting_frequency, talk_ratio_avg, commitment_follow_through, topic_diversity, relationship_depth, trajectory, notes, created_at) VALUES
  (1, date('now'), 3.0, 0.40, 1.0, 0.8, 'collaborative', 'strengthening', 'Highly engaged patient. Asks good questions, follows through on care plans. Strong therapeutic relationship.', datetime('now', '-2 days')),
  (13, date('now'), 2.0, 0.45, 1.0, 0.6, 'collaborative', 'strengthening', 'Very motivated patient. Self-reporting progress via email. Brother''s diagnosis is a strong motivator.', datetime('now', '-3 days')),
  (17, date('now'), 2.0, 0.50, 0.8, 0.7, 'professional', 'strengthening', 'Improving engagement. Scheduling accommodation (7:30 AM) was key to retention. A1c trending well.', datetime('now', '-1 days')),
  (21, date('now'), 4.0, 0.35, 0.9, 0.9, 'trusted', 'stable', 'Core operational partner. High trust, strong delegation. Handles scheduling, outreach, and front desk autonomously.', datetime('now', '-1 days')),
  (23, date('now'), 3.0, 0.30, 1.0, 0.6, 'professional', 'strengthening', 'Growing into a key role. Independently identified billing root cause. Proactive and detail-oriented.', datetime('now', '-2 days')),
  (28, date('now'), 1.5, 0.30, 1.0, 0.5, 'professional', 'strengthening', 'Responsive vendor contact. Fixed issues quickly, proactively suggests improvements. Good partnership.', datetime('now', '-6 days')),
  (16, date('now'), 0.5, NULL, 0.0, 0.2, 'transactional', 'at_risk', 'Three missed follow-ups. Hypertension not adequately monitored. Needs direct outreach.', datetime('now', '-14 days')),
  (14, date('now'), 2.0, 0.45, 0.7, 0.5, 'professional', 'stable', 'Complex elderly patient. Daughter involved in care. Fall risk and polypharmacy concerns require close monitoring.', datetime('now', '-2 days')),
  (10, date('now'), 1.5, 0.40, 0.8, 0.4, 'professional', 'stable', 'Cognitive monitoring ongoing. Family engagement is strong. Stable but requires consistent follow-up.', datetime('now', '-4 days')),
  (26, date('now'), 1.0, 0.45, 1.0, 0.3, 'professional', 'stable', 'Insurance contact. Helpful but reactive — policy changes were not communicated proactively.', datetime('now', '-20 days'));

-- ============================================================================
-- DECISIONS
-- ============================================================================
INSERT INTO decisions (title, context, options_considered, decision, rationale, outcome, outcome_date, status, project_id, contact_id, decided_at, created_at, updated_at, confidence_level, process_quality, outcome_quality) VALUES
  ('Switch to digital intake forms', 'Paper intake forms are slowing down check-in and creating data entry burden for staff. Average check-in time is 12 minutes.', '["Keep paper forms", "Tablet-based digital forms at front desk", "Pre-visit digital forms via patient portal", "Hybrid: digital for new patients, paper for established"]', 'Pre-visit digital forms via patient portal', 'Integrates with the portal rollout project. Patients complete forms at home, reducing wait times. Staff reviews before the visit instead of transcribing after.', 'Check-in time dropped from 12 to 4 minutes for patients who complete forms online. About 40% are using it so far.', datetime('now', '-10 days'), 'validated', 3, NULL, datetime('now', '-35 days'), datetime('now', '-35 days'), datetime('now', '-10 days'), 8, 4, 5),

  ('Hire part-time vs full-time second MA', 'Patient volume increased 22% this year. Emily is overwhelmed with clinical and administrative duties.', '["Part-time MA (20 hrs/week)", "Full-time MA (40 hrs/week)", "Contract/temp MA for 3 months to evaluate need", "Redistribute tasks to existing staff"]', 'Full-time MA (40 hrs/week)', 'Volume growth is sustained, not seasonal. A full-time hire gives scheduling flexibility and allows Emily to focus on clinical tasks. The cost is justified by the volume increase.', 'Hired a second MA who started 3 weeks ago. Already reduced patient wait times and Emily is able to take on more clinical responsibilities.', datetime('now', '-18 days'), 'validated', 5, NULL, datetime('now', '-55 days'), datetime('now', '-55 days'), datetime('now', '-18 days'), 9, 5, 5),

  ('Implement same-day appointment slots', 'Patients calling for acute issues (UTI, back pain flares, medication reactions) cannot get seen for 3-5 days. Some going to urgent care instead.', '["Keep scheduled-only model", "Reserve 3 same-day slots daily", "Open access scheduling (50% same-day)", "Nurse triage line to filter urgency"]', 'Reserve 3 same-day slots daily', 'Compromise between access and predictability. Three slots covers most acute demand without disrupting the schedule. Can adjust based on data.', 'Same-day utilization is 85%. Patient satisfaction improved. Only 2 patients went to urgent care last month vs 8 previously.', datetime('now', '-7 days'), 'validated', NULL, NULL, datetime('now', '-40 days'), datetime('now', '-40 days'), datetime('now', '-7 days'), 7, 4, 4),

  ('Start a structured diabetic care program', 'Five diabetic and three pre-diabetic patients would benefit from coordinated monthly check-ins, A1c tracking, and nutrition support. Currently managed ad hoc.', '["Continue ad hoc management", "Monthly group visits", "Individual monthly check-ins with structured protocol", "Partner with diabetes educator for external program"]', 'Individual monthly check-ins with structured protocol', 'Group visits have stigma concerns. Individual check-ins are more personal and allow tailored care plans. Glucose monitor distribution through Jennifer creates a value-add.', NULL, NULL, 'decided', 4, NULL, datetime('now', '-14 days'), datetime('now', '-14 days'), datetime('now', '-14 days'), 7, 4, NULL),

  ('Change lab vendor from Quest to LabCorp for lipid panels', 'Quest turnaround for lipid panels is 5-7 days. LabCorp offers 2-3 day turnaround at similar pricing.', '["Stay with Quest", "Switch fully to LabCorp", "Use LabCorp for lipids only, Quest for everything else", "Negotiate faster turnaround with Quest"]', 'Use LabCorp for lipids only, Quest for everything else', 'Splitting avoids migration risk. Quest is reliable for everything else. LabCorp lipid turnaround benefits patients waiting for results to discuss medication changes.', 'Working well. Lipid results back in 2 days consistently. No issues with dual-vendor setup. Quest account unchanged.', datetime('now', '-5 days'), 'validated', NULL, NULL, datetime('now', '-28 days'), datetime('now', '-28 days'), datetime('now', '-5 days'), 6, 3, 4),

  ('Address Stephanie Lee missed appointments', 'Stephanie has missed 3 blood pressure follow-ups. Last BP was 148/92. She is a busy attorney who screens calls.', '["Send certified letter about clinical risk", "Call her office directly", "Email with strong clinical language", "Flag chart for next visit whenever she comes in"]', 'Call her office directly and send email with clinical urgency', 'Multi-channel approach. Office number bypasses call screening. Email creates a written record of the clinical recommendation. Less aggressive than a certified letter.', NULL, NULL, 'decided', NULL, 16, datetime('now', '-14 days'), datetime('now', '-14 days'), datetime('now', '-14 days'), 6, 3, NULL),

  ('Deprescribe omeprazole for Dorothy Hawkins', 'Dorothy is on 9 medications including omeprazole 20mg daily. No current GI symptoms, no documented indication for continued use. Polypharmacy risk in 80-year-old.', '["Continue omeprazole (avoid disruption)", "Taper to 10mg for 2 weeks then stop", "Stop immediately", "Switch to H2 blocker as step-down"]', 'Taper to 10mg for 2 weeks then stop', 'Gradual taper reduces rebound acid risk. At 80, every unnecessary medication is a fall risk and interaction risk. Daughter supportive of simplifying regimen.', NULL, NULL, 'decided', NULL, 14, datetime('now', '-2 days'), datetime('now', '-2 days'), datetime('now', '-2 days'), 8, 4, NULL);

-- ============================================================================
-- JOURNAL ENTRIES
-- ============================================================================
INSERT INTO journal_entries (content, mood, energy, highlights, entry_date, linked_contacts, linked_projects, created_at, updated_at) VALUES
  ('Really good day at the practice. Margaret Chen''s A1c is holding steady and she is so engaged — asking about her diet, tracking her numbers. That is the kind of patient relationship that makes this work meaningful. Also, Mark cracked the Meridian billing mystery. 73% of denials from one missing modifier. Sometimes it really is that simple.', 'great', 5, '["Margaret Chen A1c stable", "Billing root cause identified"]', date('now', '-2 days'), '[1, 23]', '[2]', datetime('now', '-2 days'), datetime('now', '-2 days')),

  ('Worried about Stephanie Lee. Third missed follow-up and her BP is not controlled. Sent a direct email. As a doctor you cannot force patients to come in but at 148/92 I need to document that I tried. Called her office too. Hopefully that gets through.', 'concerned', 3, '["Stephanie Lee missed visit concern"]', date('now', '-14 days'), '[16]', NULL, datetime('now', '-14 days'), datetime('now', '-14 days')),

  ('Staff huddle went well today. The team is really coming together. Lisa runs those meetings almost as well as I do — honestly probably better. Emily''s portal enrollment numbers are strong and she shows real initiative with the printed guides. Feeling grateful for this team.', 'grateful', 4, '["Strong team performance", "Emily showing initiative"]', date('now', '-1 days'), '[21, 22]', '[3]', datetime('now', '-1 days'), datetime('now', '-1 days')),

  ('Dorothy Hawkins'' daughter called about a near-fall. No injury but it reinforced why I want to simplify her medication list. Nine meds at 80 years old is too many. Going to deprescribe the omeprazole — there is no current indication. Small step but important.', 'reflective', 3, '["Dorothy fall risk — medication review needed"]', date('now', '-16 days'), '[14]', NULL, datetime('now', '-16 days'), datetime('now', '-16 days')),

  ('Frank DeLuca emailed that he is down 10 lbs total. His brother''s diabetes diagnosis scared him straight and he is channeling that fear into real action. His wife is changing how she cooks. This is the ripple effect of good patient education — it extends to families.', 'inspired', 5, '["Frank DeLuca 10 lb weight loss", "Family ripple effect"]', date('now', '-4 days'), '[13]', '[4]', datetime('now', '-4 days'), datetime('now', '-4 days')),

  ('Long day. Back to back patients from 7:30 to 5. The same-day slots are being used every day — clearly there was pent-up demand. Good validation of that decision. But I need to figure out how to protect some documentation time. Falling behind on notes.', 'drained', 2, '["Same-day slots fully utilized", "Documentation time needed"]', date('now', '-8 days'), NULL, NULL, datetime('now', '-8 days'), datetime('now', '-8 days')),

  ('Ahmed Hassan thanked me for the early morning appointments. Such a small accommodation but it made the difference between him keeping visits and dropping off. His A1c is down to 7.1. Lesson: access barriers are often simple logistics problems, not clinical ones.', 'satisfied', 4, '["Scheduling flexibility improved adherence", "Ahmed A1c improvement"]', date('now', '-3 days'), '[17]', NULL, datetime('now', '-3 days'), datetime('now', '-3 days')),

  ('Thomas Nguyen''s migraines are getting worse — 10 per month now. Started him on topiramate for prevention. I always feel a bit uncertain starting preventive meds — the evidence is good but predicting which patient responds is still mostly trial and error. Gave him a migraine diary to track.', 'thoughtful', 3, '["Started migraine prevention for Thomas Nguyen"]', date('now', '-1 days'), '[7]', NULL, datetime('now', '-1 days'), datetime('now', '-1 days')),

  ('Thinking about the diabetic care program design. We have 5 diabetics and 3 pre-diabetics who would benefit. Jennifer Walsh quoted glucose monitors at $18/unit bulk. The math works — better monitoring should reduce ER visits and complications. Need to design the monthly protocol.', 'focused', 4, '["Diabetic care program planning", "Glucose monitor pricing confirmed"]', date('now', '-7 days'), '[27]', '[4]', datetime('now', '-7 days'), datetime('now', '-7 days')),

  ('Helen Brooks'' cognitive assessment was stable today — MMSE 26/30, same as 3 months ago. That is actually good news at 73 with mild concerns. Her daughter Karen is incredible — so involved and supportive. Discussed advance directives. Hard conversation but necessary.', 'reflective', 3, '["Helen Brooks cognitive stable", "Advance directive discussion"]', date('now', '-4 days'), '[10]', NULL, datetime('now', '-4 days'), datetime('now', '-4 days')),

  ('Portal rollout is gaining traction. Emily enrolled 8 patients this week. The 60% target in 90 days feels achievable. Alex at PracticePulse fixed the appointment routing — that was a blocker. Now patients can request appointments and it goes straight to Lisa. Technology actually working as promised for once.', 'optimistic', 4, '["Portal enrollment on track", "Routing fix resolved"]', date('now', '-6 days'), '[22, 28]', '[3]', datetime('now', '-6 days'), datetime('now', '-6 days')),

  ('End of a tough week. Realized I have not taken a real lunch break in 8 days. The second MA hire is helping with patient flow but I am still the bottleneck on documentation and decision-making. Need to think about how to delegate more of the non-clinical admin to Lisa.', 'tired', 2, '["Work-life balance concern", "Need to delegate more"]', date('now', '-10 days'), '[21]', NULL, datetime('now', '-10 days'), datetime('now', '-10 days'));

-- ============================================================================
-- STANDALONE NOTES
-- ============================================================================
INSERT INTO standalone_notes (title, content, linked_contacts, linked_projects, tags, pinned, created_at, updated_at) VALUES
  ('Diabetic care program — patient list', 'Eligible patients for structured program:\n- Margaret Chen (Type 2, A1c 7.0)\n- Ahmed Hassan (Type 2, A1c 7.1)\n- Frank DeLuca (pre-diabetic, A1c 6.2)\n- Robert Kim (monitor glucose with COPD meds)\n- Helen Brooks (check for metabolic factors with cognitive protocol)\n\nMaybe: David Okafor (elevated cholesterol, metabolic risk)', '[1, 17, 13, 19, 10, 3]', '[4]', '["#diabetes", "#care-program"]', 1, datetime('now', '-10 days'), datetime('now', '-3 days')),

  ('Meridian billing checklist', 'Pre-submission checklist for Meridian Health claims:\n1. Verify modifier 25 on all same-day E/M + procedure claims\n2. Check prior auth status before submission\n3. Confirm patient eligibility is current\n4. Attach clinical notes for claims over $500\n5. Double-check diagnosis code specificity (ICD-10 to highest level)\n\nTarget: denial rate under 5% by end of quarter', NULL, '[2]', '["#billing", "#meridian", "#checklist"]', 1, datetime('now', '-15 days'), datetime('now', '-5 days')),

  ('Patient portal talking points', 'When enrolling patients:\n- Emphasize convenience: see lab results, message us, request appointments\n- For older patients: "Your daughter/son can help you set it up"\n- For younger patients: "Like checking your bank account but for health"\n- Show them the app on their phone right there\n- Hand them the printed guide to take home', NULL, '[3]', '["#portal", "#enrollment"]', 0, datetime('now', '-12 days'), datetime('now', '-12 days')),

  ('Same-day appointment data', 'After 5 weeks of 3 same-day slots daily:\n- Average utilization: 85% (2.55 of 3 slots used)\n- Most common: UTI (6), back pain (5), medication reactions (4), rashes (3)\n- Patient satisfaction anecdotally much better\n- Only 2 urgent care diversions vs 8 in previous 5 weeks\n\nConsider adding a 4th slot on Mondays (highest demand day)', NULL, NULL, '["#scheduling", "#access"]', 0, datetime('now', '-7 days'), datetime('now', '-7 days')),

  ('County Medical Society dinner notes', 'Talked to Dr. Zhao about referral patterns. He mentioned that several practices are starting chronic care management programs — might be a trend. Also met Dr. Ananya Rao, a geriatrician who might be a good referral partner for Dorothy and Helen.\n\nFollow up: get Dr. Rao contact info from Dr. Zhao', '[24]', NULL, '["#networking", "#referrals"]', 0, datetime('now', '-25 days'), datetime('now', '-25 days')),

  ('Documentation time problem', 'I am falling behind on chart notes. Currently:\n- Spend 45 min after last patient catching up on notes\n- Some notes from 2 days ago still not done\n- Risk: less accurate notes when written from memory\n\nPossible solutions:\n1. Block 30 min mid-day for notes\n2. Use voice dictation during visits\n3. Have Emily do more pre-visit documentation\n4. Template common visit types to speed up', NULL, NULL, '["#workflow", "#documentation"]', 0, datetime('now', '-8 days'), datetime('now', '-8 days')),

  ('Advance directive conversation guide', 'For elderly patients and families:\n1. Frame as empowerment, not end-of-life\n2. Ask: "If you could not speak for yourself, who would you trust to make decisions?"\n3. Discuss: resuscitation, ventilation, feeding tubes, comfort care\n4. Provide the state form — do not just talk about it\n5. Encourage family meeting to discuss, not just one person deciding\n\nUsed this approach with Helen Brooks and her daughter — went really well', '[10]', NULL, '["#clinical", "#advance-directives"]', 1, datetime('now', '-4 days'), datetime('now', '-4 days')),

  ('Ideas for practice growth', 'Things to explore in Q2:\n- Chronic care management (CCM) billing codes — Medicare pays for this\n- Telehealth follow-ups for stable patients (save them a trip)\n- Weight management program (Frank''s success could be a model)\n- Community health workshop at the library (Helen''s old workplace)', '[13, 10]', NULL, '["#strategy", "#growth"]', 0, datetime('now', '-5 days'), datetime('now', '-5 days'));

-- ============================================================================
-- ENTITY-ATTACHED NOTES
-- ============================================================================
INSERT INTO notes (entity_type, entity_id, content, created_at) VALUES
  ('contact', 1, 'Margaret is the ideal patient for our diabetic care program pilot. She tracks everything, asks questions, and follows through. Consider asking her to be a program ambassador.', datetime('now', '-5 days')),
  ('contact', 14, 'Dorothy''s daughter Karen is the real care partner here. Always include her in communications. She manages the pill organizer and drives Dorothy to appointments.', datetime('now', '-2 days')),
  ('contact', 16, 'Three missed follow-ups. Consider sending a certified letter if the next attempt fails. Document all outreach attempts carefully.', datetime('now', '-14 days')),
  ('contact', 17, 'Ahmed works 10am-10pm at the restaurant. Only available early morning. 7:30 AM slots are working. Do not schedule mid-day.', datetime('now', '-22 days')),
  ('contact', 13, 'Frank''s brother''s Type 2 diagnosis is a strong motivator. Reference it gently in conversations to reinforce his commitment to lifestyle changes.', datetime('now', '-20 days')),
  ('contact', 21, 'Lisa is ready for more responsibility. Consider a practice manager title and corresponding raise at the 6-month review.', datetime('now', '-10 days')),
  ('contact', 7, 'Thomas works at a computer 10+ hours daily. Ergonomic assessment could be key to migraine reduction. Consider occupational therapy referral.', datetime('now', '-1 days')),
  ('contact', 28, 'Alex mentioned PracticePulse is releasing a chronic care management module in Q2. Get on the beta list for the diabetic care program.', datetime('now', '-13 days')),
  ('project', 2, 'Root cause was simpler than expected — just a missing modifier code. Good reminder to investigate billing denials systematically rather than accepting them.', datetime('now', '-20 days')),
  ('project', 4, 'Jennifer Walsh can supply glucose monitors at $18/unit (bulk). Budget ~$900 for 50 units to cover initial program enrollment.', datetime('now', '-8 days'));

-- ============================================================================
-- ACTIVITY LOG (representative entries)
-- ============================================================================
INSERT INTO activity_log (entity_type, entity_id, action, details, created_at) VALUES
  ('user_profile', 0, 'profile_created', 'Initial profile setup completed', datetime('now', '-45 days')),
  ('contact', 1, 'created', 'Added contact: Margaret Chen', datetime('now', '-90 days')),
  ('contact', 2, 'created', 'Added contact: James Rivera', datetime('now', '-85 days')),
  ('contact', 3, 'created', 'Added contact: David Okafor', datetime('now', '-80 days')),
  ('contact', 4, 'created', 'Added contact: Linda Patel', datetime('now', '-78 days')),
  ('contact', 5, 'created', 'Added contact: Michael Torres', datetime('now', '-75 days')),
  ('contact', 6, 'created', 'Added contact: Barbara Anderson', datetime('now', '-72 days')),
  ('contact', 7, 'created', 'Added contact: Thomas Nguyen', datetime('now', '-70 days')),
  ('contact', 8, 'created', 'Added contact: Patricia Murphy', datetime('now', '-68 days')),
  ('contact', 9, 'created', 'Added contact: Carlos Gutierrez', datetime('now', '-65 days')),
  ('contact', 10, 'created', 'Added contact: Helen Brooks', datetime('now', '-62 days')),
  ('contact', 11, 'created', 'Added contact: Jason Williams', datetime('now', '-60 days')),
  ('contact', 12, 'created', 'Added contact: Maria Santos', datetime('now', '-55 days')),
  ('contact', 13, 'created', 'Added contact: Frank DeLuca', datetime('now', '-50 days')),
  ('contact', 14, 'created', 'Added contact: Dorothy Hawkins', datetime('now', '-48 days')),
  ('contact', 15, 'created', 'Added contact: Ryan O''Brien', datetime('now', '-45 days')),
  ('contact', 16, 'created', 'Added contact: Stephanie Lee', datetime('now', '-42 days')),
  ('contact', 17, 'created', 'Added contact: Ahmed Hassan', datetime('now', '-40 days')),
  ('contact', 18, 'created', 'Added contact: Nancy Palmer', datetime('now', '-38 days')),
  ('contact', 19, 'created', 'Added contact: Robert Kim', datetime('now', '-35 days')),
  ('contact', 20, 'created', 'Added contact: Susan Washington', datetime('now', '-30 days')),
  ('contact', 21, 'created', 'Added contact: Lisa Brennan', datetime('now', '-90 days')),
  ('contact', 22, 'created', 'Added contact: Emily Sato', datetime('now', '-90 days')),
  ('contact', 23, 'created', 'Added contact: Mark Davidson', datetime('now', '-90 days')),
  ('contact', 24, 'created', 'Added contact: Dr. Kevin Zhao', datetime('now', '-88 days')),
  ('contact', 25, 'created', 'Added contact: Dr. Rachel Torres', datetime('now', '-85 days')),
  ('contact', 26, 'created', 'Added contact: Tom Bradley', datetime('now', '-60 days')),
  ('contact', 27, 'created', 'Added contact: Jennifer Walsh', datetime('now', '-50 days')),
  ('contact', 28, 'created', 'Added contact: Alex Cooper', datetime('now', '-45 days')),
  ('project', 1, 'created', 'Created project: Annual Wellness Outreach', datetime('now', '-30 days')),
  ('project', 2, 'created', 'Created project: Billing Workflow Optimization', datetime('now', '-45 days')),
  ('project', 3, 'created', 'Created project: Patient Portal Rollout', datetime('now', '-21 days')),
  ('project', 4, 'created', 'Created project: Diabetic Care Program', datetime('now', '-14 days')),
  ('project', 5, 'created', 'Created project: Second MA Hiring', datetime('now', '-60 days')),
  ('project', 5, 'updated', 'Project completed: Second MA Hiring', datetime('now', '-18 days')),
  ('interaction', 1, 'created', 'Logged meeting with Margaret Chen: Quarterly diabetes review', datetime('now', '-2 days')),
  ('interaction', 2, 'created', 'Logged call with Margaret Chen: Question about metformin timing', datetime('now', '-18 days')),
  ('interaction', 4, 'created', 'Logged meeting with James Rivera: Back pain follow-up', datetime('now', '-5 days')),
  ('interaction', 7, 'created', 'Logged meeting with Linda Patel: Anxiety follow-up', datetime('now', '-3 days')),
  ('interaction', 12, 'created', 'Logged meeting with Thomas Nguyen: Migraine management', datetime('now', '-1 days')),
  ('interaction', 14, 'created', 'Logged meeting with Helen Brooks: Cognitive follow-up with family', datetime('now', '-4 days')),
  ('interaction', 17, 'created', 'Logged meeting with Frank DeLuca: Pre-diabetes check-in', datetime('now', '-3 days')),
  ('interaction', 19, 'created', 'Logged meeting with Dorothy Hawkins: Medication reconciliation', datetime('now', '-2 days')),
  ('interaction', 23, 'created', 'Logged meeting with Ahmed Hassan: Diabetes quarterly', datetime('now', '-1 days')),
  ('transcript', 1, 'created', 'Imported transcript: Weekly Staff Huddle — Feb 17', datetime('now', '-1 days')),
  ('transcript', 2, 'created', 'Imported transcript: Meridian Insurance — Claims Discussion', datetime('now', '-20 days')),
  ('transcript', 3, 'created', 'Imported transcript: PracticePulse Portal Setup', datetime('now', '-13 days')),
  ('decision', 1, 'created', 'Logged decision: Switch to digital intake forms', datetime('now', '-35 days')),
  ('decision', 2, 'created', 'Logged decision: Hire part-time vs full-time second MA', datetime('now', '-55 days')),
  ('decision', 3, 'created', 'Logged decision: Implement same-day appointment slots', datetime('now', '-40 days')),
  ('decision', 4, 'created', 'Logged decision: Start a structured diabetic care program', datetime('now', '-14 days')),
  ('decision', 5, 'created', 'Logged decision: Change lab vendor for lipid panels', datetime('now', '-28 days')),
  ('decision', 6, 'created', 'Logged decision: Address Stephanie Lee missed appointments', datetime('now', '-14 days')),
  ('decision', 7, 'created', 'Logged decision: Deprescribe omeprazole for Dorothy Hawkins', datetime('now', '-2 days')),
  ('journal', 1, 'created', 'Journal entry: Great day — Margaret A1c stable, billing root cause found', datetime('now', '-2 days')),
  ('journal', 2, 'created', 'Journal entry: Worried about Stephanie Lee', datetime('now', '-14 days')),
  ('journal', 3, 'created', 'Journal entry: Strong team performance at huddle', datetime('now', '-1 days')),
  ('journal', 4, 'created', 'Journal entry: Dorothy fall risk, medication simplification', datetime('now', '-16 days')),
  ('journal', 5, 'created', 'Journal entry: Frank DeLuca down 10 lbs', datetime('now', '-4 days')),
  ('journal', 6, 'created', 'Journal entry: Long day, documentation falling behind', datetime('now', '-8 days')),
  ('journal', 7, 'created', 'Journal entry: Ahmed scheduling accommodation success', datetime('now', '-3 days')),
  ('journal', 8, 'created', 'Journal entry: Thomas Nguyen migraine prevention started', datetime('now', '-1 days')),
  ('journal', 9, 'created', 'Journal entry: Diabetic care program planning', datetime('now', '-7 days')),
  ('journal', 10, 'created', 'Journal entry: Helen Brooks cognitive stable', datetime('now', '-4 days')),
  ('journal', 11, 'created', 'Journal entry: Portal rollout on track', datetime('now', '-6 days')),
  ('journal', 12, 'created', 'Journal entry: Need to delegate more', datetime('now', '-10 days'));
