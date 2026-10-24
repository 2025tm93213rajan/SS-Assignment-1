# Project Rules, Constraints & Operational Guidelines
## Scalable Services (SEZG583) - Assignment 1

---

## 1. Core Operating Constraints

These rules are strictly binding for all planning, implementation, testing, and documentation activities:

1. **No Git Commits by Agent**:
   - The AI assistant will **NEVER** execute `git commit` or push to remote repositories. All git commits and repository management will be handled exclusively by the user.

2. **Rigorous Verification & Testing**:
   - Always run tests and execute verification scripts to cross-check what was implemented before claiming completion.
   - Every implementation must be backed by reproducible test runs and recorded outputs.

3. **Strict Adherence to Plan and User Instructions**:
   - Always follow the agreed architecture, milestone roadmap, and specific user instructions.
   - Never deviate from the core academic objectives and scope outlined in the assignment specification.

4. **Laser Focus on Assignment Requirements**:
   - Stay aligned with the assignment rubric: the 5 mandatory conditions, 5 isolated services, database-per-service pattern, concurrency control, idempotency, and event-driven/saga reliability.

5. **Centralized Documentation in `docs/`**:
   - All findings, architectural updates, instructional logs, rules, and technical research must always be documented in the [docs/](file:///c:/BITS/Sem%203/SS/Assignments/SS-Assignment-1/docs) folder.

6. **Deliverables in `submission/` Folder Only**:
   - All final deliverable documents, templates, presentation outlines, report drafts, and evaluation matrices must be written inside the `submission/` directory.

7. **Markdown Format Exclusively (No Binary Docs/PDFs)**:
   - Never generate `.pdf`, `.docx`, or other binary documents directly.
   - Always produce clean, structured, standard GitHub Flavored Markdown (`.md`) files that can be easily reviewed, edited, and converted to PDF/Docx by the user.

8. **Rich Visual Diagrams**:
   - Use proper Mermaid diagrams, state charts, sequence flows, and component layouts to explain architecture, data flows, failure compensations, and state transitions in submission documents.

9. **Continuous Session Documentation**:
   - At the end of each chat run, command execution, or set of changes, always update the documentation in the [docs/](file:///c:/BITS/Sem%203/SS/Assignments/SS-Assignment-1/docs) folder (e.g. changelog, execution logs, finding notes).

---

## 2. Directory Governance

| Directory | Purpose | Rules |
| :--- | :--- | :--- |
| `docs/rules/` | Operational rules & constraints | Strict compliance enforced across turns. |
| `docs/plans/` | Master plan, architecture, and requirement analysis | High-level roadmap and system design. |
| `docs/findings/` | Research findings and trade-off analysis | Exploratory and domain research. |
| `docs/instructions/` | Assignment prompt guidelines & rubrics | Academic expectations and checklists. |
| `docs/changes/` | Continuous changelog and decision records | Updated at the conclusion of every step. |
| `submission/` | Final deliverables (Design Report draft in Markdown, video script, checklists) | Final review artifacts only. Markdown format exclusively. |
| `services/` | Microservice source code, unit tests, Dockerfiles, and `.env.example` files | Independent folders per service with isolated databases. |
| `scripts/` | Automated test runners (E2E, Concurrency, Idempotency, Broker catchup) | Must be standalone and repeatable. |
| `evidence/` | Raw execution logs, terminal outputs, DB snapshots, timestamped proof | Direct proof corresponding to claims made in the report. |
