# Client Directories

Each onboarded client gets a directory here with:

```
<client-slug>/
├── intake.md                         # Original intake form
├── onboarding-complete-<date>.md     # Completion report
├── 30-day-tasks.md                   # Customized task checklist
├── audits/
│   ├── baseline-<date>/              # Pre-deployment audit
│   ├── post-deploy-<date>/           # Post-deployment audit
│   └── weekly-<date>/                # Ongoing weekly audits
└─��� notes/                            # Ongoing client notes
```

All contents are gitignored (client-specific data).
Site configs live in `sites/` (also gitignored).
