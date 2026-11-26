"""plan_gates - phase-level skip/reason/surfacing helpers: when a phase is
already done (records on disk), what makes it failed, and the operator-facing
risk/gap surfaces printed on every launch shape (fresh, skipped, resume).

(Extracted from pipeline.py, 2026-11-26: refusals and skip logic land here;
ordering incidents land in run_phases.py.)"""
import settings
import ddd
import task_queue
import workspace



def _migration_files(slug):
    """True when the database architect delivered what its OWN records promise.

    (2026-11-26 generic-law fix) this gate used to scan for one ecosystem's FILE
    NAMING ("V*__*.sql" - Flyway's convention) inside the engine, silently fataling
    any other stack's lawful scripts (alembic versions, TypeORM migrations). The
    stack-neutral law was always the intent: the DB task records carry the paths
    their skill declared, so the gate checks those declared files exist. Location,
    naming and layout belong to the active stack skill; the engine judges only the
    promise-vs-delivery join (2026-11-17's lesson, without the Maven dialect).
    """
    root = workspace.project_root_for(slug)
    if not root.is_dir():
        return False
    index = task_queue.load_index(include_error=True)
    declared = [index.get(tid) for tid in task_queue.database_task_ids(slug)]
    return any(rec and rec.get("path") and (root / str(rec["path"])).is_file()
               for rec in declared)




def _database_reason(slug):
    """None when the database phase produced both of its artifacts."""
    if not task_queue.database_task_ids(slug):
        return "database architect queued no stage 0 database tasks"
    if not _migration_files(slug):
        return "database architect wrote no migration scripts"
    return None




def _security_reason(slug):
    """None when the security phase produced a lawful spec.

    The spec is mandatory for every domain: the strategy already carries the persistence
    and observability floors, and a plan with no permission table leaves every later unit
    to guess who may call what. Nothing is queued here on purpose - the security step
    decides WHAT must hold, the architect decides HOW and schedules it (rule (y)), so this
    phase has no task-shaped success criterion to be graded against.
    """
    return ddd.validate_security_spec(slug)




def _surface_security_risks(slug):
    """Print the domain's risk register - every entry, every launch, including the resume path    where the spec was already valid and the phase printed nothing at all.

    A risk is the spec's own record of a conflict it refused to soften (posture rule: never weaken a
    control to fit an implementation, record it). Until now the array was written, machine-checked for
    shape, and then read by nobody: the gate requires a control's entry id or an accepted posture, and
    this prints which of the two the run is living with, so an accepted exposure is a line an operator
    saw, not a field that aged out of a JSON file."""
    accepted = 0
    for entry in ddd.security_risks(slug):
        rid = str(entry.get("id", "R-??"))
        mitigation = str(entry.get("mitigation", "")).strip()
        is_accepted = ddd._risk_is_accepted(mitigation)
        accepted += 1 if is_accepted else 0
        print(f"[risk  ] {slug} {rid}: {str(entry.get('risk', ''))[:150]} -> "
              f"{'ACCEPTED, not mitigated:' if is_accepted else 'control'} {mitigation[:110]}"
              f" | residual: {str(entry.get('residual', ''))[:110]}")
    if accepted:
        print(f"[risk  ] {slug}: {accepted} of {len(ddd.security_risks(slug))} recorded risks are "
              "accepted postures - the run is defended against the rest by choice, not by accident")




def _surface_spec_risks(slug, label, risks):
    """The same disclosure channel the security register has (A2/SA6): a risk that is only
    WRITTEN is a risk nobody read. Performance and AI specs carry the register law, so the
    pipeline prints their entries on every launch too - fresh phase, skipped phase, resume."""
    accepted = 0
    for entry in risks:
        rid = str(entry.get("id", "R-??"))
        mitigation = str(entry.get("mitigation", "")).strip()
        is_accepted = ddd._risk_is_accepted(mitigation)
        accepted += 1 if is_accepted else 0
        print(f"[risk  ] {slug}/{label} {rid}: {str(entry.get('risk', ''))[:150]} -> "
              f"{'ACCEPTED, not mitigated:' if is_accepted else 'control'} {mitigation[:110]}"
              f" | residual: {str(entry.get('residual', ''))[:110]}")
    if accepted:
        print(f"[risk  ] {slug}/{label}: {accepted} of {len(risks)} recorded risks are accepted "
              "postures - sized/planned against the rest by choice, not by accident")




def _application_tasks_queued():
    """True when any stage 1..3 task is already in queue or complete (restart guard)."""
    return any((match := settings.ID_PATTERN.match(task_id)) and int(match.group(1)) >= 1
               for task_id in task_queue.load_index())




def _strategy_phase_gaps(slugs):
    """Domains whose strategy file is on disk but whose stage-0 scaffold task never
    landed - the resumable partial state (2026-11-16 09:50: the claim gate refused
    T0 before decomposition could exist, the strategy file survived; skipping phase
    1 on `database_slugs()` alone made every relaunch die [fatal] again at zero
    sessions, unable to heal the state it was handed)."""
    return [slug for slug in slugs if task_queue.scaffold_task_id(slug) == "T0-000"]
