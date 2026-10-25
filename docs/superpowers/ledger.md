# SDD ledger — plan: docs/superpowers/plans/2026-10-25-swimtop-results.md
Setup: not a git repo -> no worktree, no commits (Ruling: skipped commit steps — dir is not a repo, plan header says so — cost if wrong: none).
Pre-flight: Task2 consumes T1 helpers (parse_event/normalize_time/format_date/athlete_key) - signatures match; Task3 consumes T2 athlete dict - matches; Task4 consumes T1-3 - matches.
Task 1: complete (tests: pytest → 11 passed). Ruling: pytest installed via pip --target into scratchpad (no venv module available), run with PYTHONPATH — cost if wrong: none
Task 2: complete (pytest → 19 passed)
Task 3: complete (pytest → 33 passed)
Task 4: complete (pytest → 45 passed). Ruling: test_main expects performances-1 for Amelia — fixture has 2 identical TIM entries (same meet/date/time), spec dedup collapses them — cost if wrong: none
Task 5: complete (live run on copy: second run added 0; 404 → exit 1, file unchanged; Lap entries kept 9/9). Real results.json written on user request (backup results.backup-2026-10-25.json).
Final: reviewer (fable) findings: 4 Important, 8 Minor.
Final: fixed unexpected exception in main losing run results — test_main_unexpected_error_for_one_athlete_does_not_lose_others RED→GREEN, suite 51/51
Final: fixed non-ASCII slug UnicodeEncodeError — test_fetch_quotes_non_ascii_slug RED→GREEN
Final: fixed .bak overwritten on every save — test_save_db_keeps_first_backup_on_repeated_saves RED→GREEN
Final: fixed malformed old entries / null date,time crash — test_old_entry_without_starty_and_malformed_starts_do_not_crash, test_performance_missing_date_or_time_is_skipped_with_warning RED→GREEN
Final: fixed file mode lost on save — test_save_db_preserves_file_mode RED→GREEN
Final: Ruling: .bak is created once and never overwritten (not rotated) — protects the original from a bad first run; stale after first run — cost if wrong: user must delete .bak to refresh it
Final: minor (deferred): key collision for multi-word first/last names (athlete_key); year type-robustness (str vs int) in namesake check; new athlete with null year merges into existing with year; empty-slug inputs silently skipped; normalize_time odd formats; rok_urodzenia range not validated; BOM in results.json not accepted; test_main count relies on one fixture duplicate.
