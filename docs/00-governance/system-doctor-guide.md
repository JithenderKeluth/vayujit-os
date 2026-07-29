# System doctor guide

`npm.cmd run system:doctor` checks runtime tools, PostgreSQL, migration state,
Angular build, Electron availability, backups, and safe AI provider status. AI
output includes configured/enabled state, credential source label, model, and
validation status only. It never prints a credential. Live provider validation
is separate because it may contact an external service.
